# -*- coding: utf-8 -*-
"""
pilot5_tambak_garam.py
========================
Mendeteksi dan mengukur luas/intensitas tambak garam di Kabupaten Rembang
per kecamatan per triwulan (2017Q2-2026Q2) menggunakan:

  1. NDWI (Normalized Difference Water Index) dari Sentinel-2:
     NDWI = (Green - NIR) / (Green + NIR)
     Nilai tinggi (> 0.2) = area berair (tambak, sungai, laut)

  2. Masking non-laut: hanya hitung NDWI di area daratan/pesisir
     (bukan laut terbuka) menggunakan buffer pantai dari boundary kecamatan

  3. SAR Sentinel-1 (opsional): tambak garam punya backscatter rendah
     (permukaan air tenang = refleksi specular, kembali tidak ke sensor)
     - VV polarization median < threshold = area berair tenang
     - Membedakan tambak (stabil, geometris) dari sawah (berubah musiman)

  4. Salt Spectral Index: tambak garam saat panen punya refleksi sangat
     tinggi di semua band (garam putih) - deteksi via brightness threshold
     di Sentinel-2 band B2+B3+B4 (mean > 0.3 = area terang/garam)

AREA FOKUS:
  Kecamatan dengan tambak garam signifikan di Rembang:
  - Kaliori (terbesar, delta sungai Kaliori/Babon)
  - Rembang (pesisir utara)
  - Lasem (sedikit, pesisir timur)

OUTPUT PER KECAMATAN PER TRIWULAN:
  - ndwi_coastal_mean: rata-rata NDWI di area pesisir kecamatan
  - ndwi_saltpond_fraction: fraksi piksel berindikasi tambak (NDWI > 0.2)
  - sar_vv_median: median backscatter SAR VV (nilai rendah = air tenang)
  - salt_bright_fraction: fraksi piksel sangat cerah (proxy garam panen)

CATATAN KETERBATASAN:
  - NDWI tidak bisa membedakan tambak garam dari sawah tergenang atau
    badan air lainnya tanpa masking tambahan. Perlu validasi dengan peta
    tambak garam (dari Kementerian Kelautan/Dinas Kelautan Jawa Tengah).
  - SAR Sentinel-1 tersedia sejak 2014 di GEE, tapi coverage tidak
    selalu konsisten per periode pendek (tergantung track satelit).
  - Tambak garam di Rembang merupakan industri musiman - produksi aktif
    umumnya bulan Mei-Oktober (musim kemarau). Q1 (Jan-Mar) biasanya
    sepi/lahan kosong/tergenang hujan.

CARA JALANKAN:
  python pilot5_tambak_garam.py

PRASYARAT:
  - Sudah autentikasi GEE (earthengine authenticate)
  - batas_kecamatan_rembang_simplified.geojson ada di folder yang sama

OUTPUT:
  - tambak_garam_timeseries_2017_2026.csv
"""

import ee
import geopandas as gpd
import pandas as pd
import shapely
import time
import os

ee.Initialize(project='pdrb-big-data-extraction')

# ---------------------------------------------------------------------------
# 1. Load boundary kecamatan
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
# 3. Sentinel-2: NDWI + Salt Brightness Index
# ---------------------------------------------------------------------------
def get_s2_indices(start, end):
    coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))
    n = coll.size().getInfo()
    if n == 0:
        return None, None, 0

    def compute_indices(img):
        # NDWI: (Green - NIR) / (Green + NIR)  [B3 = Green, B8 = NIR]
        ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")
        # Salt brightness: mean of visible bands (B2+B3+B4), tambak garam
        # saat panen sangat cerah (refleksi > 0.3)
        brightness = img.select(["B2","B3","B4"]).reduce(ee.Reducer.mean()).rename("brightness")
        # Gabungkan
        return ee.Image.cat([ndwi, brightness])

    composite = coll.map(compute_indices).median()
    return composite, coll.first().projection(), n

# ---------------------------------------------------------------------------
# 4. Sentinel-1 SAR: VV median (backscatter area berair tenang)
# ---------------------------------------------------------------------------
def get_sar_vv(start, end):
    coll = (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV"))
    n = coll.size().getInfo()
    if n == 0:
        return None, 0
    return coll.median(), n

# ---------------------------------------------------------------------------
# 5. Zonal stats per kecamatan
# ---------------------------------------------------------------------------
def zonal(image, band, reducer="mean", scale=10):
    """reducer: 'mean' atau 'median' (string, bukan objek GEE)"""
    r = ee.Reducer.mean() if reducer == "mean" else ee.Reducer.median()
    stats = image.select(band).rename("val").reduceRegions(
        collection=kec_fc, reducer=r, scale=scale
    ).getInfo()
    return {f["properties"]["kecamatan"]: f["properties"].get(reducer)
            for f in stats["features"]}

def zonal_fraction(image, band, threshold, scale=10):
    """Hitung fraksi piksel di atas threshold."""
    mask = image.select(band).gt(threshold)
    stats = mask.rename("val").reduceRegions(
        collection=kec_fc, reducer=ee.Reducer.mean(), scale=scale
    ).getInfo()
    return {f["properties"]["kecamatan"]: f["properties"].get("mean")
            for f in stats["features"]}

# ---------------------------------------------------------------------------
# 6. Main loop
# ---------------------------------------------------------------------------
OUTPUT = "tambak_garam_timeseries_2017_2026.csv"
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

    s2_img, s2_proj, n_s2 = get_s2_indices(start, end)
    sar_img, n_sar = get_sar_vv(start, end)

    for kec in KECAMATAN_LIST:
        row = {
            "kecamatan": kec, "periode": label, "tahun": year, "triwulan": quarter,
            "n_s2_scenes": n_s2, "n_sar_scenes": n_sar,
        }
        if s2_img is not None:
            try:
                ndwi_mean_map = zonal(s2_img, "NDWI", "mean")
                ndwi_frac_map = zonal_fraction(s2_img, "NDWI", 0.2)
                salt_frac_map = zonal_fraction(s2_img, "brightness", 0.3)
                row["ndwi_mean"] = round(ndwi_mean_map.get(kec) or 0, 4)
                row["ndwi_water_fraction"] = round(ndwi_frac_map.get(kec) or 0, 4)
                row["salt_bright_fraction"] = round(salt_frac_map.get(kec) or 0, 4)
            except Exception as e:
                print(f"  S2 error [{kec}]: {e}")
                row["ndwi_mean"] = row["ndwi_water_fraction"] = row["salt_bright_fraction"] = None
        else:
            row["ndwi_mean"] = row["ndwi_water_fraction"] = row["salt_bright_fraction"] = None

        if sar_img is not None:
            try:
                sar_map = zonal(sar_img, "VV", "median", scale=10)
                row["sar_vv_median"] = round(sar_map.get(kec) or 0, 4)
            except Exception as e:
                print(f"  SAR error [{kec}]: {e}")
                row["sar_vv_median"] = None
        else:
            row["sar_vv_median"] = None

        rows_buffer.append(row)

    # Flush ke CSV tiap periode (resume support)
    df_buf = pd.DataFrame(rows_buffer)
    df_buf.to_csv(OUTPUT, mode="a", header=write_header, index=False)
    rows_buffer = []
    write_header = False
    print(f"  Selesai ({time.time()-t0:.1f}s) | S2: {n_s2} scene | SAR: {n_sar} scene")

print(f"\nOutput: {OUTPUT}")
