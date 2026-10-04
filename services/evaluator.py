"""Departure guidance from route arrival estimates and uncertain rain forecasts."""
import datetime
import math
import time


def departure_advice(commute_mins, safety_buffer, waypoints, origin_name="Origin", dest_name="Destination", incidents=None):
    """Return cautious guidance; waypoint ETA is relative to leaving now.

    Older callers without ETA values get evenly spaced estimates. Rain timing is
    a model estimate and cannot guarantee a dry journey or confirm flooding.
    """
    incidents = incidents or []
    notes = []
    for incident in incidents:
        if isinstance(incident, dict):
            notes.append(str(incident.get("summary") or incident.get("title") or incident.get("location") or "Traffic advisory"))
        else:
            notes.append(str(incident))
    incident_text = " Traffic advisories: " + "; ".join(notes[:3]) + "." if notes else ""

    def result(state, title, subtitle, body, leave_in_mins=None):
        return {"state": state, "title": title, "subtitle": subtitle,
                "body": body + incident_text, "leave_in_mins": leave_in_mins}

    if not waypoints:
        return result("UNKNOWN", "Weather unavailable", "Your route has not been checked.",
                      "Refresh the forecast before planning your departure.")

    unknown = False
    rain_points = []
    wet_history = []
    for index, point in enumerate(waypoints):
        name = point.get("name", "your route")
        if point.get("waterlogged"):
            wet_history.append(name)
        rain = point.get("mins_to_rain")
        eta = point.get("eta_mins")
        if not isinstance(eta, (int, float)) or not math.isfinite(eta):
            eta = commute_mins * index / max(1, len(waypoints) - 1)
        eta = max(0, eta)
        if rain is None or point.get("available") is False:
            unknown = True
            continue
        if not isinstance(rain, (int, float)) or not math.isfinite(rain):
            unknown = True
            continue
        horizon = point.get("forecast_until")
        if horizon:
            try:
                stamp = datetime.datetime.fromisoformat(horizon.replace("Z", "+00:00"))
                if stamp.timestamp() < time.time() + (eta + safety_buffer) * 60:
                    unknown = True
            except (ValueError, TypeError):
                unknown = True
        if rain < 999:
            rain_points.append({"rain": max(0, rain), "eta": eta, "name": name,
                                "index": index, "deadline": rain - eta - safety_buffer})

    if wet_history:
        return result("WATERLOGGED", "Waterlogging possible", "Heavy recent rain near " + ", ".join(wet_history[:2]) + ".",
                      "Forecast rainfall suggests a risk around low-lying roads. This is not a confirmed flood report; check local conditions.")

    if any(p["index"] == 0 and p["rain"] == 0 for p in rain_points):
        return result("ACTIVE_RAIN", "Rain likely at departure", f"Rain is forecast around {origin_name} now.",
                      f"Consider waiting or using rain protection for your estimated {commute_mins:g}-minute trip to {dest_name}.")

    conflict = [p for p in rain_points if p["rain"] < p["eta"]]
    if conflict:
        hit = min(conflict, key=lambda p: p["rain"] - p["eta"])
        return result("STRAND_RISK", "Rain may overlap your ride", f"Rain is forecast near {hit['name']} before you reach it.",
                      "Consider another departure time or route. Timing and road conditions may change.")

    if unknown:
        return result("UNKNOWN", "Forecast incomplete", "Some of your route could not be checked.",
                      "A reliable departure window is unavailable. Refresh before leaving and check local conditions.")

    leave_in = None
    if rain_points:
        limiting = min(rain_points, key=lambda p: p["deadline"])
        leave_in = max(0, math.floor(limiting["deadline"]))
        if limiting["deadline"] < max(1, safety_buffer):
            return result("RUN_NOW", "Consider leaving soon", f"Estimated departure window: {leave_in} minutes.",
                          f"Rain is forecast near {limiting['name']}. This estimate includes a {safety_buffer:g}-minute buffer; it cannot guarantee a dry trip.", leave_in)

    if incidents:
        return result("TRAFFIC_ALERT", "Check traffic before leaving", "A traffic advisory may affect your route.",
                      f"Allow extra time for your estimated {commute_mins:g}-minute trip.", leave_in)
    return result("CLEAR", "No immediate rain signal", "No rain overlap indicated for a departure now.",
                  f"Your trip to {dest_name} is estimated at {commute_mins:g} minutes. Forecasts can change; check again before leaving.", leave_in)
