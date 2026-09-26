def evaluate_state(commute_mins, safety_buffer, waypoints, origin_name="Origin", dest_name="Destination", incidents=None):
    if incidents is None:
        incidents = []
    t_rain_corridor = 999
    hit_loc = "your route"
    waterlogged_locs = []
    
    for wp in waypoints:
        if wp["t_rain"] < t_rain_corridor:
            t_rain_corridor = wp["t_rain"]
            hit_loc = wp["name"]
        
        if wp["waterlogged"]:
            waterlogged_locs.append(wp["name"])
            
    t_window = commute_mins + safety_buffer
    incident_str = f"\n⚠️ BTP Alert: {', '.join(incidents)}." if incidents else ""
    
    if waterlogged_locs:
        loc_str = " and ".join(waterlogged_locs[:2])
        if len(waterlogged_locs) > 2:
            loc_str += " and other points"
        return ("WATERLOGGED", 
                "Watch Out! 🌊", 
                f"Potential flooding near {loc_str}.",
                f"Heavy rain detected over the last 2 hours. Your route to {dest_name} indicates a commute of ~{commute_mins} mins, but expect severe waterlogging delays.{incident_str}")
        
    t_rain_origin = waypoints[0]["t_rain"]
    if t_rain_origin <= 5:
        return ("ACTIVE_RAIN", 
                "Stay Put! ☕", 
                f"It's raining at {origin_name}.",
                f"A storm is active right now. Current driving time to {dest_name} is ~{commute_mins} mins. Wait it out before leaving!{incident_str}")
        
    if commute_mins <= t_rain_corridor <= t_window:
        return ("RUN_NOW", 
                "Leave Now! 🚗", 
                f"Safe window closing in {t_rain_corridor} mins.",
                f"Rain will hit your route in ~{t_rain_corridor} mins. Your commute to {dest_name} is ~{commute_mins} mins. You can make it if you leave immediately!{incident_str}")
        
    if t_rain_corridor < commute_mins:
        return ("STRAND_RISK", 
                "Do Not Leave! 🌩️", 
                f"Storm hitting {hit_loc} in {t_rain_corridor} mins.",
                f"Your commute to {dest_name} takes ~{commute_mins} mins, but rain arrives in {t_rain_corridor} mins. You will get trapped in traffic if you leave now.{incident_str}")
        
    return ("CLEAR", 
            "Clear Skies ☀️", 
            "No immediate storm risk.", 
            f"Enjoy your {commute_mins} min commute to {dest_name}. No rain expected within your transit window.{incident_str}")
