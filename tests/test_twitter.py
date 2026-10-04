import datetime as dt
from unittest.mock import patch

import pytest

from services import twitter


def post(handle='blrcitytraffic', identity='123', **changes):
    record = {'text': 'Waterlogging reported near a junction.', 'url': f'https://x.com/{handle}/status/{identity}',
              'created_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'author': handle}
    record.update(changes)
    return record


@pytest.fixture(autouse=True)
def clear_cache():
    if hasattr(twitter, '_SOURCE_CACHE'):
        twitter._SOURCE_CACHE.clear()


def test_no_credentials_never_invents_posts():
    result = twitter.get_route_alerts([])
    assert result['alerts'] == []
    assert result['status'] == 'unavailable'
    assert all(source['status'] == 'not_configured' for source in result['sources'])


def test_disabled_feed_never_attempts_network():
    with patch('requests.get', side_effect=AssertionError('disabled feed made a request')):
        result = twitter.get_route_alerts([], enabled=False, bearer_token='test-token')
    assert result['status'] == 'disabled'
    assert result['alerts'] == []


def test_rejects_stale_malformed_future_missing_timestamp_and_wrong_authors():
    now = dt.datetime.now(dt.timezone.utc)
    records = [post(), post(),
               post(identity='2', created_at=(now-dt.timedelta(hours=3)).isoformat()),
               post(identity='3', created_at='yesterday'),
               post(identity='4', created_at=(now+dt.timedelta(hours=1)).isoformat()),
               post(identity='5', created_at=None),
               post(identity='6', created_at=now.replace(tzinfo=None).isoformat()),
               post(handle='unrelated', identity='7'),
               post(identity='8', retweeted=True)]
    with patch.object(twitter, '_fetch_browser_batch', return_value={
        'blrcitytraffic': {'status': 'ok', 'records': records},
        'Bengalururain': {'status': 'ok', 'records': []},
    }):
        result = twitter.get_route_alerts([], auth_token='test-cookie')
    assert result['status'] == 'ok'
    assert len(result['alerts']) == 1
    assert result['alerts'][0]['url'] == 'https://x.com/blrcitytraffic/status/123'
    assert result['alerts'][0]['scope'] == 'citywide'


def test_auth_failure_is_visible_and_never_clear_conditions():
    with patch.object(twitter, '_fetch_browser_batch', return_value={}):
        result = twitter.get_route_alerts([], auth_token='expired-cookie')
    assert result['status'] == 'unavailable'
    assert result['alerts'] == []
    assert all(source['status'] == 'unavailable' for source in result['sources'])


def test_only_route_selected_handles_are_requested_and_cached():
    captured = []

    def fetch(handles, auth_token):
        captured.append(set(handles))
        return {handle: {'status': 'ok', 'records': [post(handle=handle)]} for handle in handles}

    points = [{'lat': 12.93, 'lon': 77.60}, {'lat': 12.93, 'lon': 77.71}]
    with patch.object(twitter, '_fetch_browser_batch', side_effect=fetch):
        first = twitter.get_route_alerts(points, auth_token='test-cookie')
        second = twitter.get_route_alerts(points, auth_token='test-cookie')
    assert len(captured) == 1
    assert 'bellandurutrfps' in captured[0]
    assert 'wftrps' not in captured[0]
    assert first['alerts'] == second['alerts']
    assert all(source['cached'] for source in second['sources'])


def test_api_uses_resolved_author_id_and_drops_other_authors():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'data': [{'id': '123', 'author_id': '42', 'text': 'Rain update',
                              'created_at': dt.datetime.now(dt.timezone.utc).isoformat()},
                             {'id': '124', 'author_id': '99', 'text': 'Unrelated post',
                              'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}],
                    'includes': {'users': [{'id': '42', 'username': 'Bengalururain'},
                                           {'id': '99', 'username': 'unrelated'}]}}

    with patch('requests.get', return_value=Response()):
        result = twitter.get_route_alerts([], bearer_token='test-bearer')
    assert len(result['alerts']) == 1
    assert result['alerts'][0]['handle'] == 'Bengalururain'


def test_browser_credentials_take_precedence_without_exposing_them():
    with patch.object(twitter, '_fetch_browser_batch', return_value={}), \
         patch('requests.get', side_effect=AssertionError('API used instead of supplied browser login')):
        result = twitter.get_route_alerts([], auth_token='secret-cookie', bearer_token='secret-bearer')
    assert 'secret-cookie' not in str(result)
    assert 'secret-bearer' not in str(result)


def test_cached_posts_are_filtered_against_the_current_time():
    now = dt.datetime.now(dt.timezone.utc)
    records = [post(created_at=(now-dt.timedelta(minutes=119)).isoformat())]
    with patch.object(twitter, '_fetch_browser_batch', return_value={
        'blrcitytraffic': {'status': 'ok', 'records': records},
        'Bengalururain': {'status': 'ok', 'records': []},
    }), patch.object(twitter, '_utcnow', return_value=now):
        first = twitter.get_route_alerts([], auth_token='test-cookie')
    with patch.object(twitter, '_utcnow', return_value=now+dt.timedelta(minutes=3)):
        second = twitter.get_route_alerts([], auth_token='test-cookie')
    assert len(first['alerts']) == 1
    assert second['alerts'] == []
    assert all(source['cached'] for source in second['sources'])


def test_malformed_post_url_does_not_break_other_reports():
    records = [post(identity='1', url='https://[invalid'), post(identity='2')]
    with patch.object(twitter, '_fetch_browser_batch', return_value={
        'blrcitytraffic': {'status': 'ok', 'records': records},
        'Bengalururain': {'status': 'ok', 'records': []},
    }):
        result = twitter.get_route_alerts([], auth_token='test-cookie')
    assert len(result['alerts']) == 1
    assert result['alerts'][0]['url'].endswith('/2')


def test_api_malformed_success_payload_does_not_report_source_checked():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'message': 'unrecognized upstream response'}

    with patch('requests.get', return_value=Response()):
        result = twitter.get_route_alerts([], bearer_token='test-bearer')
    assert result['status'] == 'unavailable'
    assert result['alerts'] == []
