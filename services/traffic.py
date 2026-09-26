import requests
import logging
import polyline
import math

logger = logging.getLogger(__name__)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def sample_polyline(polyline_str, interval_km):
    coords = polyline.decode(polyline_str)
    if not coords:
        return []
        
    sampled = []
    last_point = coords[0]
    
    for i in range(1, len(coords) - 1): # Exclude last point (destination)
        pt = coords[i]
        dist = haversine_km(last_point[0], last_point[1], pt[0], pt[1])
        if dist >= interval_km:
            sampled.append({"lat": pt[0], "lon": pt[1]})
            last_point = pt
            
    return sampled

def get_google_maps_data(origin, destination, token, interval_km):
    if not token or token == "YOUR_GOOGLE_MAPS_API_KEY":
        raise ValueError("Invalid Google Maps token")
        
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin['lat']},{origin['lon']}",
        "destination": f"{destination['lat']},{destination['lon']}",
        "key": token,
        "departure_time": "now"
    }
    
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("status") != "OK" or not data.get("routes"):
        raise ValueError(f"Google Maps failed: {data.get('status')}")
        
    route = data["routes"][0]
    leg = route["legs"][0]
    
    if "duration_in_traffic" in leg:
        duration_seconds = leg["duration_in_traffic"]["value"]
    else:
        duration_seconds = leg["duration"]["value"]
        
    duration_mins = int(duration_seconds / 60)
    
    poly_str = route.get("overview_polyline", {}).get("points", "")
    intermediate_waypoints = sample_polyline(poly_str, interval_km)
    
    return duration_mins, intermediate_waypoints

def get_mapbox_data(origin, destination, token, interval_km):
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    params = {
        "access_token": token,
        "geometries": "geojson",
        "overview": "full"
    }
    
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get("routes"):
        raise ValueError("No routes returned from Mapbox")
        
    route = data["routes"][0]
    duration_seconds = route.get("duration", 0)
    duration_mins = int(duration_seconds / 60)
    
    geometry = route.get("geometry", {})
    intermediate_waypoints = []
    if geometry.get("type") == "LineString":
        coords = geometry.get("coordinates", [])
        if coords:
            last_point = (coords[0][1], coords[0][0])
            for i in range(1, len(coords) - 1):
                pt = (coords[i][1], coords[i][0])
                dist = haversine_km(last_point[0], last_point[1], pt[0], pt[1])
                if dist >= interval_km:
                    intermediate_waypoints.append({"lat": pt[0], "lon": pt[1]})
                    last_point = pt
                    
    return duration_mins, intermediate_waypoints

def get_commute_data(origin, destination, gmaps_token, mapbox_token, fallback_mins=60, interval_km=3.0):
    """
    Returns (duration_mins, intermediate_waypoints)
    """
    try:
        logger.info("Attempting Google Maps API...")
        return get_google_maps_data(origin, destination, gmaps_token, interval_km)
    except Exception as e:
        logger.warning(f"Google Maps failed: {e}. Falling back to Mapbox...")
        
    try:
        return get_mapbox_data(origin, destination, mapbox_token, interval_km)
    except Exception as e:
        logger.error(f"Mapbox API error: {e}. Falling back to {fallback_mins} mins.")
        return fallback_mins, []
