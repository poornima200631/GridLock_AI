import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from sklearn.cluster import DBSCAN
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(BASE_DIR, "outputs", "cleaned_data_sample.csv")

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(page_title="GridLock AI", layout="wide")

st.title("🚦 GridLock AI — Urban Congestion Command Center")

# -------------------------
# LOAD DATA
# -------------------------
df = pd.read_csv(file_path)
df = df.dropna(subset=["latitude", "longitude"])

# -------------------------
# SIDEBAR CONTROLS (VERY IMPORTANT FOR HACKATHON WOW FACTOR)
# -------------------------
st.sidebar.header("⚙️ Simulation Controls")

heat_radius = st.sidebar.slider("Heatmap Intensity", 5, 25, 12)
cluster_eps = st.sidebar.slider("Cluster Sensitivity (DBSCAN)", 0.001, 0.01, 0.003)
show_heatmap = st.sidebar.checkbox("Show Heatmap", True)
show_clusters = st.sidebar.checkbox("Show Hotspot Clusters", True)

# -------------------------
# BASE MAP
# -------------------------
center_lat = df["latitude"].mean()
center_lon = df["longitude"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

# -------------------------
# HEATMAP LAYER (CONGESTION INTENSITY)
# -------------------------
if show_heatmap:
    heat_data = df[["latitude", "longitude"]].values.tolist()
    HeatMap(heat_data, radius=heat_radius).add_to(m)

# -------------------------
# CLUSTERING (HOTSPOTS = HUGE WINNING FEATURE)
# -------------------------
if show_clusters:
    coords = df[["latitude", "longitude"]].values
    clustering = DBSCAN(eps=cluster_eps, min_samples=5).fit(coords)

    df["cluster"] = clustering.labels_

    unique_clusters = df["cluster"].unique()

    for cluster_id in unique_clusters:
        if cluster_id == -1:
            continue  # noise

        cluster_points = df[df["cluster"] == cluster_id]

        folium.Circle(
            location=[cluster_points["latitude"].mean(),
                      cluster_points["longitude"].mean()],
            radius=200,
            color="red",
            fill=True,
            fill_opacity=0.2,
            popup=f"🔥 Hotspot Cluster {cluster_id}"
        ).add_to(m)

# -------------------------
# VIOLATION MARKERS (ENFORCEMENT LAYER)
# -------------------------
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
        🚗 Vehicle: {row.get('vehicle_number','N/A')}<br>
        ⚠️ Violation: {violation}<br>
        🚨 Priority: {priority}
        """
    ).add_to(m)

# -------------------------
# RENDER MAP
# -------------------------
st.subheader("🗺️ Live City Congestion Map")
st_data = st_folium(m, width=1100, height=650)

# -------------------------
# ANALYTICS PANEL (VERY IMPORTANT FOR TOP 10 IMPACT)
# -------------------------
st.subheader("📊 System Intelligence Summary")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Violations", len(df))

with col2:
    high_risk = df[df["violation_list"].astype(str).str.contains("WRONG PARKING")].shape[0]
    st.metric("High Risk Zones", high_risk)

with col3:
    clusters = len([c for c in df.get("cluster", []) if c != -1]) if show_clusters else 0
    st.metric("Detected Hotspots", clusters)