import os
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from scipy.ndimage import binary_opening, binary_closing, label
from rasterio.features import shapes
import geopandas as gpd
from affine import Affine


# ============================================================
# FILE PATHS
# ============================================================

before_file = r"data\before\S1A_IW_GRDH_1SDV_20240629T115716_20240629T115741_054538_06A32B_151F.SAFE\measurement\s1a-iw-grd-vv-20240629t115716-20240629t115741-054538-06a32b-001.tiff"

during_file = r"data\during\S1A_IW_GRDH_1SDV_20240711T115715_20240711T115740_054713_06A943_F0AD.SAFE\measurement\s1a-iw-grd-vv-20240711t115715-20240711t115740-054713-06a943-001.tiff"


# ============================================================
# CREATE OUTPUT FOLDER
# ============================================================

os.makedirs("output", exist_ok=True)


# ============================================================
# READ BEFORE IMAGE
# ============================================================

print("Reading BEFORE...")

with rasterio.open(before_file) as src:

    before = src.read(
        1,
        out_shape=(1, 2000, 3000)
    ).astype(float)

    # Sentinel-1 raw tiffs usually have NO embedded CRS/transform.
    # Instead they carry Ground Control Points (GCPs) which we
    # use to build an approximate transform ourselves.

    if src.crs is not None:
        # Normal case - CRS already embedded in the file
        original_transform = src.transform
        crs = src.crs
        print("Found embedded CRS.")
    elif src.gcps[0]:
        # Sentinel-1 case - build transform from Ground Control Points
        gcps, gcp_crs = src.gcps
        original_transform = rasterio.transform.from_gcps(gcps)
        crs = gcp_crs
        print("No embedded CRS found - built transform from GCPs instead.")
    else:
        raise ValueError(
            "No CRS and no GCPs found in this file - "
            "cannot georeference this image."
        )

    # Correct the transform for the resized (out_shape) image
    transform = original_transform * Affine.scale(
        src.width / 3000,
        src.height / 2000
    )

print("BEFORE image loaded!")
print("Shape:", before.shape)
print("CRS:", crs)


# ============================================================
# READ DURING IMAGE
# ============================================================

print("\nReading DURING...")

with rasterio.open(during_file) as src:

    during = src.read(
        1,
        out_shape=(1, 2000, 3000)
    ).astype(float)

print("DURING image loaded!")
print("Shape:", during.shape)


# ============================================================
# BASIC SAFETY CHECK
# ============================================================

if before.shape != during.shape:
    raise ValueError(
        f"Images have different shapes: "
        f"{before.shape} vs {during.shape}"
    )


# ============================================================
# REMOVE INVALID VALUES
# ============================================================

before[before <= 0] = np.nan
during[during <= 0] = np.nan


# ============================================================
# CONVERT TO dB
# ============================================================

print("\nConverting to dB...")

before_db = 10 * np.log10(before)
during_db = 10 * np.log10(during)


# ============================================================
# CALCULATE SAR CHANGE
# ============================================================

print("Calculating SAR change...")

# Change in backscatter
change_db = during_db - before_db


# ============================================================
# SAVE BEFORE IMAGE
# ============================================================

plt.figure(figsize=(12, 8))

plt.imshow(
    before_db,
    cmap="gray",
    vmin=np.nanpercentile(before_db, 2),
    vmax=np.nanpercentile(before_db, 98)
)

plt.title("BEFORE FLOOD - 29 June 2024")
plt.axis("off")

plt.savefig(
    "output/before_flood.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# SAVE DURING IMAGE
# ============================================================

plt.figure(figsize=(12, 8))

plt.imshow(
    during_db,
    cmap="gray",
    vmin=np.nanpercentile(during_db, 2),
    vmax=np.nanpercentile(during_db, 98)
)

plt.title("DURING FLOOD - 11 July 2024")
plt.axis("off")

plt.savefig(
    "output/during_flood.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# SAVE SAR CHANGE IMAGE
# ============================================================

plt.figure(figsize=(12, 8))

plt.imshow(
    change_db,
    cmap="RdBu_r",
    vmin=-5,
    vmax=5
)

plt.colorbar(label="Backscatter Change (dB)")

plt.title("SAR Change Detection - June 29 -> July 11")

plt.axis("off")

plt.savefig(
    "output/sar_change.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# FLOOD DETECTION
# ============================================================

print("\nDetecting flooded areas...")

# Flooded water generally produces a decrease in
# radar backscatter compared with normal land.
#
# Threshold can be adjusted.
# More negative = stricter
# Less negative = more sensitive

THRESHOLD = -1.0

flood_mask = (
    change_db < THRESHOLD
)

# Remove invalid pixels
flood_mask[np.isnan(change_db)] = False


# ============================================================
# CLEAN FLOOD MASK
# ============================================================

print("Cleaning flood mask...")

# Remove very small noisy regions
flood_clean = binary_opening(
    flood_mask,
    structure=np.ones((3, 3))
)

# Fill small gaps
flood_clean = binary_closing(
    flood_clean,
    structure=np.ones((5, 5))
)


# ============================================================
# REMOVE VERY SMALL OBJECTS
# ============================================================

labeled, num_features = label(flood_clean)

print("Initial detected regions:", num_features)

clean_final = np.zeros_like(flood_clean, dtype=bool)

MIN_PIXELS = 100

for region_id in range(1, num_features + 1):

    region = labeled == region_id

    if np.sum(region) >= MIN_PIXELS:
        clean_final |= region

flood_clean = clean_final


# ============================================================
# SAVE RAW FLOOD DETECTION PNG
# ============================================================

plt.figure(figsize=(12, 8))

plt.imshow(
    flood_mask,
    cmap="gray"
)

plt.title("Detected Flood Extent - 11 July 2024")

plt.xlabel("Satellite Image X")
plt.ylabel("Satellite Image Y")

plt.savefig(
    "output/flood_detected.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# SAVE CLEAN FLOOD MASK PNG
# ============================================================

plt.figure(figsize=(12, 8))

plt.imshow(
    flood_clean,
    cmap="gray"
)

plt.title("Cleaned Flood Extent - 11 July 2024")

plt.xlabel("Satellite Image X")
plt.ylabel("Satellite Image Y")

plt.savefig(
    "output/flood_clean.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# SAVE GEOREFERENCED FLOOD MASK
# ============================================================

print("\nSaving georeferenced flood mask...")

flood_mask_uint8 = flood_clean.astype("uint8")

with rasterio.open(
    "output/flood_mask.tif",
    "w",
    driver="GTiff",
    height=flood_mask_uint8.shape[0],
    width=flood_mask_uint8.shape[1],
    count=1,
    dtype="uint8",
    crs=crs,
    transform=transform
) as dst:

    dst.write(
        flood_mask_uint8,
        1
    )

print("Saved: output/flood_mask.tif")


# ============================================================
# CONVERT GEOTIFF -> GEOJSON
# ============================================================

print("\nConverting flood mask to GeoJSON...")

with rasterio.open("output/flood_mask.tif") as src:

    mask = src.read(1)
    geo_transform = src.transform
    geo_crs = src.crs

print("CRS from GeoTIFF:", geo_crs)

if geo_crs is None:
    raise ValueError(
        "flood_mask.tif has no CRS. This means 'crs' was None "
        "when it was written above - check the BEFORE image "
        "reading step (CRS/GCP handling) ran correctly."
    )

results = (
    {
        "properties": {"flooded": int(value)},
        "geometry": geometry
    }
    for geometry, value in shapes(
        mask,
        transform=geo_transform,
        mask=(mask == 1)
    )
)

gdf = gpd.GeoDataFrame.from_features(
    results,
    crs=geo_crs
)

if len(gdf) == 0:
    print("WARNING: No flood polygons were detected. "
          "Try lowering THRESHOLD (make it less negative) "
          "and re-run.")
else:
    print("Reprojecting to EPSG:4326...")

    gdf = gdf.to_crs("EPSG:4326")

    gdf["geometry"] = gdf.geometry.simplify(0.0001)

    gdf.to_file(
        "output/flood_extent.geojson",
        driver="GeoJSON"
    )

    print("Saved: output/flood_extent.geojson")


# ============================================================
# SANITY CHECK
# ============================================================

print("\n==============================")
print("SANITY CHECK")
print("==============================")

print("CRS:", gdf.crs)
print("Total bounds:", gdf.total_bounds)
print("Number of flood polygons:", len(gdf))

print("==============================")


# ============================================================
# FINAL MESSAGE
# ============================================================

print("\nSUCCESS!")
print("All output files are in the 'output' folder.")

print("\nFiles created:")
print("1. output/before_flood.png")
print("2. output/during_flood.png")
print("3. output/sar_change.png")
print("4. output/flood_detected.png")
print("5. output/flood_clean.png")
print("6. output/flood_mask.tif")
print("7. output/flood_extent.geojson")