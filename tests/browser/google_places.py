"""Browser regressions using intercepted API/provider fixtures (no live Google billing).
Run: .venv/bin/python tests/browser/google_places.py
"""
from pathlib import Path
import sys
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from server import app

# Exercise our map adapter without depending on a configured browser key.
# The real provider library/map still needs a manual live check after key setup.
MAP_STUB = '''
window.mapObjects = [];
class Overlay {
  constructor(options) { Object.assign(this, options); this.listeners = {}; mapObjects.push(this); }
  addListener(name, fn) { this.listeners[name] = fn; }
  setMap(map) { this.map = map; }
}
class MapStub extends Overlay {
  constructor(div, options) { super(options); this.div = div; }
  getDiv() { return this.div; }
  getCenter() { return {lat: () => this.center.lat, lng: () => this.center.lng}; }
  setCenter(center) { this.center = center; }
  setZoom(zoom) { this.zoom = zoom; }
  getZoom() { return this.zoom; }
  fitBounds(bounds) { this.bounds = bounds; }
}
window.google = {maps: {Map: MapStub, Polyline: Overlay,
  marker: {AdvancedMarkerElement: Overlay},
  LatLngBounds: class { constructor() { this.points = []; } extend(p) { this.points.push(p); } },
  event: {addListenerOnce: () => {}}}};
window.initializeDrySocksMap();
'''


def run():
    document = app.test_client().get('/')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for scenario, width in [('missing', 1280), ('script_error', 390), ('ready', 1280)]:
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors, queries, details, routed = [], [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def respond(route):
                url = urlparse(route.request.url)
                q = parse_qs(url.query)
                if url.hostname == 'maps.googleapis.com':
                    if scenario == 'ready':
                        route.fulfill(content_type='text/javascript', body=MAP_STUB)
                    else:
                        route.abort()
                elif url.hostname != 'localhost':
                    route.abort()
                elif url.path == '/':
                    route.fulfill(status=200, content_type='text/html', body=document.data)
                elif url.path == '/api/config':
                    route.fulfill(json={'locations': {}, 'route': {}, 'google_maps_browser_key': None if scenario == 'missing' else 'public-fixture'})
                elif url.path == '/api/search':
                    queries.append(q)
                    if q['q'][0] == 'quota':
                        route.fulfill(status=503, json={'error': 'Google Places quota reached. Try again later.'})
                    else:
                        route.fulfill(json={'features': [
                            {'place_id': 'hoodi-id', 'text': 'Hoodi Metro', 'place_name': 'Hoodi, Bengaluru'},
                            {'place_id': 'delhi-id', 'text': 'Connaught Place', 'place_name': 'New Delhi'}]})
                elif url.path == '/api/place':
                    details.append(q)
                    route.fulfill(json={'feature': {'center': [77.2167, 28.6315] if q['place_id'][0] == 'delhi-id' else [77.71, 12.99]}})
                elif url.path == '/api/routes':
                    routed.append(route.request.post_data_json)
                    route.fulfill(json={'routes': [{'summary': 'Fixture road', 'duration_mins': 20, 'distance_km': 5,
                        'geometry': {'type': 'LineString', 'coordinates': [[77.71, 12.99], [77.72, 13.0]]},
                        'waypoints': [{'lat': 12.99, 'lon': 77.71}]}]})
                elif url.path == '/api/weather':
                    route.fulfill(json={'status': 'CLEAR', 'corridor_mins_to_rain': 999, 'waypoints': [{'lat': 12.99, 'lon': 77.71, 'available': True, 'mins_to_rain': 999}]})
                elif url.path == '/api/btp':
                    route.fulfill(json={'status': 'outside_coverage', 'sources': [], 'alerts': []})
                elif url.path == '/api/reverse':
                    route.fulfill(json={'features': []})
                elif url.path.startswith('/api/'):
                    route.fulfill(json={})
                else:
                    route.fulfill(path=str(ROOT / 'web' / url.path.lstrip('/')))
            page.route('**/*', respond)
            page.goto('http://localhost:5111/', wait_until='domcontentloaded')
            page.wait_for_function("state.config !== null")
            if scenario == 'ready':
                page.wait_for_function('map !== null')
                assert page.locator('#map-fallback').is_hidden()
            else:
                page.wait_for_function("document.querySelector('#map-fallback-title').textContent === 'Map unavailable'")
                assert page.locator('[data-pick="origin"]').is_disabled()
            origin = page.locator('#origin-input')
            origin.fill('hoodi metr')
            page.wait_for_selector('#origin-option-0')
            assert not details, 'Predictions must not fetch every place detail'
            assert page.locator('.google-attribution').first.inner_text() == 'Google Maps'
            first_session = queries[-1]['session'][0]
            origin.fill('hoodi metro')
            page.wait_for_selector('#origin-option-0')
            assert queries[-1]['session'][0] == first_session
            origin.press('ArrowDown')
            origin.press('Enter')
            page.wait_for_function("state.origin?.name === 'Hoodi Metro'")
            assert details[-1]['session'][0] == first_session
            origin.fill('hoodi again')
            page.wait_for_selector('#origin-option-0')
            assert queries[-1]['session'][0] != first_session
            page.locator('#origin-option-0').click()
            page.wait_for_function("state.origin !== null")
            page.locator('#destination-input').fill('Connaught')
            page.wait_for_selector('#destination-option-1')
            page.locator('#destination-option-1').click()
            page.wait_for_function("state.routes.length === 1")
            assert routed[-1]['destination']['lat'] == 28.6315
            page.wait_for_function("state.reports?.status === 'outside_coverage'")
            assert 'Bengaluru only' in page.locator('#reports-content').inner_text()
            page.wait_for_function('state.weather !== null')
            if scenario == 'ready':
                assert page.evaluate("mapObjects.some(o => o.map === map && o.path?.length === 2)")
                assert page.evaluate("mapObjects.some(o => o.map === map && o.content?.className === 'weather-map-dot')")
                assert page.evaluate("mapObjects.filter(o => o.map === map && o.gmpDraggable).length") == 2
                # A map pick updates the point and retires existing overlays.
                page.locator('[data-pick="origin"]').click()
                page.evaluate('map.listeners.click({latLng: {lat: () => 12.98, lng: () => 77.70}})')
                page.wait_for_function('state.origin?.lat === 12.98')
            # Even a late response that ignores cancellation must not overwrite a new edit.
            page.evaluate('''() => {
              const original = window.fetch;
              window.fetch = (url, opts) => String(url).startsWith('/api/place?')
                ? new Promise(resolve => window.finishOldPlace = () => resolve(new Response(JSON.stringify({feature: {center: [77, 12]}}))))
                : original(url, opts);
            }''')
            origin.fill('old place')
            page.wait_for_selector('#origin-option-0')
            page.locator('#origin-option-0').click()
            page.wait_for_function("typeof finishOldPlace === 'function'")
            origin.fill('new query')
            page.evaluate('finishOldPlace()')
            page.wait_for_selector('#origin-option-0')
            assert origin.input_value() == 'new query'
            assert page.evaluate('state.origin') is None
            origin.fill('quota')
            page.wait_for_function("document.querySelector('#origin-results').textContent.includes('quota reached')")
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            print(f'{scenario}, {width}px: autocomplete, sessions, selection, late details, provider errors passed')
            page.close()
        browser.close()

if __name__ == '__main__':
    run()
