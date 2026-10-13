"""Local configuration. Private credentials never belong in browser responses."""

import json
import os
import tempfile
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.json"
SECRET_ENV = {
    "google_maps_token": "GOOGLE_MAPS_API_KEY",
    "google_maps_browser_key": "GOOGLE_MAPS_BROWSER_KEY",
    "mapbox_token": "MAPBOX_ACCESS_TOKEN",
    "tomorrow_io_token": "TOMORROW_IO_API_KEY",
    "twitter_auth_token": "TWITTER_AUTH_TOKEN",
    "twitter_bearer_token": "X_BEARER_TOKEN",
}


class ConfigurationError(RuntimeError):
    """An actionable local configuration error, with no credential contents."""


def _read_json(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        raise ConfigurationError(
            "Configuration file not found. Copy config.json.example or check --config."
        ) from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ConfigurationError(
            "Configuration could not be read. Check file permissions and JSON syntax."
        ) from None
    if not isinstance(value, dict):
        raise ConfigurationError("Configuration must be a JSON object.")
    return value


def _merge(defaults, overrides):
    result = dict(defaults)
    for key, value in overrides.items():
        result[key] = (
            _merge(defaults[key], value)
            if isinstance(defaults.get(key), dict) and isinstance(value, dict)
            else value
        )
    return result


def validate_config(config):
    """Validate settings once, at the file boundary, before provider calls."""
    from .validation import geometry, location, number

    try:
        for section in ("locations", "route", "thresholds", "polling", "social"):
            if not isinstance(config.get(section), dict):
                raise ValueError(f"{section} must be an object.")
        for endpoint in ("origin", "destination"):
            location(config["locations"].get(endpoint))
        route, polling, thresholds = config["route"], config["polling"], config["thresholds"]
        if route["travel_mode"] not in ("DRIVE", "TWO_WHEELER"):
            raise ValueError("route.travel_mode must be DRIVE or TWO_WHEELER.")
        number(route["dense_sampling_interval_km"], "route.dense_sampling_interval_km", 0.25, 100)
        if route.get("selected_route") is not None:
            if not isinstance(route["selected_route"], dict):
                raise ValueError("route.selected_route must be an object.")
            geometry(route["selected_route"].get("geometry"))
        number(polling["interval_minutes"], "polling.interval_minutes", 1, 1440)
        for key in ("active_hours_start", "active_hours_end"):
            value = polling[key]
            try:
                valid = isinstance(value, str) and time.fromisoformat(value).tzinfo is None
            except ValueError:
                valid = False
            if not valid:
                raise ValueError(f"polling.{key} must be a local clock time such as 16:00.")
        for key, lower, upper in [
            ("rain_mm_15min", 0.001, 100),
            ("safety_buffer_mins", 0, 180),
            ("waterlogging_past_2h_mm", 0.001, 1000),
        ]:
            number(thresholds[key], f"thresholds.{key}", lower, upper)
        if not isinstance(config["social"]["enabled"], bool):
            raise ValueError("social.enabled must be true or false.")
        number(config["social"]["max_age_hours"], "social.max_age_hours", 0.01, 168)
        for key in SECRET_ENV:
            if config.get(key) is not None and not isinstance(config[key], str):
                raise ValueError(f"{key} must be a string.")
    except ValueError as error:
        # Validation messages name fields and constraints, never user values.
        raise ConfigurationError(f"Invalid configuration: {error}") from None
    except (KeyError, TypeError):
        raise ConfigurationError(
            "Configuration has invalid settings. Check locations, route, polling, thresholds and provider keys against config.json.example."
        ) from None
    return config


def configured(value):
    return bool(value and not str(value).startswith("YOUR_"))


def load_config(path=None, include_env=True):
    selected = path or os.environ.get("DRYSOCKS_CONFIG")
    defaults = _read_json(ROOT / "config.json.example")
    path = Path(selected) if selected else DEFAULT_CONFIG
    config = _merge(defaults, _read_json(path)) if selected or path.exists() else defaults
    if include_env:
        for key, env in SECRET_ENV.items():
            if os.environ.get(env):
                config[key] = os.environ[env]
    return validate_config(config)


def save_config(config, path=None):
    path = Path(path or os.environ.get("DRYSOCKS_CONFIG", DEFAULT_CONFIG))
    fd, temporary = tempfile.mkstemp(prefix=".dry-socks-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def public_config(config):
    return {
        # This dedicated, referrer-restricted key is intentionally public.
        "google_maps_browser_key": config.get("google_maps_browser_key")
        if configured(config.get("google_maps_browser_key"))
        else None,
        "locations": config.get("locations", {}),
        "route": config.get("route", {}),
        "thresholds": config.get("thresholds", {}),
        "polling": config.get("polling", {}),
        "providers": {
            "google_maps": configured(config.get("google_maps_token")),
            "mapbox": configured(config.get("mapbox_token")),
            "tomorrow": configured(config.get("tomorrow_io_token")),
            "x": configured(config.get("twitter_auth_token"))
            or configured(config.get("twitter_bearer_token")),
        },
    }
