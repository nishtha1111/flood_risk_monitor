# 🌊 Satellite Flood Risk & Relief Monitor

🔗 **Live Demo:** [https://flood-risk-monitor.onrender.com](https://flood-risk-monitor.onrender.com/)

A real-time satellite-driven flood monitoring and community relief coordination platform that leverages **Sentinel-1 SAR (Synthetic Aperture Radar)** imagery from the European Space Agency's Copernicus programme to detect, map, and visualize flood extents over the **Brahmaputra Basin, Assam, India**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Running Locally](#running-locally)
- [Pipeline Stages](#pipeline-stages)
  - [Stage 1 – SAR Data Ingestion](#stage-1--sar-data-ingestion)
  - [Stage 2 – Flood Detection & Pipeline Automation](#stage-2--flood-detection--pipeline-automation)
  - [Stage 3 – Backend API & Dashboard Serving](#stage-3--backend-api--dashboard-serving)
- [API Endpoints](#api-endpoints)
- [Frontend Features](#frontend-features)
- [Deployment](#deployment)
- [Screenshots](#screenshots)
- [License](#license)

---

## Overview

Floods in the Brahmaputra basin displace millions every monsoon season. Traditional monitoring systems rely on manual gauge readings and delayed government reports. This project addresses that gap by building an **automated, near-real-time flood detection pipeline** from freely available radar satellite data, paired with an **interactive web dashboard** for situational awareness and community-driven relief coordination.

### How It Works (End-to-End)

1. **Ingest** — Queries the Copernicus Data Space Ecosystem (CDSE) OData catalogue for the latest Sentinel-1 GRD SAR passes over the AOI.
2. **Detect** — Performs SAR change detection by comparing pre-flood and during-flood radar backscatter, applying a dB threshold to isolate flooded areas.
3. **Vectorize** — Converts the raster flood mask into georeferenced GeoJSON polygons for web consumption.
4. **Serve** — A Flask REST API + static server exposes live flood extent, metadata, and historical archives.
5. **Visualize** — An interactive Leaflet.js map dashboard overlays flood extents, risk zones, hospitals, roads, and enables safe route finding and community help coordination.

---

## Key Features

| Category | Feature |
|---|---|
| **Satellite Pipeline** | Automated Sentinel-1 SAR ingestion from Copernicus CDSE via OAuth2 |
| **Flood Detection** | SAR change detection (dB thresholding) with morphological noise cleanup |
| **Georeferencing** | GCP-based transform construction for Sentinel-1 raw GRDH data |
| **GeoJSON Export** | Raster-to-vector polygon conversion with EPSG:4326 reprojection |
| **REST API** | Flask API with metadata, flood extent, history, and pipeline trigger endpoints |
| **Interactive Map** | Leaflet.js dashboard with multi-layer overlays (flood, risk zones, hospitals, roads) |
| **Safe Route Finder** | OSRM-based evacuation routing with flood-avoidance spatial analysis |
| **Community Relief** | Offer/Request Help system with Firebase Firestore + LocalStorage dual persistence |
| **Background Polling** | Daemon thread that auto-checks for new satellite passes every hour |
| **Versioned Storage** | Each pipeline run is archived under `output/history/<scene_id>/` with metadata |
| **Dual Deployment** | Runs via Gunicorn (production) or Streamlit (app.py bridge) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Copernicus CDSE (ESA)                       │
│              Sentinel-1 SAR Satellite Data                  │
└────────────────────────┬────────────────────────────────────┘
                         │ OAuth2 + OData API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: ingest_sentinel1.py                               │
│  - Authenticate with CDSE Keycloak                          │
│  - Query latest GRD scenes over AOI (WKT intersection)      │
│  - Manifest-based state tracking (data/manifest.json)       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: detect_flood.py + pipeline.py                     │
│  - Read before/during Sentinel-1 TIFF (VV polarization)     │
│  - Convert raw amplitude → dB (10·log₁₀)                   │
│  - SAR change detection (dB threshold = -1.0)               │
│  - Morphological cleanup (opening + closing)                │
│  - Small object removal (< 100 px)                          │
│  - Export: GeoTIFF → GeoJSON (EPSG:4326)                    │
│  - Version archival under output/history/<scene_id>/        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: server.py (Flask REST API)                        │
│  - /api/metadata, /api/flood-extent/latest                  │
│  - /api/history, /api/pipeline/trigger                      │
│  - Static file serving (HTML, CSS, JS, GeoJSON, PNGs)       │
│  - Background poller daemon (1-hour interval)               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend: index.html + app.js + routing.js + resources.js  │
│  - Leaflet.js interactive map (CartoDB Positron tiles)       │
│  - Multi-layer: Flood extent, Risk zones, Hospitals, Roads  │
│  - OSRM-based safe evacuation route finder                  │
│  - Community Offer/Request Help (Firebase + LocalStorage)   │
│  - Live API stream polling with flicker-free layer updates   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.10+** | Core language |
| **Flask** | REST API and static asset server |
| **Gunicorn** | Production WSGI server |
| **Rasterio** | GeoTIFF I/O, CRS/GCP handling |
| **GeoPandas** | Vector geometry operations, GeoJSON I/O |
| **NumPy** | Raster array math (dB conversion, thresholding) |
| **SciPy** | Morphological operations (opening, closing, labeling) |
| **Matplotlib** | SAR visualization and PNG output |
| **Requests** | HTTP client for CDSE OAuth2 & OData catalogue |
| **Streamlit** | Alternative dashboard bridge (app.py) |

### Frontend
| Technology | Purpose |
|---|---|
| **Leaflet.js** | Interactive web mapping |
| **OSRM API** | Open-source routing for evacuation path finding |
| **Firebase Firestore** | Real-time cross-device persistence (optional) |
| **Font Awesome** | Icon library |
| **Vanilla JavaScript** | No framework — lightweight and fast |
| **CSS3** | Custom responsive styles |

### Data Sources
| Source | Description |
|---|---|
| **Sentinel-1 SAR (C-band)** | VV-polarized GRD imagery from Copernicus CDSE |
| **OpenStreetMap** | Base map tiles via CartoDB Positron |
| **Overpass/OSM** | Hospital and road network data (GeoJSON) |

---

## Project Structure

```
flood_risk_monitor/
├── ingest_sentinel1.py      # Stage 1: CDSE satellite data ingestion engine
├── detect_flood.py          # Stage 2a: SAR change detection algorithm
├── pipeline.py              # Stage 2b: End-to-end pipeline orchestration
├── server.py                # Stage 3: Flask REST API + static server
├── app.py                   # Streamlit bridge (alternative frontend)
│
├── index.html               # Main interactive dashboard (Leaflet map)
├── style.css                # Full application stylesheet
├── app.js                   # Map initialization, API polling, layer management
├── routing.js               # Safe evacuation route finder (OSRM)
├── resources.js             # Community Offer/Request Help system
│
├── data/
│   ├── manifest.json        # Pipeline state tracker (last scene, history)
│   ├── hospitals.geojson    # Hospital/medical facility locations
│   └── roads.geojson        # Major road network in AOI
│
├── output/
│   ├── flood_extent.geojson # Latest detected flood polygons
│   ├── flood_mask.tif       # Georeferenced binary flood mask
│   ├── before_flood.png     # Pre-flood SAR visualization
│   ├── during_flood.png     # During-flood SAR visualization
│   ├── sar_change.png       # SAR backscatter change map
│   ├── flood_detected.png   # Raw flood detection result
│   ├── flood_clean.png      # Cleaned flood mask
│   └── history/             # Versioned archives per scene
│
├── flood_extent.geojson     # Root-level GeoJSON (synced copy for frontend)
├── risk_zones.geojson       # Risk classification zones
├── flood_risk_map.png       # Static flood risk map
│
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── Procfile                 # Heroku/Render process file
├── render.yaml              # Render.com deployment config
└── .gitignore
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)
- **Git**
- (Optional) Free account on [Copernicus Data Space](https://dataspace.copernicus.eu) for live satellite access
- (Optional) Firebase project for real-time community relief data sync

### Installation

```bash
# Clone the repository
git clone https://github.com/nishtha1111/flood_risk_monitor.git
cd flood_risk_monitor

# Create a virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Copernicus CDSE credentials (free registration)
CDSE_USERNAME=your_email@example.com
CDSE_PASSWORD=your_password_here

# Pipeline Settings
POLL_INTERVAL_HOURS=6
AUTO_TRIGGER_PROCESSING=true
```

> **Note:** The system runs gracefully without CDSE credentials using the pre-processed demo data.

### Running Locally

#### Option 1: Flask Server (Recommended)
```bash
python server.py
```
Open `http://localhost:8000` in your browser.

#### Option 2: Gunicorn (Production)
```bash
gunicorn server:app --bind 0.0.0.0:8000
```

#### Option 3: Streamlit Bridge
```bash
streamlit run app.py
```

---

## Pipeline Stages

### Stage 1 – SAR Data Ingestion

**File:** `ingest_sentinel1.py`

- Authenticates with Copernicus CDSE via OAuth2 (Keycloak)
- Queries the OData catalogue for Sentinel-1 GRD imagery intersecting the AOI
- Uses WKT polygon spatial filter: `POLYGON((90.6445 25.0926, 93.1630 25.0926, ...))`
- Tracks processed scenes via `data/manifest.json` to avoid reprocessing
- Falls back to local manifest in offline/demo mode

### Stage 2 – Flood Detection & Pipeline Automation

**Files:** `detect_flood.py`, `pipeline.py`

1. Reads before-flood and during-flood Sentinel-1 GRD TIFF files (VV polarization)
2. Handles missing CRS by constructing affine transforms from Ground Control Points (GCPs)
3. Converts raw amplitude to decibels: `dB = 10 × log₁₀(amplitude)`
4. Calculates backscatter change: `Δ dB = during_dB − before_dB`
5. Applies threshold (default: −1.0 dB) — negative change indicates water surface
6. Morphological cleanup: binary opening (3×3) removes speckle noise, binary closing (5×5) fills gaps
7. Small object removal: discards regions < 100 pixels
8. Exports georeferenced GeoTIFF + GeoJSON (reprojected to EPSG:4326)
9. Archives each run with metadata under `output/history/<scene_id>/`

### Stage 3 – Backend API & Dashboard Serving

**File:** `server.py`

- Flask REST API serving flood data, metadata, and historical archives
- Static file server for HTML, CSS, JS, GeoJSON, and PNG assets
- Pipeline trigger endpoint for on-demand processing
- Background poller daemon thread (hourly satellite checks)
- Thread-safe pipeline execution with `threading.Lock`
- CORS headers on all responses

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/metadata` | Current satellite pass status & flood metrics |
| `GET` | `/api/flood-extent/latest` | Latest detected flood GeoJSON polygons |
| `GET` | `/api/history` | List of all historical pipeline runs |
| `GET` | `/api/history/<scene_id>/geojson` | GeoJSON for a specific historical scene |
| `POST` | `/api/pipeline/trigger` | Trigger on-demand pipeline execution |
| `GET` | `/` | Main dashboard (index.html) |
| `GET` | `/presentation` | Pitch deck / presentation page |

### Example API Response (`/api/metadata`)
```json
{
  "status": "success",
  "data": {
    "aoi": [90.6445, 25.0926, 93.163, 26.7045],
    "aoi_name": "Assam Brahmaputra Basin",
    "satellite": "Sentinel-1A (C-band SAR)",
    "last_processed_scene_id": "S1A_IW_GRDH_1SDV_20240711...",
    "last_scene_date": "2024-07-11T11:57:15.000Z",
    "total_runs": 1
  },
  "server_time": "2024-07-15T12:00:00Z"
}
```

---

## Frontend Features

### 🗺️ Operations Map
- Interactive Leaflet.js map centered on the Brahmaputra Basin
- Toggle layers: Flood Extent, Risk Zones, Hospitals, Roads
- Click any flood polygon for detailed metrics popup
- Live status badge with satellite polling indicator

### 🛣️ Safe Route Finder
- Set origin/destination by clicking on the map or using GPS
- Calculates evacuation routes via OSRM
- Performs spatial analysis to flag routes intersecting flood zones
- Suggests detour alternatives with distance/time estimates
- Built-in route memory cache for performance

### 🤝 Community Relief Connector
- **Offer Help**: Volunteers register available resources (food, shelter, transport, medical)
- **Request Help**: Affected citizens request specific aid
- Dual persistence: Firebase Firestore (cross-device) + LocalStorage (offline-first)
- Cross-tab sync via BroadcastChannel API
- Category filtering and search

### 📊 Satellite Analytics View
- Before/during SAR imagery comparison
- Backscatter change visualization
- Flood detection result display
- Pipeline execution history

---

## Deployment

### Render.com

The project includes `render.yaml` for one-click deployment:

```yaml
services:
  - type: web
    name: flood-risk-monitor
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn server:app
```

### Heroku

Use the included `Procfile`:

```
web: gunicorn server:app
```

---

## Area of Interest (AOI)

**Region:** Lower-Central Brahmaputra Basin, Assam, India  
**Bounding Box:** `[90.6445°E, 25.0926°N, 93.1630°E, 26.7045°N]`  
**Satellite:** Sentinel-1A (IW mode, VV polarization, GRD-H product)  
**Before Scene:** 29 June 2024  
**During Scene:** 11 July 2024  

---

## License

This project is open-source. See the repository for license details.

---

## Acknowledgements

- **European Space Agency (ESA)** — Copernicus Sentinel-1 SAR data
- **Copernicus Data Space Ecosystem** — Free satellite data access & OData API
- **OpenStreetMap** — Base map tiles and geographic data
- **OSRM** — Open Source Routing Machine for evacuation routing
- **Leaflet.js** — Open-source interactive mapping library