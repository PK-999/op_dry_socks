"""Exercise provider requests at the HTTP boundary, without Google billing."""
import json
from unittest.mock import Mock
import pytest
import requests
import server
from services import sources, twitter

@pytest.fixture
def web(monkeypatch):
    monkeypatch.setattr(server, '_load_config', lambda: {'google_maps_token': 'secret-server-key'})
    return server.app.test_client()

def response(data, status=200):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(data).encode()
    return r

def test_partial_search_uses_autocomplete_without_appending_city(web, monkeypatch):
    post = Mock(return_value=response({'suggestions': [{'placePrediction': {
        'placeId': 'metro-id', 'text': {'text': 'Hoodi, Bengaluru'},
        'structuredFormat': {'mainText': {'text': 'Hoodi'}, 'secondaryText': {'text': 'Bengaluru'}}}}]}))
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', Mock(side_effect=requests.ConnectionError()))
    r = web.get('/api/search?q=hoodi%20metr&session=abc-123&lat=12.99&lon=77.71')
    assert r.status_code == 200
    assert r.json['features'][0]['place_id'] == 'metro-id'
    args, kwargs = post.call_args
    assert args[0] == 'https://places.googleapis.com/v1/places:autocomplete'
    assert kwargs['json']['input'] == 'hoodi metr'
    assert kwargs['json']['includedRegionCodes'] == ['in']
    assert kwargs['json']['sessionToken'] == 'abc-123'
    assert kwargs['json']['locationBias']['circle']['center'] == {'latitude': 12.99, 'longitude': 77.71}
    assert 'includedPrimaryTypes' not in kwargs['json']
    assert 'secret-server-key' not in r.text

def test_provider_denied_is_actionable_and_does_not_fallback(web, monkeypatch):
    monkeypatch.setattr(requests, 'post', Mock(return_value=response({'error': {'status': 'PERMISSION_DENIED', 'message': 'secret-server-key'}}, 403)))
    get = Mock(side_effect=AssertionError('Must not use Photon'))
    monkeypatch.setattr(requests, 'get', get)
    r = web.get('/api/search?q=hoodi&session=abc')
    assert r.status_code == 503
    assert 'Places API' in r.json['error']
    assert 'secret-server-key' not in r.text

def test_details_resolves_coordinates_outside_bengaluru(web, monkeypatch):
    get = Mock(return_value=response({'id': 'delhi-id', 'formattedAddress': 'Connaught Place, New Delhi',
                                     'location': {'latitude': 28.6315, 'longitude': 77.2167}}))
    monkeypatch.setattr(requests, 'get', get)
    r = web.get('/api/place?place_id=delhi-id&session=abc')
    assert r.status_code == 200
    assert r.json['feature']['center'] == [77.2167, 28.6315]
    assert get.call_args.kwargs['params']['sessionToken'] == 'abc'
    assert server.location({'name': 'Delhi', 'lat': 28.63, 'lon': 77.21})['lat'] == 28.63
    assert server.geometry({'type': 'LineString', 'coordinates': [[77.21, 28.63], [77.22, 28.64]]})

def test_bad_search_parameters_do_not_reach_google(web, monkeypatch):
    post = Mock(side_effect=AssertionError('Bad input must be rejected locally'))
    monkeypatch.setattr(requests, 'post', post)
    for query in ('q=hello&session=bad%2Ftoken', 'q=hello&session=abc&lat=nan&lon=77', 'q=hello&session=abc&lat=12'):
        assert web.get('/api/search?' + query).status_code == 400

def test_non_bengaluru_route_does_not_fetch_city_accounts(monkeypatch):
    points = [{'lat': 28.63, 'lon': 77.21}, {'lat': 28.64, 'lon': 77.22}]
    assert sources.select_sources(points) == []
    monkeypatch.setattr(twitter, '_fetch_sources', Mock(side_effect=AssertionError('No Bengaluru requests for Delhi')))
    assert twitter.get_route_alerts(points, auth_token='private')['status'] == 'outside_coverage'

def test_only_dedicated_browser_key_is_public():
    from services.configuration import public_config
    value = public_config({'google_maps_token': 'server-private', 'google_maps_browser_key': 'browser-public'})
    assert value['google_maps_browser_key'] == 'browser-public'
    assert 'server-private' not in json.dumps(value)
