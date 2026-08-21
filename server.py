"""
============================================================
STAGE 3: LIVE BACKEND API & ASSET SERVER (server.py)
============================================================
Fast, lightweight Flask REST API and static server that connects
the automated Sentinel-1 pipeline to the interactive frontend.

Endpoints:
- GET  /api/metadata               -> Current satellite pass & flood metadata
- GET  /api/flood-extent/latest    -> Latest detected GeoJSON flood polygons
- GET  /api/history                -> Historical scene archives & run summaries
- GET  /api/history/<id>/geojson   -> Versioned GeoJSON for a historical pass
- POST /api/pipeline/trigger       -> Trigger on-demand ingestion/processing
- Static file serving (index.html, style.css, JS modules, GeoJSON, PNGs)
============================================================
"""

import os
import json
import threading
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory, make_response

import pipeline
import ingest_sentinel1

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)
PORT = 8000
MANIFEST_PATH = os.path.join("data", "manifest.json")
OUTPUT_DIR = "output"

# Global Pipeline Lock to avoid concurrent execution clashes
pipeline_lock = threading.Lock()


def add_cors_headers(response):
    """Ensure CORS is allowed across all endpoints."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.after_request
def after_request_func(response):
    return add_cors_headers(response)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route("/api/metadata", methods=["GET"])
def api_metadata():
    """Returns current satellite status, last pass timestamp, and flood metrics."""
    meta = pipeline.get_latest_metadata()
    return jsonify({
        "status": "success",
        "data": meta,
        "server_time": datetime.now(timezone.utc).isoformat()
    })


@app.route("/api/flood-extent/latest", methods=["GET"])
def api_latest_flood_extent():
    """Serves the latest detected flood extent GeoJSON."""
    geojson_path = os.path.join(OUTPUT_DIR, "flood_extent.geojson")
    if not os.path.exists(geojson_path):
        geojson_path = "flood_extent.geojson"

    if not os.path.exists(geojson_path):
        return jsonify({"error": "Flood extent GeoJSON not found"}), 404

    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = pipeline.get_latest_metadata()
        resp = make_response(jsonify(data))
        resp.headers["Content-Type"] = "application/json"
        resp.headers["X-Scene-ID"] = str(meta.get("last_processed_scene_id") or "")
        resp.headers["X-Scene-Date"] = str(meta.get("last_scene_date") or "")
        return resp
    except Exception as e:
        return jsonify({"error": f"Failed reading GeoJSON: {str(e)}"}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    """Returns the list of historical satellite scenes and runs."""
    manifest = ingest_sentinel1.load_manifest(MANIFEST_PATH)
    return jsonify({
        "status": "success",
        "total_runs": len(manifest.get("history", [])),
        "history": manifest.get("history", [])
    })


@app.route("/api/history/<scene_id>/geojson", methods=["GET"])
def api_history_scene_geojson(scene_id):
    """Serves the historical GeoJSON for a specific satellite pass."""
    safe_name = scene_id.replace(".SAFE", "")
    historical_path = os.path.join(OUTPUT_DIR, "history", safe_name, "flood_extent.geojson")
    
    if not os.path.exists(historical_path):
        return jsonify({"error": f"Historical run not found for scene {scene_id}"}), 404

    try:
        with open(historical_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Error loading historical scene: {str(e)}"}), 500


@app.route("/api/pipeline/trigger", methods=["POST"])
def api_trigger_pipeline():
    """
    On-demand API trigger for Sentinel-1 ingestion & detection pipeline.
    Accepts JSON payload: { "force": true/false }
    """
    if pipeline_lock.locked():
        return jsonify({
            "status": "RUNNING",
            "message": "A pipeline execution job is already in progress. Please wait."
        }), 429

    payload = request.get_json(silent=True) or {}
    force_run = payload.get("force", False)

    def run_job():
        with pipeline_lock:
            try:
                pipeline.run_pipeline(force=force_run)
            except Exception as err:
                print(f"[API Trigger Error] {err}")

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()

    return jsonify({
        "status": "TRIGGERED",
        "message": "Automated Sentinel-1 pipeline execution has been launched in the background.",
        "force": force_run,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 202


# ============================================================
# STATIC ASSETS & DASHBOARD SERVING
# ============================================================

@app.route("/")
def index():
    return send_from_directory(ROOT_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static_file(filename):
    full_path = os.path.join(ROOT_DIR, filename)
    if os.path.isfile(full_path):
        return send_from_directory(ROOT_DIR, filename)
    return jsonify({"error": f"File '{filename}' not found"}), 404


# ============================================================
# BACKGROUND SCHEDULED POLLER (DAEMON)
# ============================================================

def start_background_poller(interval_seconds=3600):
    """Periodically checks Copernicus CDSE for new satellite scenes."""
    def poller_loop():
        print(f"[Background Poller] Sentinel-1 satellite watcher active (interval: {interval_seconds}s).")
        while True:
            time.sleep(interval_seconds)
            try:
                print("[Background Poller] Checking for fresh satellite imagery...")
                with pipeline_lock:
                    pipeline.run_pipeline(force=False)
            except Exception as e:
                print(f"[Background Poller Warning] {e}")

    t = threading.Thread(target=poller_loop, daemon=True)
    t.start()


if __name__ == "__main__":
    print("=" * 60)
    print(f"STARTING SENTINEL-1 FLOOD MONITOR BACKEND API (PORT {PORT})")
    print("=" * 60)
    
    start_background_poller(interval_seconds=3600)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
