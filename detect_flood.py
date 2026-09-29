"""
============================================================
STAGE 2: SENTINEL-1 SAR FLOOD DETECTION & VECTORIZATION
============================================================
Processes before/during Sentinel-1 SAR GRDH GeoTIFF rasters using
log-ratio backscatter change detection, spatial filtering, and
vectorization into EPSG:4326 GeoJSON polygons.

Memory Guard:
- Uses 32-bit floating point arrays and explicit garbage collection
  to keep total memory footprint well under 200 MB (well below 7 GB limit).
- Dynamically discovers input measurement TIFFs from data/before and data/during.
- Updates data/manifest.json with latest scene ID, timestamp, and metrics.
============================================================
"""

import os
import sys
import gc
import glob
import json
import shutil
from datetime import datetime, timezone
import numpy as np
import rasterio
from rasterio.features import shapes
from affine import Affine
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import binary_opening, binary_closing, label

MANIFEST_PATH = os.path.join("data", "manifest.json")
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)


def find_vv_measurement_tiff(folder):
    """Dynamically finds the VV polarization measurement TIFF in a directory."""
    patterns = [
        os.path.join(folder, "**", "measurement", "*-vv-*.tiff"),
        os.path.join(folder, "**", "measurement", "*-vv-*.tif"),
        os.path.join(folder, "**", "*-vv-*.tiff"),
        os.path.join(folder, "**", "*-vv-*.tif"),
        os.path.join(folder, "**", "*.tiff"),
        os.path.join(folder, "**", "*.tif"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return os.path.abspath(matches[0])
    return None


def get_scene_info_from_path(during_file_path):
    """Extracts scene name and acquisition date from SAFE directory path or filename."""
    # Look for *.SAFE folder in path
    parts = during_file_path.replace("\\", "/").split("/")
    safe_folder = next((p for p in parts if p.endswith(".SAFE")), None)
    
    if safe_folder:
        scene_id = safe_folder
    else:
        scene_id = os.path.basename(during_file_path).split(".")[0]

    # Parse ISO acquisition date from standard Sentinel-1 naming (e.g. 20240711T115715)
    scene_date = None
    for token in scene_id.split("_"):
        if len(token) == 15 and token[8] == "T" and token[:8].isdigit() and token[9:].isdigit():
            try:
                dt = datetime.strptime(token, "%Y%m%dT%H%M%S")
                scene_date = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                break
            except Exception:
                pass

    if not scene_date:
        scene_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return scene_id, scene_date


def main():
    print("=" * 60)
    print("SENTINEL-1 SAR FLOOD DETECTION ENGINE")
    print("=" * 60)

    # 1. Locate measurement TIFFs
    before_file = find_vv_measurement_tiff(os.path.join("data", "before"))
    during_file = find_vv_measurement_tiff(os.path.join("data", "during"))

    # Fallbacks if running with existing staged dataset
    if not before_file:
        fallback_before = r"data\before\S1A_IW_GRDH_1SDV_20240629T115716_20240629T115741_054538_06A32B_151F.SAFE\measurement\s1a-iw-grd-vv-20240629t115716-20240629t115741-054538-06a32b-001.tiff"
        if os.path.exists(fallback_before):
            before_file = fallback_before

    if not during_file:
        fallback_during = r"data\during\S1A_IW_GRDH_1SDV_20240711T115715_20240711T115740_054713_06A943_F0AD.SAFE\measurement\s1a-iw-grd-vv-20240711t115715-20240711t115740-054713-06a943-001.tiff"
        if os.path.exists(fallback_during):
            during_file = fallback_during

    if not before_file or not os.path.exists(before_file):
        print(f"ERROR: Before baseline TIFF not found in data/before.")
        sys.exit(1)

    if not during_file or not os.path.exists(during_file):
        print(f"ERROR: During flood candidate TIFF not found in data/during.")
        sys.exit(1)

    print(f"Before File: {before_file}")
    print(f"During File: {during_file}")

    scene_id, scene_date = get_scene_info_from_path(during_file)
    print(f"Detected Scene ID:   {scene_id}")
    print(f"Acquisition Date:    {scene_date}")

    # Target resampled grid (2000 x 3000) keeps memory ~24 MB per array
    target_shape = (1, 2000, 3000)

    # 2. Read Before Image (Windowed / Resampled with float32)
    print("\nReading BEFORE raster...")
    with rasterio.open(before_file) as src:
        before = src.read(1, out_shape=target_shape).astype(np.float32)
        
        if src.crs is not None:
            original_transform = src.transform
            crs = src.crs
        elif src.gcps[0]:
            gcps, gcp_crs = src.gcps
            original_transform = rasterio.transform.from_gcps(gcps)
            crs = gcp_crs
        else:
            raise ValueError("No CRS and no GCPs found in before image.")

        transform = original_transform * Affine.scale(src.width / 3000, src.height / 2000)

    # 3. Read During Image (Windowed / Resampled with float32)
    print("Reading DURING raster...")
    with rasterio.open(during_file) as src:
        during = src.read(1, out_shape=target_shape).astype(np.float32)

    if before.shape != during.shape:
        raise ValueError(f"Images have different shapes: {before.shape} vs {during.shape}")

    # 4. Remove invalid values and convert to dB
    print("Computing SAR backscatter change...")
    before[before <= 0] = np.nan
    during[during <= 0] = np.nan

    before_db = 10 * np.log10(before)
    during_db = 10 * np.log10(during)

    # Immediately release raw linear arrays
    del before, during
    gc.collect()

    change_db = during_db - before_db

    # 5. Save visual change PNGs (downsampled visualization)
    print("Generating visual preview images...")
    plt.figure(figsize=(10, 6))
    plt.imshow(change_db, cmap="RdBu_r", vmin=-5, vmax=5)
    plt.colorbar(label="Backscatter Change (dB)")
    plt.title(f"SAR Change Detection: {scene_date[:10]}")
    plt.axis("off")
    plt.savefig(os.path.join(OUTPUT_DIR, "sar_change.png"), dpi=120, bbox_inches="tight")
    plt.close()

    # Free dB arrays
    del before_db, during_db
    gc.collect()

    # 6. Flood Mask Detection (Thresholding & Morphological Filtering)
    print("Detecting and filtering flood extent...")
    THRESHOLD = -1.0
    flood_mask = change_db < THRESHOLD
    flood_mask[np.isnan(change_db)] = False

    del change_db
    gc.collect()

    # Binary opening and closing
    flood_clean = binary_opening(flood_mask, structure=np.ones((3, 3)))
    flood_clean = binary_closing(flood_clean, structure=np.ones((5, 5)))
    del flood_mask
    gc.collect()

    # Remove small isolated pixel groups (<100 pixels)
    labeled, num_features = label(flood_clean)
    clean_final = np.zeros_like(flood_clean, dtype=bool)
    MIN_PIXELS = 100

    for region_id in range(1, num_features + 1):
        region = (labeled == region_id)
        if np.sum(region) >= MIN_PIXELS:
            clean_final |= region

    del labeled, flood_clean
    gc.collect()

    flood_clean = clean_final.astype("uint8")

    # 7. Write Georeferenced Mask GeoTIFF
    mask_tif_path = os.path.join(OUTPUT_DIR, "flood_mask.tif")
    with rasterio.open(
        mask_tif_path,
        "w",
        driver="GTiff",
        height=flood_clean.shape[0],
        width=flood_clean.shape[1],
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform
    ) as dst:
        dst.write(flood_clean, 1)

    print(f"Saved: {mask_tif_path}")

    # 8. Vectorize GeoTIFF to GeoJSON Polygons
    print("Vectorizing flood mask to GeoJSON polygons...")
    with rasterio.open(mask_tif_path) as src:
        mask = src.read(1)
        geo_transform = src.transform
        geo_crs = src.crs

    results = (
        {"properties": {"flooded": int(value)}, "geometry": geom}
        for geom, value in shapes(mask, transform=geo_transform, mask=(mask == 1))
    )

    gdf = gpd.GeoDataFrame.from_features(results, crs=geo_crs)
    del mask, flood_clean
    gc.collect()

    flooded_area_km2 = 0.0
    if len(gdf) > 0:
        # Reproject to WGS84 for GeoJSON web standard
        gdf = gdf.to_crs("EPSG:4326")
        gdf["geometry"] = gdf.geometry.simplify(0.0001)

        # Compute area in metric CRS
        gdf_proj = gdf.to_crs("EPSG:3857")
        flooded_area_km2 = round(gdf_proj.geometry.area.sum() / 1e6, 2)
        print(f"Detected {len(gdf)} flood polygons covering {flooded_area_km2} km².")
    else:
        print("Warning: No flood polygons detected above threshold.")

    # 9. Save GeoJSON outputs to all required paths
    primary_geojson = os.path.join(OUTPUT_DIR, "flood_extent.geojson")
    data_geojson = os.path.join("data", "flood_extent.geojson")
    root_geojson = "flood_extent.geojson"

    gdf.to_file(primary_geojson, driver="GeoJSON")
    shutil.copyfile(primary_geojson, data_geojson)
    shutil.copyfile(primary_geojson, root_geojson)
    print(f"Saved: {primary_geojson}")
    print(f"Saved: {data_geojson}")
    print(f"Saved: {root_geojson}")

    # 10. Update data/manifest.json
    print("\nUpdating data/manifest.json...")
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    processed_now = datetime.now(timezone.utc).isoformat()
    manifest["last_processed_scene_id"] = scene_id
    manifest["last_scene_date"] = scene_date
    manifest["last_check_timestamp"] = processed_now

    history = manifest.get("history", [])
    # Append to history if not already recorded
    if not any(h.get("scene_id") == scene_id for h in history):
        history.append({
            "scene_id": scene_id,
            "acquisition_date": scene_date,
            "processed_timestamp": processed_now,
            "flooded_area_km2": flooded_area_km2,
            "status": "PROCESSED",
            "output_geojson": "data/flood_extent.geojson"
        })
    manifest["history"] = history

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Successfully updated manifest state in {MANIFEST_PATH}.")
    print("\n[SUCCESS] Pipeline processing completed.")


if __name__ == "__main__":
    main()