# -*- coding: utf-8 -*-
"""
clean_timeseries_satelit.py
=============================
Membersihkan dan memproses indikator_timeseries_satelit_2010_2026.csv:

  1. Flag periode NTL tidak reliable (ntl_valid = False) jika median NTL
     SELURUH kecamatan pada periode itu < threshold (banyak nilai 0
     serempak -> indikasi gap data VIIRS bulanan, sering terjadi di Q1).
  2. Untuk ntl_relative yang dihitung dari ntl_mean_all mendekati 0
     (menghasilkan rasio ekstrem seperti 8.6 atau 14), set ke NaN jika
     ntl_valid = False.
  3. Buat agregasi TAHUNAN (rata-rata 4 triwulan, exclude periode
     ntl_valid=False untuk NTL) sebagai unit analisis yang lebih stabil.
  4. Tandai era sensor (untuk transparansi): NDVI era (Landsat-7/8,
     Sentinel-2), NTL era (DMSP-OLS, VIIRS) - rekomendasi: gunakan data
     >= 2014 untuk NTL (VIIRS stabil) dan >= 2017 untuk NDVI (Sentinel-2,
     resolusi tinggi & konsisten).

Cara jalankan:
  python clean_timeseries_satelit.py

Output:
  - timeseries_satelit_cleaned.csv (data triwulanan + flag ntl_valid)
  - timeseries_satelit_annual.csv (agregasi tahunan per kecamatan)
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
df = pd.read_csv("indikator_timeseries_satelit_2010_2026.csv")
print(f"Total baris: {len(df)}")

# ---------------------------------------------------------------------------
# 2. Flag ntl_valid per periode
#    Threshold: median dari ntl_median seluruh kecamatan pada periode itu
#    harus > 0.05 (untuk VIIRS) supaya dianggap valid. Untuk DMSP-OLS
#    (skala 0-63), threshold berbeda (>0.5).
# ---------------------------------------------------------------------------
median_per_periode = df.groupby("periode")["ntl_median"].median()
source_per_periode = df.groupby("periode")["ntl_source"].first()

def is_valid(periode):
    source = source_per_periode[periode]
    median_all = median_per_periode[periode]
    if source == "DMSP-OLS":
        return median_all > 0.5
    elif source == "no_data":
        return False
    else:  # VIIRS
        return median_all > 0.05

df["ntl_valid"] = df["periode"].map(is_valid)

n_invalid = df.loc[~df["ntl_valid"], "periode"].nunique()
print(f"\nJumlah periode dengan NTL ditandai TIDAK VALID: {n_invalid}")
print("Daftar periode tidak valid:")
print(sorted(df.loc[~df["ntl_valid"], "periode"].unique()))

# ---------------------------------------------------------------------------
# 3. Set ntl_relative ke NaN jika tidak valid (menghindari rasio ekstrem
#    akibat pembagian dengan rata-rata mendekati nol)
# ---------------------------------------------------------------------------
df.loc[~df["ntl_valid"], "ntl_relative"] = np.nan
df.loc[~df["ntl_valid"], "ntl_median"] = np.nan

# ---------------------------------------------------------------------------
# 4. Tandai rekomendasi era data
# ---------------------------------------------------------------------------
df["ndvi_recommended"] = df["ndvi_source"] == "Sentinel-2"
df["ntl_recommended"] = (df["ntl_source"] == "VIIRS") & (df["tahun"] >= 2014) & df["ntl_valid"]

# ---------------------------------------------------------------------------
# 5. Simpan data triwulanan yang sudah dibersihkan
# ---------------------------------------------------------------------------
df.to_csv("timeseries_satelit_cleaned.csv", index=False)
print(f"\nData triwulanan tersimpan: timeseries_satelit_cleaned.csv")

# ---------------------------------------------------------------------------
# 6. Agregasi tahunan
#    - ndvi_mean: rata-rata dari triwulan yang punya data (NaN diabaikan)
#    - ntl_median: rata-rata dari triwulan yang ntl_valid=True
#    - ntl_relative: rata-rata dari triwulan yang valid
#    - n_quarter_ndvi / n_quarter_ntl: jumlah triwulan yang punya data
#      (transparansi - kalau cuma 1-2 dari 4, rata-rata kurang reliable)
# ---------------------------------------------------------------------------
annual = (
    df.groupby(["kecamatan", "tahun"])
    .agg(
        ndvi_mean=("ndvi_mean", "mean"),
        n_quarter_ndvi=("ndvi_mean", lambda x: x.notna().sum()),
        ntl_median=("ntl_median", "mean"),
        ntl_relative=("ntl_relative", "mean"),
        n_quarter_ntl=("ntl_median", lambda x: x.notna().sum()),
    )
    .reset_index()
)

annual.to_csv("timeseries_satelit_annual.csv", index=False)
print(f"Data tahunan tersimpan: timeseries_satelit_annual.csv ({len(annual)} baris)")

# ---------------------------------------------------------------------------
# 7. Ringkasan untuk Rembang sebagai contoh
# ---------------------------------------------------------------------------
print("\nContoh data tahunan untuk kecamatan Rembang:")
print(annual[annual["kecamatan"] == "Rembang"].to_string(index=False))
