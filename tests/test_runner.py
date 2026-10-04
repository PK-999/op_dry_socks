from datetime import datetime
from zoneinfo import ZoneInfo

import main
from services import state_manager


def test_active_window_uses_india_and_supports_overnight():
    config = {'polling': {'active_hours_start': '22:00', 'active_hours_end': '02:00'}}
    assert main.is_active_window(config, datetime(2026, 10, 3, 23, tzinfo=ZoneInfo('Asia/Kolkata')))
    assert main.is_active_window(config, datetime(2026, 10, 4, 1, tzinfo=ZoneInfo('Asia/Kolkata')))
    assert not main.is_active_window(config, datetime(2026, 10, 4, 12, tzinfo=ZoneInfo('Asia/Kolkata')))


def test_rain_escalation_bypasses_old_clear_cooldown(monkeypatch, tmp_path):
    monkeypatch.setattr(state_manager, 'STATE_FILE', str(tmp_path / 'state.json'))
    state_manager.save_state({'last_state': 'CLEAR', 'last_alert_timestamp': 1000, 'last_notified_rain_mins': 999})
    monkeypatch.setattr(state_manager.time, 'time', lambda: 1001)
    assert state_manager.should_notify('RUN_NOW', 40)[0] is True


def test_route_change_does_not_suppress_notification(monkeypatch, tmp_path):
    monkeypatch.setattr(state_manager, 'STATE_FILE', str(tmp_path / 'state.json'))
    state_manager.save_state({'route_key': 'old', 'last_state': 'RUN_NOW', 'last_alert_timestamp': 1000})
    monkeypatch.setattr(state_manager.time, 'time', lambda: 1001)
    assert state_manager.should_notify('RUN_NOW', 40, route_key='new')[0] is True
