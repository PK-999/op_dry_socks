import sys
import json
import time
import argparse
import datetime
import os
from services.traffic import get_commute_data
from services.weather import get_weather_data
from services.state_manager import should_notify, update_state
from services.evaluator import evaluate_state
from services.notifier import notify

DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(DIR, "config.json")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def is_active_window(config):
    now = datetime.datetime.now().time()
    start_time = datetime.datetime.strptime(config["polling"]["active_hours_start"], "%H:%M").time()
    end_time = datetime.datetime.strptime(config["polling"]["active_hours_end"], "%H:%M").time()
    return start_time <= now <= end_time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without sending notifications or updating state")
    parser.add_argument("--reverse", action="store_true", help="Swap origin and destination")
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    if not args.dry_run and not is_active_window(config):
        sys.exit(0)

    origin = config["locations"]["origin"]
    destination = config["locations"]["destination"]
    
    if args.reverse:
        origin, destination = destination, origin
    mapbox_token = config.get("mapbox_token")
    gmaps_token = config.get("google_maps_token")
    tomorrow_token = config.get("tomorrow_io_token")
    twitter_auth_token = config.get("twitter_auth_token")
    
    fallback = config["route"]["fallback_commute_mins"]
    interval_km = config["route"].get("dense_sampling_interval_km", 3.0)
    
    rain_thresh = config["thresholds"]["rain_mm_15min"]
    water_thresh = config["thresholds"]["waterlogging_past_2h_mm"]
    buffer_mins = config["thresholds"]["safety_buffer_mins"]

    commute_mins, intermediate_waypoints = get_commute_data(origin, destination, gmaps_token, mapbox_token, fallback, interval_km)

    coords_to_check = [
        {"name": origin["name"], "lat": origin["lat"], "lon": origin["lon"]},
    ]
    for i, wp in enumerate(intermediate_waypoints):
        dist_km = int((i + 1) * interval_km)
        coords_to_check.append({"name": f"~{dist_km}km from {origin['name']}", "lat": wp["lat"], "lon": wp["lon"]})
        
    coords_to_check.append({"name": destination["name"], "lat": destination["lat"], "lon": destination["lon"]})

    weather_results = []
    t_rain_corridor = 999
    
    for c in coords_to_check:
        t_rain, waterlogged = get_weather_data(c["lat"], c["lon"], tomorrow_token, rain_thresh, water_thresh)
        weather_results.append({
            "name": c["name"],
            "t_rain": t_rain,
            "waterlogged": waterlogged
        })
        if t_rain < t_rain_corridor:
            t_rain_corridor = t_rain

    from services.twitter import check_btp_alerts
    incidents = check_btp_alerts(route_polyline_or_waypoints=coords_to_check, auth_token=twitter_auth_token)

    state, title, subtitle, body = evaluate_state(
        commute_mins, buffer_mins, 
        weather_results,
        origin["name"], destination["name"],
        incidents
    )

    from services.telemetry import log_telemetry
    if not args.dry_run:
        log_telemetry(origin["name"], destination["name"], commute_mins, state, t_rain_corridor, weather_results)

    if args.dry_run:
        print(f"=== DRY RUN ===")
        print(f"Commute: {commute_mins} mins")
        for wr in weather_results:
            print(f"{wr['name']} -> Rain in: {wr['t_rain']} mins, Waterlogged: {wr['waterlogged']}")
        print(f"\nEvaluated State: {state}")
        print(f"Notification: {title} | {subtitle} - {body}")
        sys.exit(0)

    should_send, state_data = should_notify(state, t_rain_corridor)
    if should_send:
        notify(state, title, subtitle, body)
        update_state(state_data, state, t_rain_corridor)

if __name__ == "__main__":
    main()
