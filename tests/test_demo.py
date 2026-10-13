"""Exercise the demo through HTTP with provider calls and persistence forbidden."""

import json

import pytest
import requests

from server import create_app
from services import configuration, dashboard


@pytest.fixture
def demo(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("The demo must not read credentials, call providers or save to disk")

    monkeypatch.setattr(configuration, "load_config", forbidden)
    monkeypatch.setattr(configuration, "save_config", forbidden)
    monkeypatch.setattr(dashboard, "load_config", forbidden)
    monkeypatch.setattr(dashboard, "save_config", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    # Even an explicit, credential-bearing file must not be read in demo mode.
    path = tmp_path / "private.json"
    path.write_text('{"google_maps_token": "private-secret"}')
    return create_app(path, demo=True).test_client(), path


def test_demo_search_routes_weather_and_memory_save(demo):
    web, path = demo
    config = web.get("/api/config").json
    assert config["demo"] is True
    assert not any(config["providers"].values())
    assert "private-secret" not in json.dumps(config)
    matches = web.get("/api/search?q=indira&session=demo-session").json["features"]
    assert matches
    selected = web.get(
        "/api/place?place_id=" + matches[0]["place_id"] + "&session=demo-session"
    ).json["feature"]
    assert len(selected["center"]) == 2
    payload = dict(config["locations"], travel_mode="TWO_WHEELER")
    routes = web.post("/api/routes", json=payload).json["routes"]
    assert len(routes) >= 2
    assert all(
        route["provider"].startswith("Demo") and route["traffic_aware"] is False for route in routes
    )
    route = routes[1]
    outlook = web.post(
        "/api/weather",
        json={"waypoints": route["waypoints"], "duration_mins": route["duration_mins"]},
    ).json
    assert outlook["status"] != "UNKNOWN"
    assert "Demo" in outlook["source"]
    assert outlook["coverage"]["available"] == len(route["waypoints"])
    reports = web.post(
        "/api/btp", json={"waypoints": route["waypoints"], "geometry": route["geometry"]}
    ).json
    assert reports["status"] == "demo"
    assert reports["alerts"] == []
    payload.update(travel_mode="DRIVE", selected_route=route)
    assert web.post("/api/config", json=payload).status_code == 200
    saved = web.get("/api/config").json
    assert saved["route"]["travel_mode"] == "DRIVE"
    assert saved["route"]["selected_route"]["geometry"] == route["geometry"]
    assert path.read_text() == '{"google_maps_token": "private-secret"}'


def test_demo_instances_do_not_share_saved_changes(demo):
    first, _ = demo
    first.post("/api/config", json={"travel_mode": "DRIVE"})
    second = create_app(demo=True).test_client()
    assert second.get("/api/config").json["route"]["travel_mode"] == "TWO_WHEELER"


def test_demo_unknown_place_and_invalid_save_are_explicit(demo):
    web, _ = demo
    assert web.get("/api/place?place_id=missing&session=demo").status_code == 400
    before = web.get("/api/config").json
    assert web.post("/api/config", json={"origin": {"lat": 999, "lon": 77}}).status_code == 400
    assert web.get("/api/config").json == before
