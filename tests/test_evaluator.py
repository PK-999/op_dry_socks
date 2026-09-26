import pytest
from services.evaluator import evaluate_state

def test_evaluator_clear():
    weather_results = [
        {"name": "Office", "t_rain": 999, "waterlogged": False},
        {"name": "~3km from Office", "t_rain": 999, "waterlogged": False},
        {"name": "Home", "t_rain": 999, "waterlogged": False}
    ]
    state, _, _, _ = evaluate_state(commute_mins=30, safety_buffer=15, waypoints=weather_results, origin_name="Office", dest_name="Home")
    assert state == "CLEAR"

def test_evaluator_waterlogged():
    weather_results = [
        {"name": "Office", "t_rain": 999, "waterlogged": True},
        {"name": "Home", "t_rain": 999, "waterlogged": False}
    ]
    state, _, _, _ = evaluate_state(30, 15, weather_results, "Office", "Home")
    assert state == "WATERLOGGED"

def test_evaluator_strand_risk():
    weather_results = [
        {"name": "Office", "t_rain": 999, "waterlogged": False},
        {"name": "~15km from Office", "t_rain": 10, "waterlogged": False}, # Rain hits midpoint in 10 mins!
        {"name": "Home", "t_rain": 999, "waterlogged": False}
    ]
    # Commute is 45 mins. Rain hits midway in 10 mins. This is a trap!
    state, _, _, _ = evaluate_state(45, 15, weather_results, "Office", "Home")
    assert state == "STRAND_RISK"

def test_evaluator_run_now():
    weather_results = [
        {"name": "Office", "t_rain": 999, "waterlogged": False},
        {"name": "Home", "t_rain": 40, "waterlogged": False} # Rain hits destination in 40 mins
    ]
    # Commute is 30 mins. Rain arrives in 40 mins. Barely inside the safety buffer window (30+15=45).
    state, _, _, _ = evaluate_state(30, 15, weather_results, "Office", "Home")
    assert state == "RUN_NOW"
