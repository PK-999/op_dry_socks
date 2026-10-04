from services.evaluator import departure_advice

def test_evaluator_clear():
    weather_results = [
        {"name": "Office", "mins_to_rain": 999, "waterlogged": False},
        {"name": "~3km from Office", "mins_to_rain": 999, "waterlogged": False},
        {"name": "Home", "mins_to_rain": 999, "waterlogged": False}
    ]
    advice = departure_advice(commute_mins=30, safety_buffer=15, waypoints=weather_results, origin_name="Office", dest_name="Home")
    assert advice["state"] == "CLEAR"

def test_evaluator_waterlogged():
    weather_results = [
        {"name": "Office", "mins_to_rain": 999, "waterlogged": True},
        {"name": "Home", "mins_to_rain": 999, "waterlogged": False}
    ]
    advice = departure_advice(30, 15, weather_results, "Office", "Home")
    assert advice["state"] == "WATERLOGGED"

def test_evaluator_strand_risk():
    weather_results = [
        {"name": "Office", "mins_to_rain": 999, "waterlogged": False},
        {"name": "~15km from Office", "mins_to_rain": 10, "waterlogged": False}, # Rain hits midpoint in 10 mins!
        {"name": "Home", "mins_to_rain": 999, "waterlogged": False}
    ]
    # Commute is 45 mins. Rain hits midway in 10 mins. This is a trap!
    advice = departure_advice(45, 15, weather_results, "Office", "Home")
    assert advice["state"] == "STRAND_RISK"

def test_evaluator_run_now():
    weather_results = [
        {"name": "Office", "mins_to_rain": 999, "waterlogged": False},
        {"name": "Home", "mins_to_rain": 40, "waterlogged": False} # Rain hits destination in 40 mins
    ]
    # Commute is 30 mins. Rain arrives in 40 mins. Barely inside the safety buffer window (30+15=45).
    advice = departure_advice(30, 15, weather_results, "Office", "Home")
    assert advice["state"] == "RUN_NOW"
