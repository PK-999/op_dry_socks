"""Offline cross-component review checks; no provider or notification effects."""
import copy

import pytest

import main
from services import notifier, state_manager, telemetry, twitter, weather


@pytest.fixture
def commute(monkeypatch):
    config = {
        'locations': {'origin': {'name': 'Start', 'lat': 12.9, 'lon': 77.6},
                      'destination': {'name': 'End', 'lat': 12.94, 'lon': 77.64}},
        'route': {'travel_mode': 'TWO_WHEELER'}, 'thresholds': {},
    }
    route = {'duration_mins': 30, 'geometry': {'type': 'LineString', 'coordinates': [[77.6, 12.9], [77.64, 12.94]]},
             'waypoints': [{'name': 'Start', 'lat': 12.9, 'lon': 77.6, 'eta_mins': 0},
                           {'name': 'End', 'lat': 12.94, 'lon': 77.64, 'eta_mins': 30}]}
    monkeypatch.setattr(main, 'get_routes', lambda *args: [copy.deepcopy(route)])
    monkeypatch.setattr(weather, 'get_route_weather', lambda points, *args: [dict(point, available=True, mins_to_rain=999, waterlogged=False) for point in points])
    monkeypatch.setattr(twitter, 'get_route_alerts', lambda *args, **kwargs: {'status': 'ok', 'alerts': [], 'sources': []})
    return config


def test_source_area_post_is_context_not_a_confirmed_disruption(commute, monkeypatch):
    monkeypatch.setattr(twitter, 'get_route_alerts', lambda *args, **kwargs: {
        'status': 'ok', 'sources': [], 'alerts': [{
            'handle': 'hsrltrafficps', 'text': 'Thank you to all volunteers at our road safety education event.',
            'scope': 'route', 'kind': 'traffic', 'url': 'https://x.com/hsrltrafficps/status/123',
        }],
    })
    assert main.assess_commute(commute)['state'] == 'CLEAR'


def test_dry_run_never_writes_state_or_telemetry_or_sends_notification(commute, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Dry runs must be free of local persistence and notifications')
    monkeypatch.setattr(main, 'notify', forbidden)
    monkeypatch.setattr(main, 'should_notify', forbidden)
    monkeypatch.setattr(telemetry, 'log_telemetry', forbidden)
    monkeypatch.setattr(state_manager, 'save_state', forbidden)
    assert main.run_once(commute, dry_run=True)['state'] == 'CLEAR'


def test_failed_notification_does_not_consume_alert(commute, monkeypatch):
    monkeypatch.setattr(weather, 'get_route_weather', lambda points, *args: [dict(point, available=True, mins_to_rain=0, waterlogged=False) for point in points])
    monkeypatch.setattr(main, 'notify', lambda *args: False)
    monkeypatch.setattr(main, 'should_notify', lambda *args, **kwargs: (True, {}))
    monkeypatch.setattr(telemetry, 'log_telemetry', lambda *args: None)
    def forbidden(*args):
        pytest.fail('Failed delivery must not be recorded as a sent alert')
    monkeypatch.setattr(main, 'update_state', forbidden)
    assert main.run_once(commute)['state'] == 'ACTIVE_RAIN'


def test_notification_text_cannot_break_applescript_string(monkeypatch):
    scripts = []
    monkeypatch.setattr(notifier.subprocess, 'run', lambda args, **kwargs: scripts.append(args))
    assert notifier.notify('RUN_NOW', 'Title', 'Subtitle', 'Road \\"quoted"\nnext line') is True
    assert scripts[0][:2] == ['osascript', '-e']
    assert 'Road \\\\\\"quoted\\" next line' in scripts[0][2]
