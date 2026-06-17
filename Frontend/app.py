import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from sklearn.cluster import DBSCAN
import os
import plotly.express as px

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="GridLock AI", layout="wide", page_icon="🚨")
st.title("🚦 GridLock AI — Urban Congestion Command Center")
st.markdown("""
### AI-Powered Urban Congestion Prevention System

Predicting illegal parking spillover,
prioritizing enforcement actions,
and preventing city-wide traffic congestion before it happens.

---
""")

# ==========================================
# LOAD DATA (From Person 1/2 outputs)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Updated path because app.py is now inside Frontend folder
file_path = os.path.join(BASE_DIR, "..", "Backend", "outputs", "cleaned_data_sample.csv")
zone_file = os.path.join(
    BASE_DIR,
    "..",
    "Backend",
    "outputs",
    "zone_full_data.csv"
)

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(file_path)
        df = df.dropna(subset=["latitude", "longitude"])
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    

def load_zone_data():
    try:
        return pd.read_csv(zone_file)
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()
zone_df = load_zone_data()


if df.empty:
    st.error("❌ Dataset not found! Make sure 'cleaned_data_sample.csv' is in Backend/outputs/")
else:
    # -------------------------
    # SIDEBAR CONTROLS
    # -------------------------
    st.sidebar.header("⚙️ Command Center Controls")
    heat_radius = st.sidebar.slider("Heatmap Intensity", 5, 25, 12)
    cluster_eps = st.sidebar.slider("Cluster Sensitivity (DBSCAN)", 0.001, 0.01, 0.003)
    show_heatmap = st.sidebar.checkbox("Show Heatmap", True)
    show_clusters = st.sidebar.checkbox("Show Hotspot Clusters", True)
    severity_filter = st.sidebar.multiselect(
    "Filter Risk Zones",
    ["HIGH", "MEDIUM", "LOW"],
    default=["HIGH", "MEDIUM", "LOW"]
)
    
    st.sidebar.markdown("---")
    st.sidebar.success("✅ ML Engine: Active")
    st.sidebar.success("✅ Geo Engine: Active")
    st.sidebar.markdown("---")

    st.sidebar.markdown("### 🧠 AI Modules")

    st.sidebar.info("Risk Prediction Engine")

    st.sidebar.info("Impact Score Engine")

    st.sidebar.info("Hotspot Detection")

    st.sidebar.info("Enforcement Prioritization")

    # -------------------------
    # TOP KPI METRICS
    # -------------------------
    col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "🚗 Total Violations",
    len(df)
)

col2.metric(
    "🔥 High Risk Zones",
    len(zone_df[zone_df["severity"] == "HIGH"])
)

col3.metric(
    "🚨 Avg Impact Score",
    round(
        zone_df["impact_score"].mean(),
        3
    )
)

col4.metric(
    "🛰️ System Status",
    "LIVE"
)
st.markdown("---")

def recommend_action(row):

    if row["severity"] == "HIGH":
        return "🚨 Dispatch Tow Truck + Traffic Patrol"

    elif row["severity"] == "MEDIUM":
        return "🟡 Send Enforcement Team"

    else:
        return "🟢 Issue E-Challan"

tab1, tab2, tab3 = st.tabs([
    "🗺️ Live Congestion Map",
    "🟡 Spillover Risk Data",
    "🚨 Enforcement Priority"
])

    # === TAB 1: PERSON 2'S MAP ===
# === TAB 1: PERSON 2'S MAP ===
with tab1:
    st.subheader("Live City Congestion & Hotspots")
    top5 = zone_df.sort_values(
    by="impact_score",
    ascending=False
).head(5)

    st.markdown("## 🚨 Critical Zones Requiring Immediate Action")

    st.dataframe(
    top5[
        [
            "zone_id",
            "severity",
            "impact_score"
        ]
    ],
    use_container_width=True,
    hide_index=True
)
    highest_zone = top5.iloc[0]

    st.error(
    f"""
    🚨 CRITICAL ALERT

    Zone {highest_zone['zone_id']} currently has the
    highest congestion impact score
    ({highest_zone['impact_score']:.3f})

    Recommended Action:
    Immediate enforcement deployment.
    """
)
    # Base Map
    m = folium.Map(
        location=[
            df["latitude"].mean(),
            df["longitude"].mean()
        ],
        zoom_start=12,
        tiles="CartoDB dark_matter"
    )

    # Heatmap Layer
    if show_heatmap:
        heat_data = df[["latitude", "longitude"]].values.tolist()
        HeatMap(heat_data, radius=heat_radius).add_to(m)

    # Clustering Layer
    if show_clusters:
        coords = df[["latitude", "longitude"]].values
        clustering = DBSCAN(eps=cluster_eps, min_samples=5).fit(coords)
        df["cluster"] = clustering.labels_

        for cluster_id in df["cluster"].unique():
            if cluster_id == -1:
                continue

            cluster_points = df[df["cluster"] == cluster_id]

            folium.Circle(
                location=[
                    cluster_points["latitude"].mean(),
                    cluster_points["longitude"].mean()
                ],
                radius=200,
                color="red",
                fill=True,
                fill_opacity=0.2,
                popup=f"🔥 Hotspot Cluster {cluster_id}"
            ).add_to(m)

    # AI Risk Zones
    filtered_zones = zone_df[
    zone_df["severity"].isin(severity_filter)
]
    for _, row in zone_df.iterrows():

        severity = str(row["severity"])

        if severity == "HIGH":
            color = "red"
        elif severity == "MEDIUM":
            color = "orange"
        else:
            color = "green"

        radius = max(
            5,
            min(row["impact_score"] * 80, 20)
        )

        popup_text = f"""
        🚨 Zone: {row['zone_id']}
        <br>Severity: {row['severity']}
        <br>Risk Score: {row['risk_score']:.5f}
        <br>Impact Score: {row['impact_score']:.3f}
        <br>Priority: {row['enforcement_priority']}
        """

        folium.CircleMarker(
            location=[
                row["center_lat"],
                row["center_lng"]
            ],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.8,
            popup=popup_text
        ).add_to(m)

    # Violation Markers
    for _, row in df.iterrows():

        violation = str(row.get("violation_list", ""))

        if "WRONG PARKING" in violation:
            color = "red"
            priority = "HIGH RISK"
        elif "NO PARKING" in violation:
            color = "orange"
            priority = "MEDIUM RISK"
        else:
            color = "blue"
            priority = "LOW RISK"

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=f"""
            🚗 Vehicle: {row.get('vehicle_number','N/A')}
            <br>⚠️ Violation: {violation}
            <br>🚨 Priority: {priority}
            """
        ).add_to(m)
        # Risk Legend
    st.markdown("""
### 🚨 Risk Levels

🔴 High Severity Zone

🟠 Medium Severity Zone

🟢 Low Severity Zone
""")

 

    st_folium(m, width=1200, height=600)
    # === TAB 2: SPILLOVER RISK DATA ===
with tab2:

    st.subheader("🟡 Spillover Risk Analysis")

    # ======================================
    # TOP 10 RISK ZONES CHART
    # ======================================

    st.markdown("## 🔥 Top 10 Highest Risk Zones")

    top10 = zone_df.sort_values(
        by="impact_score",
        ascending=False
    ).head(10)

    fig = px.bar(
        top10,
        x="zone_id",
        y="impact_score",
        color="severity",
        hover_data=[
            "risk_score",
            "enforcement_priority"
        ],
        title="Top 10 Congestion Risk Zones"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )
    highest_zone = top10.iloc[0]
    severity_count = zone_df["severity"].value_counts()

    fig2 = px.pie(
    values=severity_count.values,
    names=severity_count.index,
    title="City Risk Distribution"
)

    st.plotly_chart(
    fig2,
    use_container_width=True
)

  
    # ======================================
    # AI ALERT BOX
    # ======================================

    highest_zone = top10.iloc[0]

    st.warning(
        f"""
        🚨 AI ALERT

        Zone: {highest_zone['zone_id']}

        Severity: {highest_zone['severity']}

        Impact Score: {highest_zone['impact_score']:.3f}

        Recommended Action:
        Immediate enforcement deployment.
        """
    )

    # ======================================
    # TOP 10 TABLE
    # ======================================

    st.markdown("## 🚨 Top 10 Critical Enforcement Zones")

    display_zones = top10[
        [
            "zone_id",
            "severity",
            "risk_score",
            "impact_score",
            "enforcement_priority"
        ]
    ]

    st.dataframe(
        display_zones,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # ======================================
    # RAW DATA
    # ======================================

    with st.expander("📊 View Raw ML Dataset"):
        st.dataframe(
            df,
            use_container_width=True
        )


# === TAB 3: ENFORCEMENT PRIORITY ===
with tab3:

    st.subheader("🚨 AI Enforcement Command Center")
    critical_zone = zone_df.sort_values(
    by="impact_score",
    ascending=False
).iloc[0]

    st.error(
    f"""
    🚨 AI Enforcement Recommendation

    Deploy enforcement immediately to:

    Zone: {critical_zone['zone_id']}

    Severity: {critical_zone['severity']}

    Impact Score: {critical_zone['impact_score']:.3f}
    """
)

    st.markdown(
        "Priority zones identified by the GridLock AI engine."
    )

    # KPI CARDS
    c1, c2, c3 = st.columns(3)

    c1.metric(
        "🔴 High Risk Zones",
        len(zone_df[zone_df["severity"] == "HIGH"])
    )

    c2.metric(
        "🟠 Medium Risk Zones",
        len(zone_df[zone_df["severity"] == "MEDIUM"])
    )

    c3.metric(
        "🟢 Total Zones",
        len(zone_df)
    )

    st.markdown("---")
    st.success(
    """
    🟢 All Systems Operational

    ✅ Spillover Prediction Engine Online

    ✅ Impact Score Engine Online

    ✅ Hotspot Detection Active

    ✅ Enforcement Prioritization Active
    """
)

    # TOP PRIORITY ZONES
    priority_zones = zone_df.sort_values(
        by="enforcement_priority"
    ).head(20)

    priority_zones["Recommended_Action"] = (
        priority_zones.apply(
            recommend_action,
            axis=1
        )
    )

    display_cols = [
        "zone_id",
        "severity",
        "risk_score",
        "impact_score",
        "Recommended_Action"
    ]

    st.dataframe(
        priority_zones[display_cols],
        use_container_width=True,
        hide_index=True
    )
    csv = priority_zones.to_csv(index=False)

st.download_button(
    label="📥 Download Enforcement Report",
    data=csv,
    file_name="gridlock_ai_enforcement_report.csv",
    mime="text/csv"
)
st.markdown("---")

st.markdown("""
## 🏗️ GridLock AI Architecture

### Data Layer
Parking Violation Dataset

⬇

### Intelligence Layer
Risk Prediction Engine
+
Impact Score Engine

⬇

### Decision Layer
Hotspot Detection
+
Zone Ranking

⬇

### Action Layer
Enforcement Recommendations
+
Incident Reports
""")