# data/raw/

File CSV dan GeoJSON mentah, hasil dari skrip di `scripts/pipeline/`. File-file ini
digabungkan oleh `scripts/build_data_js.py` menjadi `assets/data.js`, yang dipakai
langsung oleh dashboard.

| File | Asal | Digunakan di |
|---|---|---|
| `batas_kecamatan_rembang.geojson` | `scripts/pipeline/01_fetch_satellite_timeseries.py` (geometri disederhanakan) | Peta semua dashboard |
| `timeseries_satelit_cleaned.csv` | Tahap 1 + 2 | Dashboard NDVI & NTL |
| `timeseries_satelit_annual.csv` | Tahap 2 | (cadangan, agregasi tahunan) |
| `ndvi_cropland_masked_2017_2026.csv` | Tahap 3 | Dashboard NDVI (peta & korelasi) |
| `pdrb_total_triwulanan.csv` | Tahap 4 | Dashboard NTL (korelasi) |
| `pdrb_tanaman_pangan_triwulanan.csv` | Tahap 4 | Dashboard NDVI (korelasi) |
| `gfw_fishing_effort_rembang_monthly.csv` | Tahap 6 | Dashboard GFW (tren) |
| `gfw_fishing_effort_rembang_raw.csv` | Tahap 6 | Dashboard GFW (geartype & tabel kapal) |

Setelah memperbarui file-file ini, jalankan `python scripts/build_data_js.py` untuk
memperbarui `assets/data.js`.
