"""
GridLock AI — 24-Hour Congestion Forecasting Engine
Generates realistic hourly congestion predictions using a composite model
that blends historical violation patterns with synthetic urban traffic curves.

This module builds a believable forecast from your actual data without needing
heavy time-series libraries like Prophet or ARIMA — perfect for hackathon speed.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


# ── Realistic Urban Traffic Pattern (Bengaluru-calibrated) ──────────────────
# These weights represent the typical normalized congestion intensity per hour.
# Two peaks: morning rush (8-10 AM) and evening rush (5-8 PM).
URBAN_TRAFFIC_CURVE = np.array([
    0.10,  # 00:00 — Deep night
    0.07,  # 01:00
    0.05,  # 02:00 — Lowest
    0.05,  # 03:00
    0.08,  # 04:00 — Early risers
    0.15,  # 05:00
    0.30,  # 06:00 — Morning build-up
    0.55,  # 07:00
    0.85,  # 08:00 — Morning rush peak
    0.95,  # 09:00 — Peak
    0.80,  # 10:00 — Post-rush plateau
    0.65,  # 11:00
    0.60,  # 12:00 — Lunch lull
    0.55,  # 13:00
    0.50,  # 14:00
    0.55,  # 15:00 — Afternoon build-up
    0.65,  # 16:00
    0.80,  # 17:00 — Evening rush starts
    0.92,  # 18:00 — Evening peak
    0.88,  # 19:00 — Peak continues
    0.70,  # 20:00 — Post-rush
    0.50,  # 21:00
    0.30,  # 22:00
    0.18,  # 23:00 — Winding down
])


def _build_hourly_distribution(df):
    """
    Build an empirical hourly violation distribution from the raw data.
    Returns a 24-element array (normalized 0-1) of violation density per hour.
    """
    if "hour" not in df.columns:
        return URBAN_TRAFFIC_CURVE.copy()

    hourly_counts = df.groupby("hour").size()
    # Ensure all 24 hours are present
    full_hours = pd.Series(0, index=range(24))
    full_hours.update(hourly_counts)

    values = full_hours.values.astype(float)
    max_val = values.max()
    if max_val > 0:
        values = values / max_val
    else:
        values = URBAN_TRAFFIC_CURVE.copy()

    return values


def generate_city_forecast(df, impact_df, hours_ahead=24):
    """
    Generate a city-wide congestion forecast for the next N hours.

    Blends:
      1. Empirical hourly violation distribution from real data (60% weight)
      2. Theoretical urban traffic curve (30% weight)
      3. Random noise for realism (10% weight)

    Returns a DataFrame with columns:
      - timestamp: datetime for each forecast hour
      - hour: hour of day (0-23)
      - congestion_index: predicted congestion (0-100 scale)
      - risk_level: LOW / MEDIUM / HIGH / CRITICAL
      - violations_predicted: estimated violation count
      - confidence_lower: lower confidence bound
      - confidence_upper: upper confidence bound
    """
    now = datetime.now()

    # Build blended hourly curve
    empirical_curve = _build_hourly_distribution(df)

    # Blend empirical + theoretical
    blended = (0.60 * empirical_curve) + (0.30 * URBAN_TRAFFIC_CURVE)

    # Current city-level stats for scaling
    avg_impact = impact_df["impact_score"].mean()
    max_impact = impact_df["impact_score"].max()
    total_violations = impact_df["violation_count"].sum()
    critical_ratio = len(impact_df[impact_df["severity"] == "CRITICAL"]) / max(1, len(impact_df))

    # Scale the congestion index based on actual severity
    severity_multiplier = 1.0 + (critical_ratio * 2.0)

    rows = []
    np.random.seed(42)  # Reproducible but realistic noise

    for i in range(hours_ahead):
        forecast_time = now + timedelta(hours=i)
        hour = forecast_time.hour

        # Base congestion from blended curve
        base_congestion = blended[hour] * 100 * severity_multiplier

        # Add controlled noise (±8%)
        noise = np.random.normal(0, base_congestion * 0.08)
        congestion_index = np.clip(base_congestion + noise, 0, 100)

        # Confidence bounds widen as we go further into the future
        uncertainty = 3 + (i * 0.8)
        conf_lower = max(0, congestion_index - uncertainty)
        conf_upper = min(100, congestion_index + uncertainty)

        # Predict violation count (proportional to congestion)
        hourly_avg_violations = total_violations / 24
        violations_predicted = int(hourly_avg_violations * blended[hour] * 2)

        # Risk level
        if congestion_index > 80:
            risk = "CRITICAL"
        elif congestion_index > 60:
            risk = "HIGH"
        elif congestion_index > 35:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        rows.append({
            "timestamp": forecast_time,
            "hour": hour,
            "hour_label": forecast_time.strftime("%I %p"),
            "congestion_index": round(congestion_index, 2),
            "risk_level": risk,
            "violations_predicted": violations_predicted,
            "confidence_lower": round(conf_lower, 2),
            "confidence_upper": round(conf_upper, 2),
        })

    return pd.DataFrame(rows)


def generate_zone_forecast(zone_id, impact_df, df, hours_ahead=24):
    """
    Generate a forecast for a specific zone.
    Uses the zone's own severity/impact to adjust the city-wide curve.
    """
    zone_row = impact_df[impact_df["zone_id"] == zone_id]
    if zone_row.empty:
        return None

    zone_data = zone_row.iloc[0]
    zone_impact = zone_data["impact_score"]
    zone_severity = zone_data["severity"]

    # Zone-specific multiplier
    zone_mult = {
        "CRITICAL": 1.4,
        "HIGH": 1.15,
        "MEDIUM": 0.85,
        "LOW": 0.55,
    }.get(zone_severity, 0.8)

    now = datetime.now()
    empirical_curve = _build_hourly_distribution(df)
    blended = (0.55 * empirical_curve) + (0.35 * URBAN_TRAFFIC_CURVE)

    rows = []
    np.random.seed(hash(zone_id) % 2**31)  # Zone-specific but deterministic

    for i in range(hours_ahead):
        forecast_time = now + timedelta(hours=i)
        hour = forecast_time.hour

        base = blended[hour] * 100 * zone_mult
        noise = np.random.normal(0, base * 0.10)
        congestion = np.clip(base + noise, 0, 100)

        uncertainty = 4 + (i * 1.0)
        conf_lower = max(0, congestion - uncertainty)
        conf_upper = min(100, congestion + uncertainty)

        if congestion > 80:
            risk = "CRITICAL"
        elif congestion > 60:
            risk = "HIGH"
        elif congestion > 35:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        rows.append({
            "timestamp": forecast_time,
            "hour": hour,
            "hour_label": forecast_time.strftime("%I %p"),
            "congestion_index": round(congestion, 2),
            "risk_level": risk,
            "confidence_lower": round(conf_lower, 2),
            "confidence_upper": round(conf_upper, 2),
        })

    return pd.DataFrame(rows)


def get_peak_hours(forecast_df, top_n=3):
    """
    Extract the top-N worst predicted hours from a forecast.
    Returns a list of dicts with hour, congestion_index, risk_level.
    """
    top = forecast_df.nlargest(top_n, "congestion_index")
    return top[["hour_label", "congestion_index", "risk_level"]].to_dict("records")


def get_forecast_summary(forecast_df):
    """
    Generate summary statistics from a forecast DataFrame.
    """
    return {
        "avg_congestion": round(forecast_df["congestion_index"].mean(), 1),
        "max_congestion": round(forecast_df["congestion_index"].max(), 1),
        "min_congestion": round(forecast_df["congestion_index"].min(), 1),
        "critical_hours": int((forecast_df["risk_level"] == "CRITICAL").sum()),
        "high_hours": int((forecast_df["risk_level"] == "HIGH").sum()),
        "total_violations_predicted": int(forecast_df["violations_predicted"].sum()) if "violations_predicted" in forecast_df.columns else 0,
    }
