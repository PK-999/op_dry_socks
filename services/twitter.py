"""Optional, attributed X source feeds. Unavailable data never becomes a report.

The caller supplies their existing X cookie; this module does not read browser
profiles or discover credentials. Browser access is best effort and may expire.
"""

import datetime as dt
import hashlib
import re
import threading
import time
from urllib.parse import urlparse

import requests

from .sources import select_sources


_SOURCE_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 120
_FAILURE_TTL_SECONDS = 30
_BATCH_TIMEOUT_SECONDS = 25


def _credential(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and not value.upper().startswith('YOUR_') else None


def _utcnow():
    return dt.datetime.now(dt.timezone.utc)


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(dt.timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _canonical_url(value, handle):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    match = re.fullmatch(r'/([A-Za-z0-9_]+)/status/(\d+)(?:/.*)?', parsed.path)
    if (parsed.scheme != 'https' or parsed.netloc.lower() not in ('x.com', 'www.x.com', 'twitter.com')
            or not match or match.group(1).lower() != handle.lower()):
        return None
    return f'https://x.com/{handle}/status/{match.group(2)}'


def _valid_alert(record, source, now, max_age_hours):
    if not isinstance(record, dict) or record.get('retweeted'):
        return None
    posted = _timestamp(record.get('created_at'))
    url = _canonical_url(record.get('url'), source['handle'])
    author = record.get('author', source['handle'])
    if (not posted or not url or not isinstance(author, str) or author.lower() != source['handle'].lower()
            or not 0 <= (now - posted).total_seconds() <= max_age_hours * 3600):
        return None
    text = str(record.get('text') or '').strip()
    media_url = record.get('media_url')
    if not text and not media_url:
        return None
    return {'text': text or 'Image report — open the original post to read it.',
            'url': url, 'handle': source['handle'], 'created_at': posted.isoformat(),
            'scope': source['scope'], 'area': source['area'], 'kind': source['kind'],
            'media_url': media_url, 'coverage': source['coverage']}


def _fetch_api(handle, bearer_token, timeout=5):
    """Fetch a bounded recent-search page; author expansion validates ownership."""
    try:
        response = requests.get('https://api.x.com/2/tweets/search/recent',
                                headers={'Authorization': f'Bearer {bearer_token}'},
                                params={'query': f'from:{handle} -is:retweet -is:reply',
                                        'max_results': 20, 'tweet.fields': 'created_at,author_id,referenced_tweets',
                                        'expansions': 'author_id', 'user.fields': 'username'}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if (not isinstance(payload, dict) or payload.get('errors')
                or ('data' not in payload and payload.get('meta', {}).get('result_count') != 0)
                or not isinstance(payload.get('data', []), list)):
            return {'status': 'unavailable', 'records': [], 'message': 'X API could not return this source.'}
        authors = {str(user['id']): user.get('username', '') for user in payload.get('includes', {}).get('users', [])}
        records = []
        for item in payload.get('data', []):
            author = authors.get(str(item.get('author_id')), '')
            if author.lower() != handle.lower():
                continue
            records.append({'text': item.get('text'), 'created_at': item.get('created_at'), 'author': author,
                            'url': f'https://x.com/{author}/status/{item.get("id", "")}',
                            'retweeted': any(ref.get('type') == 'retweeted' for ref in item.get('referenced_tweets', []))})
        return {'status': 'ok', 'records': records}
    except Exception:
        # Requests and Playwright errors may contain authenticated URLs or headers.
        return {'status': 'unavailable', 'records': [],
                'message': 'X API unavailable. Check access, credits, or rate limits.'}


def _fetch_browser_batch(handles, auth_token):
    """Share one context; navigation and total work have bounded time budgets."""
    results = {}
    deadline = time.monotonic() + _BATCH_TIMEOUT_SECONDS
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=5000)
            try:
                context = browser.new_context()
                context.add_cookies([{'name': 'auth_token', 'value': auth_token, 'domain': '.x.com',
                                      'path': '/', 'secure': True, 'httpOnly': True}])
                page = context.new_page()
                for handle in handles:
                    remaining_ms = int((deadline - time.monotonic()) * 1000)
                    if remaining_ms <= 0:
                        break
                    try:
                        page.goto(f'https://x.com/{handle}', wait_until='domcontentloaded',
                                  timeout=min(5000, remaining_ms))
                        remaining_ms = int((deadline - time.monotonic()) * 1000)
                        if remaining_ms <= 0:
                            break
                        page.wait_for_selector('article[data-testid="tweet"]', timeout=min(2500, remaining_ms))
                        records = page.locator('article[data-testid="tweet"]').evaluate_all('''articles => articles.slice(0, 20).map(article => {
                            const time = article.querySelector('time');
                            const link = time?.closest('a');
                            const social = article.querySelector('[data-testid="socialContext"]');
                            return {text: article.querySelector('[data-testid="tweetText"]')?.innerText || '',
                                url: link?.href || '', created_at: time?.getAttribute('datetime'),
                                media_url: article.querySelector('[data-testid="tweetPhoto"] img')?.src || null,
                                retweeted: !!social && /repost|retweet/i.test(social.innerText)};
                        })''')
                        results[handle] = {'status': 'ok', 'records': records}
                    except Exception:
                        results[handle] = {'status': 'unavailable', 'records': [],
                                           'message': 'X timeline unavailable; the browser login may have expired.'}
            finally:
                browser.close()
    except Exception:
        pass
    return results


def _fetch_sources(handles, auth_token, bearer_token):
    mode, token = ('browser', auth_token) if auth_token else ('api', bearer_token)
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    results, pending = {}, []
    now = time.monotonic()
    with _CACHE_LOCK:
        for handle in handles:
            cached = _SOURCE_CACHE.get((mode, fingerprint, handle.lower()))
            if cached and cached['expires'] > now:
                results[handle] = {**cached['result'], 'cached': True}
            else:
                pending.append(handle)
    if pending:
        if auth_token:
            fetched = _fetch_browser_batch(pending, auth_token)
        else:
            fetched = {}
            deadline = time.monotonic() + _BATCH_TIMEOUT_SECONDS
            for handle in pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                fetched[handle] = _fetch_api(handle, bearer_token, timeout=min(5, remaining))
        for handle in pending:
            result = dict(fetched.get(handle) or {'status': 'unavailable', 'records': [],
                          'message': 'X source could not be checked. Login, network, or refresh time limit may be responsible.'})
            result['checked_at'] = _utcnow().isoformat()
            result['cached'] = False
            ttl = _CACHE_TTL_SECONDS if result['status'] == 'ok' else _FAILURE_TTL_SECONDS
            with _CACHE_LOCK:
                _SOURCE_CACHE[(mode, fingerprint, handle.lower())] = {
                    'expires': time.monotonic() + ttl, 'result': result}
                if len(_SOURCE_CACHE) > 128:
                    oldest = next(iter(_SOURCE_CACHE))
                    del _SOURCE_CACHE[oldest]
            results[handle] = result
    return results


def get_route_alerts(route_waypoints, auth_token=None, bearer_token=None, geometry=None,
                     max_age_hours=2, enabled=True):
    """Return source reports, never a conclusion that the route is clear or blocked."""
    sources = select_sources(route_waypoints, geometry)
    now = _utcnow()
    result = {'status': 'unavailable', 'alerts': [], 'sources': sources, 'updated_at': now.isoformat()}
    if not sources:
        result['status'] = 'outside_coverage'
        return result
    auth_token, bearer_token = _credential(auth_token), _credential(bearer_token)
    if not enabled or not (auth_token or bearer_token):
        status = 'disabled' if not enabled else 'not_configured'
        for source in sources:
            source.update(status=status, message='X updates disabled.' if not enabled else 'Add an existing X login to read this source.', cached=False)
        result['status'] = 'disabled' if not enabled else 'unavailable'
        return result
    try:
        max_age_hours = float(max_age_hours)
        if not 0 < max_age_hours <= 168:
            raise ValueError
    except (ValueError, TypeError):
        max_age_hours = 2
    fetched = _fetch_sources([source['handle'] for source in sources], auth_token, bearer_token)
    # A post published while fetching is valid; compare against completion time.
    now = _utcnow()
    result['updated_at'] = now.isoformat()
    seen = set()
    for source in sources:
        feed = fetched[source['handle']]
        source.update(status=feed['status'], message=feed.get('message', 'Recent posts checked; coverage may be incomplete.'),
                      cached=feed.get('cached', False), checked_at=feed.get('checked_at'))
        for record in feed.get('records', []):
            alert = _valid_alert(record, source, now, max_age_hours)
            if alert and alert['url'].lower() not in seen:
                seen.add(alert['url'].lower())
                result['alerts'].append(alert)
    result['alerts'].sort(key=lambda alert: alert['created_at'], reverse=True)
    count = sum(source['status'] == 'ok' for source in sources)
    result['status'] = 'ok' if count == len(sources) else ('partial' if count else 'unavailable')
    return result
