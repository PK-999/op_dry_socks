"""Live verification must reject partial weather even if a warning is returned."""

from datetime import datetime, timedelta, timezone

import e2e_test


def test_warning_with_missing_checkpoint_is_not_complete():
    result = {"state": "ACTIVE_RAIN", "weather": [{"available": False}]}
    assert not e2e_test.assessment_complete(result)


def test_forecast_must_cover_arrival_and_buffer():
    now = datetime.now(timezone.utc)
    point = {
        "available": True,
        "eta_mins": 30,
        "forecast_until": (now + timedelta(minutes=20)).isoformat(),
    }
    result = {"state": "STRAND_RISK", "weather": [point]}
    assert not e2e_test.assessment_complete(result, safety_buffer=15)
    point["forecast_until"] = (now + timedelta(hours=2)).isoformat()
    assert e2e_test.assessment_complete(result, safety_buffer=15)
