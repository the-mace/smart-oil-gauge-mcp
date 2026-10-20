import parse

NOW = 1790000000 + 3600


def test_tank_status_matches_web_app_estimates(tanks_list):
    status = parse.tank_status(tanks_list["tanks"][0], NOW)
    assert status["tank_name"] == "Basement"
    assert status["gallons"] == 137.5
    assert status["percent_full"] == 50.0
    assert status["gallons_to_fill"] == 113.5
    assert status["is_low"] is False
    assert status["days_to_low"] == 27.5
    assert status["days_to_eighth"] == 41.2
    assert status["days_to_empty"] == 55.0
    assert status["battery"] == "Fair"
    assert status["sensor_offline"] is False
    assert status["last_reading"] == "2026-09-21T13:13:20+00:00"


def test_offline_sensor_has_no_estimates_and_tiny_usage_is_zero(tanks_list):
    status = parse.tank_status(tanks_list["tanks"][1], NOW)
    assert status["sensor_offline"] is True
    assert status["usage_gallons_per_day"] == 0.0
    assert status["is_low"] is True
    assert status["days_to_low"] is None
    assert status["days_to_empty"] is None


def test_virtual_gauge_uses_model_gallons():
    status = parse.tank_status({"tank_id": "9", "nominal": "200", "sensor_gallons": None,
                                "model_gallons": "100", "sensor_usg": "4"}, NOW)
    assert status["gallons"] == 100.0
    assert status["percent_full"] == 50.0
    assert status["days_to_empty"] == 25.0


def test_usage_history(tanks_list, graph_data):
    history = parse.usage_history(tanks_list["tanks"][0], graph_data, include_daily_levels=False)
    assert history["gallons_used_7_days"] == 17.5
    assert history["average_gallons_per_day_365_days"] == 1.9
    assert history["temperature_f"] == 65.0
    assert history["last_fill"] == "2026-08-24T19:33:20+00:00"
    # Uses the dead-zone-corrected level after the fill, not the raw reading.
    assert history["last_fill_gallons"] == 185.0
    assert "daily_levels" not in history


def test_daily_levels_keep_last_reading_per_day(tanks_list, graph_data):
    history = parse.usage_history(tanks_list["tanks"][0], graph_data, include_daily_levels=True)
    assert history["daily_levels"] == [
        {"date": "2025-10-09", "gallons": 200.0},
        {"date": "2026-08-23", "gallons": 60.0},
        {"date": "2026-08-24", "gallons": 245.0},
        {"date": "2026-09-15", "gallons": 150.0},
        {"date": "2026-09-21", "gallons": 137.5},
    ]


def test_noise_is_not_a_fill():
    dataset = {"day": {"points": [{"ts": 1, "gallons": 100}, {"ts": 2, "gallons": 101.5}]}}
    assert parse.detect_last_fill(dataset, 275) == (None, None)


def test_missing_graph_data():
    history = parse.usage_history({"tank_id": "1"}, None, include_daily_levels=True)
    assert history["gallons_used_today"] is None
    assert history["last_fill"] is None
    assert history["daily_levels"] == []
