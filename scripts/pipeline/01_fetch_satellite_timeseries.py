# -*- coding: utf-8 -*-
"""
PILOT 2 (v5) - Time Series Historis NDVI/NTL Triwulanan 2010-2026
=====================================================================
Perluasan dari v4: menarik NDVI (Sentinel-2) dan NTL (VIIRS) per kecamatan
untuk SEMUA triwulan dari 2010Q1 hingga 2026Q2, sebagai baseline historis
untuk analisis time series / nowcasting PDRB.

PENTING - Keterbatasan ketersediaan data satelit:
  1. Sentinel-2 (NDVI) baru tersedia mulai akhir 2015 (data konsisten mulai
     2017). Untuk periode 2010-2016, NDVI akan kosong (NaN) - skrip ini
     otomatis fallback ke Landsat 8 (tersedia sejak 2013) untuk periode
     2013-2016, dan Landsat 7 (tersedia sejak 1999) untuk 2010-2012.
     NDVI dari Landsat dihitung dari band yang berbeda (B5/B4 untuk L8,
     B4/B3 untuk L7) tapi formula normalizedDifference-nya sama, sehingga
     nilainya sebanding (meski resolusi piksel berbeda: 30m vs 10m).

  2. VIIRS DNB (NTL) baru tersedia mulai April 2012. Untuk 2010-2012Q1,
     skrip menggunakan DMSP-OLS (tersedia 1992-2013) sebagai alternatif -
     TAPI skala nilai DMSP-OLS (0-63, integer) BERBEDA dari VIIRS (radiance
     kontinu) sehingga TIDAK BISA dibandingkan langsung secara nilai
     absolut. Skrip menandai sumber data di kolom 'ntl_source' supaya
     analisis selanjutnya tahu kapan terjadi pergantian sensor.

  3. Karena perbedaan sensor ini, untuk analisis time series yang benar:
     - Gunakan ntl_relative (rasio terhadap rata-rata kabupaten pada
       periode & SENSOR yang sama) untuk perbandingan antar kecamatan
     - HINDARI membandingkan ntl_median absolut antar sensor berbeda
       (DMSP-OLS vs VIIRS) sebagai "pertumbuhan" - itu akan menangkap
       pergantian sensor, bukan pertumbuhan ekonomi riil

Cara jalankan:
  python pilot2_satelit_gee_v5_timeseries.py

Output: indikator_timeseries_satelit_2010_2026.csv
  Kolom: kecamatan, tahun, triwulan, periode, ndvi_mean, ndvi_source,
         ntl_median, ntl_source, ntl_relative

Estimasi waktu: ~65 periode x 14 kecamatan x 2 reducer = bisa memakan
waktu CUKUP LAMA (kemungkinan 30-60+ menit) karena banyak panggilan
getInfo() ke server GEE. Skrip menyimpan progress secara incremental
(append per periode) sehingga bisa di-resume jika terhenti di tengah.
"""

import ee
import geopandas as gpd
import pandas as pd
import shapely
import os
import time

# ---------------------------------------------------------------------------
# 0. INISIALISASI
# ---------------------------------------------------------------------------
ee.Initialize(project='pdrb-big-data-extraction')

# ---------------------------------------------------------------------------
# 1. LOAD BOUNDARY POLYGON KECAMATAN
# ---------------------------------------------------------------------------
GEOJSON_PATH = "batas_kecamatan_rembang_simplified.geojson"
gdf = gpd.read_file(GEOJSON_PATH)

if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

gdf["geometry"] = gdf["geometry"].simplify(0.0001, preserve_topology=True)
gdf["geometry"] = gdf["geometry"].apply(lambda geom: shapely.force_2d(geom))


def gdf_to_ee_featurecollection(gdf, name_col="kecamatan"):
    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        features.append(ee.Feature(geom, {"kecamatan": row[name_col]}))
    return ee.FeatureCollection(features)


kec_fc = gdf_to_ee_featurecollection(gdf)
KECAMATAN_LIST = list(gdf["kecamatan"])

# ---------------------------------------------------------------------------
# 2. DAFTAR PERIODE TRIWULAN 2010Q1 - 2026Q2
# ---------------------------------------------------------------------------
def build_periode_list(start_year=2010, end_year=2026, end_quarter=2):
    periode = {}
    quarter_months = {1: ("01-01", "03-31"), 2: ("04-01", "06-30"),
                       3: ("07-01", "09-30"), 4: ("10-01", "12-31")}
    for year in range(start_year, end_year + 1):
        max_q = end_quarter if year == end_year else 4
        for q in range(1, max_q + 1):
            start_md, end_md = quarter_months[q]
            label = f"{year}Q{q}"
            periode[label] = (f"{year}-{start_md}", f"{year}-{end_md}", year, q)
    return periode


PERIODE = build_periode_list()
print(f"Total periode: {len(PERIODE)} (dari {list(PERIODE.keys())[0]} sampai {list(PERIODE.keys())[-1]})")

# ---------------------------------------------------------------------------
# 3. NDVI - pilih sumber sesuai ketersediaan data
#    - 2017 dst: Sentinel-2 SR (10m)
#    - 2013-2016: Landsat 8 SR (30m), band B5(NIR)/B4(Red)
#    - 2010-2012: Landsat 7 SR (30m), band B4(NIR)/B3(Red)
# ---------------------------------------------------------------------------
def get_ndvi_image(start, end, year):
    if year >= 2017:
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        )
        img = coll.map(lambda i: i.normalizedDifference(["B8", "B4"]).rename("NDVI")).select("NDVI").mean()
        source = "Sentinel-2"
        size = coll.size()
    elif year >= 2013:
        coll = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
        )
        # L2 surface reflectance perlu scaling factor
        def scale_l8(i):
            return i.select(["SR_B5", "SR_B4"]).multiply(0.0000275).add(-0.2)

        img = coll.map(lambda i: scale_l8(i).normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")).select("NDVI").mean()
        source = "Landsat-8"
        size = coll.size()
    else:
        coll = (
            ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
        )
        def scale_l7(i):
            return i.select(["SR_B4", "SR_B3"]).multiply(0.0000275).add(-0.2)

        img = coll.map(lambda i: scale_l7(i).normalizedDifference(["SR_B4", "SR_B3"]).rename("NDVI")).select("NDVI").mean()
        source = "Landsat-7"
        size = coll.size()

    return img, source, size


# ---------------------------------------------------------------------------
# 4. NTL - pilih sumber sesuai ketersediaan data
#    - April 2012 dst: VIIRS DNB Monthly (avg_rad, radiance kontinu, ~500m)
#    - sebelum itu: DMSP-OLS Nighttime Lights (stable_lights, 0-63, ~1km)
# ---------------------------------------------------------------------------
def get_ntl_image(start, end, year, quarter):
    use_viirs = (year > 2012) or (year == 2012 and quarter >= 2)
    if use_viirs:
        coll = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterDate(start, end)
            .filterBounds(kec_fc)
            .select("avg_rad")
        )
        img = coll.median()
        source = "VIIRS"
        size = coll.size()
    else:
        # DMSP-OLS hanya tersedia sebagai komposit tahunan (F-series satellites)
        # ambil komposit tahun yang sesuai
        year_dmsp = min(year, 2013)
        coll = (
            ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS")
            .filterDate(f"{year_dmsp}-01-01", f"{year_dmsp}-12-31")
            .filterBounds(kec_fc)
            .select("stable_lights")
        )
        img = coll.median()
        source = "DMSP-OLS"
        size = coll.size()

    return img, source, size


# ---------------------------------------------------------------------------
# 5. ZONAL STATISTICS
# ---------------------------------------------------------------------------
def zonal_stat(image, band_name, reducer, scale):
    stats = image.rename(band_name).reduceRegions(
        collection=kec_fc, reducer=reducer, scale=scale,
    )
    return stats.getInfo()


def run_periode(label, start, end, year, quarter):
    ndvi_img, ndvi_source, ndvi_n = get_ndvi_image(start, end, year)
    ntl_img, ntl_source, ntl_n = get_ntl_image(start, end, year, quarter)

    n_ndvi = ndvi_n.getInfo()
    n_ntl = ntl_n.getInfo()

    rows = []
    if n_ndvi == 0:
        ndvi_map = {kec: None for kec in KECAMATAN_LIST}
    else:
        ndvi_result = zonal_stat(ndvi_img, "ndvi", ee.Reducer.mean(), scale=30 if ndvi_source != "Sentinel-2" else 10)
        ndvi_map = {f["properties"]["kecamatan"]: f["properties"].get("mean") for f in ndvi_result["features"]}

    if n_ntl == 0:
        ntl_map = {kec: None for kec in KECAMATAN_LIST}
    else:
        scale_ntl = 1000 if ntl_source == "DMSP-OLS" else 500
        ntl_result = zonal_stat(ntl_img, "ntl", ee.Reducer.median(), scale=scale_ntl)
        ntl_map = {f["properties"]["kecamatan"]: f["properties"].get("median") for f in ntl_result["features"]}

    ntl_vals = [v for v in ntl_map.values() if v is not None]
    ntl_mean_all = sum(ntl_vals) / len(ntl_vals) if ntl_vals else None

    for kec in KECAMATAN_LIST:
        ntl_val = ntl_map.get(kec)
        ntl_rel = (ntl_val / ntl_mean_all) if (ntl_val is not None and ntl_mean_all) else None
        rows.append({
            "kecamatan": kec,
            "tahun": year,
            "triwulan": quarter,
            "periode": label,
            "ndvi_mean": ndvi_map.get(kec),
            "ndvi_source": ndvi_source if n_ndvi > 0 else "no_data",
            "ntl_median": ntl_val,
            "ntl_source": ntl_source if n_ntl > 0 else "no_data",
            "ntl_relative": ntl_rel,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUTPUT_PATH = "indikator_timeseries_satelit_2010_2026.csv"

    # Resume support: skip periode yang sudah ada di file output
    done_periode = set()
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH)
        done_periode = set(existing["periode"].unique())
        print(f"File output sudah ada, {len(done_periode)} periode sudah selesai, akan dilanjutkan.")

    write_header = not os.path.exists(OUTPUT_PATH)

    for label, (start, end, year, quarter) in PERIODE.items():
        if label in done_periode:
            continue
        t0 = time.time()
        try:
            df = run_periode(label, start, end, year, quarter)
            df.to_csv(OUTPUT_PATH, mode="a", header=write_header, index=False)
            write_header = False
            elapsed = time.time() - t0
            print(f"[{label}] selesai ({elapsed:.1f}s) - NDVI src: {df['ndvi_source'].iloc[0]}, NTL src: {df['ntl_source'].iloc[0]}")
        except Exception as e:
            print(f"[{label}] ERROR: {e}")
            print("Berhenti - jalankan ulang script untuk resume dari periode ini.")
            break

    print(f"\nSelesai. Hasil tersimpan di {OUTPUT_PATH}")
