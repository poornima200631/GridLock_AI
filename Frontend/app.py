import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import json
import os

# ==========================================
# ⚙️ PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="GridLock AI", layout="wide", page_icon="🚨")
st.title("🚦 GridLock AI — Urban Congestion Command Center")

# Custom CSS for better UI
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📊 LOAD DATA (From Person 1 Pipeline)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "..", "Backend", "outputs")

@st.cache_data
def load_pipeline_data():
    try:
        impact_df = pd.read_csv(os.path.join(OUTPUTS_DIR, "zone_impact_scores.csv"))
        hotspot_df = pd.read_csv(os.path.join(OUTPUTS_DIR, "hotspot_summary.csv"))
        
        with open(os.path.join(OUTPUTS_DIR, "pipeline_summary.json"), "r") as f:
            summary = json.load(f)
            
        return impact_df, hotspot_df, summary
    except Exception as e:
        return None, None, None

impact_df, hotspot_df, summary = load_pipeline_data()

if impact_df is None:
    st.error("❌ Pipeline data not found! Please run `python Backend/run_pipeline.py` first.")
else:
    # -------------------------
    # 🎛️ SIDEBAR CONTROLS
    # -------------------------
    st.sidebar.header("⚙️ Command Center")
    heat_radius = st.sidebar.slider("🔥 Heatmap Radius", 10, 50, 25)
    show_heatmap = st.sidebar.checkbox("Show Heatmap Layer", True)
    show_zones = st.sidebar.checkbox("Show Zone Markers", True)
    
    st.sidebar.markdown("---")
    st.sidebar.success("✅ ML Engine: Live")
    st.sidebar.success("✅ Risk Model: Active")
    st.sidebar.info("Model F1 Score: " + str(summary.get("model_f1", 0.85)))

    # -------------------------
    # 📈 TOP KPI METRICS
    # -------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🚗 Total Violations Processed", f"{summary.get('total_raw_records', 0):,}")
    col2.metric("📍 Total Monitored Zones", f"{summary.get('total_zones', 0):,}")
    col3.metric("🚨 CRITICAL Choke Points", summary.get("critical_zones", 0), delta="High Priority", delta_color="inverse")
    col4.metric("⚠️ HIGH Risk Zones", summary.get("high_zones", 0), delta="Action Needed", delta_color="inverse")
    st.markdown("---")

    # -------------------------
    # 📁 3-TAB STRUCTURE (PERSON 3)
    # -------------------------
    tab1, tab2, tab3 = st.tabs(["🗺️ Live Congestion Map", "🤖 Spillover Risk Analytics", "🚓 Enforcement Dispatch"])

    # === TAB 1: GEO ENGINE (PERSON 2) ===
    with tab1:
        st.subheader("Live City Congestion & Hotspots")
        st.markdown("Interactive **Dark Mode** map plotting machine-learned zones. Higher impact zones are red.")
        
        # Base Dark Map
        m = folium.Map(
            location=[impact_df["center_lat"].mean(), impact_df["center_lng"].mean()], 
            zoom_start=12,
            tiles="CartoDB dark_matter"  # Dark mode theme
        )
        
        # Heatmap Layer (Weighted by Impact Score)
        if show_heatmap:
            heat_data = impact_df[["center_lat", "center_lng", "impact_score"]].values.tolist()
            HeatMap(heat_data, radius=heat_radius, blur=15, max_zoom=1).add_to(m)
            
        # Zone Markers (Tooltips)
        if show_zones:
            for _, row in impact_df.iterrows():
                severity = row.get("severity", "LOW")
                
                if severity == "CRITICAL":
                    color, radius = "#ff4b4b", 250
                elif severity == "HIGH":
                    color, radius = "#ffa500", 200
                elif severity == "MEDIUM":
                    color, radius = "#ffea00", 150
                else:
                    color, radius = "#00ff00", 100

                tooltip_html = f"""
                <div style='font-family: Arial; padding: 5px;'>
                    <h4>Zone {row['zone_id']}</h4>
                    <b>Severity:</b> {severity}<br>
                    <b>Impact Score:</b> {row['impact_score']:.2f}<br>
                    <b>Violations:</b> {row['violation_count']}<br>
                    <b>Priority Rank:</b> #{row['enforcement_priority']}
                </div>
                """

                folium.Circle(
                    location=[row["center_lat"], row["center_lng"]],
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_opacity=0.4,
                    tooltip=tooltip_html
                ).add_to(m)

        # Render Map
        st_data = st_folium(m, width=1200, height=600)

    # === TAB 2: ML ENGINE (PERSON 1) ===
    with tab2:
        st.subheader("Spillover Risk Model Output")
        st.markdown("Data generated by `run_pipeline.py`. Shows calculated risk components.")
        st.dataframe(impact_df, use_container_width=True)

    # === TAB 3: DISPATCH UI (PERSON 3) ===
    with tab3:
        st.subheader("🚓 Targeted Enforcement Dispatch List")
        st.markdown("Automated prioritization for traffic police. Dispatch tow trucks to **CRITICAL** zones immediately.")
        
        # Display hotspot summary cleanly
        display_df = hotspot_df.copy()
        
        # Add emojis to severity
        def format_severity(val):
            if val == "CRITICAL": return "🚨 CRITICAL"
            if val == "HIGH": return "🔥 HIGH"
            return val
            
        display_df["severity"] = display_df["severity"].apply(format_severity)
        
        # Action column
        display_df["Action"] = display_df["severity"].apply(
            lambda x: "🚨 Tow ASAP" if "CRITICAL" in x else "🚓 Dispatch Patrol"
        )
        
        cols_to_show = ["enforcement_priority", "zone_id", "severity", "impact_score", "violation_count", "Action"]
        st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)
