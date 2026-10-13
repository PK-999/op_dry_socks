"""One route/weather/advice pipeline for the dashboard and scheduled monitor."""

import hashlib
import json
from datetime import datetime, timezone

from .routing import RoutingUnavailable, get_routes, select_saved_route


def weather_outlook(
    config, points, duration, origin_name, destination_name, *, weather_fetcher=None
):
    from .evaluator import departure_advice
    from .weather import get_route_weather

    thresholds = config.get("thresholds", {})
    results = (weather_fetcher or get_route_weather)(
        points,
        config.get("tomorrow_io_token"),
        thresholds.get("rain_mm_15min", 0.4),
        thresholds.get("waterlogging_past_2h_mm", 5),
    )
    advice = departure_advice(
        duration, thresholds.get("safety_buffer_mins", 15), results, origin_name, destination_name
    )
    known = [point["mins_to_rain"] for point in results if point.get("mins_to_rain") is not None]
    return {
        "status": advice["state"],
        "status_label": advice["title"],
        "summary": advice["body"],
        "advice": advice,
        "corridor_mins_to_rain": min(known) if known else None,
        "any_waterlogged": any(point.get("waterlogged") for point in results),
        "waypoints": results,
        "updated_at": min(
            (point["fetched_at"] for point in results if point.get("fetched_at")),
            default=datetime.now(timezone.utc).isoformat(),
        ),
        "source": "Open-Meteo + Tomorrow.io"
        if any(point.get("corroborating_source") for point in results)
        else "Open-Meteo model forecast",
        "resolution_note": "15-minute values may be interpolated from hourly forecasts depending on model coverage. Rain timing and point arrival times are estimates; rainfall accumulation is not confirmed flooding.",
        "coverage": {
            "available": sum(bool(point.get("available")) for point in results),
            "total": len(points),
        },
    }


def assess_commute(config, reverse=False, social=True, route_fetcher=None):
    from services.twitter import get_route_alerts

    origin, destination = config["locations"]["origin"], config["locations"]["destination"]
    if reverse:
        origin, destination = destination, origin
    settings = config.get("route", {})
    mode = settings.get("travel_mode", "TWO_WHEELER")
    route_key = hashlib.sha256(
        json.dumps(
            [origin, destination, mode, settings.get("selected_route")], sort_keys=True
        ).encode()
    ).hexdigest()[:20]
    try:
        routes = (route_fetcher or get_routes)(config, origin, destination, mode)
        # Reverse commutes need their own newly calculated choice.
        route = select_saved_route(routes, None if reverse else settings.get("selected_route"))
    except RoutingUnavailable as error:
        return {
            "state": "UNKNOWN",
            "title": "Route unavailable",
            "subtitle": "Commute timing could not be checked.",
            "body": str(error),
            "leave_in_mins": None,
            "route_key": route_key,
            "rain_mins": None,
            "weather": [],
            "commute_mins": None,
            "origin": origin,
            "destination": destination,
            "social_status": "not_checked",
        }
    points = route["waypoints"]
    points[0]["name"], points[-1]["name"] = origin["name"], destination["name"]
    outlook = weather_outlook(
        config, points, route["duration_mins"], origin["name"], destination["name"]
    )
    weather = outlook["waypoints"]
    reports = get_route_alerts(
        points,
        config.get("twitter_auth_token"),
        config.get("twitter_bearer_token"),
        geometry=route["geometry"],
        max_age_hours=config.get("social", {}).get("max_age_hours", 2),
        enabled=social and config.get("social", {}).get("enabled", True),
    )
    # Source coverage alone does not prove a post describes an active incident.
    # Keep original reports as attributed context, as the dashboard does.
    advice = outlook["advice"]
    known = [p["mins_to_rain"] for p in weather if p.get("mins_to_rain") is not None]
    advice.update(
        route_key=route_key,
        rain_mins=min(known) if known else None,
        weather=weather,
        commute_mins=route["duration_mins"],
        origin=origin,
        destination=destination,
        social_status=reports["status"],
        reports=reports["alerts"],
    )
    return advice
