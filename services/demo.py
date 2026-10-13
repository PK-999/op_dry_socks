"""Synthetic portfolio fixtures. Never used as a fallback for live providers."""

import copy
import math
from datetime import datetime, timedelta, timezone

from .routing import haversine_km, sample_geometry

PLACES = [
    {"id": "koramangala", "name": "Koramangala", "lat": 12.9350, "lon": 77.6245},
    {"id": "indiranagar", "name": "Indiranagar", "lat": 12.9784, "lon": 77.6408},
    {"id": "whitefield", "name": "Whitefield", "lat": 12.9698, "lon": 77.7499},
    {"id": "bellandur", "name": "Bellandur", "lat": 12.9304, "lon": 77.6784},
    {"id": "marathahalli", "name": "Marathahalli", "lat": 12.9569, "lon": 77.7011},
    {"id": "silk-board", "name": "Silk Board", "lat": 12.9177, "lon": 77.6238},
]


def config():
    return {
        "locations": {
            key: {field: place[field] for field in ("name", "lat", "lon")}
            for key, place in zip(("origin", "destination"), PLACES)
        },
        "route": {"travel_mode": "TWO_WHEELER", "dense_sampling_interval_km": 2},
        "thresholds": {
            "rain_mm_15min": 0.4,
            "safety_buffer_mins": 15,
            "waterlogging_past_2h_mm": 5,
        },
        "polling": {
            "interval_minutes": 5,
            "active_hours_start": "16:00",
            "active_hours_end": "20:30",
        },
        "social": {"enabled": False, "max_age_hours": 2},
        "demo": True,
    }


def autocomplete(query):
    return [
        {
            "place_id": place["id"],
            "text": place["name"],
            "place_name": f"{place['name']}, Bengaluru · demo place",
        }
        for place in PLACES
        if query.casefold() in place["name"].casefold()
    ]


def details(place_id):
    place = next((place for place in PLACES if place["id"] == place_id), None)
    if place is None:
        raise ValueError("Choose one of the sample Bengaluru locations in demo mode.")
    return {"center": [place["lon"], place["lat"]], "place_name": place["name"]}


def routes(settings, origin, destination, mode):
    """Sample corridors between user points; these are deliberately not road routes."""
    if haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"]) < 0.01:
        raise ValueError("Choose different start and destination points.")
    result = []
    for index, offset in enumerate((0.009, -0.012)):
        coords = [
            [origin["lon"], origin["lat"]],
            [
                (origin["lon"] + destination["lon"]) / 2 + offset,
                (origin["lat"] + destination["lat"]) / 2,
            ],
            [destination["lon"], destination["lat"]],
        ]
        distance = sum(haversine_km(a[1], a[0], b[1], b[0]) for a, b in zip(coords, coords[1:]))
        duration = min(
            360, max(15, math.ceil(distance * (5 if mode == "DRIVE" else 4)) + index * 4)
        )
        shape = {"type": "LineString", "coordinates": coords}
        result.append(
            {
                "index": index,
                "summary": f"Sample corridor {index + 1}",
                "duration_mins": duration,
                "distance_km": round(distance, 1),
                "geometry": shape,
                "waypoints": sample_geometry(
                    shape, settings["route"]["dense_sampling_interval_km"], duration
                ),
                "provider": "Demo geometry · not road routing",
                "traffic_aware": False,
            }
        )
    return result


def weather(points, *_args):
    now = datetime.now(timezone.utc)
    interval = now.replace(second=0, microsecond=0, minute=now.minute // 15 * 15) + timedelta(
        minutes=15
    )
    results = []
    for index, point in enumerate(points):
        rain_interval = max(4, 8 - index)
        forecast = [
            {
                "time": (interval + timedelta(minutes=15 * step)).isoformat(),
                "precipitation_mm": 0.0 if step < rain_interval else 0.6,
            }
            for step in range(26)
        ]
        rain = max(
            0,
            math.floor(
                ((interval + timedelta(minutes=15 * (rain_interval - 1))) - now).total_seconds()
                / 60
            ),
        )
        results.append(
            dict(
                copy.deepcopy(point),
                mins_to_rain=rain,
                waterlogged=False,
                past_2h_rain_mm=0.0,
                available=True,
                forecast=forecast,
                forecast_until=forecast[-1]["time"],
                fetched_at=now.isoformat(),
                cached=False,
            )
        )
    return results
