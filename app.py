import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Flood Risk Monitor",
    page_icon="🌊",
    layout="wide"
)

# ---------- DATA ----------
risk = gpd.read_file("output/risk_zones_clean.geojson")

high = 272.15
medium = 190.55
low = 197.55
classified = 660.26
flood_extent = 723.94

# ---------- TITLE ----------
st.title("🌊 Satellite Flood Risk Monitor")
st.caption("Sentinel-1 SAR based flood detection and risk classification")

# ---------- METRICS ----------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Detected Flood", "723.94 km²")
c2.metric("Classified Risk", "660.26 km²")
c3.metric("High Risk", "272.15 km²")
c4.metric("High Risk Share", "41.22%")

st.divider()

# ---------- RISK BREAKDOWN ----------
st.subheader("Risk Distribution")

c1, c2, c3 = st.columns(3)

c1.metric("🔴 High", "272.15 km²", "41.22%")
c2.metric("🟠 Medium", "190.55 km²", "28.86%")
c3.metric("🟢 Low", "197.55 km²", "29.92%")

st.divider()

# ---------- MAP ----------
st.subheader("Interactive Flood Risk Map")

# Convert to WGS84
risk = risk.to_crs(epsg=4326)

# Map center
center = [
    risk.geometry.union_all().centroid.y,
    risk.geometry.union_all().centroid.x
]

m = folium.Map(
    location=center,
    zoom_start=9,
    tiles="CartoDB positron"
)

# Risk colors
colors = {
    "High": "#d73027",
    "Medium": "#fc8d59",
    "Low": "#91cf60"
}

for _, row in risk.iterrows():

    risk_level = row["Risk"]

    folium.GeoJson(
        row.geometry,
        style_function=lambda feature, level=risk_level: {
            "fillColor": colors.get(level, "#999999"),
            "color": colors.get(level, "#999999"),
            "weight": 1,
            "fillOpacity": 0.55
        },
        tooltip=folium.Tooltip(
            f"Risk: {risk_level}"
        )
    ).add_to(m)

st_folium(
    m,
    width=None,
    height=600
)

st.divider()

# ---------- SATELLITE IMAGERY ----------
st.subheader("Satellite Flood Detection")

c1, c2, c3 = st.columns(3)

with c1:
    st.image(
        "output/before.png",
        caption="Before Flood",
        use_container_width=True
    )

with c2:
    st.image(
        "output/during.png",
        caption="During Flood",
        use_container_width=True
    )

with c3:
    st.image(
        "output/flood_detected.png",
        caption="Detected Flood",
        use_container_width=True
    )

st.divider()

st.caption(
    "Risk classification is derived from Sentinel-1 flood detection. "
    "Risk zones are mutually exclusive; infrastructure exposure is not "
    "included in the current analysis."
)
