import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import plotly.express as px
import os
import sys
import json
from datetime import datetime

# Add Backend to path for twilio_dispatch import
BACKEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Backend"))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

# [COMMENTED OUT] Twilio dispatch — uncomment when secrets.toml is configured
# from api.twilio_dispatch import send_sms, send_whatsapp, build_alert_message, is_twilio_configured
from models.congestion_forecast import (
    generate_city_forecast, generate_zone_forecast,
    get_peak_hours, get_forecast_summary
)

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="GridLock AI", layout="wide", page_icon="🚦")

# ==========================================
# CUSTOM COMPONENT CSS
# ==========================================
# We no longer inject .stApp background colors here to avoid flashing.
# The dark mode is now handled natively via .streamlit/config.toml.
st.markdown("""
<style>
    .status-box {
        background-color: #1B3B2B;
        color: #A3E4D7;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #2ECC71;
        margin-bottom: 25px;
    }
    .alert-banner {
        background: linear-gradient(90deg, #C0392B, #922B21);
        color: white;
        padding: 15px;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        animation: pulse 2s infinite;
        margin-bottom: 20px;
    }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.8; } 100% { opacity: 1; } }
</style>
""", unsafe_allow_html=True)

st.title("🚦 GridLock AI — Urban Congestion Command Center")

# ==========================================
# LOAD DATA (Optimized)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "..", "Backend", "outputs")

@st.cache_data
def load_data():
    raw_df = pd.read_csv(os.path.join(OUTPUTS_DIR, "cleaned_data_sample.csv"))
    raw_df = raw_df.dropna(subset=["latitude", "longitude"])
    
    impact_df = pd.read_csv(os.path.join(OUTPUTS_DIR, "zone_impact_scores.csv"))
    hotspot_df = pd.read_csv(os.path.join(OUTPUTS_DIR, "hotspot_summary.csv"))
    return raw_df, impact_df, hotspot_df

df, impact_df, hotspot_df = load_data()

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Map Simulation Controls")
show_heatmap = st.sidebar.checkbox("🔥 Show Heatmap Layer", True)
show_clusters = st.sidebar.checkbox("⭕ Show Hotspot Clusters", True)
heat_radius = st.sidebar.slider("Heatmap Intensity", 5, 25, 12)

st.sidebar.markdown("---")
st.sidebar.header("⏱️ Predictive AI Engine")
future_mins = st.sidebar.slider("Fast-Forward Time (Mins)", 0, 60, 0, step=15)

# Initialize simulated_df based on the slider
impact_multiplier = 1.0 + (future_mins * 0.05)
simulated_df = impact_df.copy()
simulated_df["impact_score"] = simulated_df["impact_score"] * impact_multiplier

# Always show an AI Alert for the worst zone
top_zone = impact_df.sort_values(by="impact_score", ascending=False).iloc[0]

if future_mins > 0:
    alert_msg = f"⚠️ PREDICTIVE AI ALERT (T+{future_mins} mins): Spillover expanding from Zone {top_zone['zone_id']}. Pre-emptive dispatch engaged."
    st.markdown(f"<div class='alert-banner'>{alert_msg}</div>", unsafe_allow_html=True)
else:
    alert_msg = f"🚨 AI ALERT: Zone {top_zone['zone_id']} is a CRITICAL ZONE REQUIRING IMMEDIATE ACTION. Heavy congestion detected."
    st.markdown(f"<div class='alert-banner'>{alert_msg}</div>", unsafe_allow_html=True)

# ==========================================
# HEADER UI
# ==========================================
st.markdown("##### Priority zones identified by the GridLock AI engine.")

total_zones = len(impact_df)
high_zones = len(impact_df[impact_df['severity'] == 'CRITICAL']) + len(impact_df[impact_df['severity'] == 'HIGH'])
med_zones = len(impact_df[impact_df['severity'] == 'MEDIUM'])

m1, m2, m3 = st.columns(3)
with m1: st.markdown(f"🔴 **High Risk Zones**\n# {high_zones}")
with m2: st.markdown(f"🟠 **Medium Risk Zones**\n# {med_zones}")
with m3: st.markdown(f"🟢 **Total Zones**\n# {total_zones}")

st.markdown("""
<div class="status-box">
    <h3>🟢 All Systems Operational</h3>
    <p>✅ <b>Spillover Prediction Engine Online</b></p>
    <p>✅ <b>Impact Score Engine Online</b></p>
    <p>✅ <b>Hotspot Detection Active</b></p>
    <p>✅ <b>Enforcement Prioritization Active</b></p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3-TAB STRUCTURE
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Live Congestion Map", "📊 ML Risk Analytics", "🚓 Priority Dispatch", "🕒 24H Forecast"])

# Dynamically escalate severity based on simulated impact_score
def update_severity(score):
    if score > 0.8: return "CRITICAL"
    if score > 0.6: return "HIGH"
    if score > 0.4: return "MEDIUM"
    return "LOW"
    
if future_mins > 0:
    simulated_df["severity"] = simulated_df["impact_score"].apply(update_severity)

# === TAB 1: OPTIMIZED FOLIUM MAP ===
with tab1:
    st.subheader("Live City Congestion Map")
    
    center_lat = simulated_df["center_lat"].mean()
    center_lon = simulated_df["center_lng"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # 1. Heatmap (Optimized but Visible)
    if show_heatmap:
        # 5000 points is a good balance between fast load time and dense enough to show heat
        heat_sample = df.sample(min(5000, len(df))) if len(df) > 5000 else df
        heat_data = heat_sample[["latitude", "longitude"]].values.tolist()
        # Ensure radius is large enough to be visible
        HeatMap(heat_data, radius=heat_radius, blur=max(5, heat_radius-5), max_zoom=1).add_to(m)

    # 2. Clusters (Only show the TOP 15 Critical Hotspots so the map isn't completely covered in red)
    if show_clusters:
        # Sort by impact score and take the worst 15 bottlenecks
        top_critical = simulated_df[simulated_df['severity'].isin(["CRITICAL", "HIGH"])].sort_values(by="impact_score", ascending=False).head(15)
        for _, row in top_critical.iterrows():
            folium.Circle(
                location=[row["center_lat"], row["center_lng"]],
                radius=min(800, 300 + (row['impact_score'] * 400)), 
                color="red" if row['severity'] == "CRITICAL" else "orange",
                fill=True,
                fill_opacity=0.3,
                tooltip=f"<b style='color:red;'>Major Bottleneck: Zone {row['zone_id']}</b><br>Simulated Impact: {row['impact_score']:.2f}"
            ).add_to(m)

    # 3. Individual Violation Markers (Detailed E-Challan View)
    sample_dots = df.sample(min(150, len(df)))
    # Fetch risk and impact score from the zone data
    sample_dots = sample_dots.merge(simulated_df[['zone_id', 'risk_score', 'impact_score']], on='zone_id', how='left')
    
    for _, row in sample_dots.iterrows():
        violation = str(row.get("violation_list", ""))
        veh_num = str(row.get("vehicle_number", "UNKNOWN"))
        
        if "WRONG PARKING" in violation: 
            color = "red"
            action = "🚨 TOW TRUCK REQUIRED"
        elif "NO PARKING" in violation: 
            color = "orange"
            action = "🟡 ISSUE E-CHALLAN"
        else: 
            color = "green"
            action = "🟢 STANDARD FINE"

        r_score = row.get('risk_score', 0)
        i_score = row.get('impact_score', 0)
        if pd.isna(r_score): r_score = 0
        if pd.isna(i_score): i_score = 0

        tooltip_html = f"""
        <div style='font-family: sans-serif;'>
            <b>🚗 Vehicle:</b> {veh_num}<br>
            <b>⚠️ Violation:</b> {violation}<br>
            <b>📈 Zone Risk Score:</b> {r_score:.4f}<br>
            <b>💥 Zone Impact Score:</b> {i_score:.4f}<br>
            <hr style='margin: 5px 0;'>
            <b>⚡ Recommended:</b> {action}
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.9,
            tooltip=tooltip_html
        ).add_to(m)

    # Force re-render when controls change, and disable returned_objects for maximum speed
    map_key = f"map_{heat_radius}_{future_mins}_{show_heatmap}_{show_clusters}"
    st_folium(m, width=1200, height=600, key=map_key, returned_objects=[])

# === TAB 2: ML RISK ANALYTICS ===
with tab2:
    st.subheader("🤖 Deep ML Risk Analysis")
    
    # ---------------- ROW 1 ----------------
    row1_c1, row1_c2 = st.columns(2)
    
    with row1_c1:
        severity_counts = simulated_df['severity'].value_counts().reset_index()
        severity_counts.columns = ['severity', 'count']
        fig1 = px.pie(
            severity_counts, values='count', names='severity', hole=0.4,
            title="Severity Distribution",
            color='severity',
            color_discrete_map={"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "green"},
            template="plotly_dark"
        )
        st.plotly_chart(fig1, use_container_width=True)

    with row1_c2:
        # User requested 'Reason' Pie Chart
        # We extract violation reasons from the raw data
        def clean_violation(v):
            v_str = str(v).upper()
            if "WRONG PARKING" in v_str: return "Wrong Parking"
            if "NO PARKING" in v_str: return "No Parking Zone"
            if "FOOTPATH" in v_str: return "Footpath Parking"
            if "DOUBLE" in v_str: return "Double Parking"
            return "Other Violations"
            
        df_reasons = df.copy()
        df_reasons['Reason'] = df_reasons['violation_list'].apply(clean_violation)
        reason_counts = df_reasons['Reason'].value_counts().reset_index()
        reason_counts.columns = ['Reason', 'count']
        
        fig_reason = px.pie(
            reason_counts, values='count', names='Reason', hole=0.4,
            title="Primary Reasons for Congestion",
            color='Reason',
            color_discrete_sequence=px.colors.sequential.Plasma,
            template="plotly_dark"
        )
        st.plotly_chart(fig_reason, use_container_width=True)

    # ---------------- ROW 2 ----------------
    row2_c1, row2_c2 = st.columns(2)
    
    with row2_c1:
        top_10 = simulated_df.sort_values(by="impact_score", ascending=False).head(10)
        top_10["zone_id_str"] = "Zone " + top_10["zone_id"].astype(str)
        fig2 = px.bar(
            top_10, x="zone_id_str", y="impact_score", color="severity",
            title="Top 10 Critical Enforcement Zones",
            color_discrete_map={"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "green"},
            template="plotly_dark"
        )
        st.plotly_chart(fig2, use_container_width=True)

    with row2_c2:
        fig3 = px.scatter(
            simulated_df, x="violation_count", y="impact_score", 
            color="severity", size="risk_score", hover_data=["zone_id"],
            title="Impact vs Total Violations",
            color_discrete_map={"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "green"},
            template="plotly_dark"
        )
        st.plotly_chart(fig3, use_container_width=True)

# === TAB 3: DISPATCH CONSOLE ===
with tab3:
    st.subheader("🚓 Automated Enforcement Dispatch Console")
    
    def format_urgency(val):
        if val == "CRITICAL": return "🚨 Dispatch Tow Truck ASAP"
        if val == "HIGH": return "🚓 Send Patrol Unit"
        return "🟢 Issue E-Challan"

    dispatch_df = simulated_df.copy()
    dispatch_df["Recommended_Action"] = dispatch_df["severity"].apply(format_urgency)
    
    # ---- Custom CSS for dispatch panel ----
    st.markdown("""
    <style>
        .dispatch-card {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid #0f3460;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
        }
        .dispatch-card h4 {
            color: #e94560;
            margin-bottom: 10px;
        }
        .dispatch-success {
            background: linear-gradient(135deg, #0d3b0d 0%, #1a4d1a 100%);
            border: 1px solid #2ecc71;
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
            color: #a3e4d7;
        }
        .dispatch-demo {
            background: linear-gradient(135deg, #2c2c0d 0%, #3d3d1a 100%);
            border: 1px solid #f39c12;
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
            color: #fdebd0;
        }
        .dispatch-log {
            background: #0a0a1a;
            border: 1px solid #1a1a3e;
            border-radius: 8px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #00ff88;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .notify-header {
            background: linear-gradient(90deg, #e94560, #c0392b);
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 20px;
            letter-spacing: 1px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ---- Overview Metrics ----
    st.markdown("##### 🚨 Critical Zones Requiring Immediate Action")
    action_summary = dispatch_df['Recommended_Action'].value_counts().reset_index()
    action_summary.columns = ['Action', 'Count']
    
    fig_dispatch = px.bar(
        action_summary, x="Count", y="Action", orientation='h',
        title="Units Needed For Immediate Dispatch",
        color="Action",
        color_discrete_map={"🚨 Dispatch Tow Truck ASAP": "red", "🚓 Send Patrol Unit": "orange", "🟢 Issue E-Challan": "green"},
        template="plotly_dark"
    )
    st.plotly_chart(fig_dispatch, use_container_width=True)
    
    st.markdown("---")

    # ============================================================
    # 📲 AUTOMATED DISPATCH NOTIFICATION PANEL
    # [COMMENTED OUT] — Uncomment when .streamlit/secrets.toml is configured with Twilio creds
    # ============================================================
    st.markdown('<div class="notify-header">📲 AUTOMATED DISPATCH NOTIFICATION SYSTEM</div>', unsafe_allow_html=True)
    st.info("📲 **Twilio SMS/WhatsApp Dispatch** is available but currently disabled. "
            "To enable, configure `.streamlit/secrets.toml` with your Twilio credentials "
            "and uncomment the Twilio code in `app.py`.")

    
    st.markdown("---")

    # ============================================================
    # ORIGINAL DISPATCH TABLE (preserved)
    # ============================================================
    c_btn1, c_btn2 = st.columns([0.8, 0.2])
    with c_btn1:
        st.markdown("##### Priority Action Table (Enforcement Dispatch)")
    with c_btn2:
        # Download Report Feature added back
        csv = dispatch_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Dispatch Report",
            data=csv,
            file_name='gridlock_critical_dispatch_report.csv',
            mime='text/csv',
        )
    
    c1, c2 = st.columns(2)
    with c1:
        severity_filter = st.multiselect("Filter by Severity:", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], default=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    with c2:
        sort_by = st.selectbox("Sort Priority By:", ["Highest Impact", "Most Violations"])
        
    if severity_filter:
        dispatch_df = dispatch_df[dispatch_df["severity"].isin(severity_filter)]
        
    if sort_by == "Highest Impact":
        dispatch_df = dispatch_df.sort_values(by="impact_score", ascending=False)
    else:
        dispatch_df = dispatch_df.sort_values(by="violation_count", ascending=False)
    
    display_cols = ["zone_id", "severity", "risk_score", "impact_score", "Recommended_Action"]
    
    dispatch_df["risk_score"] = dispatch_df["risk_score"].round(4)
    dispatch_df["impact_score"] = dispatch_df["impact_score"].round(4)
    
    def highlight_critical(row):
        if row.severity == 'CRITICAL':
            return ['background-color: rgba(255, 0, 0, 0.2)'] * len(row)
        return [''] * len(row)
        
    st.dataframe(
        dispatch_df[display_cols].style.apply(highlight_critical, axis=1),
        use_container_width=True,
        hide_index=True,
        height=500
    )

# === TAB 4: 24-HOUR CONGESTION FORECAST ===
with tab4:
    st.subheader("🕒 24-Hour Predictive Congestion Forecast")

    # ---- Custom CSS for forecast tab ----
    st.markdown("""
    <style>
        .forecast-metric-card {
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            border-radius: 14px;
            padding: 22px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        .forecast-metric-card h2 {
            margin: 0;
            font-size: 38px;
        }
        .forecast-metric-card p {
            margin: 5px 0 0 0;
            color: #a0a0c0;
            font-size: 14px;
        }
        .peak-alert {
            background: linear-gradient(90deg, #ff416c, #ff4b2b);
            color: white;
            padding: 14px 20px;
            border-radius: 10px;
            font-weight: bold;
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .forecast-info-box {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid #0f3460;
            border-radius: 12px;
            padding: 18px;
            margin-top: 15px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("##### 🤖 AI-powered congestion predictions based on historical violation patterns & urban traffic modeling.")

    # ---- Generate city-wide forecast ----
    @st.cache_data
    def get_city_forecast(_df_hash, _impact_hash):
        return generate_city_forecast(df, impact_df, hours_ahead=24)

    city_forecast = get_city_forecast(
        hash(tuple(df.index.tolist()[:100])),
        hash(tuple(impact_df["impact_score"].tolist()[:50]))
    )
    summary = get_forecast_summary(city_forecast)
    peaks = get_peak_hours(city_forecast, top_n=3)

    # ---- Summary Metrics Row ----
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        color = "#ff4b2b" if summary["max_congestion"] > 75 else "#f39c12" if summary["max_congestion"] > 50 else "#2ecc71"
        st.markdown(f"""
        <div class="forecast-metric-card">
            <h2 style="color: {color};">{summary['max_congestion']}</h2>
            <p>🔺 Peak Congestion Index</p>
        </div>
        """, unsafe_allow_html=True)
    with fc2:
        st.markdown(f"""
        <div class="forecast-metric-card">
            <h2 style="color: #3498db;">{summary['avg_congestion']}</h2>
            <p>📊 Avg Congestion (24h)</p>
        </div>
        """, unsafe_allow_html=True)
    with fc3:
        st.markdown(f"""
        <div class="forecast-metric-card">
            <h2 style="color: #e74c3c;">{summary['critical_hours']}</h2>
            <p>🔴 Critical Hours Ahead</p>
        </div>
        """, unsafe_allow_html=True)
    with fc4:
        st.markdown(f"""
        <div class="forecast-metric-card">
            <h2 style="color: #e67e22;">{summary['high_hours']}</h2>
            <p>🟠 High-Risk Hours Ahead</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Peak Hour Alerts ----
    st.markdown("##### ⚠️ Predicted Peak Congestion Windows")
    for p in peaks:
        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(p["risk_level"], "⚪")
        st.markdown(f"""
        <div class="peak-alert">
            <span>{risk_emoji} {p['hour_label']} — Congestion Index: <strong>{p['congestion_index']:.1f}</strong></span>
            <span style="opacity:0.8;">Risk: {p['risk_level']}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Main Forecast Chart: Area chart with confidence bands ----
    st.markdown("##### 📈 City-Wide Congestion Forecast (Next 24 Hours)")

    import plotly.graph_objects as go

    fig_forecast = go.Figure()

    # Confidence band (filled area)
    fig_forecast.add_trace(go.Scatter(
        x=city_forecast["hour_label"],
        y=city_forecast["confidence_upper"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig_forecast.add_trace(go.Scatter(
        x=city_forecast["hour_label"],
        y=city_forecast["confidence_lower"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(99, 110, 250, 0.15)",
        name="95% Confidence Band",
        hoverinfo="skip",
    ))

    # Main prediction line
    # Color each point by risk level
    risk_colors = city_forecast["risk_level"].map({
        "CRITICAL": "#e74c3c",
        "HIGH": "#e67e22",
        "MEDIUM": "#f1c40f",
        "LOW": "#2ecc71",
    }).tolist()

    fig_forecast.add_trace(go.Scatter(
        x=city_forecast["hour_label"],
        y=city_forecast["congestion_index"],
        mode="lines+markers",
        name="Predicted Congestion",
        line=dict(color="#636EFA", width=3),
        marker=dict(size=10, color=risk_colors, line=dict(width=2, color="white")),
        hovertemplate="<b>%{x}</b><br>Congestion: %{y:.1f}<br><extra></extra>",
    ))

    # Threshold lines
    fig_forecast.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="CRITICAL", annotation_position="top right")
    fig_forecast.add_hline(y=60, line_dash="dash", line_color="orange", annotation_text="HIGH", annotation_position="top right")
    fig_forecast.add_hline(y=35, line_dash="dot", line_color="yellow", annotation_text="MEDIUM", annotation_position="top right")

    fig_forecast.update_layout(
        template="plotly_dark",
        height=450,
        yaxis_title="Congestion Index",
        xaxis_title="Time",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=40, b=40),
        yaxis=dict(range=[0, 105]),
    )

    st.plotly_chart(fig_forecast, use_container_width=True)

    # ---- Predicted Violations Bar Chart ----
    st.markdown("##### 🚗 Predicted Violations Per Hour")

    fig_violations = px.bar(
        city_forecast,
        x="hour_label",
        y="violations_predicted",
        color="risk_level",
        color_discrete_map={"CRITICAL": "#e74c3c", "HIGH": "#e67e22", "MEDIUM": "#f1c40f", "LOW": "#2ecc71"},
        template="plotly_dark",
        title="Estimated Parking Violations by Hour",
    )
    fig_violations.update_layout(
        height=350,
        xaxis_title="Time",
        yaxis_title="Predicted Violations",
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig_violations, use_container_width=True)

    # ---- Zone-Level Drill Down ----
    st.markdown("---")
    st.markdown("##### 🔍 Zone-Level Forecast Drill-Down")

    top_zones_for_select = simulated_df.sort_values(by="impact_score", ascending=False).head(20)
    zone_select = st.selectbox(
        "Select a zone to view its 24h forecast:",
        options=top_zones_for_select["zone_id"].tolist(),
        format_func=lambda z: f"Zone {z} — {simulated_df[simulated_df['zone_id'] == z]['severity'].values[0]} "
                               f"(Impact: {simulated_df[simulated_df['zone_id'] == z]['impact_score'].values[0]:.4f})",
        key="forecast_zone_select"
    )

    zone_forecast = generate_zone_forecast(zone_select, simulated_df, df, hours_ahead=24)

    if zone_forecast is not None:
        zone_summary = get_forecast_summary(zone_forecast)

        zc1, zc2, zc3 = st.columns(3)
        with zc1:
            st.metric("🔺 Peak Congestion", f"{zone_summary['max_congestion']}")
        with zc2:
            st.metric("📊 Avg Congestion", f"{zone_summary['avg_congestion']}")
        with zc3:
            st.metric("🔴 Critical Hours", f"{zone_summary['critical_hours']}")

        fig_zone = go.Figure()

        fig_zone.add_trace(go.Scatter(
            x=zone_forecast["hour_label"],
            y=zone_forecast["confidence_upper"],
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig_zone.add_trace(go.Scatter(
            x=zone_forecast["hour_label"],
            y=zone_forecast["confidence_lower"],
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(255, 99, 71, 0.15)",
            name="Confidence Band",
            hoverinfo="skip",
        ))

        zone_risk_colors = zone_forecast["risk_level"].map({
            "CRITICAL": "#e74c3c", "HIGH": "#e67e22",
            "MEDIUM": "#f1c40f", "LOW": "#2ecc71",
        }).tolist()

        fig_zone.add_trace(go.Scatter(
            x=zone_forecast["hour_label"],
            y=zone_forecast["congestion_index"],
            mode="lines+markers",
            name=f"Zone {zone_select} Forecast",
            line=dict(color="#FF6347", width=3),
            marker=dict(size=9, color=zone_risk_colors, line=dict(width=2, color="white")),
            hovertemplate="<b>%{x}</b><br>Congestion: %{y:.1f}<extra></extra>",
        ))

        fig_zone.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="CRITICAL")
        fig_zone.add_hline(y=60, line_dash="dash", line_color="orange", annotation_text="HIGH")

        fig_zone.update_layout(
            template="plotly_dark",
            height=400,
            title=f"Zone {zone_select} — 24h Congestion Forecast",
            yaxis_title="Congestion Index",
            xaxis_title="Time",
            yaxis=dict(range=[0, 105]),
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_zone, use_container_width=True)
    else:
        st.warning("No data available for this zone.")

    # ---- Model Info Box ----
    st.markdown("""
    <div class="forecast-info-box">
        <h4>🧠 About this Forecast Model</h4>
        <p style="color: #a0a0c0; font-size: 14px; line-height: 1.7;">
            This forecast uses a <b>Composite Hybrid Model</b> that blends:<br>
            📊 <b>60%</b> — Empirical hourly violation distribution (from real e-challan data)<br>
            🏙️ <b>30%</b> — Calibrated urban traffic curve (Bengaluru peak-hour patterns)<br>
            🎲 <b>10%</b> — Stochastic noise for realistic variance<br><br>
            Confidence bands widen progressively to reflect increasing uncertainty over time.
            Zone-level forecasts are adjusted by each zone's severity multiplier and historical impact score.
        </p>
    </div>
    """, unsafe_allow_html=True)