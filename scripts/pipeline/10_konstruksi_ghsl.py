# -*- coding: utf-8 -*-
"""
pilot7_konstruksi_ghsl.py
===========================
Mendeteksi pertambahan area terbangun (proxy sektor Konstruksi / PDRB F)
di Kabupaten Rembang menggunakan dua pendekatan komplementer:

PENDEKATAN 1 — GHSL (Global Human Settlement Layer, JRC/EU):
  - Dataset: JRC/GHSL/P2023A/GHS_BUILT_S (built-up surface, m² per piksel)
  - Resolusi temporal: 5-tahunan (2000, 2005, 2010, 2015, 2020, 2025)
  - Resolusi spasial: 100m
  - Yang dihitung: luas total area terbangun (m²) per kecamatan per epoch,
    dan perubahan antar epoch sebagai proxy akumulasi konstruksi
  - Keunggulan: konsisten, tervalidasi secara global, data 50+ tahun
  - Keterbatasan: resolusi temporal 5 tahun, tidak bisa korelasi triwulanan

PENDEKATAN 2 — NDBI dari Sentinel-2 (triwulanan):
  - NDBI = (SWIR1 - NIR) / (SWIR1 + NIR) = (B11 - B8) / (B11 + B8)
  - Nilai positif = area terbangun (aspal, beton, atap seng)
  - Nilai negatif = vegetasi
  - Triwulanan 2017Q2-2026Q2, resolusi 10m
  - NDBI fraction: fraksi piksel dengan NDBI > 0 (terbangun) per kecamatan
  - Keunggulan: triwulanan, bisa deteksi perubahan dalam tahun
  - Keterbatasan: NDBI tinggi juga untuk lahan galian C dan tanah terbuka
    (overlap dengan BSI) — perlu filter tambahan

OUTPUT:
  - ghsl_buildup_per_kecamatan.csv: luas terbangun GHSL per epoch per kecamatan
  - ndbi_timeseries_2017_2026.csv: NDBI triwulanan per kecamatan

CARA JALANKAN:
  python pilot7_konstruksi_ghsl.py
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
# 2. PENDEKATAN 1: GHSL Built-up Surface per epoch
# ---------------------------------------------------------------------------
print("=== PENDEKATAN 1: GHSL Built-up Surface ===")

# Epoch yang tersedia di GHSL P2023A: 1975,1980,...,2020,2025,2030
# Kita ambil 2000-2025 (relevan untuk konstruksi modern)
GHSL_EPOCHS = [2000, 2005, 2010, 2015, 2020, 2025]

def get_ghsl_buildup(epoch):
    """
    GHS_BUILT_S: band 'built_surface' = luas area terbangun dalam piksel (m²/piksel)
    Pada resolusi 100m, satu piksel = 10.000 m². built_surface = fraksi terbangun × 10.000
    """
    img = ee.Image(f"JRC/GHSL/P2023A/GHS_BUILT_S/{epoch}")
    # Band: built_surface (total) dan built_surface_nres (non-residential)
    return img

ghsl_rows = []
for epoch in GHSL_EPOCHS:
    print(f"  Mengambil GHSL epoch {epoch}...")
    t0 = time.time()
    img = get_ghsl_buildup(epoch)

    # Zonal stats: sum built_surface per kecamatan (total m² terbangun)
    stats_total = img.select("built_surface").rename("val").reduceRegions(
        collection=kec_fc,
        reducer=ee.Reducer.sum(),
        scale=100
    ).getInfo()

    stats_nres = img.select("built_surface_nres").rename("val").reduceRegions(
        collection=kec_fc,
        reducer=ee.Reducer.sum(),
        scale=100
    ).getInfo()

    total_map = {f["properties"]["kecamatan"]: f["properties"].get("sum")
                 for f in stats_total["features"]}
    nres_map = {f["properties"]["kecamatan"]: f["properties"].get("sum")
                for f in stats_nres["features"]}

    for kec in KECAMATAN_LIST:
        total = total_map.get(kec)
        nres = nres_map.get(kec)
        res_only = (total - nres) if (total and nres) else None
        ghsl_rows.append({
            "kecamatan": kec,
            "epoch": epoch,
            "buildup_total_m2": round(total, 0) if total else None,
            "buildup_nres_m2": round(nres, 0) if nres else None,
            "buildup_res_m2": round(res_only, 0) if res_only else None,
        })
    print(f"    Selesai ({time.time()-t0:.1f}s)")

df_ghsl = pd.DataFrame(ghsl_rows)

# Hitung perubahan (delta) antar epoch per kecamatan
df_ghsl_pivot = df_ghsl.pivot(index="kecamatan", columns="epoch",
                               values="buildup_total_m2")
for i in range(1, len(GHSL_EPOCHS)):
    e_prev = GHSL_EPOCHS[i-1]
    e_curr = GHSL_EPOCHS[i]
    col_name = f"delta_{e_prev}_{e_curr}_m2"
    df_ghsl[col_name] = df_ghsl.apply(
        lambda row: None, axis=1  # placeholder, compute below
    )

# Pivot lagi untuk delta
delta_rows = []
for kec in KECAMATAN_LIST:
    kec_data = df_ghsl[df_ghsl["kecamatan"] == kec].set_index("epoch")
    for i in range(1, len(GHSL_EPOCHS)):
        e_prev = GHSL_EPOCHS[i-1]
        e_curr = GHSL_EPOCHS[i]
        val_prev = kec_data.loc[e_prev, "buildup_total_m2"] if e_prev in kec_data.index else None
        val_curr = kec_data.loc[e_curr, "buildup_total_m2"] if e_curr in kec_data.index else None
        delta = (val_curr - val_prev) if (val_curr and val_prev) else None
        delta_rows.append({
            "kecamatan": kec, "epoch_dari": e_prev, "epoch_ke": e_curr,
            "delta_buildup_m2": round(delta, 0) if delta else None,
            "delta_buildup_pct": round(delta/val_prev*100, 2) if (delta and val_prev) else None,
        })
df_delta = pd.DataFrame(delta_rows)

df_ghsl.to_csv("ghsl_buildup_per_kecamatan.csv", index=False)
df_delta.to_csv("ghsl_delta_buildup_per_kecamatan.csv", index=False)
print(f"\nGHSL tersimpan: ghsl_buildup_per_kecamatan.csv & ghsl_delta_buildup_per_kecamatan.csv")

# Print ringkasan
print("\n--- Luas area terbangun (m²) per kecamatan, epoch 2000-2025 ---")
print(df_ghsl_pivot.round(0).to_string())

print("\n--- Pertambahan area terbangun 2020-2025 (m²) per kecamatan ---")
delta_2020_2025 = df_delta[df_delta["epoch_dari"]==2020].sort_values(
    "delta_buildup_m2", ascending=False)
print(delta_2020_2025[["kecamatan","delta_buildup_m2","delta_buildup_pct"]].to_string(index=False))

# ---------------------------------------------------------------------------
# 3. PENDEKATAN 2: NDBI triwulanan dari Sentinel-2 (2017Q2-2026Q2)
# ---------------------------------------------------------------------------
print("\n=== PENDEKATAN 2: NDBI Triwulanan Sentinel-2 ===")

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

OUTPUT_NDBI = "ndbi_timeseries_2017_2026.csv"
done = set()
if os.path.exists(OUTPUT_NDBI):
    existing = pd.read_csv(OUTPUT_NDBI)
    done = set(existing["periode"].unique())
    print(f"Resume: {len(done)} periode sudah selesai")

write_header = not os.path.exists(OUTPUT_NDBI)
rows_buffer = []

for label, start, end, year, quarter in PERIODE:
    if label in done:
        continue
    t0 = time.time()

    coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))
    n = coll.size().getInfo()

    for kec in KECAMATAN_LIST:
        row = {"kecamatan": kec, "periode": label, "tahun": year, "triwulan": quarter,
               "n_scenes": n}
        if n == 0:
            row["ndbi_mean"] = row["ndbi_fraction"] = row["ndbi_minus_ndvi"] = None
        else:
            try:
                def compute_ndbi(img):
                    # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
                    ndbi = img.normalizedDifference(["B11","B8"]).rename("NDBI")
                    # NDVI untuk pembanding
                    ndvi = img.normalizedDifference(["B8","B4"]).rename("NDVI")
                    # UI (Urban Index) = NDBI - NDVI
                    # positif kuat = urban, negatif = vegetasi
                    ui = ndbi.subtract(ndvi).rename("UI")
                    return ee.Image.cat([ndbi, ndvi, ui])

                composite = coll.map(compute_ndbi).median()

                # NDBI mean
                ndbi_mean = composite.select("NDBI").rename("val").reduceRegions(
                    collection=kec_fc, reducer=ee.Reducer.mean(), scale=10
                ).getInfo()
                ndbi_mean_map = {f["properties"]["kecamatan"]: f["properties"].get("mean")
                                 for f in ndbi_mean["features"]}

                # Fraksi piksel NDBI > 0 (area terbangun)
                ndbi_mask = composite.select("NDBI").gt(0)
                ndbi_frac = ndbi_mask.rename("val").reduceRegions(
                    collection=kec_fc, reducer=ee.Reducer.mean(), scale=10
                ).getInfo()
                ndbi_frac_map = {f["properties"]["kecamatan"]: f["properties"].get("mean")
                                 for f in ndbi_frac["features"]}

                # Urban Index mean (NDBI - NDVI, positif = urban)
                ui_mean = composite.select("UI").rename("val").reduceRegions(
                    collection=kec_fc, reducer=ee.Reducer.mean(), scale=10
                ).getInfo()
                ui_mean_map = {f["properties"]["kecamatan"]: f["properties"].get("mean")
                               for f in ui_mean["features"]}

                v_ndbi = ndbi_mean_map.get(kec)
                v_frac = ndbi_frac_map.get(kec)
                v_ui = ui_mean_map.get(kec)
                row["ndbi_mean"] = round(v_ndbi, 4) if v_ndbi else None
                row["ndbi_fraction"] = round(v_frac, 4) if v_frac else None
                row["urban_index_mean"] = round(v_ui, 4) if v_ui else None

            except Exception as e:
                print(f"  Error [{kec}]: {e}")
                row["ndbi_mean"] = row["ndbi_fraction"] = row["urban_index_mean"] = None

        rows_buffer.append(row)

    df_buf = pd.DataFrame(rows_buffer)
    df_buf.to_csv(OUTPUT_NDBI, mode="a", header=write_header, index=False)
    rows_buffer = []
    write_header = False
    print(f"[{label}] selesai ({time.time()-t0:.1f}s) | {n} scene")

print(f"\nOutput: {OUTPUT_NDBI}")
