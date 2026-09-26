import requests
import logging
import time
from services.tomorrow import get_tomorrow_rain

logger = logging.getLogger(__name__)

def get_open_meteo_data(lat, lon, rain_threshold=0.4, waterlog_threshold=5.0):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "minutely_15": "precipitation",
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata",
        "forecast_days": 1,
        "past_hours": 2,
        "timeformat": "unixtime"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        now_ts = int(time.time())
        
        past_rain_sum = 0.0
        hourly_times = data.get("hourly", {}).get("time", [])
        hourly_precip = data.get("hourly", {}).get("precipitation", [])
        
        for t, precip in zip(hourly_times, hourly_precip):
            if now_ts - 7200 <= t <= now_ts:
                past_rain_sum += precip or 0.0
                
        is_waterlogged = past_rain_sum >= waterlog_threshold
        
        mins_to_rain = 999
        minutely_times = data.get("minutely_15", {}).get("time", [])
        minutely_precip = data.get("minutely_15", {}).get("precipitation", [])
        
        for t, precip in zip(minutely_times, minutely_precip):
            if t >= now_ts and (precip or 0.0) >= rain_threshold:
                mins_to_rain = int((t - now_ts) / 60)
                break
                
        return mins_to_rain, is_waterlogged
        
    except Exception as e:
        logger.error(f"Open-Meteo API error: {e}")
        return 999, False

def get_weather_data(lat, lon, tomorrow_token, rain_threshold=0.4, waterlog_threshold=5.0):
    """
    Orchestrates the Conditional Ensemble Strategy.
    Returns (mins_to_rain, is_waterlogged)
    """
    om_mins, is_waterlogged = get_open_meteo_data(lat, lon, rain_threshold, waterlog_threshold)
    
    if om_mins < 60 and tomorrow_token and tomorrow_token != "YOUR_TOMORROW_IO_API_KEY":
        logger.info(f"Open-Meteo detected rain in {om_mins}m. Verifying with Tomorrow.io...")
        tom_mins = get_tomorrow_rain(lat, lon, tomorrow_token, rain_threshold)
        
        if tom_mins < 60:
            final_mins = min(om_mins, tom_mins)
            return final_mins, is_waterlogged
        else:
            logger.info("Tomorrow.io overrode Open-Meteo (No rain).")
            return 999, is_waterlogged
            
    return om_mins, is_waterlogged
