import pytest
import polyline

from services import routing


def test_sampling_follows_distance_around_bend():
    geometry = {'type': 'LineString', 'coordinates': [[77.6, 12.9], [77.62, 12.9], [77.62, 12.92]]}
    points = routing.sample_geometry(geometry, interval_km=1, duration_mins=40)
    assert len(points) >= 5
    assert points[0]['eta_mins'] == 0
    assert points[-1]['eta_mins'] == 40
    assert points[1]['lat'] == pytest.approx(12.9)
    assert 77.6 < points[1]['lon'] < 77.62


def test_google_receives_mode_and_decimal_duration(monkeypatch):
    encoded = polyline.encode([(12.9, 77.6), (12.94, 77.64)])
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'routes': [{'duration': '1800.5s', 'distanceMeters': 5000,
                                'polyline': {'encodedPolyline': encoded}}]}
    def post(url, **kwargs):
        assert kwargs['json']['travelMode'] == 'DRIVE'
        return Response()
    monkeypatch.setattr(routing.requests, 'post', post)
    routes = routing.get_routes({'google_maps_token': 'configured'}, {'lat': 12.9, 'lon': 77.6}, {'lat': 12.94, 'lon': 77.64}, 'DRIVE')
    assert routes[0]['duration_mins'] == 31
    assert routes[0]['traffic_aware'] is True


def test_missing_routing_key_is_explicit():
    with pytest.raises(routing.RoutingUnavailable):
        routing.get_routes({}, {'lat': 12.9, 'lon': 77.6}, {'lat': 12.94, 'lon': 77.64}, 'TWO_WHEELER')


def test_saved_route_matches_geometry_not_old_duration():
    first = {'geometry': {'coordinates': [[77.5, 12.9], [77.55, 12.94]]}, 'duration_mins': 25}
    second = {'geometry': {'coordinates': [[77.5, 12.9], [77.6, 12.9], [77.55, 12.94]]}, 'duration_mins': 40}
    saved = dict(second, duration_mins=15)
    assert routing.select_saved_route([first, second], saved)['duration_mins'] == 40
