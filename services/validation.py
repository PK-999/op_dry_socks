"""Validation shared by the HTTP and configuration boundaries."""

import math


def number(value, label, lower, upper):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not lower <= value <= upper
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} must be a number between {lower} and {upper}.")
    return value


def location(value, default="Location"):
    if not isinstance(value, dict):
        raise ValueError("Location must contain latitude and longitude.")
    name = value.get("name", default)
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError("Location name must contain 1–200 characters.")
    return {
        "name": name.strip(),
        "lat": number(value.get("lat"), "Latitude", -90, 90),
        "lon": number(value.get("lon"), "Longitude", -180, 180),
    }


def waypoints(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError("Provide between 1 and 32 route weather points.")
    results = []
    for i, item in enumerate(value):
        point = location(item, f"Point {i + 1}")
        if "eta_mins" in item:
            point["eta_mins"] = number(item["eta_mins"], "Point arrival time", 0, 360)
        results.append(point)
    return results


def geometry(value):
    if not isinstance(value, dict) or value.get("type") != "LineString":
        raise ValueError("Route geometry must be a LineString.")
    coords = value.get("coordinates")
    if not isinstance(coords, list) or not 2 <= len(coords) <= 20000:
        raise ValueError("Route geometry must contain 2–20,000 coordinates.")
    clean = []
    for pair in coords:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each coordinate must be [longitude, latitude].")
        clean.append(
            [number(pair[0], "Longitude", -180, 180), number(pair[1], "Latitude", -90, 90)]
        )
    return {"type": "LineString", "coordinates": clean}
