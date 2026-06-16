# -*- coding: utf-8 -*-
"""
09_correlate_tambak_galian_pdrb.py
=====================================
Menghitung korelasi antara indikator tambak garam dan galian C
(dari pilot5 dan pilot6) dengan PDRB Kategori B (Pertambangan dan Penggalian)
dari data BPS Rembang.

Cara jalankan (setelah pilot5 dan pilot6 selesai):
  python 09_correlate_tambak_galian_pdrb.py

Membutuhkan:
  - tambak_garam_timeseries_2017_2026.csv
  - galian_c_timeseries_2017_2026.csv
  - pdrb_rembang_long_adhk.csv (dari script 04)
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Load data PDRB kategori B
# ---------------------------------------------------------------------------
pdrb_long = pd.read_csv("pdrb_rembang_long_adhk.csv")
pdrb_b = pdrb_long[pdrb_long["kategori"] == "B"][["periode","nilai_juta_rupiah"]].copy()
pdrb_b = pdrb_b.rename(columns={"nilai_juta_rupiah": "pdrb_pertambangan"})
print(f"PDRB B (Pertambangan): {len(pdrb_b)} periode, {pdrb_b['periode'].min()} - {pdrb_b['periode'].max()}")

# ---------------------------------------------------------------------------
# 2. Agregasi tambak garam ke level kabupaten (rata-rata kecamatan)
# ---------------------------------------------------------------------------
tambak = pd.read_csv("tambak_garam_timeseries_2017_2026.csv")
tambak_kab = (
    tambak.groupby("periode")
    .agg(
        ndwi_mean=("ndwi_mean", "mean"),
        ndwi_water_fraction=("ndwi_water_fraction", "mean"),
        salt_bright_fraction=("salt_bright_fraction", "mean"),
        sar_vv_median=("sar_vv_median", "mean"),
    )
    .reset_index()
)

# ---------------------------------------------------------------------------
# 3. Agregasi galian C ke level kabupaten
# ---------------------------------------------------------------------------
galian = pd.read_csv("galian_c_timeseries_2017_2026.csv")
galian_kab = (
    galian.groupby("periode")
    .agg(
        bsi_mean=("bsi_mean", "mean"),
        bsi_high_fraction=("bsi_high_fraction", "mean"),
        ndvi_low_fraction=("ndvi_low_fraction", "mean"),
        limestone_ratio_mean=("limestone_ratio_mean", "mean"),
        ndvi_stddev=("ndvi_stddev", "mean"),
    )
    .reset_index()
)

# ---------------------------------------------------------------------------
# 4. Fokus kecamatan: hanya kecamatan yang relevan
# ---------------------------------------------------------------------------
# Tambak garam: Kaliori, Rembang, Lasem
TAMBAK_KEC = ["Kaliori", "Rembang", "Lasem"]
tambak_fokus = (
    tambak[tambak["kecamatan"].isin(TAMBAK_KEC)]
    .groupby("periode")
    .agg(
        ndwi_water_fraction_fokus=("ndwi_water_fraction", "mean"),
        salt_bright_fraction_fokus=("salt_bright_fraction", "mean"),
    )
    .reset_index()
)

# Galian C: Gunem, Sale, Bulu, Sedan, Sarang
GALIAN_KEC = ["Gunem", "Sale", "Bulu", "Sedan", "Sarang"]
galian_fokus = (
    galian[galian["kecamatan"].isin(GALIAN_KEC)]
    .groupby("periode")
    .agg(
        bsi_mean_fokus=("bsi_mean", "mean"),
        bsi_high_fraction_fokus=("bsi_high_fraction", "mean"),
        limestone_ratio_fokus=("limestone_ratio_mean", "mean"),
    )
    .reset_index()
)

# ---------------------------------------------------------------------------
# 5. Gabungkan semua dengan PDRB B
# ---------------------------------------------------------------------------
merged = (pdrb_b
    .merge(tambak_kab, on="periode", how="inner")
    .merge(tambak_fokus, on="periode", how="inner")
    .merge(galian_kab, on="periode", how="inner")
    .merge(galian_fokus, on="periode", how="inner")
    .dropna(subset=["pdrb_pertambangan"])
    .sort_values("periode")
)

print(f"\nJumlah periode untuk korelasi: {len(merged)}")
print(f"Rentang: {merged['periode'].iloc[0]} - {merged['periode'].iloc[-1]}")

# ---------------------------------------------------------------------------
# 6. Hitung korelasi - level dan growth
# ---------------------------------------------------------------------------
merged["pdrb_diff"] = merged["pdrb_pertambangan"].diff()

INDIKATOR = {
    # Tambak garam - seluruh kabupaten
    "ndwi_water_fraction": "NDWI fraksi air (seluruh kabupaten)",
    "salt_bright_fraction": "Fraksi area cerah/garam (seluruh kabupaten)",
    # Tambak garam - kecamatan fokus
    "ndwi_water_fraction_fokus": "NDWI fraksi air (Kaliori+Rembang+Lasem)",
    "salt_bright_fraction_fokus": "Fraksi area cerah (Kaliori+Rembang+Lasem)",
    # SAR
    "sar_vv_median": "SAR VV median (area berair tenang)",
    # Galian C - seluruh kabupaten
    "bsi_mean": "BSI mean (tanah terbuka, seluruh kabupaten)",
    "bsi_high_fraction": "BSI fraksi tinggi (lahan galian, seluruh kabupaten)",
    "ndvi_low_fraction": "NDVI fraksi rendah (lahan terbuka/galian)",
    "limestone_ratio_mean": "Red/Green ratio (indikasi batu kapur)",
    # Galian C - kecamatan fokus
    "bsi_mean_fokus": "BSI mean (Gunem+Sale+Bulu+Sedan+Sarang)",
    "bsi_high_fraction_fokus": "BSI fraksi tinggi (kecamatan galian fokus)",
    "limestone_ratio_fokus": "Red/Green ratio (kecamatan galian fokus)",
}

print("\n=== KORELASI LEVEL (vs PDRB Pertambangan ADHK) ===")
for col, label in INDIKATOR.items():
    if col not in merged.columns:
        continue
    valid = merged.dropna(subset=[col])
    c = valid[col].corr(valid["pdrb_pertambangan"])
    print(f"  {c:+.3f}  {label}")

print("\n=== KORELASI GROWTH (first-difference) ===")
for col, label in INDIKATOR.items():
    if col not in merged.columns:
        continue
    diff_col = f"{col}_diff"
    merged[diff_col] = merged[col].diff()
    valid = merged.dropna(subset=[diff_col, "pdrb_diff"])
    c = valid[diff_col].corr(valid["pdrb_diff"])
    print(f"  {c:+.3f}  {label}")

# ---------------------------------------------------------------------------
# 7. Print tren per kecamatan untuk indikator terkuat
# ---------------------------------------------------------------------------
print("\n=== TREN TAHUNAN BSI PER KECAMATAN (rata-rata triwulanan) ===")
galian_annual = (
    galian.groupby(["kecamatan", "tahun"])["bsi_mean"]
    .mean().round(4).reset_index()
)
for kec in GALIAN_KEC:
    data = galian_annual[galian_annual["kecamatan"] == kec]
    print(f"\n{kec}:")
    for _, r in data.iterrows():
        bar = "█" * int(r["bsi_mean"] * 200)
        print(f"  {int(r['tahun'])}: {r['bsi_mean']:.4f} {bar}")

# ---------------------------------------------------------------------------
# 8. Simpan data gabungan untuk dashboard
# ---------------------------------------------------------------------------
merged.to_csv("korelasi_tambak_galian_pdrb_data.csv", index=False)
tambak.to_csv("tambak_garam_per_kecamatan.csv", index=False)
galian.to_csv("galian_c_per_kecamatan.csv", index=False)
print("\nData tersimpan: korelasi_tambak_galian_pdrb_data.csv")
