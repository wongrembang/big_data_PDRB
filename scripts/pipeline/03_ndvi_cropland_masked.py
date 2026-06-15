# -*- coding: utf-8 -*-
"""
pilot3_ndvi_cropland_masked.py
================================
Menghitung NDVI per kecamatan per triwulan, di-MASK hanya pada area
"Cropland" menurut ESA WorldCover (2021, 10m resolution), supaya NDVI
lebih merepresentasikan lahan pertanian (bukan hutan/permukiman/badan air
yang ikut terhitung di rata-rata kabupaten sebelumnya).

ESA WorldCover kelas 40 = "Cropland" (mencakup sawah, lahan kering
pertanian, perkebunan semusim - tidak membedakan jenis tanaman spesifik,
tapi memisahkan dari hutan/permukiman/air).

PENTING - keterbatasan:
  - ESA WorldCover hanya 1 snapshot (2021), dipakai sebagai mask STATIS
    untuk seluruh periode 2017-2026. Jika ada perubahan tutupan lahan
    signifikan (alih fungsi lahan), mask ini tidak menangkapnya.
  - Kelas "Cropland" tidak membedakan padi vs jagung vs tebu - hanya
    memisahkan lahan pertanian dari non-pertanian.
  - Hanya dijalankan untuk periode Sentinel-2 (2017+) karena resolusi
    mask (10m) match dengan Sentinel-2.

Cara jalankan:
  python pilot3_ndvi_cropland_masked.py

Membutuhkan:
  - batas_kecamatan_rembang.geojson

Output:
  - ndvi_cropland_masked_2017_2026.csv
    Kolom: kecamatan, periode, ndvi_cropland_mean, ndvi_unmasked_mean,
           cropland_pct (persentase area cropland dalam kecamatan)
"""

import ee
import geopandas as gpd
import pandas as pd
import shapely
import time

ee.Initialize(project='pdrb-big-data-extraction')

# ---------------------------------------------------------------------------
# 1. Load boundary
# ---------------------------------------------------------------------------
gdf = gpd.read_file("batas_kecamatan_rembang_simplified.geojson")
if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)
gdf["geometry"] = gdf["geometry"].simplify(0.0001, preserve_topology=True)
gdf["geometry"] = gdf["geometry"].apply(lambda g: shapely.force_2d(g))

features = []
for _, row in gdf.iterrows():
    geom = ee.Geometry(row.geometry.__geo_interface__)
    features.append(ee.Feature(geom, {"kecamatan": row["kecamatan"]}))
kec_fc = ee.FeatureCollection(features)
KECAMATAN_LIST = list(gdf["kecamatan"])

# ---------------------------------------------------------------------------
# 2. ESA WorldCover - cropland mask (kelas 40)
# ---------------------------------------------------------------------------
worldcover = ee.ImageCollection("ESA/WorldCover/v200").first()
cropland_mask = worldcover.select("Map").eq(40)

# Hitung persentase cropland per kecamatan (sekali saja, statis)
cropland_pct_result = cropland_mask.rename("is_cropland").reduceRegions(
    collection=kec_fc, reducer=ee.Reducer.mean(), scale=10
).getInfo()
cropland_pct_map = {f["properties"]["kecamatan"]: f["properties"].get("mean", 0) * 100
                     for f in cropland_pct_result["features"]}

print("Persentase area Cropland per kecamatan (ESA WorldCover 2021):")
for kec, pct in sorted(cropland_pct_map.items(), key=lambda x: -x[1]):
    print(f"  {kec}: {pct:.1f}%")

# ---------------------------------------------------------------------------
# 3. Periode (Sentinel-2 era only: 2017Q2 - 2026Q2)
# ---------------------------------------------------------------------------
def build_periode_list(start_year=2017, start_q=2, end_year=2026, end_q=2):
    quarter_months = {1: ("01-01", "03-31"), 2: ("04-01", "06-30"),
                       3: ("07-01", "09-30"), 4: ("10-01", "12-31")}
    periode = {}
    for year in range(start_year, end_year + 1):
        q_start = start_q if year == start_year else 1
        q_end = end_q if year == end_year else 4
        for q in range(q_start, q_end + 1):
            start_md, end_md = quarter_months[q]
            periode[f"{year}Q{q}"] = (f"{year}-{start_md}", f"{year}-{end_md}")
    return periode

PERIODE = build_periode_list()
print(f"\nTotal periode: {len(PERIODE)} ({list(PERIODE.keys())[0]} - {list(PERIODE.keys())[-1]})")

# ---------------------------------------------------------------------------
# 4. NDVI per periode - dengan dan tanpa mask cropland
# ---------------------------------------------------------------------------
def get_ndvi_image(start, end):
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(kec_fc)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )
    n = coll.size().getInfo()
    if n == 0:
        return None
    img = coll.map(lambda i: i.normalizedDifference(["B8", "B4"]).rename("NDVI")).select("NDVI").mean()
    return img


def zonal_mean(image, band_name, scale=10):
    stats = image.rename(band_name).reduceRegions(
        collection=kec_fc, reducer=ee.Reducer.mean(), scale=scale
    ).getInfo()
    return {f["properties"]["kecamatan"]: f["properties"].get("mean") for f in stats["features"]}


if __name__ == "__main__":
    all_rows = []
    for label, (start, end) in PERIODE.items():
        t0 = time.time()
        ndvi_img = get_ndvi_image(start, end)
        if ndvi_img is None:
            for kec in KECAMATAN_LIST:
                all_rows.append({
                    "kecamatan": kec, "periode": label,
                    "ndvi_unmasked_mean": None, "ndvi_cropland_mean": None,
                    "cropland_pct": cropland_pct_map.get(kec),
                })
            print(f"[{label}] no_data")
            continue

        unmasked_map = zonal_mean(ndvi_img, "ndvi")
        masked_img = ndvi_img.updateMask(cropland_mask)
        masked_map = zonal_mean(masked_img, "ndvi")

        for kec in KECAMATAN_LIST:
            all_rows.append({
                "kecamatan": kec, "periode": label,
                "ndvi_unmasked_mean": unmasked_map.get(kec),
                "ndvi_cropland_mean": masked_map.get(kec),
                "cropland_pct": cropland_pct_map.get(kec),
            })
        print(f"[{label}] selesai ({time.time()-t0:.1f}s)")

    result = pd.DataFrame(all_rows)
    result.to_csv("ndvi_cropland_masked_2017_2026.csv", index=False)
    print(f"\nDisimpan: ndvi_cropland_masked_2017_2026.csv ({len(result)} baris)")
