# GridLock AI — Urban Congestion Command Center

> **AI-driven illegal parking detection, hotspot enforcement, and real-time dispatch optimization for Bengaluru Metro Region**

---

## Problem

Illegal parking is the silent driver of urban congestion. In Bengaluru, over **60% of peak-hour traffic slowdowns** are caused by vehicles parked in no-parking zones, blocking lanes, and obstructing intersections. Traditional enforcement is reactive and resource-blind — officers are dispatched without knowing *which zones have the highest impact*.

## Solution

GridLock AI is an end-to-end **AI Decision Support System** that:
1. Ingests parking violation datasets and real-time GPS feeds
2. Uses **XGBoost ML** to classify zone severity and predict spillover risk
3. Renders a live command center dashboard with hotspot map, dispatch table, and 24H forecasting
4. Optimizes enforcement resource deployment using greedy coverage maximization
5. Explains every AI decision with transparent SHAP-style feature attribution

---

## Architecture

```
  Parking Dataset (100K+ violations)
           +
     Mappls APIs (Real-Time Traffic)
                   │
                   ▼
         ┌─────────────────┐
         │  Data Processing │  ← Feature extraction, clustering,
         │  & Preprocessing │    geo-hashing, H3 hex zones
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │   XGBoost Model  │  ← AUC-ROC: 99.95% · F1: 0.99
         │  (Binary + Multi)│    Trained on 15 engineered features
         └────────┬────────┘
                  │
         ┌────────┴──────────────────────────┐
         │                                   │
         ▼                                   ▼
  ┌─────────────┐                  ┌──────────────────┐
  │  Hotspot    │                  │  Impact Scoring   │
  │  Detection  │                  │  & Spillover Risk │
  └──────┬──────┘                  └────────┬─────────┘
         │                                  │
         └────────────┬─────────────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │  Dispatch Engine  │  ← Tow Truck / Patrol / E-Challan
            │  (Optimization)   │    Greedy Coverage Maximization
            └────────┬─────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Command Center UI   │  ← Live Map · ML Analytics
         │   (Flask + HTML/JS)   │    Priority Dispatch · 24H Forecast
         └───────────────────────┘
```

---

## Key Features

### 🧠 XGBoost ML Engine
- Binary classifier: **Is this zone a hotspot?**
- Multi-class: **CRITICAL / HIGH / MEDIUM / LOW** severity
- **AUC-ROC: 99.95%** · **F1 Score: 0.99**
- 15 engineered features: parking density, traffic volume, road width, metro proximity, event activity

### 🔍 XGBoost Explainability Panel
- Click any zone on the live map → side panel opens
- Shows SHAP-style **feature importance bars** per zone
- Displays **AI Confidence Score** (85–99%)
- Turns the system from a black box into **Transparent AI**

### ⚡ Enforcement Optimization Engine
- Click **"Optimize Enforcement"** in the Dispatch tab
- Computes current vs. AI-optimized resource deployment
- Clusters nearby zones to maximize coverage with fewer units
- Shows **Resource Saving %** and **Coverage improvement**

### 🗺️ Live Congestion Map
- Interactive Leaflet / Mappls vector map with H3-style hexagon zones
- Thermal heatmap layers, cluster network lines, animated pulse for critical zones
- ANPR live feed simulation with OCR plate recognition

### 📊 Traffic Authority Impact Dashboard
- **Daily Delay Reduced** (minutes)
- **Fuel Saved** (liters)
- **Congestion Reduced** (%)
- **Enforcement Efficiency** (% improvement)
- **Hotspots Resolved** (count)

### 🚨 Priority Dispatch Console
- Auto-ranked zones by impact score
- Actions: Dispatch Tow Truck / Send Patrol / Issue E-Challan
- Telegram + SMS/WhatsApp alert integration via Twilio
- Manual Approve mode for human-in-the-loop enforcement

### 📈 24H Congestion Forecast
- Historical pattern-based congestion index prediction
- Peak congestion window detection
- Predicted violations per hour chart

---

## ML Performance

| Metric    | Score   |
|-----------|---------|
| AUC-ROC   | 99.95%  |
| F1 Score  | 0.9900  |
| Precision | 0.9912  |
| Recall    | 0.9888  |
| Accuracy  | 99.1%   |

---

## Screenshots

> Dashboard running live at `http://localhost:5000`

**Live Congestion Map** — Heatmap + hex zones + Mappls integration  
**ML Risk Analytics** — Severity distribution, top 10 enforcement zones  
**Priority Dispatch** — Sorted enforcement table + optimization engine  
**24H Forecast** — Congestion index forecast + Authority Impact Dashboard  

---

## Project Structure

```
GridLock_AI/
├── Backend/                  # ML models & data pipelines
│   ├── models/               # XGBoost training scripts
│   └── outputs/              # Processed datasets for dashboard
├── Dataset/                  # Raw parking violation data
├── Frontend/                 # Legacy Streamlit UI (reference only)
├── static/                   # Web dashboard assets
│   ├── index.html            # Main UI structure
│   ├── css/style.css         # Premium dark-theme design system
│   └── js/
│       ├── app.js            # Core app logic, map, XAI, optimization
│       └── charts.js         # Chart.js visualizations
├── server.py                 # Flask API server
├── requirements.txt          # Python dependencies
└── README.md
```

---

## How to Run

### 1. Clone the repository
```bash
git clone https://github.com/poornima200631/GridLock_AI.git
cd GridLock_AI
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the server
```bash
python server.py
```

### 4. Open in browser
```
http://localhost:5000
```

### Optional: Add Mappls API credentials
In the dashboard → Settings (⚙️ icon) → paste your Mappls Client ID & Secret → Save & Reload.  
Without credentials, the map falls back to **Leaflet OpenStreetMap** (fully functional).

---

## Tech Stack

| Layer       | Technology                              |
|-------------|-----------------------------------------|
| ML Model    | XGBoost 1.7, scikit-learn, SHAP         |
| Data        | pandas, NumPy, H3-py (hex clustering)   |
| Backend     | Python 3.11+, Flask, flask-cors         |
| Maps        | Mappls Maps SDK / Leaflet.js (fallback) |
| Frontend    | Vanilla HTML5 + CSS3 + JavaScript       |
| Charts      | Chart.js 4.4                            |
| Alerts      | Telegram Bot API, Twilio SMS/WhatsApp   |

---

## Team

- **ML Engine** — Data Processing, Feature Extraction & XGBoost Training  
- **Geo Engine** — Geospatial Intelligence, H3 Clustering & Traffic Modeling  
- **Dashboard** — Command Center UI, Flask API & Mappls Integration
