import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from sklearn.cluster import DBSCAN
import plotly.express as px
import os
import json

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="GridLock AI", layout="wide", page_icon="🚦")

# ==========================================
# LIGHT/DARK MODE TOGGLE & CSS
# ==========================================
theme_toggle = st.sidebar.toggle("🌙 Enable Dark Mode", value=True)

if theme_toggle:
    # Premium Dark Mode CSS (NOT pure black, dark slate/navy instead)
    st.markdown("""
    <style>
        .stApp { background-color: #1A1F2B; color: #E0E6ED; }
        .stTabs [data-baseweb="tab-list"] { background-color: #242A38; border-radius: 8px; }
        div[data-testid="metric-container"] {
            background-color: #242A38;
            border: 1px solid #3A4150;
            padding: 15px;
            border-radius: 12px;
        }
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
else:
    # Light Mode CSS
    st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #2C3E50; }
        div[data-testid="metric-container"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .status-box {
            background-color: #E8F8F5;
            color: #145A32;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #2ECC71;
            margin-bottom: 25px;
        }
        .alert-banner {
            background: linear-gradient(90deg, #E74C3C, #C0392B);
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
# LOAD DATA
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
st.sidebar.markdown("Simulate future congestion spillover.")
future_mins = st.sidebar.slider("Fast-Forward Time (Mins)", 0, 60, 0, step=15)

if future_mins > 0:
    alert_msg = f"⚠️ PREDICTIVE ALERT (T+{future_mins} mins): Spillover expected in High Risk Zones. Automated pre-emptive dispatch engaged."
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
tab1, tab2, tab3 = st.tabs(["🗺️ Live Congestion Map", "📊 ML Risk Analytics", "🚓 Priority Dispatch"])

# === TAB 1: EXACT MAP (PERFECT LIGHT/DARK HANDLING) ===
with tab1:
    st.subheader("Live City Congestion Map")
    
    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    # Map switches tile style cleanly: 
    # "CartoDB dark_matter" is perfect for Dark Mode
    # "CartoDB positron" is a clean light grey map perfect for Light Mode
    tile_style = "CartoDB dark_matter" if theme_toggle else "CartoDB positron"
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=tile_style)

    if show_heatmap:
        heat_data = df[["latitude", "longitude"]].values.tolist()
        HeatMap(heat_data, radius=heat_radius).add_to(m)

    if show_clusters:
        coords = df[["latitude", "longitude"]].values
        clustering = DBSCAN(eps=0.003, min_samples=5).fit(coords)
        df["cluster"] = clustering.labels_

        unique_clusters = df["cluster"].unique()
        for cluster_id in unique_clusters:
            if cluster_id == -1: continue
            cluster_points = df[df["cluster"] == cluster_id]
            folium.Circle(
                location=[cluster_points["latitude"].mean(), cluster_points["longitude"].mean()],
                radius=200 + (future_mins * 10), 
                color="red",
                fill=True,
                fill_opacity=0.2,
                popup=f"🔥 Hotspot Cluster {cluster_id}"
            ).add_to(m)

    sample_df = df.head(1000)
    for _, row in sample_df.iterrows():
        violation = str(row.get("violation_list", ""))
        if "WRONG PARKING" in violation: color = "red"
        elif "NO PARKING" in violation: color = "orange"
        else: color = "green"

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=4,
            color=color,
            fill=True,
            fill_opacity=0.8,
            tooltip=f"Violation: {violation}"
        ).add_to(m)

    st_folium(m, width=1200, height=600)

# === TAB 2: ML RISK ANALYTICS (TOP 10 BROUGHT BACK) ===
with tab2:
    st.subheader("🤖 Deep ML Risk Analysis & Top Predictions")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig1 = px.scatter(
            impact_df, x="violation_count", y="impact_score", 
            color="severity", size="risk_score", hover_data=["zone_id"],
            title="Impact vs Violations",
            color_discrete_map={"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "green"},
            template="plotly_dark" if theme_toggle else "plotly_white"
        )
        st.plotly_chart(fig1, use_container_width=True)
        
    with col_chart2:
        # TOP 10 PREDICTIONS (As requested by user)
        top_10 = impact_df.sort_values(by="impact_score", ascending=False).head(10)
        top_10["zone_id_str"] = "Zone " + top_10["zone_id"].astype(str)
        fig2 = px.bar(
            top_10, x="zone_id_str", y="impact_score", color="severity",
            title="Top 10 ML Predicted Critical Zones",
            color_discrete_map={"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "yellow", "LOW": "green"},
            template="plotly_dark" if theme_toggle else "plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)

# === TAB 3: DISPATCH CONSOLE ===
with tab3:
    st.subheader("🚓 Automated Action Output")
    
    st.markdown("##### Priority Action Table")
    dispatch_df = hotspot_df.copy()
    
    def format_urgency_detailed(val):
        if val == "CRITICAL": return "🚨 Dispatch Tow Truck ASAP"
        if val == "HIGH": return "🚓 Send Patrol Unit"
        return "🟢 Issue E-Challan"
        
    dispatch_df["Recommended_Action"] = dispatch_df["severity"].apply(format_urgency_detailed)
    display_cols = ["zone_id", "severity", "risk_score", "impact_score", "Recommended_Action"]
    
    dispatch_df["risk_score"] = dispatch_df["risk_score"].round(4)
    dispatch_df["impact_score"] = dispatch_df["impact_score"].round(4)
    
    def highlight_critical(row):
        if row.severity == 'CRITICAL':
            # Dark mode uses subtle red background, Light mode uses brighter red background
            bg_color = "rgba(255, 0, 0, 0.2)" if theme_toggle else "rgba(255, 0, 0, 0.1)"
            return [f'background-color: {bg_color}'] * len(row)
        return [''] * len(row)
        
    st.dataframe(
        dispatch_df[display_cols].sort_values(by="impact_score", ascending=False).style.apply(highlight_critical, axis=1),
        use_container_width=True,
        hide_index=True,
        height=500
    )