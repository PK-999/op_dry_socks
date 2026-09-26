import json
import os
import time

STATE_FILE = os.path.expanduser("~/.varuna_state.json")

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_state": "CLEAR", "last_alert_timestamp": 0, "last_notified_rain_mins": 999}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_state": "CLEAR", "last_alert_timestamp": 0, "last_notified_rain_mins": 999}

def save_state(state):
    tmp_file = f"{STATE_FILE}.tmp"
    with open(tmp_file, "w") as f:
        json.dump(state, f)
    os.rename(tmp_file, STATE_FILE)

def should_notify(new_state, rain_corridor_mins):
    state = load_state()
    last_state = state.get("last_state")
    last_alert = state.get("last_alert_timestamp", 0)
    last_rain_mins = state.get("last_notified_rain_mins", 999)
    now = int(time.time())
    
    # 3. Escalation Override
    if new_state in ["STRAND_RISK", "ACTIVE_RAIN", "WATERLOGGED"] and new_state != last_state:
        return True, state
        
    # 1. Identical State Suppression
    if new_state == last_state:
        if new_state == "RUN_NOW" and (last_rain_mins - rain_corridor_mins) >= 10:
            return True, state
        return False, state
        
    # 2. Global Cooldown (20 mins = 1200 seconds)
    if now - last_alert < 1200:
        return False, state
        
    return True, state

def update_state(state_data, new_state, rain_corridor_mins):
    state_data["last_state"] = new_state
    state_data["last_alert_timestamp"] = int(time.time())
    state_data["last_notified_rain_mins"] = rain_corridor_mins
    save_state(state_data)
