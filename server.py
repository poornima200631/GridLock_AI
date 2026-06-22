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
import requests
import time

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

# ── Active Dispatch Store (in-memory) ─────────────────────────────────────
_active_dispatches = {}  # zone_id -> dispatch record

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


# ── Mappls API Proxy Integration ───────────────────────────────────────────

MAPPLS_TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"
mappls_cache = {
    "token": None,
    "expiry": 0,
    "client_id": None,
    "client_secret": None
}

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    config = {
        "MAPPLS_CLIENT_ID": "",
        "MAPPLS_CLIENT_SECRET": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
        "TWILIO_FROM_PHONE": "",
        "TWILIO_TO_PHONE": "",
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config.update(json.load(f))
        except Exception as e:
            print(f"Error loading config.json: {e}")
    
    # Fallback to env vars if config.json fields are empty
    env_keys = {
        "MAPPLS_CLIENT_ID": "MAPPLS_CLIENT_ID",
        "MAPPLS_CLIENT_SECRET": "MAPPLS_CLIENT_SECRET",
        "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
        "TWILIO_ACCOUNT_SID": "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN": "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_PHONE": "TWILIO_FROM_PHONE",
        "TWILIO_TO_PHONE": "TWILIO_TO_PHONE",
        "TWILIO_WHATSAPP_FROM": "TWILIO_WHATSAPP_FROM"
    }
    
    # Check .env first if it exists to import initial credentials
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    for k, env_var in env_keys.items():
        if not config.get(k):
            config[k] = os.environ.get(env_var, "")
    
    return config

def save_config(config_data):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config.json: {e}")
        return False

def get_mappls_config():
    config = load_config()
    mappls_cache["client_id"] = config.get("MAPPLS_CLIENT_ID", "")
    mappls_cache["client_secret"] = config.get("MAPPLS_CLIENT_SECRET", "")
    return mappls_cache["client_id"], mappls_cache["client_secret"]

def get_mappls_token():
    client_id, client_secret = get_mappls_config()
    if not client_id or not client_secret:
        return None, True # Mock mode

    now = time.time()
    if mappls_cache["token"] and now < mappls_cache["expiry"]:
        return mappls_cache["token"], False

    try:
        res = requests.post(
            MAPPLS_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )
        if res.status_code == 200:
            data = res.json()
            mappls_cache["token"] = data.get("access_token")
            mappls_cache["expiry"] = now + int(data.get("expires_in", 86400)) - 3600
            return mappls_cache["token"], False
    except Exception as e:
        print(f"Error fetching Mappls token: {e}")
    
    return None, True # Fallback to mock

# Endpoints
@app.route("/api/mappls/token")
def api_mappls_token():
    token, is_mock = get_mappls_token()
    return jsonify({
        "access_token": token or "mock_token_gridlock_ai",
        "is_mock": is_mock
    })

@app.route("/api/mappls/rev_geocode")
def api_mappls_rev_geocode():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    if not lat or not lng:
        return jsonify({"error": "Missing lat/lng"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://search.mappls.com/search/address/rev-geocode?lat={lat}&lng={lng}"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls rev_geocode error: {e}")

    lat_f = float(lat)
    lng_f = float(lng)
    address = "MG Road, Craig Park Layout, Bengaluru, Karnataka 560001"
    if lat_f < 12.93:
        address = "Koramangala 5th Block, 80 Feet Road, Bengaluru, Karnataka 560095"
    elif lat_f < 12.95:
        address = "Jayanagar 4th Block, 11th Main Rd, Bengaluru, Karnataka 560011"
    elif lng_f < 77.55:
        address = "Vijay Nagar Central, 1st Main Road, Bengaluru, Karnataka 560040"
    
    return jsonify({
        "results": [{
            "formatted_address": address,
            "locality": "Bengaluru",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001"
        }]
    })

@app.route("/api/mappls/nearby")
def api_mappls_nearby():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    keyword = request.args.get("keyword", "police station")
    if not lat or not lng:
        return jsonify({"error": "Missing lat/lng"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://search.mappls.com/search/places/nearby/json?keywords={keyword}&refLocation={lat},{lng}"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls nearby error: {e}")

    pois = []
    if "police" in keyword.lower():
        pois = [
            {"placeName": "Madiwala Police Station", "eLoc": "MADI01", "placeAddress": "Madiwala Main Rd, Bengaluru, 560068", "distance": 450},
            {"placeName": "Koramangala Police Yard", "eLoc": "KORA02", "placeAddress": "80 Feet Rd, Koramangala, Bengaluru, 560034", "distance": 1200},
            {"placeName": "Bengaluru Traffic Headquarters", "eLoc": "HEAD01", "placeAddress": "Infantry Rd, Bengaluru, 560001", "distance": 3200}
        ]
    else:
        pois = [
            {"placeName": "GridLock Heavy Towing Yard A", "eLoc": "TOW001", "placeAddress": "Silk Board Junction, Bengaluru, 560068", "distance": 800},
            {"placeName": "City Towing Services Ltd", "eLoc": "TOW002", "placeAddress": "Hosur Road, Bengaluru, 560029", "distance": 1500}
        ]
    
    return jsonify({"suggestedLocations": pois})

@app.route("/api/mappls/place_detail")
def api_mappls_place_detail():
    eloc = request.args.get("eloc")
    if not eloc:
        return jsonify({"error": "Missing eloc"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://explore.mappls.com/apis/O2O/entity/{eloc}"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls place_detail error: {e}")

    details = {
        "MADI01": {"placeName": "Madiwala Police Station", "address": "Madiwala Main Rd, Bengaluru, 560068", "phone": "+91 80 2294 2561", "type": "Police Station", "rating": "4.2", "lat": 12.9220, "lng": 77.6200},
        "KORA02": {"placeName": "Koramangala Police Yard", "address": "80 Feet Rd, Koramangala, Bengaluru, 560034", "phone": "+91 80 2294 3622", "type": "Police Station", "rating": "3.8", "lat": 12.9340, "lng": 77.6220},
        "TOW001": {"placeName": "GridLock Heavy Towing Yard A", "address": "Silk Board Junction, Bengaluru, 560068", "phone": "+91 98860 12345", "type": "Towing Service", "rating": "4.5", "lat": 12.9176, "lng": 77.6238},
        "TOW002": {"placeName": "City Towing Services Ltd", "address": "Hosur Road, Bengaluru, 560029", "phone": "+91 99000 54321", "type": "Towing Service", "rating": "4.1", "lat": 12.9300, "lng": 77.6100}
    }
    
    default_detail = {"placeName": f"Agency {eloc}", "address": "Bengaluru Metro Area", "phone": "+91 80 1000 0000", "type": "Emergency responder", "rating": "4.0", "lat": 12.9716, "lng": 77.5946}
    
    return jsonify(details.get(eloc, default_detail))

@app.route("/api/mappls/route")
def api_mappls_route():
    start_lat = request.args.get("start_lat")
    start_lng = request.args.get("start_lng")
    end_lat = request.args.get("end_lat")
    end_lng = request.args.get("end_lng")
    
    if not all([start_lat, start_lng, end_lat, end_lng]):
        return jsonify({"error": "Missing coordinates"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://apis.mappls.com/advancedmaps/v1/route?start={start_lat},{start_lng}&end={end_lat},{end_lng}&resource=route_eta"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls route error: {e}")

    s_lat, s_lng = float(start_lat), float(start_lng)
    e_lat, e_lng = float(end_lat), float(end_lng)
    
    steps = [
        [s_lat, s_lng],
        [s_lat + (e_lat - s_lat) * 0.3, s_lng + (e_lng - s_lng) * 0.1],
        [s_lat + (e_lat - s_lat) * 0.6, s_lng + (e_lng - s_lng) * 0.7],
        [e_lat, e_lng]
    ]
    
    dist_km = round(((s_lat - e_lat)**2 + (s_lng - e_lng)**2)**0.5 * 111, 2)
    duration_min = round(dist_km * 2.5 + 4, 1)
    
    return jsonify({
        "routes": [{
            "geometry": steps,
            "duration": duration_min * 60,
            "distance": dist_km * 1000,
            "traffic_delay": round(duration_min * 0.25 * 60)
        }]
    })

@app.route("/api/mappls/distance_matrix")
def api_mappls_distance_matrix():
    origins = request.args.get("origins")
    destinations = request.args.get("destinations")
    
    if not origins or not destinations:
        return jsonify({"error": "Missing origins/destinations"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://apis.mappls.com/advancedmaps/v1/distance_matrix?origins={origins}&destinations={destinations}"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls distance_matrix error: {e}")

    orig_list = [o.split(",") for o in origins.split(";")]
    dest_list = [d.split(",") for d in destinations.split(";")]
    
    results = []
    for o in orig_list:
        row = []
        o_lat, o_lng = float(o[0]), float(o[1])
        for d in dest_list:
            d_lat, d_lng = float(d[0]), float(d[1])
            dist = round(((o_lat - d_lat)**2 + (o_lng - d_lng)**2)**0.5 * 111, 2)
            dur = round(dist * 2.5 + 3, 1)
            row.append({
                "distance": dist * 1000,
                "duration": dur * 60
            })
        results.append(row)
        
    return jsonify({"results": {"distances": [[r["distance"] for r in row] for row in results], "durations": [[r["duration"] for r in row] for row in results]}})

@app.route("/api/mappls/snap_to_road")
def api_mappls_snap_to_road():
    pts = request.args.get("pts")
    if not pts:
        return jsonify({"error": "Missing points"}), 400

    token, is_mock = get_mappls_token()
    if not is_mock and token:
        try:
            url = f"https://apis.mappls.com/advancedmaps/v1/snap_to_road?pts={pts}"
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if res.status_code == 200:
                return jsonify(res.json())
        except Exception as e:
            print(f"Mappls snap_to_road error: {e}")

    snapped = []
    for pt in pts.split("|"):
        coords = pt.split(",")
        lat, lng = float(coords[0]), float(coords[1])
        snapped.append({
            "latitude": round(lat, 5),
            "longitude": round(lng, 5)
        })
        
    return jsonify({"snappedPoints": snapped})

@app.route("/api/mappls/road_details")
def api_mappls_road_details():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    if not lat or not lng:
        return jsonify({"error": "Missing lat/lng"}), 400

    lat_f = float(lat)
    road_name = "Outer Ring Road (ORR)"
    speed_limit = 60
    lanes = 4
    road_type = "Primary Arterial"
    
    if lat_f < 12.93:
        road_name = "Hosur Main Road"
        speed_limit = 50
        lanes = 3
        road_type = "Secondary Arterial"
    elif lat_f < 12.95:
        road_name = "Sarjapura Road"
        speed_limit = 40
        lanes = 2
        road_type = "Urban Collector"
        
    return jsonify({
        "road_name": road_name,
        "speed_limit_kmh": speed_limit,
        "lanes": lanes,
        "road_type": road_type
    })

@app.route("/api/mappls/predictive_flow")
def api_mappls_predictive_flow():
    zone_id = request.args.get("zone_id", "Z_68_85")
    hours = list(range(24))
    speeds = []
    for h in hours:
        base_speed = 45
        if h in [9, 10, 17, 18, 19]:
            speed = base_speed - 25 - (h % 3) * 2
        elif h in [8, 11, 16, 20]:
            speed = base_speed - 15
        else:
            speed = base_speed - (h % 5)
        speeds.append(max(8, speed))
        
    return jsonify({
        "zone_id": zone_id,
        "hours": hours,
        "historical_avg_speeds_kmh": speeds
    })


@app.route("/api/mappls/keys")
def api_mappls_keys():
    config = load_config()
    return jsonify({
        "client_id": config.get("MAPPLS_CLIENT_ID", ""),
        "client_secret": config.get("MAPPLS_CLIENT_SECRET", "")
    })


@app.route("/api/mappls/save_keys", methods=["POST"])
def api_mappls_save_keys():
    try:
        data = request.json
        client_id = data.get("client_id", "").strip()
        client_secret = data.get("client_secret", "").strip()
        if not client_id or not client_secret:
            return jsonify({"success": False, "error": "Missing client credentials"}), 400
        
        config = load_config()
        config["MAPPLS_CLIENT_ID"] = client_id
        config["MAPPLS_CLIENT_SECRET"] = client_secret
        save_config(config)
        
        # Clear cache
        mappls_cache["client_id"] = client_id
        mappls_cache["client_secret"] = client_secret
        mappls_cache["token"] = None
        mappls_cache["expiry"] = 0
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/config")
def api_get_config():
    config = load_config()
    return jsonify(config)


@app.route("/api/config/save", methods=["POST"])
def api_save_config():
    try:
        data = request.json
        config = load_config()
        config.update(data)
        if save_config(config):
            # Reset Mappls credentials cache
            mappls_cache["client_id"] = config.get("MAPPLS_CLIENT_ID", "")
            mappls_cache["client_secret"] = config.get("MAPPLS_CLIENT_SECRET", "")
            mappls_cache["token"] = None
            mappls_cache["expiry"] = 0
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to write config"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dispatch/send", methods=["POST"])
def api_dispatch_send():
    try:
        data = request.json
        zone_id = data.get("zone_id")
        severity = data.get("severity")
        impact_score = float(data.get("impact_score", 0))
        center_lat = float(data.get("center_lat", 0))
        center_lng = float(data.get("center_lng", 0))
        action = data.get("action")
        risk_score = data.get("risk_score")
        violation_count = int(data.get("violation_count", 0))
        if risk_score is not None:
            risk_score = float(risk_score)

        # ── Store in active dispatches ─────────────────────────────────
        _active_dispatches[zone_id] = {
            "zone_id": zone_id,
            "severity": severity,
            "impact_score": impact_score,
            "center_lat": center_lat,
            "center_lng": center_lng,
            "action": action,
            "risk_score": risk_score,
            "violation_count": violation_count,
            "dispatched_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "resolved": False,
            "resolved_at": None
        }

        config = load_config()
        response_status = {}

        # 1. Telegram Alert Integration
        tg_token = config.get("TELEGRAM_BOT_TOKEN")
        tg_chat = config.get("TELEGRAM_CHAT_ID")
        if tg_token and tg_chat:
            severity_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
            emoji = severity_emoji.get(severity, "⚪")
            google_maps_link = f"https://www.google.com/maps?q={center_lat},{center_lng}"
            
            message_text = (
                f"🚨 *GRIDLOCK AI — ENFORCEMENT DISPATCH*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"\n"
                f"{emoji} *Severity:* {severity}\n"
                f"📍 *Zone:* {zone_id}\n"
                f"💥 *Impact Score:* {impact_score:.4f}\n"
            )
            if risk_score is not None:
                message_text += f"📈 *Risk Score:* {risk_score:.4f}\n"
            message_text += (
                f"\n"
                f"⚡ *Action:* {action}\n"
                f"🗺️ *Location:* {center_lat:.6f}, {center_lng:.6f}\n"
                f"📎 *Map:* [Open Google Maps]({google_maps_link})\n"
                f"\n"
                f"🕒 *Dispatched:* {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚙️ Powered by GridLock AI Engine"
            )
            
            try:
                tg_res = requests.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={
                        "chat_id": tg_chat,
                        "text": message_text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    },
                    timeout=5
                )
                response_status["telegram"] = {
                    "success": tg_res.status_code == 200,
                    "status_code": tg_res.status_code,
                    "response": tg_res.text
                }
            except Exception as e:
                response_status["telegram"] = {"success": False, "error": str(e)}
        else:
            response_status["telegram"] = {"success": False, "reason": "Not configured"}

        # 2. Twilio SMS & WhatsApp alerts (using the local twilio_dispatch file)
        twilio_sid = config.get("TWILIO_ACCOUNT_SID")
        twilio_token = config.get("TWILIO_AUTH_TOKEN")
        if twilio_sid and twilio_token:
            try:
                from api.twilio_dispatch import send_sms, send_whatsapp
                
                # Check for SMS
                sms_success, sms_msg = send_sms(
                    zone_id=zone_id,
                    severity=severity,
                    impact_score=impact_score,
                    center_lat=center_lat,
                    center_lng=center_lng,
                    recommended_action=action,
                    risk_score=risk_score,
                    secrets=config
                )
                response_status["sms"] = {"success": sms_success, "message": sms_msg}

                # Check for WhatsApp
                wa_success, wa_msg = send_whatsapp(
                    zone_id=zone_id,
                    severity=severity,
                    impact_score=impact_score,
                    center_lat=center_lat,
                    center_lng=center_lng,
                    recommended_action=action,
                    risk_score=risk_score,
                    secrets=config
                )
                response_status["whatsapp"] = {"success": wa_success, "message": wa_msg}
            except Exception as e:
                response_status["twilio_error"] = str(e)
        else:
            # Twilio Demo Mode Fallback (like twilio_dispatch's fallback response)
            from api.twilio_dispatch import build_alert_message
            msg_body = build_alert_message(zone_id, severity, impact_score, center_lat, center_lng, action, risk_score)
            response_status["sms"] = {"success": True, "message": f"📨 (DEMO MODE) SMS: {msg_body}"}
            response_status["whatsapp"] = {"success": True, "message": f"📨 (DEMO MODE) WhatsApp: {msg_body}"}

        return jsonify({"success": True, "status": response_status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── API: Active Responder Dispatch List ────────────────────────────────────
@app.route("/api/responder/active")
def api_responder_active():
    dispatches = list(_active_dispatches.values())
    dispatches.sort(key=lambda x: x.get('impact_score', 0), reverse=True)
    return jsonify(dispatches)


@app.route("/api/responder/resolve", methods=["POST"])
def api_responder_resolve():
    try:
        data = request.json
        zone_id = data.get("zone_id")
        if zone_id and zone_id in _active_dispatches:
            _active_dispatches[zone_id]["resolved"] = True
            _active_dispatches[zone_id]["resolved_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dispatch/clear", methods=["POST"])
def api_dispatch_clear():
    try:
        _active_dispatches.clear()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── API: Traffic Mitigation Impact Statistics ──────────────────────────────
@app.route("/api/mitigation/stats")
def api_mitigation_stats():
    resolved_dispatches = sum(1 for d in _active_dispatches.values() if d.get("resolved"))
    total_dispatches = len(_active_dispatches)
    active_dispatches = total_dispatches - resolved_dispatches

    # Impact model: avg 350 vehicles per congestion zone, 22 min avg delay
    avg_vehicles_per_zone = 350
    avg_idle_time_mins = 22

    vehicles_helped = resolved_dispatches * avg_vehicles_per_zone
    hours_saved = round((vehicles_helped * avg_idle_time_mins) / 60, 1)
    fuel_saved_l = round(hours_saved * 2.8, 1)      # 2.8 L/hr idle burn rate
    co2_saved_kg = round(fuel_saved_l * 2.31, 1)    # petrol: 2.31 kg CO2/L
    fines_issued = sum(d.get("violation_count", 0) for d in _active_dispatches.values())
    efficiency_score = round(
        min(100, (resolved_dispatches / max(1, total_dispatches)) * 100), 1
    )

    return jsonify({
        "zones_resolved": resolved_dispatches,
        "active_dispatches": active_dispatches,
        "total_dispatches": total_dispatches,
        "vehicles_helped": vehicles_helped,
        "hours_saved": hours_saved,
        "fuel_saved_litres": fuel_saved_l,
        "co2_saved_kg": co2_saved_kg,
        "fines_issued": fines_issued,
        "efficiency_score": efficiency_score
    })


# ── Mobile Responder Portal ────────────────────────────────────────────────
@app.route("/responder")
def responder_page():
    return send_from_directory("static", "responder.html")


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    print("[GridLock AI] Command Center - Starting server...")
    print("   Dashboard: http://localhost:5000")
    app.run(debug=True, port=5000)
