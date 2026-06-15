# -*- coding: utf-8 -*-
"""
build_data_js.py
==================
Mengonversi semua file CSV mentah (di data/raw/) menjadi satu file
JavaScript (data.js) berisi objek-objek data yang ringkas, untuk
di-embed langsung di dashboard HTML (agar dapat berjalan sebagai
static site di GitHub Pages tanpa server/backend).

Cara jalankan:
  python build_data_js.py

Output:
  - ../assets/data.js
"""

import pandas as pd
import json
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "data.js")


def load_csv(name):
    return pd.read_csv(os.path.join(RAW_DIR, name))


# ---------------------------------------------------------------------------
# 1. Boundary GeoJSON (14 kecamatan)
# ---------------------------------------------------------------------------
with open(os.path.join(RAW_DIR, "batas_kecamatan_rembang.geojson")) as f:
    geojson = json.load(f)

# ---------------------------------------------------------------------------
# 2. NDVI & NTL triwulanan (timeseries_satelit_cleaned.csv)
#    Hanya simpan kolom yang relevan, dan hanya periode yang
#    "recommended" (ndvi_recommended / ntl_recommended) ditandai jelas
# ---------------------------------------------------------------------------
sat = load_csv("timeseries_satelit_cleaned.csv")
sat_records = sat[[
    "kecamatan", "periode", "tahun", "triwulan",
    "ndvi_mean", "ndvi_source", "ndvi_recommended",
    "ntl_median", "ntl_relative", "ntl_source", "ntl_valid", "ntl_recommended",
]].copy()
# Bulatkan angka untuk mengurangi ukuran file
for col in ["ndvi_mean", "ntl_median", "ntl_relative"]:
    sat_records[col] = sat_records[col].round(4)
sat_records = sat_records.where(pd.notna(sat_records), None)
satelit_timeseries = sat_records.to_dict(orient="records")

# ---------------------------------------------------------------------------
# 3. NDVI cropland masked (ndvi_cropland_masked_2017_2026.csv)
# ---------------------------------------------------------------------------
ndvi_crop = load_csv("ndvi_cropland_masked_2017_2026.csv")
for col in ["ndvi_unmasked_mean", "ndvi_cropland_mean", "cropland_pct"]:
    ndvi_crop[col] = ndvi_crop[col].round(4)
ndvi_crop = ndvi_crop.where(pd.notna(ndvi_crop), None)
ndvi_cropland = ndvi_crop.to_dict(orient="records")

# ---------------------------------------------------------------------------
# 4. Data tahunan (timeseries_satelit_annual.csv)
# ---------------------------------------------------------------------------
annual = load_csv("timeseries_satelit_annual.csv")
for col in ["ndvi_mean", "ntl_median", "ntl_relative"]:
    annual[col] = annual[col].round(4)
annual = annual.where(pd.notna(annual), None)
satelit_annual = annual.to_dict(orient="records")

# ---------------------------------------------------------------------------
# 5. PDRB - total triwulanan dan tanaman pangan
# ---------------------------------------------------------------------------
pdrb_total = load_csv("pdrb_total_triwulanan.csv")
for col in ["pdrb_total_adhb", "pdrb_total_adhk"]:
    pdrb_total[col] = pdrb_total[col].round(2)
pdrb_total = pdrb_total.where(pd.notna(pdrb_total), None)
pdrb_total_records = pdrb_total.to_dict(orient="records")

pdrb_tp = load_csv("pdrb_tanaman_pangan_triwulanan.csv")
pdrb_tp["pdrb_tanaman_pangan"] = pdrb_tp["pdrb_tanaman_pangan"].round(2)
pdrb_tp = pdrb_tp.where(pd.notna(pdrb_tp), None)
pdrb_tanaman_pangan = pdrb_tp[["periode", "pdrb_tanaman_pangan"]].to_dict(orient="records")

# ---------------------------------------------------------------------------
# 6. GFW - bulanan dan ringkasan per kapal
# ---------------------------------------------------------------------------
gfw_monthly = load_csv("gfw_fishing_effort_rembang_monthly.csv")
gfw_monthly["total_fishing_hours"] = gfw_monthly["total_fishing_hours"].round(2)
gfw_monthly = gfw_monthly.where(pd.notna(gfw_monthly), None)
gfw_monthly_records = gfw_monthly.to_dict(orient="records")

gfw_raw = load_csv("gfw_fishing_effort_rembang_raw.csv")
gfw_raw["hours"] = gfw_raw["hours"].round(2)
# Ringkasan per kapal: total jam, jumlah bulan aktif, geartype paling sering
vessel_summary = (
    gfw_raw.groupby(["mmsi", "shipName", "vesselType", "flag"])
    .agg(
        total_hours=("hours", "sum"),
        bulan_aktif=("date", "nunique"),
        geartype_utama=("geartype", lambda x: x.mode().iloc[0] if not x.mode().empty else None),
    )
    .reset_index()
    .sort_values("total_hours", ascending=False)
)
vessel_summary["total_hours"] = vessel_summary["total_hours"].round(2)
vessel_summary = vessel_summary.where(pd.notna(vessel_summary), None)
gfw_vessel_summary = vessel_summary.to_dict(orient="records")

# Geartype distribution per bulan (untuk chart breakdown)
geartype_monthly = (
    gfw_raw.groupby(["date", "geartype"])["hours"].sum().round(2).reset_index()
)
gfw_geartype_monthly = geartype_monthly.to_dict(orient="records")

# ---------------------------------------------------------------------------
# 7. Tulis ke data.js
# ---------------------------------------------------------------------------
output = {
    "geojson": geojson,
    "satelitTimeseries": satelit_timeseries,
    "ndviCropland": ndvi_cropland,
    "satelitAnnual": satelit_annual,
    "pdrbTotal": pdrb_total_records,
    "pdrbTanamanPangan": pdrb_tanaman_pangan,
    "gfwMonthly": gfw_monthly_records,
    "gfwVesselSummary": gfw_vessel_summary,
    "gfwGeartypeMonthly": gfw_geartype_monthly,
}

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w") as f:
    f.write("// File ini di-generate otomatis oleh scripts/build_data_js.py\n")
    f.write("// Jangan diedit manual - jalankan ulang script untuk memperbarui data.\n")
    f.write("const REMBANG_DATA = ")
    json.dump(output, f, separators=(",", ":"))
    f.write(";\n")

size_kb = os.path.getsize(OUT_PATH) / 1024
print(f"Selesai. File tersimpan: {OUT_PATH} ({size_kb:.1f} KB)")
print(f"  - satelitTimeseries: {len(satelit_timeseries)} baris")
print(f"  - ndviCropland: {len(ndvi_cropland)} baris")
print(f"  - satelitAnnual: {len(satelit_annual)} baris")
print(f"  - pdrbTotal: {len(pdrb_total_records)} baris")
print(f"  - pdrbTanamanPangan: {len(pdrb_tanaman_pangan)} baris")
print(f"  - gfwMonthly: {len(gfw_monthly_records)} baris")
print(f"  - gfwVesselSummary: {len(gfw_vessel_summary)} baris")
print(f"  - gfwGeartypeMonthly: {len(gfw_geartype_monthly)} baris")
