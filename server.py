"""
GridLock AI — Flask API Server
Serves the Command Center dashboard and provides JSON API endpoints
that read from the existing Backend/outputs CSV data.
"""

import os
import sys
import json
import pandas as pd
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

# Add Backend to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_PATH = os.path.join(BASE_DIR, "Backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from models.congestion_forecast import (
    generate_city_forecast, generate_zone_forecast,
    get_peak_hours, get_forecast_summary
)

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

OUTPUTS_DIR = os.path.join(BASE_DIR, "Backend", "outputs")

# ── Cache loaded data ──────────────────────────────────────────────────────
_cache = {}

def _load_data():
    if "loaded" not in _cache:
        _cache["raw_df"] = pd.read_csv(os.path.join(OUTPUTS_DIR, "cleaned_data_sample.csv"))
        _cache["raw_df"] = _cache["raw_df"].dropna(subset=["latitude", "longitude"])
        _cache["impact_df"] = pd.read_csv(os.path.join(OUTPUTS_DIR, "zone_impact_scores.csv"))
        _cache["hotspot_df"] = pd.read_csv(os.path.join(OUTPUTS_DIR, "hotspot_summary.csv"))
        _cache["loaded"] = True
    return _cache["raw_df"], _cache["impact_df"], _cache["hotspot_df"]


# ── Serve Frontend ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── API: Dashboard Stats ───────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    raw_df, impact_df, _ = _load_data()
    
    total_zones = len(impact_df)
    critical_zones = len(impact_df[impact_df["severity"] == "CRITICAL"])
    high_zones = len(impact_df[impact_df["severity"] == "HIGH"])
    medium_zones = len(impact_df[impact_df["severity"] == "MEDIUM"])
    low_zones = len(impact_df[impact_df["severity"] == "LOW"])
    total_violations = int(impact_df["violation_count"].sum())
    avg_impact = round(float(impact_df["impact_score"].mean()), 4)
    max_impact = round(float(impact_df["impact_score"].max()), 4)

    # Compute units deployed: tow trucks for CRITICAL, patrols for HIGH
    tow_trucks = critical_zones
    patrols = high_zones
    units_deployed = tow_trucks + patrols

    # Top critical zone for alert
    top_zone = impact_df.sort_values(by="impact_score", ascending=False).iloc[0]

    return jsonify({
        "total_zones": total_zones,
        "critical_zones": critical_zones,
        "high_zones": high_zones,
        "medium_zones": medium_zones,
        "low_zones": low_zones,
        "total_violations": total_violations,
        "avg_impact": avg_impact,
        "max_impact": max_impact,
        "units_deployed": units_deployed,
        "tow_trucks": tow_trucks,
        "patrols": patrols,
        "top_alert_zone": {
            "zone_id": str(top_zone["zone_id"]),
            "impact_score": round(float(top_zone["impact_score"]), 4),
            "severity": str(top_zone["severity"]),
            "center_lat": float(top_zone["center_lat"]),
            "center_lng": float(top_zone["center_lng"]),
        }
    })


# ── API: Zone Impact Scores ────────────────────────────────────────────────
@app.route("/api/zones")
def api_zones():
    _, impact_df, _ = _load_data()

    future_mins = request.args.get("future_mins", 0, type=int)
    multiplier = 1.0 + (future_mins * 0.05)

    df = impact_df.copy()
    df["impact_score"] = df["impact_score"] * multiplier

    def update_severity(score):
        if score > 0.8: return "CRITICAL"
        if score > 0.6: return "HIGH"
        if score > 0.4: return "MEDIUM"
        return "LOW"

    if future_mins > 0:
        df["severity"] = df["impact_score"].apply(update_severity)

    # Return top zones sorted by impact
    df = df.sort_values(by="impact_score", ascending=False)

    zones = []
    for _, row in df.iterrows():
        zones.append({
            "zone_id": str(row["zone_id"]),
            "center_lat": float(row["center_lat"]),
            "center_lng": float(row["center_lng"]),
            "violation_count": int(row["violation_count"]),
            "risk_score": round(float(row["risk_score"]), 6),
            "impact_score": round(float(row["impact_score"]), 4),
            "severity": str(row["severity"]),
            "enforcement_priority": int(row["enforcement_priority"]),
        })

    return jsonify(zones)


# ── API: Hotspot Summary ──────────────────────────────────────────────────
@app.route("/api/hotspots")
def api_hotspots():
    _, _, hotspot_df = _load_data()
    top = hotspot_df.sort_values(by="impact_score", ascending=False).head(30)
    records = []
    for _, row in top.iterrows():
        records.append({
            "zone_id": str(row["zone_id"]),
            "center_lat": float(row["center_lat"]),
            "center_lng": float(row["center_lng"]),
            "violation_count": int(row["violation_count"]),
            "risk_score": round(float(row["risk_score"]), 6),
            "impact_score": round(float(row["impact_score"]), 4),
            "severity": str(row["severity"]),
        })
    return jsonify(records)


# ── API: Congestion Forecast ──────────────────────────────────────────────
@app.route("/api/forecast")
def api_forecast():
    raw_df, impact_df, _ = _load_data()
    hours = request.args.get("hours", 24, type=int)
    zone_id = request.args.get("zone_id", None)

    if zone_id:
        forecast_df = generate_zone_forecast(zone_id, impact_df, raw_df, hours_ahead=hours)
        if forecast_df is None:
            return jsonify({"error": "Zone not found"}), 404
    else:
        forecast_df = generate_city_forecast(raw_df, impact_df, hours_ahead=hours)

    summary = get_forecast_summary(forecast_df)
    peaks = get_peak_hours(forecast_df, top_n=3)

    records = []
    for _, row in forecast_df.iterrows():
        records.append({
            "hour_label": str(row["hour_label"]),
            "hour": int(row["hour"]),
            "congestion_index": round(float(row["congestion_index"]), 2),
            "risk_level": str(row["risk_level"]),
            "confidence_lower": round(float(row["confidence_lower"]), 2),
            "confidence_upper": round(float(row["confidence_upper"]), 2),
            "violations_predicted": int(row.get("violations_predicted", 0)),
        })

    return jsonify({
        "forecast": records,
        "summary": summary,
        "peaks": peaks,
    })


# ── API: Violation Reasons ─────────────────────────────────────────────────
@app.route("/api/violations")
def api_violations():
    raw_df, _, _ = _load_data()

    def clean_violation(v):
        v_str = str(v).upper()
        if "WRONG PARKING" in v_str: return "Wrong Parking"
        if "NO PARKING" in v_str: return "No Parking Zone"
        if "FOOTPATH" in v_str: return "Footpath Parking"
        if "DOUBLE" in v_str: return "Double Parking"
        if "MAIN ROAD" in v_str: return "Main Road Parking"
        return "Other Violations"

    reasons = raw_df["violation_list"].apply(clean_violation)
    reason_counts = reasons.value_counts().to_dict()

    return jsonify({
        "reason_counts": reason_counts,
        "total_records": len(raw_df),
    })


# ── API: Dispatch Data ─────────────────────────────────────────────────────
@app.route("/api/dispatch")
def api_dispatch():
    _, impact_df, _ = _load_data()

    future_mins = request.args.get("future_mins", 0, type=int)
    multiplier = 1.0 + (future_mins * 0.05)
    df = impact_df.copy()
    df["impact_score"] = df["impact_score"] * multiplier

    def update_severity(score):
        if score > 0.8: return "CRITICAL"
        if score > 0.6: return "HIGH"
        if score > 0.4: return "MEDIUM"
        return "LOW"

    if future_mins > 0:
        df["severity"] = df["impact_score"].apply(update_severity)

    def format_action(sev):
        if sev == "CRITICAL": return "🚨 Dispatch Tow Truck ASAP"
        if sev == "HIGH": return "🚓 Send Patrol Unit"
        return "🟢 Issue E-Challan"

    df["action"] = df["severity"].apply(format_action)
    df = df.sort_values(by="impact_score", ascending=False)

    records = []
    for _, row in df.iterrows():
        records.append({
            "zone_id": str(row["zone_id"]),
            "severity": str(row["severity"]),
            "risk_score": round(float(row["risk_score"]), 4),
            "impact_score": round(float(row["impact_score"]), 4),
            "violation_count": int(row["violation_count"]),
            "action": str(row["action"]),
            "enforcement_priority": int(row["enforcement_priority"]),
        })

    return jsonify(records)


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    print("[GridLock AI] Command Center - Starting server...")
    print("   Dashboard: http://localhost:5000")
    app.run(debug=True, port=5000)
