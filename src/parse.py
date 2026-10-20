"""Turn Smart Oil Gauge web-app responses into plain tool results.

"Days to" estimates and the offline cutoff follow the web app's own
JavaScript (app.js: calcDTL, calcDTE, isOffline), as worked out in
kkrankall/smartoil-gauge (MIT), so numbers match app.smartoilgauge.com.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# The web app treats a sensor as offline after 96 h without a reading and
# then stops showing "days to" estimates.
OFFLINE_AFTER = 96 * 3600
# The web app shows usage under 0.2 gal/day as 0.
MIN_USAGE_RATE = 0.2
# A rise this large between readings is a delivery, not sensor noise
# (readings wander by a gallon or two).
FILL_MIN_GALLONS = 20.0
FILL_MIN_FRACTION = 0.10
BATTERY_RANK = {"Poor": 0, "Low": 0, "Fair": 1, "Good": 2, "Excellent": 3}


def _num(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _iso(ts: float | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC).isoformat()


def _oldest_read(last_read: Any) -> int | None:
    """last_read is one epoch per sensor, comma-separated; use the oldest."""
    times = [int(t) for t in str(last_read or "").split(",") if t.strip().isdigit()]
    return min(times) if times else None


def _worst_battery(battery: Any) -> str | None:
    """battery is one reading per sensor, comma-separated; report the worst."""
    values = [b.strip() for b in str(battery or "").split(",") if b.strip()]
    return min(values, key=lambda b: BATTERY_RANK.get(b, 0)) if values else None


def _days_until(gallons: float, target: float, rate: float | None) -> float | None:
    if not rate or rate <= 0:
        return None
    return round(max((gallons - target) / rate, 0.0), 1)


def tank_status(tank: dict, now: float) -> dict[str, Any]:
    """Current level and estimates from one get_tanks_list entry."""
    capacity = _num(tank.get("nominal"))
    fillable = _num(tank.get("fillable"))
    low_fraction = _num(tank.get("low_level")) or 0.25
    sensor_gallons = _num(tank.get("sensor_gallons"))
    # Tanks without a sensor (the "virtual" gauge) only have a modelled level.
    gallons = sensor_gallons if sensor_gallons is not None else _num(tank.get("model_gallons"))
    rate = _num(tank.get("sensor_usg"))
    if rate is not None and abs(rate) < MIN_USAGE_RATE:
        rate = 0.0
    last_read = _oldest_read(tank.get("last_read"))
    offline = last_read is not None and now - last_read > OFFLINE_AFTER

    data: dict[str, Any] = {
        "tank_id": str(tank.get("tank_id")),
        "tank_name": tank.get("tank_name"),
        "gallons": gallons,
        "percent_full": None,
        "capacity_gallons": capacity,
        "fillable_gallons": fillable,
        "gallons_to_fill": None,
        "usage_gallons_per_day": None if rate is None else round(rate, 2),
        "low_level_percent": round(low_fraction * 100, 1),
        "is_low": None,
        "days_to_low": None,
        "days_to_eighth": None,
        "days_to_empty": None,
        "battery": _worst_battery(tank.get("battery")),
        "sensor_status": tank.get("sensor_status") or None,
        "sensor_offline": offline,
        "last_reading": _iso(last_read),
    }
    if gallons is not None and capacity:
        data["percent_full"] = round(min(max(gallons * 100 / capacity, 0.0), 100.0), 1)
        data["is_low"] = gallons < capacity * low_fraction
        if not offline:
            data["days_to_low"] = (0.0 if data["is_low"] else
                                   _days_until(gallons, capacity * low_fraction, rate))
            data["days_to_eighth"] = _days_until(gallons, capacity * 0.125, rate)
            data["days_to_empty"] = _days_until(gallons, 0.0, rate)
    if gallons is not None and fillable:
        data["gallons_to_fill"] = round(max(fillable - gallons, 0.0), 1)
    return data


def _dataset(graph: dict | None, tank: dict) -> dict:
    """The graph datasets are keyed by sensor registration id."""
    datasets = (graph or {}).get("datasets") or {}
    for sensor in tank.get("sensors") or []:
        if str(sensor.get("registration_id")) in datasets:
            return datasets[str(sensor["registration_id"])]
    return next(iter(datasets.values()), {})


def detect_last_fill(dataset: dict, capacity: float | None) -> tuple[int | None, float | None]:
    """Latest delivery in the history as (reading epoch, gallons added).

    The year, month, week and day series are readings of the same tank at
    different spacing, so they merge into one series. Right after a fill the
    raw reading can sit in the sensor's dead zone near the top of the tank;
    the site's corrected value (fgal) gives the level after the fill.
    """
    points: dict[int, tuple[float, float | None]] = {}
    for period in ("year", "month", "week", "day"):
        for point in (dataset.get(period) or {}).get("points") or []:
            gallons = _num(point.get("gallons"))
            if point.get("ts") is not None and gallons is not None:
                points[int(point["ts"])] = (gallons, _num(point.get("fgal")))
    series = sorted(points.items())
    threshold = max(FILL_MIN_GALLONS, (capacity or 0) * FILL_MIN_FRACTION)
    for i in range(len(series) - 1, 0, -1):
        ts, (gallons, corrected) = series[i]
        before = series[i - 1][1][0]
        if gallons - before >= threshold:
            return ts, round(max(gallons, corrected or 0) - before, 1)
    return None, None


def daily_levels(dataset: dict) -> list[dict[str, Any]]:
    """Tank level over the past year, the last reading of each UTC day.

    Uses the site's smoothed, dead-zone-corrected value (fgal), as on its
    graph, falling back to the raw reading.
    """
    by_day: dict[str, tuple[int, float]] = {}
    for period in ("year", "month", "week", "day"):
        for point in (dataset.get(period) or {}).get("points") or []:
            gallons = _num(point.get("fgal"))
            if gallons is None:
                gallons = _num(point.get("gallons"))
            if point.get("ts") is None or gallons is None:
                continue
            ts = int(point["ts"])
            day = datetime.fromtimestamp(ts, UTC).date().isoformat()
            if day not in by_day or ts >= by_day[day][0]:
                by_day[day] = (ts, round(gallons, 2))
    return [{"date": day, "gallons": g} for day, (_, g) in sorted(by_day.items())]


def _latest_temperature(dataset: dict) -> float | None:
    """Temperature comes in tenths of a degree F (a basement tank reads
    540-810 over a year). Use the newest reading that has one."""
    for period in ("day", "week", "month"):
        points = [p for p in (dataset.get(period) or {}).get("points") or []
                  if _num(p.get("temperature"))]
        if points:
            latest = max(points, key=lambda p: int(p["ts"]))
            return round(_num(latest["temperature"]) / 10, 1)
    return None


def usage_history(tank: dict, graph: dict | None, include_daily_levels: bool) -> dict[str, Any]:
    """Usage totals, temperature and last delivery from get_graph_data."""
    dataset = _dataset(graph, tank)
    data: dict[str, Any] = {"tank_id": str(tank.get("tank_id")), "tank_name": tank.get("tank_name")}
    # The site's totals and gal/day averages per graph period. "day" starts
    # at local midnight and can be negative early on because readings wander.
    for label, period in (("today", "day"), ("7_days", "week"), ("30_days", "month"),
                          ("365_days", "year")):
        summary = dataset.get(period) or {}
        data[f"gallons_used_{label}"] = _num(summary.get("gallons"))
        data[f"average_gallons_per_day_{label}"] = _num(summary.get("gpd"))
    data["temperature_f"] = _latest_temperature(dataset)
    fill_ts, fill_gallons = detect_last_fill(dataset, _num(tank.get("nominal")))
    data["last_fill"] = _iso(fill_ts)
    data["last_fill_gallons"] = fill_gallons
    if include_daily_levels:
        data["daily_levels"] = daily_levels(dataset)
    return data
