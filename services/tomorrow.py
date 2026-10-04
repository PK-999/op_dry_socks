import datetime
import logging
import math
import time

import requests

logger = logging.getLogger(__name__)


def get_tomorrow_rain(lat, lon, token, rain_threshold=0.4):
    """Return rain onset minutes, 999 for a dry forecast, or None if unavailable.

    Minute forecasts require an eligible Tomorrow.io plan. The configured rain
    threshold is mm/15 minutes; Tomorrow.io intensity is mm/hour.
    """
    if not token or token.startswith("YOUR_"):
        return None
    params = {"location": f"{lat},{lon}", "units": "metric", "apikey": token}
    try:
        resp = requests.get("https://api.tomorrow.io/v4/weather/forecast", params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        now = time.time()
        samples = []
        for entry in data.get("timelines", {}).get("minutely", []):
            stamp = datetime.datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                continue
            seconds = stamp.timestamp() - now
            values = entry.get("values", {})
            intensity = values.get("rainIntensity", values.get("precipitationIntensity"))
            if not isinstance(intensity, (int, float)) or not math.isfinite(intensity) or intensity < 0:
                continue
            if seconds >= -60:
                samples.append((seconds, intensity))
        if not samples:
            return None
        for seconds, intensity in sorted(samples):
            if intensity >= rain_threshold * 4:
                return max(0, math.floor(seconds / 60))
        return 999
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Request exception text can contain the API key in its URL.
        logger.warning("Tomorrow.io unavailable (%s)", type(exc).__name__)
        return None
