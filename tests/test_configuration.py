"""Configuration failures are actionable and never echo secret values."""

import json

import pytest

from services import configuration


def test_missing_explicit_config_does_not_silently_use_example(tmp_path):
    with pytest.raises(configuration.ConfigurationError, match="not found"):
        configuration.load_config(tmp_path / "missing.json")


@pytest.mark.parametrize(
    "content",
    [
        '{"google_maps_token": "secret-value",',
        "[]",
        '{"locations": []}',
        '{"route": {"travel_mode": "FLY"}}',
        '{"polling": {"interval_minutes": 0}}',
        '{"polling": {"active_hours_start": "25:00"}}',
        '{"thresholds": {"rain_mm_15min": "secret-value"}}',
        '{"google_maps_token": {"private": "secret-value"}}',
        '{"thresholds": {"rain_mm_15min": ' + "1" + "0" * 400 + "}}",
    ],
)
def test_invalid_config_is_redacted(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    with pytest.raises(configuration.ConfigurationError) as error:
        configuration.load_config(path)
    assert "secret-value" not in str(error.value)


def test_sparse_config_receives_defaults_without_persisting_env(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"social": {"enabled": false}}')
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "env-private")
    config = configuration.load_config(path)
    assert config["route"]["travel_mode"] == "TWO_WHEELER"
    assert config["social"]["enabled"] is False
    assert config["social"]["max_age_hours"] == 2
    assert config["google_maps_token"] == "env-private"
    assert "env-private" not in json.dumps(configuration.load_config(path, include_env=False))
