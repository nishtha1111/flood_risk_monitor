import os
import json
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Flood Risk Monitor",
    page_icon="🌊",
    layout="wide"
)

# ============================================================
# DATA LOADING WITH GRACEFUL ERROR HANDLING
# ============================================================

def load_geojson_safe(primary_path, fallback_paths=None, layer_name="layer"):
    """
    Safely load a GeoJSON dataset with fallback path support and robust error handling.
    Always converts geometries to WGS84 (EPSG:4326) if valid.
    """
    search_paths = [primary_path] + (fallback_paths or [])
    for path in search_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            gdf = gpd.read_file(path)
            if gdf is None or len(gdf) == 0:
                st.warning(f"⚠️ GeoJSON dataset for **{layer_name}** (`{path}`) is empty.")
                return None
            # Ensure valid CRS
            if gdf.crs is None:
                gdf = gdf.set_crs(epsg=4326)
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            return gdf
        except json.JSONDecodeError as jde:
            st.error(f"❌ JSON decode error in **{layer_name}** file (`{path}`): {jde}")
            return None
        except Exception as e:
            st.warning(f"⚠️ Unable to load **{layer_name}** from `{path}`: {e}")
            return None

    return None


# Load datasets with fallbacks
risk = load_geojson_safe(
    "output/risk_zones_clean.geojson",
    fallback_paths=["risk_zones.geojson", "data/risk_zones_clean.geojson"],
    layer_name="Flood Risk Zones"
)

hospitals = load_geojson_safe(
    "data/hospitals.geojson",
    fallback_paths=["output/hospitals.geojson", "hospitals.geojson"],
    layer_name="Hospitals"
)

roads = load_geojson_safe(
    "data/roads.geojson",
    fallback_paths=["output/roads.geojson", "roads.geojson"],
    layer_name="Roads"
)

# Metrics constants
high_area = 272.15
medium_area = 190.55
low_area = 197.55
classified_area = 660.26
flood_extent_area = 723.94

# ============================================================
# TITLE & HEADER
# ============================================================
st.title("🌊 Satellite Flood Risk Monitor")
st.caption("Sentinel-1 SAR based flood detection, risk classification, and infrastructure exposure")

# ============================================================
# METRICS
# ============================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Detected Flood", f"{flood_extent_area:.2f} km²")
c2.metric("Classified Risk", f"{classified_area:.2f} km²")
c3.metric("High Risk", f"{high_area:.2f} km²")
c4.metric("High Risk Share", "41.22%")

st.divider()

# ============================================================
# RISK BREAKDOWN & INFRASTRUCTURE EXPOSURE
# ============================================================
st.subheader("Risk & Infrastructure Overview")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("🔴 High Risk", f"{high_area:.2f} km²", "41.22%")
m2.metric("🟠 Medium Risk", f"{medium_area:.2f} km²", "28.86%")
m3.metric("🟢 Low Risk", f"{low_area:.2f} km²", "29.92%")
m4.metric("🏥 Hospitals Monitored", f"{len(hospitals)}" if hospitals is not None else "N/A")
m5.metric("🛣️ Road Corridors", f"{len(roads)}" if roads is not None else "N/A")

st.divider()

# ============================================================
# INTERACTIVE MAP
# ============================================================
st.subheader("Interactive Flood Risk & Infrastructure Map")

# Map center calculation
if risk is not None and not risk.empty:
    center = [
        risk.geometry.union_all().centroid.y,
        risk.geometry.union_all().centroid.x
    ]
elif hospitals is not None and not hospitals.empty:
    center = [
        hospitals.geometry.union_all().centroid.y,
        hospitals.geometry.union_all().centroid.x
    ]
elif roads is not None and not roads.empty:
    center = [
        roads.geometry.union_all().centroid.y,
        roads.geometry.union_all().centroid.x
    ]
else:
    center = [26.15, 91.75]

m = folium.Map(
    location=center,
    zoom_start=9,
    tiles="CartoDB positron"
)

# Feature Groups for Layer Control
fg_risk = folium.FeatureGroup(name="🌊 Flood Risk Zones", show=True)
fg_roads = folium.FeatureGroup(name="🛣️ Roads & Infrastructure", show=True)
fg_hospitals = folium.FeatureGroup(name="🏥 Hospitals", show=True)

# 1. ADD RISK ZONES LAYER
if risk is not None and not risk.empty:
    colors = {
        "High": "#d73027",
        "Medium": "#fc8d59",
        "Low": "#91cf60"
    }

    for _, row in risk.iterrows():
        risk_level = row.get("Risk", "Unknown")
        area_val = row.get("area_km2", None)
        tooltip_txt = f"Risk: {risk_level}" + (f" ({area_val:.2f} km²)" if area_val else "")

        folium.GeoJson(
            row.geometry,
            style_function=lambda feature, level=risk_level: {
                "fillColor": colors.get(level, "#999999"),
                "color": colors.get(level, "#999999"),
                "weight": 1,
                "fillOpacity": 0.55
            },
            tooltip=folium.Tooltip(tooltip_txt)
        ).add_to(fg_risk)

fg_risk.add_to(m)

# 2. ADD ROADS LAYER
if roads is not None and not roads.empty:
    for _, row in roads.iterrows():
        road_name = row.get("name") or row.get("Name") or row.get("road_name") or "Unnamed Road"
        road_type = row.get("type") or row.get("Type") or "Road Corridor"
        road_surface = row.get("surface") or "Paved"

        tooltip_content = f"<b>🛣️ {road_name}</b><br>Type: {road_type}"

        folium.GeoJson(
            row.geometry,
            style_function=lambda feature: {
                "color": "#2c3e50",
                "weight": 2.5,
                "opacity": 0.85
            },
            highlight_function=lambda feature: {
                "color": "#1d4ed8",
                "weight": 4.0,
                "opacity": 1.0
            },
            tooltip=folium.Tooltip(tooltip_content)
        ).add_to(fg_roads)

fg_roads.add_to(m)

# 3. ADD HOSPITALS LAYER
if hospitals is not None and not hospitals.empty:
    for _, row in hospitals.iterrows():
        geom = row.geometry
        if geom is None:
            continue

        # Extract lat/lon whether Point or representative centroid
        if geom.geom_type == "Point":
            lat, lon = geom.y, geom.x
        else:
            centroid = geom.centroid
            lat, lon = centroid.y, centroid.x

        hosp_name = row.get("name") or row.get("Name") or row.get("hospital_name") or "Hospital"
        hosp_type = row.get("type") or row.get("Type") or "Medical Facility"
        hosp_emerg = row.get("emergency") or "Available"
        hosp_beds = row.get("beds") or "N/A"
        district = row.get("district") or ""

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 180px; padding: 2px;">
            <div style="font-size: 14px; font-weight: bold; color: #b91c1c; margin-bottom: 6px;">🏥 {hosp_name}</div>
            <div style="margin-bottom: 3px;"><b>Type:</b> {hosp_type}</div>
            <div style="margin-bottom: 3px;"><b>Emergency:</b> {hosp_emerg}</div>
            <div style="margin-bottom: 3px;"><b>Beds:</b> {hosp_beds}</div>
            {f'<div style="margin-bottom: 3px;"><b>District:</b> {district}</div>' if district else ''}
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=folium.Tooltip(f"🏥 {hosp_name}"),
            icon=folium.Icon(
                color="red",
                icon="plus",
                prefix="fa"
            )
        ).add_to(fg_hospitals)

fg_hospitals.add_to(m)

# Layer Control
folium.LayerControl(position="topright", collapsed=False).add_to(m)

# Floating HTML Map Legend
legend_html = """
<div style="
    position: fixed; 
    bottom: 25px; 
    left: 25px; 
    z-index: 9999; 
    background-color: #ffffff; 
    padding: 12px 16px; 
    border-radius: 8px; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    font-family: Arial, sans-serif;
    font-size: 13px;
    font-weight: 600;
    line-height: 22px;
    border: 2px solid #cbd5e1;
    color: #000000 !important;
">
    <div style="font-weight: 800; margin-bottom: 6px; font-size: 14px; color: #000000 !important;">Legend</div>
    <div style="color: #000000 !important; display: flex; align-items: center; margin-bottom: 4px;"><span style="background-color: #d73027; opacity: 0.85; width: 14px; height: 14px; display: inline-block; margin-right: 8px; border-radius: 2px; border: 1px solid #b91c1c;"></span><span style="color: #000000 !important;">High Risk Zone</span></div>
    <div style="color: #000000 !important; display: flex; align-items: center; margin-bottom: 4px;"><span style="background-color: #fc8d59; opacity: 0.85; width: 14px; height: 14px; display: inline-block; margin-right: 8px; border-radius: 2px; border: 1px solid #ea580c;"></span><span style="color: #000000 !important;">Medium Risk Zone</span></div>
    <div style="color: #000000 !important; display: flex; align-items: center; margin-bottom: 4px;"><span style="background-color: #91cf60; opacity: 0.85; width: 14px; height: 14px; display: inline-block; margin-right: 8px; border-radius: 2px; border: 1px solid #16a34a;"></span><span style="color: #000000 !important;">Low Risk Zone</span></div>
    <div style="color: #000000 !important; display: flex; align-items: center; margin-bottom: 4px; margin-top: 4px;"><span style="color: #dc2626; font-size: 15px; margin-right: 8px;">➕</span><span style="color: #000000 !important;">Hospital Marker</span></div>
    <div style="color: #000000 !important; display: flex; align-items: center; margin-top: 4px;"><span style="border-top: 3px solid #1e293b; width: 16px; display: inline-block; vertical-align: middle; margin-right: 8px;"></span><span style="color: #000000 !important;">Road Infrastructure</span></div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Render Folium Map in Streamlit
st_folium(
    m,
    width=None,
    height=600
)

st.divider()

# ============================================================
# SATELLITE IMAGERY
# ============================================================
st.subheader("Satellite Flood Detection")

c1, c2, c3 = st.columns(3)

with c1:
    if os.path.exists("output/before.png"):
        st.image("output/before.png", caption="Before Flood", use_container_width=True)
    elif os.path.exists("output/before_flood.png"):
        st.image("output/before_flood.png", caption="Before Flood", use_container_width=True)

with c2:
    if os.path.exists("output/during.png"):
        st.image("output/during.png", caption="During Flood", use_container_width=True)
    elif os.path.exists("output/during_flood.png"):
        st.image("output/during_flood.png", caption="During Flood", use_container_width=True)

with c3:
    if os.path.exists("output/flood_detected.png"):
        st.image("output/flood_detected.png", caption="Detected Flood", use_container_width=True)

st.divider()

st.caption(
    "Risk classification is derived from Sentinel-1 SAR flood detection. "
    "Hospitals and road infrastructure layers provide exposure and accessibility insights "
    "for emergency management and disaster response planning."
)
