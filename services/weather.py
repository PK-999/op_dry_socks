"""Rain estimates with explicit missing-data handling.

Open-Meteo precipitation timestamps end the preceding 15-minute interval.
In Bengaluru these intervals are interpolated model estimates, not local radar.
"""
import datetime
from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import math
import threading
import time

import requests

from services.tomorrow import get_tomorrow_rain

logger = logging.getLogger(__name__)
NO_RAIN = 999  # Compatibility sentinel; None always means unavailable.
_weather_cache = {}
_cache_lock = threading.Lock()
_CACHE_SECONDS = 120


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _iso(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_result(waypoint):
    return {
        "lat": waypoint.get("lat"), "lon": waypoint.get("lon"),
        "name": waypoint.get("name", "Route point"),
        "eta_mins": waypoint.get("eta_mins"),
        "mins_to_rain": None, "waterlogged": False,
        "past_2h_rain_mm": None, "available": False, "forecast": [],
        "forecast_until": None,
    }


def _parse_weather(item, waypoint, now, rain_threshold, waterlog_threshold):
    result = _empty_result(waypoint)
    if not isinstance(item, dict):
        return result
    history = item.get("hourly") or {}
    past = [(t, p) for t, p in zip(history.get("time", []), history.get("precipitation", []))
            if _number(t) and now - 7200 < t <= now]
    if len(past) == 2 and all(_number(p) and p >= 0 for _, p in past):
        result["past_2h_rain_mm"] = round(sum(p for _, p in past), 2)
        result["waterlogged"] = result["past_2h_rain_mm"] >= waterlog_threshold

    timeline = item.get("minutely_15") or {}
    times, amounts = timeline.get("time", []), timeline.get("precipitation", [])
    if not times or len(times) != len(amounts):
        return result
    samples = sorted((t, p) for t, p in zip(times, amounts) if _number(t) and t > now)
    if not samples:
        return result
    result["forecast"] = [{"time": _iso(t), "precipitation_mm": p if _number(p) and p >= 0 else None}
                          for t, p in samples]
    result["forecast_until"] = _iso(samples[-1][0])
    # A current interval and consecutive valid intervals are required for a clear claim.
    covered = samples[0][0] - 900 <= now < samples[-1][0]
    complete = all(_number(p) and p >= 0 for _, p in samples)
    consecutive = all(right[0] - left[0] == 900 for left, right in zip(samples, samples[1:]))
    if not (covered and complete and consecutive):
        return result

    result["available"] = True
    result["mins_to_rain"] = NO_RAIN
    for end, amount in samples:
        if amount >= rain_threshold:
            # Conservative beginning of the accumulation interval, never its end.
            result["mins_to_rain"] = max(0, math.floor((end - 900 - now) / 60))
            break
    return result


def get_route_weather(waypoints, tomorrow_token=None, rain_threshold=0.4, waterlog_threshold=5.0):
    """Fetch one batch and return an ordered result for every route waypoint.

    ``waterlogged`` is a rainfall-based risk proxy, not a flooding observation.
    ``forecast`` timestamps are UTC interval ends. Provider failure never means dry.
    """
    if not waypoints:
        return []
    now = time.time()
    fingerprint = hashlib.sha256(str(tomorrow_token or '').encode()).hexdigest()
    keys = [(wp['lat'], wp['lon'], rain_threshold, waterlog_threshold, fingerprint) for wp in waypoints]
    entries = {}
    with _cache_lock:
        for key in keys:
            cached = _weather_cache.get(key)
            if cached and 0 <= now - cached['fetched_at'] < _CACHE_SECONDS:
                entries[key] = cached
    missing = list(dict.fromkeys(key for key in keys if key not in entries))
    params = {
        "latitude": ",".join(str(key[0]) for key in missing),
        "longitude": ",".join(str(key[1]) for key in missing),
        "minutely_15": "precipitation", "hourly": "precipitation",
        "timezone": "UTC", "past_hours": 2, "forecast_hours": 1,
        "past_minutely_15": 1, "forecast_minutely_15": 25,
        "timeformat": "unixtime",
    }
    if missing:
        try:
            resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else [data]
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.warning("Open-Meteo unavailable (%s)", type(exc).__name__)
            items = []
        for index, key in enumerate(missing):
            entry = {'item': items[index] if index < len(items) else {}, 'fetched_at': now}
            entries[key] = entry
            # Do not hold outages in the success cache; a refresh can recover.
            if entry['item']:
                with _cache_lock:
                    _weather_cache[key] = entry
                    while len(_weather_cache) > 256:
                        _weather_cache.pop(next(iter(_weather_cache)))

    results = []
    now = time.time()
    for index, waypoint in enumerate(waypoints):
        entry = entries[keys[index]]
        item = entry['item']
        try:
            result = _parse_weather(item, waypoint, now, rain_threshold, waterlog_threshold)
        except (TypeError, ValueError, OverflowError):
            result = _empty_result(waypoint)
        result['fetched_at'] = _iso(entry['fetched_at'])
        result['cached'] = entry['fetched_at'] < now
        results.append(result)
    if tomorrow_token and not tomorrow_token.startswith('YOUR_'):
        candidates = sorted((i for i, result in enumerate(results)
                             if result['mins_to_rain'] is not None and result['mins_to_rain'] < 60),
                            key=lambda i: results[i]['mins_to_rain'])[:3]
        def corroborate(index):
            entry, waypoint, result = entries[keys[index]], waypoints[index], results[index]
            if 'tomorrow_at' not in entry:
                tomorrow = get_tomorrow_rain(waypoint['lat'], waypoint['lon'], tomorrow_token, rain_threshold)
                entry['tomorrow_at'] = now + tomorrow * 60 if tomorrow is not None and tomorrow < NO_RAIN else None
            if entry['tomorrow_at'] is not None:
                tomorrow = max(0, math.floor((entry['tomorrow_at'] - time.time()) / 60))
                if tomorrow < result['mins_to_rain']:
                    result['mins_to_rain'] = tomorrow
                    result['corroborating_source'] = 'Tomorrow.io'
        # Optional corroboration must not turn a 32-point route into 32 serial waits.
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(corroborate, candidates))
    return results


def get_open_meteo_data(lat, lon, rain_threshold=0.4, waterlog_threshold=5.0):
    result = get_route_weather([{"lat": lat, "lon": lon}], rain_threshold=rain_threshold,
                               waterlog_threshold=waterlog_threshold)[0]
    return result["mins_to_rain"], result["waterlogged"]


def get_weather_data(lat, lon, tomorrow_token=None, rain_threshold=0.4, waterlog_threshold=5.0):
    """Compatibility tuple: (minutes until rain or None, rainfall-based risk)."""
    result = get_route_weather([{"lat": lat, "lon": lon}], tomorrow_token, rain_threshold,
                               waterlog_threshold)[0]
    return result["mins_to_rain"], result["waterlogged"]
