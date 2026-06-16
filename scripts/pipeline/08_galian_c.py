# -*- coding: utf-8 -*-
"""
pilot6_galian_c.py
====================
Mendeteksi dan mengukur aktivitas pertambangan/penggalian (galian C:
batu kapur, pasir, tanah liat) di Kabupaten Rembang per kecamatan
per triwulan (2017Q2-2026Q2) menggunakan kombinasi indeks Sentinel-2.

INDIKATOR UTAMA:
  1. BSI (Bare Soil Index):
     BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
     Sentinel-2: (B11 + B4 - B8 - B2) / (B11 + B4 + B8 + B2)
     Nilai tinggi = tanah/batuan terbuka (lahan galian, jalan tanah, area
     konstruksi). Batu kapur punya BSI sangat tinggi karena refleksi putih
     di semua band.

  2. NDVI negatif/rendah di area yang seharusnya bervegetasi:
     Anomali NDVI rendah (< 0.1) di area bukan pantai = kemungkinan
     lahan terbuka karena galian, konstruksi, atau degredasi vegetasi.

  3. NDVI variability (standar deviasi antar scene):
     Area galian aktif cenderung punya NDVI berfluktuasi karena pengupasan
     tanah bertahap (naik turun sesuai fase penambangan).

  4. Limestone Spectral Signature: batu kapur punya refleksi tinggi di
     band Red dan SWIR tapi rendah di Green (berbeda dari pasir pantai
     yang tinggi di semua visible band). Indeks:
     Calcite/Kapur = B4/B3 (Red/Green ratio > 1.2 untuk batu kapur).

AREA FOKUS:
  Kecamatan dengan potensi galian C di Rembang berdasarkan geologi:
  - Gunem (batu kapur formasi Rembang)
  - Sale (batu kapur dan batupasir)
  - Bulu (batu kapur)
  - Sedan (tanah liat/lempung untuk bata)
  - Sarang (pasir sungai)

OUTPUT PER KECAMATAN PER TRIWULAN:
  - bsi_mean: rata-rata Bare Soil Index seluruh kecamatan
  - bsi_high_fraction: fraksi piksel dengan BSI > 0.05 (area terbuka/galian)
  - ndvi_low_fraction: fraksi piksel dengan NDVI < 0.1 (bukan pesisir/laut)
  - limestone_ratio_mean: rata-rata Red/Green ratio (indikasi batu kapur)
  - ndvi_stddev: standar deviasi NDVI antar scene (variabilitas aktivitas)

CARA JALANKAN:
  python pilot6_galian_c.py

OUTPUT:
  - galian_c_timeseries_2017_2026.csv
"""

import ee
import geopandas as gpd
import pandas as pd
import shapely
import time
import os

ee.Initialize(project='pdrb-big-data-extraction')

# ---------------------------------------------------------------------------
# 1. Load boundary
# ---------------------------------------------------------------------------
gdf = gpd.read_file("batas_kecamatan_rembang_simplified.geojson")
if gdf.crs and gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)
gdf["geometry"] = gdf["geometry"].apply(lambda g: shapely.force_2d(g))

features = []
for _, row in gdf.iterrows():
    geom = ee.Geometry(row.geometry.__geo_interface__)
    features.append(ee.Feature(geom, {"kecamatan": row["kecamatan"]}))
kec_fc = ee.FeatureCollection(features)
KECAMATAN_LIST = list(gdf["kecamatan"])

# ---------------------------------------------------------------------------
# 2. Periode triwulanan 2017Q2-2026Q2
# ---------------------------------------------------------------------------
def build_periode_list():
    quarter_months = {1: ("01-01","03-31"), 2: ("04-01","06-30"),
                      3: ("07-01","09-30"), 4: ("10-01","12-31")}
    periode = []
    for year in range(2017, 2027):
        q_start = 2 if year == 2017 else 1
        q_end = 2 if year == 2026 else 4
        for q in range(q_start, q_end + 1):
            s, e = quarter_months[q]
            periode.append((f"{year}Q{q}", f"{year}-{s}", f"{year}-{e}", year, q))
    return periode

PERIODE = build_periode_list()

# ---------------------------------------------------------------------------
# 3. Sentinel-2: BSI + NDVI + Limestone ratio
# ---------------------------------------------------------------------------
def get_mining_indices(start, end):
    coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))
    n = coll.size().getInfo()
    if n == 0:
        return None, 0

    def compute_indices(img):
        # Scale reflectance
        scaled = img.select(["B2","B3","B4","B8","B11"]).divide(10000)
        B2 = scaled.select("B2")   # Blue
        B3 = scaled.select("B3")   # Green
        B4 = scaled.select("B4")   # Red
        B8 = scaled.select("B8")   # NIR
        B11 = scaled.select("B11") # SWIR1

        # BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
        bsi = (B11.add(B4).subtract(B8.add(B2))
               .divide(B11.add(B4).add(B8).add(B2))
               .rename("BSI"))

        # NDVI = (NIR - Red) / (NIR + Red)
        ndvi = B8.subtract(B4).divide(B8.add(B4)).rename("NDVI")

        # Red/Green ratio - tinggi untuk batu kapur/mineral terang
        limestone = B4.divide(B3.add(ee.Number(0.0001))).rename("limestone_ratio")

        return ee.Image.cat([bsi, ndvi, limestone])

    composite_mean = coll.map(compute_indices).mean()
    # NDVI std dev sebagai ukuran variabilitas
    ndvi_only = coll.map(lambda img: img.normalizedDifference(["B8","B4"]).rename("NDVI"))
    ndvi_stddev = ndvi_only.reduce(ee.Reducer.stdDev()).rename("NDVI_stddev")

    return ee.Image.cat([composite_mean, ndvi_stddev]), n

# ---------------------------------------------------------------------------
# 4. Zonal stats
# ---------------------------------------------------------------------------
def zonal_mean(image, band, scale=10):
    stats = image.select(band).rename("val").reduceRegions(
        collection=kec_fc, reducer=ee.Reducer.mean(), scale=scale
    ).getInfo()
    return {f["properties"]["kecamatan"]: f["properties"].get("mean")
            for f in stats["features"]}

def zonal_fraction(image, band, lo=None, hi=None, scale=10):
    """Fraksi piksel dalam rentang [lo, hi] (lo/hi bisa None untuk open-ended)."""
    img = image.select(band)
    if lo is not None and hi is not None:
        mask = img.gt(lo).And(img.lt(hi))
    elif lo is not None:
        mask = img.gt(lo)
    else:
        mask = img.lt(hi)
    stats = mask.rename("val").reduceRegions(
        collection=kec_fc, reducer=ee.Reducer.mean(), scale=scale
    ).getInfo()
    return {f["properties"]["kecamatan"]: f["properties"].get("mean")
            for f in stats["features"]}

# ---------------------------------------------------------------------------
# 5. Main loop
# ---------------------------------------------------------------------------
OUTPUT = "galian_c_timeseries_2017_2026.csv"
done = set()
if os.path.exists(OUTPUT):
    existing = pd.read_csv(OUTPUT)
    done = set(existing["periode"].unique())
    print(f"Resume: {len(done)} periode sudah selesai")

write_header = not os.path.exists(OUTPUT)
rows_buffer = []

for label, start, end, year, quarter in PERIODE:
    if label in done:
        continue
    t0 = time.time()
    print(f"\n[{label}] Memproses...")

    img, n_s2 = get_mining_indices(start, end)

    for kec in KECAMATAN_LIST:
        row = {
            "kecamatan": kec, "periode": label,
            "tahun": year, "triwulan": quarter,
            "n_s2_scenes": n_s2,
        }
        if img is not None:
            try:
                row["bsi_mean"] = round(zonal_mean(img, "BSI").get(kec) or 0, 4)
                row["bsi_high_fraction"] = round(zonal_fraction(img, "BSI", lo=0.05).get(kec) or 0, 4)
                row["ndvi_mean"] = round(zonal_mean(img, "NDVI").get(kec) or 0, 4)
                row["ndvi_low_fraction"] = round(zonal_fraction(img, "NDVI", hi=0.1).get(kec) or 0, 4)
                row["limestone_ratio_mean"] = round(zonal_mean(img, "limestone_ratio").get(kec) or 0, 4)
                row["ndvi_stddev"] = round(zonal_mean(img, "NDVI_stddev").get(kec) or 0, 4)
            except Exception as e:
                print(f"  Error [{kec}]: {e}")
                for col in ["bsi_mean","bsi_high_fraction","ndvi_mean",
                            "ndvi_low_fraction","limestone_ratio_mean","ndvi_stddev"]:
                    row[col] = None
        else:
            for col in ["bsi_mean","bsi_high_fraction","ndvi_mean",
                        "ndvi_low_fraction","limestone_ratio_mean","ndvi_stddev"]:
                row[col] = None

        rows_buffer.append(row)

    df_buf = pd.DataFrame(rows_buffer)
    df_buf.to_csv(OUTPUT, mode="a", header=write_header, index=False)
    rows_buffer = []
    write_header = False
    print(f"  Selesai ({time.time()-t0:.1f}s) | {n_s2} scene")

print(f"\nOutput: {OUTPUT}")
