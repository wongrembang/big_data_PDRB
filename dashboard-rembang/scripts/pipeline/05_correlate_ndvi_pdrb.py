# -*- coding: utf-8 -*-
"""
correlate_ndvi_tanaman_pangan.py
====================================
Ekstrak PDRB sub-kategori A01 (Tanaman Pangan) ADHK dari file Excel,
lalu hitung korelasi dengan NDVI agregat kabupaten - level, growth,
dan beberapa skenario lag (0-3 triwulan), karena fase tanam/panen padi
biasanya tidak persis selaras triwulan kalender.

Cara jalankan:
  python correlate_ndvi_tanaman_pangan.py

Membutuhkan:
  - PDRB_Kab_Rembang_triwulanan.xlsx
  - timeseries_satelit_cleaned.csv
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Ekstrak PDRB A01 (Tanaman Pangan) ADHK dari Excel
# ---------------------------------------------------------------------------
raw = pd.read_excel("PDRB Kab Rembang triwulanan.xlsx", sheet_name="3317", header=None)

year_header_row = raw.iloc[3]
quarter_header_row = raw.iloc[4]
triwulan_order = {"I": 1, "II": 2, "III": 3, "IV": 4}

col_map = []
current_year = None
for col_idx in range(4, raw.shape[1]):
    val = year_header_row[col_idx]
    if isinstance(val, str) and val.startswith("Triwulanan"):
        current_year = int(val.split()[-1])
    q_label = quarter_header_row[col_idx]
    if isinstance(q_label, str) and q_label.strip() in ("I", "II", "III", "IV"):
        col_map.append((col_idx, current_year, q_label.strip()))

# Cari baris dengan kode sub-kategori "A01" di kolom index 3, dalam tabel
# ADHK (baris >= 85, sesuai struktur yang sudah diketahui)
row_a01 = None
for row_idx in range(85, 152):
    code = raw.iloc[row_idx, 3]
    if isinstance(code, str) and code.strip() == "A01":
        row_a01 = row_idx
        break

if row_a01 is None:
    raise ValueError("Baris A01 (Tanaman Pangan) tidak ditemukan di tabel ADHK")

print(f"Baris A01 (Tanaman Pangan) ditemukan di index {row_a01}: {raw.iloc[row_a01, 2]}")

rows = []
for col_idx, tahun, triwulan in col_map:
    val = raw.iloc[row_a01, col_idx]
    rows.append({"tahun": tahun, "triwulan": triwulan, "pdrb_tanaman_pangan": val})

pdrb_a01 = pd.DataFrame(rows)
pdrb_a01["triwulan_num"] = pdrb_a01["triwulan"].map(triwulan_order)
pdrb_a01["periode"] = pdrb_a01["tahun"].astype(str) + "Q" + pdrb_a01["triwulan_num"].astype(str)
pdrb_a01 = pdrb_a01.sort_values(["tahun", "triwulan_num"]).reset_index(drop=True)
pdrb_a01.to_csv("pdrb_tanaman_pangan_triwulanan.csv", index=False)
print(f"Tersimpan: pdrb_tanaman_pangan_triwulanan.csv ({len(pdrb_a01)} baris)")
print(pdrb_a01.head(8).to_string(index=False))

# ---------------------------------------------------------------------------
# 2. Load NDVI agregat kabupaten
# ---------------------------------------------------------------------------
sat = pd.read_csv("timeseries_satelit_cleaned.csv")
sat_kab = (
    sat.groupby("periode")
    .agg(
        ndvi_mean=("ndvi_mean", "mean"),
        ndvi_recommended=("ndvi_recommended", "first"),
        tahun=("tahun", "first"),
        triwulan=("triwulan", "first"),
    )
    .reset_index()
)

# ---------------------------------------------------------------------------
# 3. Gabungkan dan hitung korelasi - level, growth, dan lag 0-3
# ---------------------------------------------------------------------------
merged = sat_kab.merge(
    pdrb_a01[["periode", "pdrb_tanaman_pangan"]],
    on="periode", how="inner"
)
merged = merged[merged["ndvi_recommended"] & merged["pdrb_tanaman_pangan"].notna()]
merged = merged.sort_values(["tahun", "triwulan"]).reset_index(drop=True)

print(f"\nJumlah periode (NDVI Sentinel-2, PDRB A01 tersedia): {len(merged)}")
print(f"Rentang: {merged['periode'].iloc[0]} - {merged['periode'].iloc[-1]}")

corr_level = merged["ndvi_mean"].corr(merged["pdrb_tanaman_pangan"])
print(f"\nKorelasi LEVEL: NDVI vs PDRB Tanaman Pangan (ADHK) = {corr_level:.4f}")

merged["ndvi_diff"] = merged["ndvi_mean"].diff()
merged["pdrb_diff"] = merged["pdrb_tanaman_pangan"].diff()
corr_growth = merged["ndvi_diff"].corr(merged["pdrb_diff"])
print(f"Korelasi FIRST-DIFFERENCE (growth): NDVI vs PDRB Tanaman Pangan = {corr_growth:.4f}")

# ---------------------------------------------------------------------------
# 4. Coba beberapa skenario lag: NDVI triwulan t vs PDRB triwulan t+k
#    k = 0, 1, 2, 3 (fase tanam -> panen bisa butuh 1-3 triwulan)
# ---------------------------------------------------------------------------
print("\nKorelasi LEVEL dengan berbagai LAG (NDVI[t] vs PDRB_TanamanPangan[t+k]):")
full = sat_kab.merge(
    pdrb_a01[["periode", "pdrb_tanaman_pangan"]],
    on="periode", how="inner"
).sort_values(["tahun", "triwulan"]).reset_index(drop=True)

for k in range(0, 4):
    full[f"pdrb_lag{k}"] = full["pdrb_tanaman_pangan"].shift(-k)
    valid = full[full["ndvi_recommended"] & full[f"pdrb_lag{k}"].notna()]
    c = valid["ndvi_mean"].corr(valid[f"pdrb_lag{k}"])
    print(f"  lag k={k}: korelasi = {c:.4f}  (n={len(valid)})")

merged.to_csv("korelasi_ndvi_tanaman_pangan_data.csv", index=False)
