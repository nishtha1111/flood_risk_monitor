"""
============================================================
SATELLITE FLOOD RISK & RELIEF MONITOR - STREAMLIT BRIDGE
============================================================
Renders the complete unified flood risk & relief application
within Streamlit, ensuring 100% feature parity whether deployed
via Gunicorn (server.py) or Streamlit (app.py).
============================================================
"""

import os
import streamlit as st
import streamlit.components.v1 as components

# Configure Streamlit page
st.set_page_config(
    page_title="Satellite Flood Risk & Relief Monitor",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Remove Streamlit top padding and branding for full-bleed interface
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
    }
    iframe {
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Load and render unified dashboard HTML
current_dir = os.path.dirname(os.path.abspath(__file__))
index_path = os.path.join(current_dir, "index.html")

if os.path.exists(index_path):
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Render with responsive full-height viewport
    components.html(html_content, height=920, scrolling=True)
else:
    st.error("Error: Unified dashboard index.html not found.")
