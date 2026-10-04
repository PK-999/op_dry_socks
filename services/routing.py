"""Fresh route alternatives shared by the dashboard and notification runner."""
import math

import polyline
import requests

from .configuration import configured


class RoutingUnavailable(RuntimeError):
    pass


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def sample_geometry(geometry, interval_km=3.0, duration_mins=0):
    """Interpolate along cumulative road distance, including both endpoints.

    Point ETA assumes uniform progress; it is not a junction-level traffic ETA.
    At most 32 points are requested from the weather provider.
    """
    coords = geometry.get('coordinates', [])
    if len(coords) < 2:
        return []
    lengths = [haversine_km(a[1], a[0], b[1], b[0]) for a, b in zip(coords, coords[1:])]
    total = sum(lengths)
    if total <= 0:
        return []
    interval = max(float(interval_km), total / 30, 0.25)
    distances = [i * interval for i in range(int(total / interval) + 1)]
    if total - distances[-1] > 0.001:
        distances.append(total)
    else:
        distances[-1] = total
    points, segment, walked = [], 0, 0.0
    for target in distances:
        while segment < len(lengths) - 1 and walked + lengths[segment] < target:
            walked += lengths[segment]
            segment += 1
        a, b = coords[segment], coords[segment + 1]
        fraction = min(1, max(0, (target - walked) / lengths[segment])) if lengths[segment] else 0
        points.append({
            'lat': a[1] + (b[1] - a[1]) * fraction,
            'lon': a[0] + (b[0] - a[0]) * fraction,
            'distance_km': round(target, 2),
            'eta_mins': round(duration_mins * target / total, 1),
            'name': f'{target:.1f} km along route',
        })
    points[0]['name'], points[-1]['name'] = 'Start', 'Destination'
    return points


def _route(index, summary, seconds, meters, geometry, interval, provider, traffic_aware):
    seconds, meters = float(seconds), float(meters)
    if not math.isfinite(seconds) or seconds <= 0 or not math.isfinite(meters) or meters <= 0:
        raise ValueError('Invalid route metrics')
    mins = max(1, math.ceil(seconds / 60))
    points = sample_geometry(geometry, interval, mins)
    if not points:
        raise ValueError('Missing route geometry')
    return {
        'index': index, 'summary': summary or f'Route {index + 1}',
        'duration_mins': mins, 'distance_km': round(meters / 1000, 1),
        'geometry': geometry, 'waypoints': points, 'provider': provider,
        'traffic_aware': traffic_aware,
    }


def get_routes(config, origin, destination, travel_mode='TWO_WHEELER'):
    if travel_mode not in ('DRIVE', 'TWO_WHEELER'):
        raise ValueError('Choose car or two-wheeler')
    interval = config.get('route', {}).get('dense_sampling_interval_km', 3.0)
    google = config.get('google_maps_token')
    if configured(google):
        try:
            response = requests.post(
                'https://routes.googleapis.com/directions/v2:computeRoutes',
                headers={'X-Goog-Api-Key': google,
                         'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.description'},
                json={
                    'origin': {'location': {'latLng': {'latitude': origin['lat'], 'longitude': origin['lon']}}},
                    'destination': {'location': {'latLng': {'latitude': destination['lat'], 'longitude': destination['lon']}}},
                    'travelMode': travel_mode, 'routingPreference': 'TRAFFIC_AWARE',
                    'computeAlternativeRoutes': True, 'languageCode': 'en-US',
                }, timeout=12)
            response.raise_for_status()
            routes = []
            for index, item in enumerate(response.json().get('routes', [])[:3]):
                coordinates = [[lon, lat] for lat, lon in polyline.decode(item['polyline']['encodedPolyline'])]
                routes.append(_route(index, item.get('description'), item['duration'].removesuffix('s'),
                                     item['distanceMeters'], {'type': 'LineString', 'coordinates': coordinates},
                                     interval, 'Google Routes', True))
            if routes:
                return routes
        except (requests.RequestException, ValueError, KeyError, TypeError):
            pass  # Do not expose credential-bearing upstream URLs in error messages.
    mapbox = config.get('mapbox_token')
    # Mapbox driving is not a substitute for a motorcycle route.
    if travel_mode == 'DRIVE' and configured(mapbox):
        try:
            response = requests.get(
                f"https://api.mapbox.com/directions/v5/mapbox/driving/{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}",
                params={'access_token': mapbox, 'geometries': 'geojson', 'overview': 'full', 'alternatives': 'true'}, timeout=12)
            response.raise_for_status()
            routes = [_route(i, f'Driving route {i + 1}', r['duration'], r['distance'], r['geometry'],
                             interval, 'Mapbox · no live traffic', False)
                      for i, r in enumerate(response.json().get('routes', [])[:3])]
            if routes:
                return routes
        except (requests.RequestException, ValueError, KeyError, TypeError):
            pass
    raise RoutingUnavailable('Routes unavailable. Check your Google Routes API key and quota in config.json. Car routes can also use a Mapbox key.')


def _distance_to_segment(point, a, b):
    scale = math.cos(math.radians(point[1]))
    ax, ay = (a[0] - point[0]) * scale, a[1] - point[1]
    bx, by = (b[0] - point[0]) * scale, b[1] - point[1]
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) if dx * dx + dy * dy else 0
    return math.hypot(ax + t * dx, ay + t * dy) * 111.2


def select_saved_route(routes, saved=None):
    """Match a preference to fresh alternatives; never reuse a saved old ETA."""
    if not routes:
        raise RoutingUnavailable('No routes available')
    saved_coords = (saved or {}).get('geometry', {}).get('coordinates', [])
    if len(saved_coords) < 2:
        return routes[0]
    def score(route):
        coords = route['geometry']['coordinates']
        points = coords[::max(1, len(coords) // 40)]
        reverse = saved_coords[::max(1, len(saved_coords) // 40)]
        # Symmetric comparison avoids preferring a shortcut with only shared endpoints.
        return (sum(min(_distance_to_segment(p, a, b) for a, b in zip(saved_coords, saved_coords[1:])) for p in points) / len(points)
                + sum(min(_distance_to_segment(p, a, b) for a, b in zip(coords, coords[1:])) for p in reverse) / len(reverse))
    return min(routes, key=score)
