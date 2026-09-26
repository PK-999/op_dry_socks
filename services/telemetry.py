import csv
import os
import datetime
import json

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_FILE = os.path.join(DIR, "telemetry.csv")

def log_telemetry(origin_name, dest_name, commute_mins, state, t_rain_corridor, weather_results):
    file_exists = os.path.isfile(TELEMETRY_FILE)
    
    with open(TELEMETRY_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "origin", "destination", "commute_mins", "state", "mins_to_rain", "weather_data"])
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        weather_str = json.dumps(weather_results)
        
        writer.writerow([timestamp, origin_name, dest_name, commute_mins, state, t_rain_corridor, weather_str])
