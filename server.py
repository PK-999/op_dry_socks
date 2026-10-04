"""Dry Socks local dashboard. Run python server.py and open localhost:5111."""
import math
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from services.configuration import load_config, public_config, save_config
from services import places
from services.routing import RoutingUnavailable, get_routes as fetch_routes

DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get('DRYSOCKS_CONFIG', os.path.join(DIR, 'config.json'))
WEB_DIR = os.path.join(DIR, 'web')
app = Flask(__name__, static_folder=WEB_DIR)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
_CONFIG_LOCK = threading.Lock()


def _load_config():
    return load_config(CONFIG_FILE)


@app.before_request
def local_requests_only():
    # Prevent cross-origin writes and DNS-rebinding access to this local service.
    if request.host.split(':')[0] not in ('localhost', '127.0.0.1'):
        return jsonify(error='This app accepts local connections only.'), 403
    if request.method == 'POST':
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            return jsonify(error='Cross-origin requests are not allowed.'), 403
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(error='Cross-site requests are not allowed.'), 403


@app.after_request
def response_headers(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Web map tiles require an identifying Referer. Send only our origin to
    # cross-origin providers; API responses retain the stricter policy.
    response.headers['Referrer-Policy'] = ('strict-origin-when-cross-origin'
                                          if response.mimetype == 'text/html' else 'same-origin')
    return response


@app.errorhandler(ValueError)
def invalid_request(error):
    return jsonify(error=str(error)), 400


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Request is too large.'), 413


def payload():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError('Send a JSON object.')
    return value


def number(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f'{label} must be a number between {lower} and {upper}.')
    return value


def location(value, default='Location'):
    if not isinstance(value, dict):
        raise ValueError('Location must contain latitude and longitude.')
    name = value.get('name', default)
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError('Location name must contain 1–200 characters.')
    return {'name': name.strip(), 'lat': number(value.get('lat'), 'Latitude', -90, 90),
            'lon': number(value.get('lon'), 'Longitude', -180, 180)}


def waypoints(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError('Provide between 1 and 32 route weather points.')
    results = []
    for i, item in enumerate(value):
        point = location(item, f'Point {i + 1}')
        if 'eta_mins' in item:
            point['eta_mins'] = number(item['eta_mins'], 'Point arrival time', 0, 360)
        results.append(point)
    return results


def geometry(value):
    if not isinstance(value, dict) or value.get('type') != 'LineString':
        raise ValueError('Route geometry must be a LineString.')
    coords = value.get('coordinates')
    if not isinstance(coords, list) or not 2 <= len(coords) <= 20000:
        raise ValueError('Route geometry must contain 2–20,000 coordinates.')
    clean = []
    for pair in coords:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError('Each coordinate must be [longitude, latitude].')
        clean.append([number(pair[0], 'Longitude', -180, 180), number(pair[1], 'Latitude', -90, 90)])
    return {'type': 'LineString', 'coordinates': clean}


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(WEB_DIR, filename)


@app.get('/api/config')
def get_config():
    return jsonify(public_config(_load_config()))


@app.post('/api/config')
def update_config():
    data = payload()
    with _CONFIG_LOCK:
        # Never copy environment credentials into the configuration on disk.
        config = load_config(CONFIG_FILE, include_env=False)
        changed = False
        for name in ('origin', 'destination'):
            if name in data:
                value = location(data[name])
                changed |= value != config.get('locations', {}).get(name)
                config.setdefault('locations', {})[name] = value
        route = config.setdefault('route', {})
        if 'travel_mode' in data:
            if data['travel_mode'] not in ('DRIVE', 'TWO_WHEELER'):
                raise ValueError('Choose car or two-wheeler.')
            changed |= route.get('travel_mode') != data['travel_mode']
            route['travel_mode'] = data['travel_mode']
        if changed:
            route.pop('selected_route', None)
        if data.get('selected_route') is not None:
            selected = data['selected_route']
            if not isinstance(selected, dict):
                raise ValueError('Selected route must be an object.')
            route['selected_route'] = {'geometry': geometry(selected.get('geometry')),
                                       'summary': str(selected.get('summary', 'Saved route'))[:200]}
        save_config(config, CONFIG_FILE)
    return jsonify(status='ok', locations=config['locations'], route=config['route'])


@app.errorhandler(places.PlacesUnavailable)
def places_unavailable(error):
    return jsonify(features=[], provider='google', error=str(error)), 503


@app.get('/api/search')
def search_places():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify(features=[], provider='google')
    if len(query) > 160:
        raise ValueError('Search must be under 160 characters.')
    session = places.session_token(request.args.get('session'))
    lat, lon = 12.9716, 77.5946
    if 'lat' in request.args or 'lon' in request.args:
        try:
            point = location({'lat': float(request.args['lat']), 'lon': float(request.args['lon'])})
        except (ValueError, KeyError):
            raise ValueError('Provide valid latitude and longitude for the search area.')
        lat, lon = point['lat'], point['lon']
    return jsonify(features=places.autocomplete(_load_config(), query, session, lat, lon), provider='google')


@app.get('/api/place')
def place_details():
    session = places.session_token(request.args.get('session'))
    return jsonify(feature=places.details(_load_config(), request.args.get('place_id', ''), session), provider='google')


@app.get('/api/reverse')
def reverse_geocode():
    try:
        point = location({'lat': float(request.args.get('lat', '')), 'lon': float(request.args.get('lon', ''))})
    except (ValueError, TypeError):
        raise ValueError('Provide a valid map point.')
    return jsonify(features=places.reverse(_load_config(), point['lat'], point['lon']), provider='google')


@app.post('/api/routes')
def get_routes():
    data, config = payload(), _load_config()
    origin, destination = location(data.get('origin')), location(data.get('destination'))
    mode = data.get('travel_mode', data.get('travelMode', config.get('route', {}).get('travel_mode', 'TWO_WHEELER')))
    try:
        routes = fetch_routes(config, origin, destination, mode)
    except RoutingUnavailable as error:
        return jsonify(routes=[], error=str(error)), 503
    for route in routes:
        route['waypoints'][0]['name'], route['waypoints'][-1]['name'] = origin['name'], destination['name']
    return jsonify(routes=routes)


@app.post('/api/weather')
def get_weather():
    from services.weather import get_route_weather
    from services.evaluator import departure_advice
    data, config = payload(), _load_config()
    points = waypoints(data.get('waypoints'))
    duration = number(data.get('duration_mins', 60), 'Commute duration', 1, 360)
    thresholds = config.get('thresholds', {})
    results = get_route_weather(points, config.get('tomorrow_io_token'),
                                thresholds.get('rain_mm_15min', 0.4), thresholds.get('waterlogging_past_2h_mm', 5.0))
    advice = departure_advice(duration, thresholds.get('safety_buffer_mins', 15), results,
                              str(data.get('origin_name', points[0]['name']))[:200],
                              str(data.get('destination_name', points[-1]['name']))[:200])
    known = [p['mins_to_rain'] for p in results if p.get('mins_to_rain') is not None]
    return jsonify(status=advice['state'], status_label=advice['title'], summary=advice['body'], advice=advice,
                   corridor_mins_to_rain=min(known) if known else None,
                   any_waterlogged=any(p.get('waterlogged') for p in results), waypoints=results,
                   updated_at=min((r['fetched_at'] for r in results if r.get('fetched_at')), default=datetime.now(timezone.utc).isoformat()),
                   source='Open-Meteo + Tomorrow.io' if any(r.get('corroborating_source') for r in results) else 'Open-Meteo model forecast',
                   resolution_note='15-minute values may be interpolated from hourly forecasts depending on model coverage. Rain timing and point arrival times are estimates; rainfall accumulation is not confirmed flooding.',
                   coverage={'available': sum(bool(p.get('available')) for p in results), 'total': len(points)})


@app.post('/api/waterlogging')
def get_waterlogging():
    return jsonify(error='Standalone flood reports are unavailable. Use /api/weather for forecast accumulation risk.'), 410


@app.post('/api/btp')
def get_btp_alerts():
    from services.twitter import get_route_alerts
    data, config = payload(), _load_config()
    points = waypoints(data.get('waypoints'))
    route_geometry = geometry(data['geometry']) if data.get('geometry') else None
    return jsonify(get_route_alerts(points, auth_token=config.get('twitter_auth_token'),
                                    bearer_token=config.get('twitter_bearer_token'), geometry=route_geometry,
                                    max_age_hours=config.get('social', {}).get('max_age_hours', 2),
                                    enabled=config.get('social', {}).get('enabled', True)))


if __name__ == '__main__':
    print('Dry Socks — http://localhost:5111')
    app.run(host='127.0.0.1', port=5111, debug=False)
