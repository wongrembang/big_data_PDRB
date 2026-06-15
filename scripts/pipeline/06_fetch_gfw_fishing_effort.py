# -*- coding: utf-8 -*-
"""
pilot4_gfw_fishing_effort.py
==============================
Mengambil data "apparent fishing effort" (perkiraan jam aktivitas
penangkapan ikan berbasis sinyal AIS kapal) dari Global Fishing Watch (GFW)
untuk perairan di sekitar Kabupaten Rembang, sebagai proksi untuk PDRB
sublapangan A.09 (Perikanan / Perikanan Tangkap).

CARA MENDAPATKAN API TOKEN (gratis, untuk penggunaan non-komersial):
  1. Daftar akun gratis di https://globalfishingwatch.org (bisa pakai
     akun Gmail)
  2. Buka halaman API Portal / "Get your free API key"
     (https://globalfishingwatch.org/our-apis/)
  3. Generate token, lalu isi ke variabel GFW_API_TOKEN di bawah, atau
     set sebagai environment variable GFW_API_TOKEN

WILAYAH PERAIRAN RembANG:
  Kabupaten Rembang berada di pesisir utara Jawa Tengah (Laut Jawa).
  Karena GFW 4Wings API menerima region berupa polygon kustom (GeoJSON),
  digunakan sebuah kotak (bounding box) perairan di depan pesisir Rembang
  sebagai area analisis - BUKAN batas administratif laut resmi (yang
  belum tersedia dalam eksplorasi ini), melainkan area perairan yang
  secara geografis berdekatan dengan garis pantai 14 kecamatan Rembang.

  Bounding box yang digunakan (perkiraan, garis pantai Rembang berada
  di sekitar -6.55 sampai -6.95 lintang, 111.0 sampai 111.7 bujur):
    - Lintang: -7.20 sampai -6.55 (dari garis pantai ke arah laut)
    - Bujur:   111.00 sampai 111.75

PENTING - KETERBATASAN:
  - Data AIS hanya menangkap kapal yang memancarkan sinyal AIS. Banyak
    kapal nelayan tradisional/skala kecil (terutama di bawah 30 GT)
    TIDAK dilengkapi/tidak wajib menggunakan AIS, sehingga aktivitas
    mereka TIDAK akan terekam dalam data ini. Untuk perikanan rakyat
    skala kecil yang dominan di banyak TPI Rembang, proksi ini mungkin
    kurang representatif.
  - "Apparent fishing effort" adalah ESTIMASI berbasis pola gerak kapal
    (bukan hasil tangkapan aktual), dihasilkan oleh model machine
    learning GFW.
  - Wilayah bounding box mencakup area laut yang lebih luas dari sekadar
    "milik" Rembang - termasuk juga perairan yang mungkin lebih dekat ke
    kabupaten/kota tetangga (Lasem berbatasan dengan Tuban di timur,
    Kaliori berbatasan dengan Pati di barat). Untuk analisis lanjutan,
    bounding box ini sebaiknya disempurnakan atau diganti dengan
    polygon yang lebih presisi (misal buffer dari garis pantai 14
    kecamatan).

Cara jalankan:
  python pilot4_gfw_fishing_effort.py

Output:
  - gfw_fishing_effort_rembang.csv
    Kolom: date / periode, fishing_hours (total jam aktivitas
    penangkapan ikan terdeteksi dalam area, per periode bulanan)
"""

import requests
import json
import os
import pandas as pd
import time

# ---------------------------------------------------------------------------
# 0. KONFIGURASI - isi token API di sini, atau set environment variable
# ---------------------------------------------------------------------------
GFW_API_TOKEN = os.environ.get("GFW_API_TOKEN", "ISI_TOKEN_DISINI")

BASE_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"

# ---------------------------------------------------------------------------
# 1. Definisikan area perairan Rembang (bounding box sebagai polygon)
# ---------------------------------------------------------------------------
REMBANG_WATERS_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [111.00, -6.55],
        [111.75, -6.55],
        [111.75, -7.20],
        [111.00, -7.20],
        [111.00, -6.55],
    ]]
}

# ---------------------------------------------------------------------------
# 2. Periode - mulai dari 2017 (awal data AIS GFW yang konsisten) s.d. 2026
# ---------------------------------------------------------------------------
def build_periode_list(start_year=2017, end_year=2026, end_month=6):
    periode = []
    for year in range(start_year, end_year + 1):
        max_month = end_month if year == end_year else 12
        for month in range(1, max_month + 1):
            start = f"{year}-{month:02d}-01"
            # akhir bulan
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"
            periode.append((f"{year}-{month:02d}", start, end))
    return periode


PERIODE = build_periode_list()
print(f"Total periode (bulanan): {len(PERIODE)}")
print(f"Dari {PERIODE[0][0]} sampai {PERIODE[-1][0]}")

# ---------------------------------------------------------------------------
# 3. Panggil 4Wings Report API per periode (monthly resolution)
#    Catatan: API mendukung date-range multi-bulan dalam satu request
#    dengan temporal-resolution=monthly, sehingga TIDAK PERLU loop per
#    bulan satu-satu - tapi untuk menjaga ukuran response & menghindari
#    timeout, kita pecah per tahun (12 bulan sekaligus).
# ---------------------------------------------------------------------------
def fetch_fishing_effort_year(year, start_date, end_date, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query = (
        "spatial-resolution=LOW"
        "&temporal-resolution=MONTHLY"
        f"&datasets[0]=public-global-fishing-effort:latest"
        f"&date-range={start_date},{end_date}"
        "&format=JSON"
    )
    full_url = f"{BASE_URL}?{query}"
    body = {"geojson": REMBANG_WATERS_POLYGON}

    resp = requests.post(full_url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    if GFW_API_TOKEN == "ISI_TOKEN_DISINI":
        print("\n[PERINGATAN] Token API belum diisi.")
        print("Isi variabel GFW_API_TOKEN di script ini, atau jalankan dengan:")
        print("  set GFW_API_TOKEN=isi_token_anda   (Windows cmd)")
        print("  $env:GFW_API_TOKEN='isi_token_anda' (PowerShell)")
        print("lalu jalankan ulang: python pilot4_gfw_fishing_effort.py")
        raise SystemExit(1)

    all_rows = []
    years = sorted(set(p[1][:4] for p in PERIODE))
    for year in years:
        start_date = f"{year}-01-01"
        end_date = f"{int(year)+1}-01-01"
        # batasi end_date ke periode terakhir yang diminta (2026-06)
        if year == years[-1]:
            end_date = f"{year}-07-01"

        print(f"\n[{year}] Mengambil data...")
        try:
            data = fetch_fishing_effort_year(year, start_date, end_date, GFW_API_TOKEN)
        except requests.exceptions.HTTPError as e:
            print(f"  ERROR: {e}")
            print(f"  Response: {e.response.text[:500]}")
            continue
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # Struktur respons v3: data["entries"] adalah LIST OF DICT, dimana
        # setiap dict punya key = nama dataset (misal
        # "public-global-fishing-effort:v4.0"), berisi list record per
        # kapal/periode dengan field seperti "date", "hours", "lat", "lon".
        entries = data.get("entries", [])
        for entry_dict in entries:
            for dataset_key, records in entry_dict.items():
                if isinstance(records, list):
                    for rec in records:
                        rec["_dataset"] = dataset_key
                        all_rows.append(rec)

        print(f"  Berhasil, {len(entries)} grup data diterima.")
        time.sleep(1)  # sopan terhadap rate limit

    if all_rows:
        result = pd.DataFrame(all_rows)
        result.to_csv("gfw_fishing_effort_rembang_raw.csv", index=False)
        print(f"\nData mentah (per kapal) disimpan: gfw_fishing_effort_rembang_raw.csv ({len(result)} baris)")
        print(result.head(5).to_string())

        # Agregasi: total jam (hours) per bulan, dan jumlah kapal unik per bulan
        agg = (
            result.groupby("date")
            .agg(
                total_fishing_hours=("hours", "sum"),
                jumlah_kapal_unik=("mmsi", "nunique"),
            )
            .reset_index()
            .sort_values("date")
        )
        agg.to_csv("gfw_fishing_effort_rembang_monthly.csv", index=False)
        print(f"\nAgregasi bulanan disimpan: gfw_fishing_effort_rembang_monthly.csv ({len(agg)} baris)")
        print(agg.head(10).to_string(index=False))
        print("...")
        print(agg.tail(10).to_string(index=False))
    else:
        print("\nTidak ada data yang berhasil diambil. Cek token dan koneksi.")
