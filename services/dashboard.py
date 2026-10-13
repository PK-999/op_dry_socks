"""Dashboard endpoints. Validation and commute decisions live in shared services."""

from flask import Blueprint, current_app, jsonify, request

from . import demo, places
from .commute import weather_outlook
from .configuration import load_config, public_config, save_config
from .routing import RoutingUnavailable
from .routing import get_routes as fetch_routes
from .validation import geometry, location, number, waypoints

dashboard = Blueprint("dashboard", __name__)


def _load_config():
    if current_app.config["DEMO"]:
        from copy import deepcopy

        return deepcopy(current_app.extensions["demo_config"])
    return load_config(current_app.config["CONFIG_PATH"])


def payload():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Send a JSON object.")
    return value


@dashboard.get("/api/config")
def get_config():
    return jsonify(dict(public_config(_load_config()), demo=current_app.config["DEMO"]))


@dashboard.post("/api/config")
def update_config():
    data = payload()
    with current_app.extensions["config_lock"]:
        # Never copy environment credentials into the configuration on disk.
        config = (
            _load_config()
            if current_app.config["DEMO"]
            else load_config(current_app.config["CONFIG_PATH"], include_env=False)
        )
        changed = False
        for name in ("origin", "destination"):
            if name in data:
                value = location(data[name])
                changed |= value != config.get("locations", {}).get(name)
                config.setdefault("locations", {})[name] = value
        route = config.setdefault("route", {})
        if "travel_mode" in data:
            if data["travel_mode"] not in ("DRIVE", "TWO_WHEELER"):
                raise ValueError("Choose car or two-wheeler.")
            changed |= route.get("travel_mode") != data["travel_mode"]
            route["travel_mode"] = data["travel_mode"]
        if changed:
            route.pop("selected_route", None)
        if data.get("selected_route") is not None:
            selected = data["selected_route"]
            if not isinstance(selected, dict):
                raise ValueError("Selected route must be an object.")
            route["selected_route"] = {
                "geometry": geometry(selected.get("geometry")),
                "summary": str(selected.get("summary", "Saved route"))[:200],
            }
        if current_app.config["DEMO"]:
            current_app.extensions["demo_config"] = config
        else:
            save_config(config, current_app.config["CONFIG_PATH"])
    return jsonify(status="ok", locations=config["locations"], route=config["route"])


@dashboard.errorhandler(places.PlacesUnavailable)
def places_unavailable(error):
    return jsonify(features=[], provider="google", error=str(error)), 503


@dashboard.get("/api/search")
def search_places():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(features=[], provider="google")
    if len(query) > 160:
        raise ValueError("Search must be under 160 characters.")
    session = places.session_token(request.args.get("session"))
    lat, lon = 12.9716, 77.5946
    if "lat" in request.args or "lon" in request.args:
        try:
            point = location({"lat": float(request.args["lat"]), "lon": float(request.args["lon"])})
        except (ValueError, KeyError):
            raise ValueError("Provide valid latitude and longitude for the search area.")
        lat, lon = point["lat"], point["lon"]
    if current_app.config["DEMO"]:
        return jsonify(features=demo.autocomplete(query), provider="demo")
    return jsonify(
        features=places.autocomplete(_load_config(), query, session, lat, lon), provider="google"
    )


@dashboard.get("/api/place")
def place_details():
    session = places.session_token(request.args.get("session"))
    if current_app.config["DEMO"]:
        return jsonify(feature=demo.details(request.args.get("place_id", "")), provider="demo")
    return jsonify(
        feature=places.details(_load_config(), request.args.get("place_id", ""), session),
        provider="google",
    )


@dashboard.get("/api/reverse")
def reverse_geocode():
    try:
        point = location(
            {"lat": float(request.args.get("lat", "")), "lon": float(request.args.get("lon", ""))}
        )
    except (ValueError, TypeError):
        raise ValueError("Provide a valid map point.")
    if current_app.config["DEMO"]:
        return jsonify(features=[], provider="demo")
    return jsonify(
        features=places.reverse(_load_config(), point["lat"], point["lon"]), provider="google"
    )


@dashboard.post("/api/routes")
def get_routes():
    data, config = payload(), _load_config()
    origin, destination = location(data.get("origin")), location(data.get("destination"))
    mode = data.get(
        "travel_mode",
        data.get("travelMode", config.get("route", {}).get("travel_mode", "TWO_WHEELER")),
    )
    try:
        if mode not in ("DRIVE", "TWO_WHEELER"):
            raise ValueError("Choose car or two-wheeler.")
        routes = (demo.routes if current_app.config["DEMO"] else fetch_routes)(
            config, origin, destination, mode
        )
    except RoutingUnavailable as error:
        return jsonify(routes=[], error=str(error)), 503
    for route in routes:
        route["waypoints"][0]["name"], route["waypoints"][-1]["name"] = (
            origin["name"],
            destination["name"],
        )
    return jsonify(routes=routes)


@dashboard.post("/api/weather")
def get_weather():
    data, config = payload(), _load_config()
    points = waypoints(data.get("waypoints"))
    duration = number(data.get("duration_mins", 60), "Commute duration", 1, 360)
    outlook = weather_outlook(
        config,
        points,
        duration,
        str(data.get("origin_name", points[0]["name"]))[:200],
        str(data.get("destination_name", points[-1]["name"]))[:200],
        weather_fetcher=demo.weather if current_app.config["DEMO"] else None,
    )
    if current_app.config["DEMO"]:
        outlook.update(
            source="Demo · synthetic forecast",
            resolution_note="Sample data for exploring the app. Do not use this forecast or geometry to plan a journey.",
        )
    return jsonify(outlook)


@dashboard.post("/api/waterlogging")
def get_waterlogging():
    return jsonify(
        error="Standalone flood reports are unavailable. Use /api/weather for forecast accumulation risk."
    ), 410


@dashboard.post("/api/btp")
def get_btp_alerts():
    from services.twitter import get_route_alerts

    data, config = payload(), _load_config()
    points = waypoints(data.get("waypoints"))
    route_geometry = geometry(data["geometry"]) if data.get("geometry") else None
    if current_app.config["DEMO"]:
        return jsonify(status="demo", sources=[], alerts=[])
    return jsonify(
        get_route_alerts(
            points,
            auth_token=config.get("twitter_auth_token"),
            bearer_token=config.get("twitter_bearer_token"),
            geometry=route_geometry,
            max_age_hours=config.get("social", {}).get("max_age_hours", 2),
            enabled=config.get("social", {}).get("enabled", True),
        )
    )
