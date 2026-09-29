"""
============================================================
STAGE 1: SENTINEL-1 SAR DATA INGESTION ENGINE
============================================================
Automates querying, matching, and downloading of the newest
Sentinel-1 SAR GRDH imagery covering the Area of Interest (AOI)
from the Copernicus Data Space Ecosystem (CDSE).

Key Requirements:
- Strictly filters by same relative orbit number (41) and pass
  direction (ASCENDING) as the baseline before-scene.
- Compares latest catalogue scene against data/manifest.json.
- Exits early if no new scene is available.
- Securely reads CDSE_USERNAME and CDSE_PASSWORD from env.
- Downloads & extracts candidate scene for detect_flood.py.
============================================================
"""

import os
import sys
import json
import time
import glob
import zipfile
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

load_dotenv()

# AOI Coordinates: [minLon, minLat, maxLon, maxLat]
# Lower-Central Brahmaputra Basin / Assam
DEFAULT_AOI = [90.6445, 25.0926, 93.1630, 26.7045]
MANIFEST_PATH = os.path.join("data", "manifest.json")
BASELINE_SCENE_ID = "S1A_IW_GRDH_1SDV_20240629T115716_20240629T115741_054538_06A32B_151F"
TARGET_RELATIVE_ORBIT = 41
TARGET_ORBIT_DIRECTION = "ASCENDING"

# CDSE Endpoints
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


def get_cdse_credentials():
    """Reads CDSE credentials from environment, failing clearly if missing."""
    username = os.environ.get("CDSE_USERNAME", "").strip()
    password = os.environ.get("CDSE_PASSWORD", "").strip()

    if not username or not password or username == "your_email@example.com":
        print("\n" + "=" * 60)
        print("ERROR: Missing Copernicus Data Space Ecosystem (CDSE) credentials!")
        print("Please set CDSE_USERNAME and CDSE_PASSWORD in your environment or GitHub Secrets.")
        print("Register for free at: https://dataspace.copernicus.eu")
        print("=" * 60 + "\n")
        sys.exit(1)

    return username, password


def get_cdse_access_token(username, password):
    """
    Authenticate against Copernicus Data Space Ecosystem via OAuth2 Keycloak.
    Returns access token string or exits on error.
    """
    payload = {
        "grant_type": "password",
        "client_id": "cdse-public",
        "username": username,
        "password": password
    }

    try:
        response = requests.post(TOKEN_URL, data=payload, timeout=25)
        if response.status_code == 200:
            token_data = response.json()
            print("[Ingestion Auth] Successfully authenticated with Copernicus CDSE.")
            return token_data.get("access_token")
        else:
            print(f"[Ingestion Auth Error] HTTP {response.status_code}: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[Ingestion Auth Error] Connection failed: {e}")
        sys.exit(1)


def query_matching_sentinel1_scenes(aoi_bbox=DEFAULT_AOI, access_token=None, limit=25):
    """
    Query Copernicus OData API for Sentinel-1 GRDH scenes over the AOI,
    strictly filtering for relativeOrbitNumber == 41 and orbitDirection == ASCENDING.
    """
    min_lon, min_lat, max_lon, max_lat = aoi_bbox

    # WKT Polygon: Counter-clockwise closed loop
    wkt_polygon = (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )

    odata_filter = (
        f"Collection/Name eq 'SENTINEL-1' and "
        f"contains(Name, 'GRD') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt_polygon}')"
    )

    params = {
        "$filter": odata_filter,
        "$orderby": "ContentDate/Start desc",
        "$expand": "Attributes",
        "$top": limit
    }

    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    print(f"[Ingestion Query] Searching CDSE catalogue for Orbit {TARGET_RELATIVE_ORBIT} ({TARGET_ORBIT_DIRECTION}) scenes...")
    resp = requests.get(CATALOGUE_URL, params=params, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        print(f"[Ingestion Query Error] HTTP {resp.status_code}: {resp.text}")
        return []

    products = resp.json().get("value", [])
    matching_scenes = []

    for prod in products:
        attrs = {a.get("Name"): a.get("Value") for a in prod.get("Attributes", [])}
        orbit = attrs.get("relativeOrbitNumber")
        direction = attrs.get("orbitDirection")
        polarization = attrs.get("polarizationChannels") or ""

        # Filter strictly for matching geometry: Relative Orbit 41 + ASCENDING pass
        if orbit == TARGET_RELATIVE_ORBIT and direction == TARGET_ORBIT_DIRECTION:
            matching_scenes.append(prod)

    print(f"[Ingestion Query] Found {len(matching_scenes)} matching scenes with Orbit {TARGET_RELATIVE_ORBIT} {TARGET_ORBIT_DIRECTION}.")
    return matching_scenes


def download_and_extract_product(product_id, dest_dir, access_token):
    """
    Downloads product ZIP from CDSE OData with redirect handling,
    streams to disk in 1MB chunks, and extracts into dest_dir.
    """
    os.makedirs(dest_dir, exist_ok=True)
    download_url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    headers = {"Authorization": f"Bearer {access_token}"}
    session = requests.Session()

    print(f"[Download] Requesting product {product_id} from CDSE...")
    resp = session.get(download_url, headers=headers, allow_redirects=False, timeout=60)
    
    # Intercept HTTP redirects while maintaining Bearer token
    while resp.status_code in (301, 302, 303, 307):
        download_url = resp.headers["Location"]
        resp = session.get(download_url, headers=headers, allow_redirects=False, timeout=60)

    if resp.status_code != 200:
        resp = session.get(download_url, headers=headers, stream=True, timeout=120)

    resp.raise_for_status()

    zip_path = os.path.join(dest_dir, "downloaded_scene.zip")
    print(f"[Download] Streaming archive to {zip_path}...")
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    print(f"[Download] Extracting scene into {dest_dir}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    os.remove(zip_path)
    print(f"[Download] Extraction complete. Raw archive cleaned up.")


def has_measurement_tiff(folder):
    """Check if destination folder contains at least one measurement TIFF."""
    tiffs = glob.glob(os.path.join(folder, "**", "*.tiff"), recursive=True) + \
            glob.glob(os.path.join(folder, "**", "*.tif"), recursive=True)
    return len(tiffs) > 0


def load_manifest(manifest_path=MANIFEST_PATH):
    """Load local scene tracking manifest."""
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Manifest Warning] Unable to read manifest: {e}")

    return {
        "aoi": DEFAULT_AOI,
        "aoi_name": "Assam Brahmaputra Basin",
        "last_processed_scene_id": None,
        "last_scene_date": None,
        "history": []
    }


def write_github_output(key, value):
    """Helper to set GitHub Actions step output."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file and os.path.exists(os.path.dirname(output_file)):
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    print("=" * 60)
    print("SENTINEL-1 SAR INGESTION ENGINE (STAGE 1)")
    print("=" * 60)

    # 1. Require credentials
    username, password = get_cdse_credentials()
    token = get_cdse_access_token(username, password)

    # 2. Load current manifest state
    manifest = load_manifest()
    last_processed_id = manifest.get("last_processed_scene_id")

    # 3. Query newest matching scenes
    scenes = query_matching_sentinel1_scenes(DEFAULT_AOI, access_token=token, limit=25)

    if not scenes:
        print("[Ingestion] No matching scenes returned from CDSE catalogue.")
        write_github_output("new_scene", "false")
        sys.exit(0)

    newest = scenes[0]
    scene_id = newest.get("Name", "")
    product_id = newest.get("Id", "")
    content_date = newest.get("ContentDate", {}).get("Start", "")

    print(f"\nLatest Matching Scene:  {scene_id}")
    print(f"Acquisition Timestamp:  {content_date}")
    print(f"Last Processed Scene:   {last_processed_id or 'None'}")

    # 4. Compare latest scene ID to last_processed_scene_id
    if last_processed_id and (scene_id == last_processed_id or scene_id in str(last_processed_id)):
        print("\n[OK] State: UP_TO_DATE. No new scene available since last satellite pass.")
        write_github_output("new_scene", "false")
        sys.exit(0)

    # New scene detected!
    print(f"\n[ALERT] State: NEW_SCENE_AVAILABLE! Proceeding with download...")
    write_github_output("new_scene", "true")
    write_github_output("scene_id", scene_id)
    write_github_output("scene_date", content_date)

    # 5. Ensure baseline 'before' scene is present
    before_dir = os.path.join("data", "before")
    if not has_measurement_tiff(before_dir):
        print(f"[Ingestion] Baseline 'before' scene missing in {before_dir}. Searching catalogue...")
        baseline_query_url = f"{CATALOGUE_URL}?$filter=contains(Name, '{BASELINE_SCENE_ID}')"
        b_resp = requests.get(baseline_query_url, headers={"Authorization": f"Bearer {token}"}, timeout=25)
        if b_resp.status_code == 200 and b_resp.json().get("value"):
            baseline_prod_id = b_resp.json()["value"][0]["Id"]
            print(f"[Ingestion] Found baseline product ID {baseline_prod_id}. Downloading...")
            download_and_extract_product(baseline_prod_id, before_dir, token)
        else:
            print(f"[Ingestion Warning] Could not find baseline product {BASELINE_SCENE_ID} in catalogue.")

    # 6. Download new 'during' scene
    during_dir = os.path.join("data", "during")
    # Clean previous during folder if present
    import shutil
    if os.path.exists(during_dir):
        shutil.rmtree(during_dir, ignore_errors=True)
    os.makedirs(during_dir, exist_ok=True)

    print(f"[Ingestion] Downloading new scene {scene_id} into {during_dir}...")
    download_and_extract_product(product_id, during_dir, token)

    print("\n[Ingestion Complete] Raw Sentinel-1 SAR scene ready for change detection.")


if __name__ == "__main__":
    main()
