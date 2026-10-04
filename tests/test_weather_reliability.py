"""Offline regression coverage for forecast timing and provider failures."""
import datetime
from unittest.mock import Mock

import pytest
import requests

from services import evaluator, tomorrow, weather


NOW = 1_800_000_000


def response(data):
    result = Mock()
    result.json.return_value = data
    return result


def forecast(amounts, offsets=None):
    offsets = offsets or [0, 900, 1800, 2700, 3600]
    return {
        "minutely_15": {"time": [NOW + n for n in offsets], "precipitation": amounts},
        "hourly": {"time": [NOW - 7200, NOW - 3600, NOW], "precipitation": [20, 2, 1]},
    }


@pytest.fixture(autouse=True)
def offline_clock(monkeypatch):
    monkeypatch.setattr(weather.time, "time", lambda: NOW)
    monkeypatch.setattr(requests, "get", Mock(side_effect=AssertionError("Unexpected network access")))
    if hasattr(weather, "_weather_cache"):
        weather._weather_cache.clear()


def test_provider_timeout_is_unknown_not_clear(monkeypatch):
    monkeypatch.setattr(requests, "get", Mock(side_effect=requests.Timeout()))
    assert weather.get_open_meteo_data(12.9, 77.6) == (None, False)


@pytest.mark.parametrize("data", [{}, {"minutely_15": {"time": [], "precipitation": []}}, forecast([None] * 5)])
def test_empty_or_null_forecast_is_unknown(monkeypatch, data):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(data))
    assert weather.get_open_meteo_data(12.9, 77.6)[0] is None


def test_rain_interval_ending_in_five_minutes_is_current(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(forecast([0, .8, 0, 0], [-600, 300, 1200, 2100])))
    assert weather.get_open_meteo_data(12.9, 77.6)[0] == 0


def test_future_rain_uses_start_of_accumulation_interval(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(forecast([0, 0, .8, 0, 0])))
    assert weather.get_open_meteo_data(12.9, 77.6)[0] == 15


def test_two_hour_history_does_not_count_three_hourly_buckets(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(forecast([0] * 5)))
    assert weather.get_open_meteo_data(12.9, 77.6) == (999, False)


def test_batch_weather_preserves_waypoint_order_eta_and_missing_results(monkeypatch):
    assert hasattr(weather, "get_route_weather"), "Route weather API is missing"
    monkeypatch.setattr(requests, "get", lambda *a, **k: response([forecast([0, 0, .8, 0, 0])]))
    points = [{"name": "Start", "lat": 12.9, "lon": 77.6, "eta_mins": 0},
              {"name": "End", "lat": 13, "lon": 77.7, "eta_mins": 40}]
    results = weather.get_route_weather(points)
    assert len(results) == 2
    assert results[0]["mins_to_rain"] == 15
    assert results[0]["past_2h_rain_mm"] == 3
    assert results[0]["forecast"][0]["time"].endswith("Z")
    assert results[1]["name"] == "End"
    assert results[1]["eta_mins"] == 40
    assert results[1]["available"] is False
    assert results[1]["mins_to_rain"] is None


def test_tomorrow_failure_cannot_erase_rain_warning(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(forecast([0, 0, .8, 0, 0])))
    monkeypatch.setattr(weather, "get_tomorrow_rain", lambda *a, **k: None)
    assert weather.get_weather_data(12.9, 77.6, "test-key")[0] == 15


def test_disagreeing_provider_cannot_erase_rain_warning(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(forecast([0, 0, .8, 0, 0])))
    monkeypatch.setattr(weather, "get_tomorrow_rain", lambda *a, **k: 999)
    assert weather.get_weather_data(12.9, 77.6, "test-key")[0] == 15


@pytest.mark.parametrize("data", [{}, {"timelines": {"minutely": []}}])
def test_tomorrow_missing_minutely_data_is_unknown(monkeypatch, data):
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(data))
    assert tomorrow.get_tomorrow_rain(12.9, 77.6, "test-key") is None


def test_tomorrow_uses_timestamps_and_converts_mm_per_hour(monkeypatch):
    def minute(offset, intensity):
        return {"time": datetime.datetime.fromtimestamp(NOW + offset, datetime.timezone.utc).isoformat(),
                "values": {"rainIntensity": intensity}}
    data = {"timelines": {"minutely": [minute(0, .5), minute(600, 2.0)]}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: response(data))
    assert tomorrow.get_tomorrow_rain(12.9, 77.6, "test-key", .4) == 10


def point(rain, eta, name="Point", **extra):
    return {"name": name, "mins_to_rain": rain, "waterlogged": False, "eta_mins": eta, **extra}


def test_unknown_waypoint_prevents_clear_recommendation():
    advice = evaluator.departure_advice(30, 15, [point(999, 0), point(None, 30)])
    assert advice["state"] == "UNKNOWN"


def test_earlier_route_point_uses_its_eta_not_full_trip_duration():
    points = [point(999, 0), point(40, 10), point(999, 60)]
    advice = evaluator.departure_advice(60, 15, points)
    assert advice["state"] == "CLEAR"


def test_rain_in_five_minutes_is_forecast_not_current():
    advice = evaluator.departure_advice(30, 15, [point(5, 0), point(999, 30)])
    assert advice["state"] == "RUN_NOW"


def test_departure_deadline_deducts_waypoint_eta_and_buffer():
    assert hasattr(evaluator, "departure_advice"), "Departure advice API is missing"
    advice = evaluator.departure_advice(45, 15, [point(999, 0), point(70, 45)])
    assert advice["leave_in_mins"] == 10
    assert advice["state"] == "RUN_NOW"


def test_incident_only_trip_is_not_clear():
    advice = evaluator.departure_advice(30, 15, [point(999, 0), point(999, 30)], incidents=["Road closed near destination"])
    assert advice["state"] == "TRAFFIC_ALERT"


def test_empty_route_is_unknown():
    advice = evaluator.departure_advice(30, 15, [])
    assert advice["state"] == "UNKNOWN"


def test_short_forecast_horizon_prevents_clear_advice():
    horizon = datetime.datetime.fromtimestamp(NOW + 1200, datetime.timezone.utc).isoformat()
    advice = evaluator.departure_advice(60, 15, [point(999, 0), point(999, 60, forecast_until=horizon)])
    assert advice["state"] == "UNKNOWN"


def test_cache_reuses_provider_data_but_recalculates_rain_countdown(monkeypatch):
    calls = []
    def provider(*args, **kwargs):
        calls.append(kwargs)
        return response(forecast([0, 0, .8, 0, 0]))
    monkeypatch.setattr(requests, "get", provider)
    assert weather.get_open_meteo_data(12.9, 77.6)[0] == 15
    monkeypatch.setattr(weather.time, "time", lambda: NOW + 60)
    assert weather.get_open_meteo_data(12.9, 77.6)[0] == 14
    assert len(calls) == 1, "Repeated route checks should not spend another provider request inside TTL"
    monkeypatch.setattr(weather.time, "time", lambda: NOW + 121)
    weather.get_open_meteo_data(12.9, 77.6)
    assert len(calls) == 2


def test_cache_does_not_reuse_a_different_threshold_or_credentials(monkeypatch):
    calls = []
    def provider(*args, **kwargs):
        calls.append(kwargs)
        return response(forecast([0, 0, .8, 0, 0]))
    monkeypatch.setattr(requests, "get", provider)
    monkeypatch.setattr(weather, "get_tomorrow_rain", lambda *a, **k: None)
    assert weather.get_weather_data(12.9, 77.6, "secret-one", .4)[0] == 15
    assert weather.get_weather_data(12.9, 77.6, "secret-one", 1)[0] == 999
    assert weather.get_weather_data(12.9, 77.6, "secret-two", .4)[0] == 15
    assert weather.get_weather_data(12.9, 77.6, "secret-two", .4)[0] == 15
    assert len(calls) == 3
    assert "secret-one" not in repr(weather._weather_cache)
    assert "secret-two" not in repr(weather._weather_cache)


def test_optional_second_provider_has_bounded_fanout(monkeypatch):
    points = [{'lat': 12.9 + i / 1000, 'lon': 77.6} for i in range(10)]
    monkeypatch.setattr(requests, 'get', lambda *a, **k: response([forecast([0, 0, .8, 0, 0]) for _ in points]))
    checked = []
    def second_provider(*args):
        checked.append(args[:2])
        return None
    monkeypatch.setattr(weather, 'get_tomorrow_rain', second_provider)
    results = weather.get_route_weather(points, 'test-key')
    assert len(checked) <= 3
    assert all(result['mins_to_rain'] == 15 for result in results)
