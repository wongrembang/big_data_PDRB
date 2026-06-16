# -*- coding: utf-8 -*-
"""
11_correlate_konstruksi_pdrb.py
===================================
Korelasi antara indikator konstruksi (GHSL + NDBI) dengan PDRB
Kategori F (Konstruksi) ADHK Kabupaten Rembang.

CATATAN PENTING tentang GHSL untuk konstruksi:
  GHSL hanya tersedia per 5 tahun — tidak bisa dikorelasikan secara
  langsung dengan PDRB triwulanan. Untuk korelasi GHSL, kita konversi ke
  tahunan (interpolasi linear antar epoch), lalu bandingkan dengan PDRB
  tahunan (rata-rata 4 triwulan).

  NDBI triwulanan dari Sentinel-2 bisa dikorelasikan langsung dengan
  PDRB triwulanan, meski interpretasinya lebih noise (NDBI juga menangkap
  lahan terbuka/galian, bukan hanya bangunan).

Cara jalankan:
  python 11_correlate_konstruksi_pdrb.py

Membutuhkan:
  - ghsl_buildup_per_kecamatan.csv (dari 10_konstruksi_ghsl.py)
  - ghsl_delta_buildup_per_kecamatan.csv
  - ndbi_timeseries_2017_2026.csv
  - pdrb_rembang_long_adhk.csv (dari 04_extract_pdrb.py)
  - PDRB Kab Rembang triwulanan.xlsx
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Ekstrak PDRB F (Konstruksi) dari Excel
# ---------------------------------------------------------------------------
raw = pd.read_excel("PDRB Kab Rembang triwulanan.xlsx", sheet_name="3317", header=None)
year_row = raw.iloc[3]; quarter_row = raw.iloc[4]
triwulan_order = {"I":1,"II":2,"III":3,"IV":4}

col_map = []
current_year = None
for col_idx in range(4, raw.shape[1]):
    val = year_row[col_idx]
    if isinstance(val, str) and val.startswith("Triwulanan"):
        current_year = int(val.split()[-1])
    q_label = quarter_row[col_idx]
    if isinstance(q_label, str) and q_label.strip() in ("I","II","III","IV"):
        col_map.append((col_idx, current_year, q_label.strip()))

# Cari baris F (Konstruksi) di tabel ADHK
row_f = None
for row_idx in range(85, 152):
    val = raw.iloc[row_idx, 0]
    if isinstance(val, str) and val.strip() == "F":
        row_f = row_idx
        print(f"Baris F ADHK: index {row_f} = {raw.iloc[row_f,1]}")
        break

rows = []
for col_idx, tahun, triwulan in col_map:
    v = raw.iloc[row_f, col_idx]
    rows.append({"tahun": tahun, "triwulan_num": triwulan_order[triwulan],
                 "pdrb_konstruksi": v})
pdrb_f = pd.DataFrame(rows)
pdrb_f["periode"] = pdrb_f["tahun"].astype(str)+"Q"+pdrb_f["triwulan_num"].astype(str)
pdrb_f = pdrb_f.sort_values(["tahun","triwulan_num"]).reset_index(drop=True)
pdrb_f.to_csv("pdrb_konstruksi_triwulanan.csv", index=False)

# Agregasi tahunan PDRB F
pdrb_f_annual = pdrb_f.groupby("tahun")["pdrb_konstruksi"].mean().reset_index()
print("\nPDRB Konstruksi (ADHK) tahunan:")
print(pdrb_f_annual.to_string(index=False))

# ---------------------------------------------------------------------------
# 2. GHSL: luas terbangun + delta per epoch → tahunan (interpolasi)
# ---------------------------------------------------------------------------
ghsl = pd.read_csv("ghsl_buildup_per_kecamatan.csv")
ghsl_delta = pd.read_csv("ghsl_delta_buildup_per_kecamatan.csv")

# Agregasi kabupaten
ghsl_kab = ghsl.groupby("epoch")["buildup_total_m2"].sum().reset_index()
print("\nLuas terbangun GHSL (total kabupaten, m²):")
print(ghsl_kab.to_string(index=False))

# Delta 5-tahunan per epoch
delta_kab = ghsl_delta.groupby(["epoch_dari","epoch_ke"])["delta_buildup_m2"].sum().reset_index()
delta_kab["delta_per_tahun"] = delta_kab["delta_buildup_m2"] / 5
print("\nPertambahan area terbangun per tahun (rata-rata per epoch):")
print(delta_kab.to_string(index=False))

# Interpolasi ke tahunan (linear)
YEARS = list(range(2000, 2026))
ghsl_interp = {}
for i in range(len(ghsl_kab)-1):
    e0 = ghsl_kab.iloc[i]["epoch"]
    e1 = ghsl_kab.iloc[i+1]["epoch"]
    v0 = ghsl_kab.iloc[i]["buildup_total_m2"]
    v1 = ghsl_kab.iloc[i+1]["buildup_total_m2"]
    for y in range(int(e0), int(e1)+1):
        t = (y - e0) / (e1 - e0)
        ghsl_interp[y] = v0 + t * (v1 - v0)

ghsl_annual = pd.DataFrame([{"tahun": y, "buildup_m2": v} for y, v in ghsl_interp.items()])
ghsl_annual["buildup_growth_m2"] = ghsl_annual["buildup_m2"].diff()

# Korelasi GHSL tahunan vs PDRB F tahunan
merged_annual = pdrb_f_annual.merge(ghsl_annual, on="tahun", how="inner")
merged_annual = merged_annual.dropna(subset=["pdrb_konstruksi","buildup_m2"])
print(f"\nJumlah tahun untuk korelasi GHSL vs PDRB F: {len(merged_annual)}")
print(f"Rentang: {merged_annual['tahun'].min()}-{merged_annual['tahun'].max()}")

c_level = merged_annual["buildup_m2"].corr(merged_annual["pdrb_konstruksi"])
c_growth = merged_annual["buildup_growth_m2"].corr(merged_annual["pdrb_konstruksi"].diff())
print(f"\nKorelasi GHSL (luas terbangun) vs PDRB Konstruksi:")
print(f"  Level:  {c_level:+.3f}")
print(f"  Growth: {c_growth:+.3f}")

merged_annual.to_csv("korelasi_ghsl_konstruksi_tahunan.csv", index=False)

# ---------------------------------------------------------------------------
# 3. NDBI triwulanan vs PDRB F triwulanan
# ---------------------------------------------------------------------------
ndbi = pd.read_csv("ndbi_timeseries_2017_2026.csv")

ndbi_kab = ndbi.groupby("periode").agg(
    ndbi_mean=("ndbi_mean","mean"),
    ndbi_fraction=("ndbi_fraction","mean"),
    urban_index_mean=("urban_index_mean","mean"),
).reset_index()

merged_q = pdrb_f.merge(ndbi_kab, on="periode", how="inner").dropna(subset=["pdrb_konstruksi"])
merged_q = merged_q.sort_values("periode").reset_index(drop=True)
print(f"\nJumlah periode untuk korelasi NDBI vs PDRB F: {len(merged_q)}")

INDIKATOR = {
    "ndbi_mean": "NDBI mean (seluruh kabupaten)",
    "ndbi_fraction": "NDBI fraction > 0 (fraksi area terbangun)",
    "urban_index_mean": "Urban Index mean (NDBI - NDVI)",
}
print("\nKorelasi LEVEL: NDBI vs PDRB Konstruksi ADHK")
for col, label in INDIKATOR.items():
    valid = merged_q.dropna(subset=[col])
    c = valid[col].corr(valid["pdrb_konstruksi"])
    print(f"  {c:+.3f}  {label}")

print("\nKorelasi GROWTH (first-difference):")
merged_q["pdrb_diff"] = merged_q["pdrb_konstruksi"].diff()
for col, label in INDIKATOR.items():
    merged_q[f"{col}_diff"] = merged_q[col].diff()
    valid = merged_q.dropna(subset=[f"{col}_diff","pdrb_diff"])
    c = valid[f"{col}_diff"].corr(valid["pdrb_diff"])
    print(f"  {c:+.3f}  {label}")

# Lag analysis NDBI
print("\nAnalisis lag NDBI mean vs PDRB Konstruksi:")
print(f"{'lag':<8} {'NDBI mean':>10} {'NDBI frac':>10} {'UI mean':>10}")
for k in range(-1, 4):
    lag_results = []
    for col in ["ndbi_mean","ndbi_fraction","urban_index_mean"]:
        if k < 0:
            shifted_pdrb = merged_q["pdrb_konstruksi"].shift(k)
            valid = merged_q.loc[shifted_pdrb.notna() & merged_q[col].notna()]
            c = valid[col].corr(shifted_pdrb.loc[valid.index])
        else:
            shifted_ind = merged_q[col].shift(k)
            valid = merged_q.loc[shifted_ind.notna() & merged_q["pdrb_konstruksi"].notna()]
            c = shifted_ind.loc[valid.index].corr(valid["pdrb_konstruksi"])
        lag_results.append(c)
    print(f"  k={k:<4} {lag_results[0]:+.3f}    {lag_results[1]:+.3f}    {lag_results[2]:+.3f}")

merged_q.to_csv("korelasi_ndbi_konstruksi_data.csv", index=False)
print("\nData tersimpan.")
