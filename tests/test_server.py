import json

import pytest

import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = json.loads(open('config.json.example').read())
    config.update(google_maps_token='private-google', twitter_auth_token='private-cookie')
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    monkeypatch.setattr(server, 'CONFIG_FILE', str(path))
    return server.app.test_client(), path, config


def test_config_does_not_expose_credentials_or_enable_cors(client):
    web, _, _ = client
    response = web.get('/api/config', headers={'Origin': 'https://unrelated.example'})
    assert 'private-google' not in response.text
    assert 'private-cookie' not in response.text
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_invalid_coordinate_does_not_mutate_saved_config(client):
    web, path, original = client
    response = web.post('/api/config', json={'origin': {'name': 'bad', 'lat': 'nan', 'lon': 77.5}})
    assert response.status_code == 400
    assert json.loads(path.read_text()) == original


def test_cross_origin_mutation_rejected(client):
    web, _, _ = client
    response = web.post('/api/config', json={'travel_mode': 'DRIVE'}, headers={'Origin': 'https://unrelated.example'})
    assert response.status_code == 403


def test_save_travel_mode_preserves_secrets(client):
    web, path, _ = client
    response = web.post('/api/config', json={'travel_mode': 'DRIVE'})
    assert response.status_code == 200
    config = json.loads(path.read_text())
    assert config['route']['travel_mode'] == 'DRIVE'
    assert config['twitter_auth_token'] == 'private-cookie'


def test_invalid_weather_payload_is_client_error(client):
    web, _, _ = client
    for value in [None, [], {'waypoints': []}, {'waypoints': [{'lat': True, 'lon': 77}]}]:
        response = web.post('/api/weather', json=value)
        assert response.status_code == 400


def test_waterlogging_is_never_random_report(client):
    web, _, _ = client
    response = web.post('/api/waterlogging', json={})
    assert response.status_code == 410


def test_document_allows_origin_referrer_for_map_tiles(client):
    web, _, _ = client
    response = web.get('/')
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    # API responses keep their existing stricter policy and secret redaction.
    assert web.get('/api/config').headers['Referrer-Policy'] == 'same-origin'
