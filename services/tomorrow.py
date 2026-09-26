import requests
import logging

logger = logging.getLogger(__name__)

def get_tomorrow_rain(lat, lon, token, rain_threshold=0.4):
    """
    Returns mins_to_rain
    """
    if not token or token == "YOUR_TOMORROW_IO_API_KEY":
        raise ValueError("Invalid Tomorrow.io token")
        
    url = "https://api.tomorrow.io/v4/weather/forecast"
    params = {
        "location": f"{lat},{lon}",
        "timesteps": "1m",
        "units": "metric",
        "apikey": token
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        timelines = data.get("timelines", {}).get("minutely", [])
        mins_to_rain = 999
        
        for i, entry in enumerate(timelines):
            precip = entry.get("values", {}).get("precipitationIntensity", 0.0)
            if precip >= rain_threshold:
                mins_to_rain = i
                break
                
        return mins_to_rain
        
    except Exception as e:
        logger.error(f"Tomorrow.io API error: {e}")
        return 999
