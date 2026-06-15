# SIMAK Rembang &mdash; Indikator Big Data untuk Proksi PDRB

Dashboard statis (3 halaman) yang menyajikan hasil eksplorasi penggunaan **citra satelit**
dan **data lalu lintas kapal (AIS)** sebagai pelengkap proksi PDRB Kabupaten Rembang,
terutama untuk gambaran tingkat kecamatan yang belum memiliki angka PDRB resmi.

**Live demo**: aktifkan GitHub Pages pada repo ini (lihat [Deploy ke GitHub Pages](#deploy-ke-github-pages)
di bawah), lalu akses `https://<username>.github.io/<repo>/`.

## Isi dashboard

| Halaman | Indikator | Sumber data |
|---|---|---|
| `index.html` | Beranda / ringkasan | &ndash; |
| `ndvi.html` | NDVI (kehijauan vegetasi) | Sentinel-2 / Landsat via Google Earth Engine |
| `ntl.html` | NTL (cahaya malam) | VIIRS via Google Earth Engine |
| `gfw.html` | Aktivitas kapal nelayan | Global Fishing Watch API |

Setiap halaman menampilkan: peta choropleth 14 kecamatan, grafik tren historis, dan
(untuk NDVI & NTL) perbandingan dengan data PDRB resmi Kabupaten Rembang.

## Struktur folder

```
.
├── index.html              # beranda
├── ndvi.html               # dashboard NDVI
├── ntl.html                # dashboard NTL
├── gfw.html                # dashboard perikanan/GFW
├── assets/
│   ├── style.css           # shared stylesheet
│   ├── shared.js           # helper umum (navbar, formatting, skala warna)
│   ├── ndvi.js              # logic dashboard NDVI
│   ├── ntl.js               # logic dashboard NTL
│   ├── gfw.js               # logic dashboard GFW
│   └── data.js              # SEMUA DATA, di-generate dari data/raw/*.csv
├── data/
│   └── raw/                 # file CSV/GeoJSON mentah (sumber data.js)
└── scripts/
    ├── build_data_js.py      # gabungkan data/raw/*.csv -> assets/data.js
    └── pipeline/              # skrip pengambilan data dari sumber asli
        ├── 01_fetch_satellite_timeseries.py
        ├── 02_clean_satellite_timeseries.py
        ├── 03_ndvi_cropland_masked.py
        ├── 04_extract_pdrb.py
        ├── 05_correlate_ndvi_pdrb.py
        ├── 06_fetch_gfw_fishing_effort.py
        └── batas_kecamatan_rembang_simplified.geojson
```

## Cara kerja dashboard (penting untuk kontributor lain)

Dashboard ini adalah **situs statis murni** &mdash; tidak ada server/backend. Semua data
sudah "dibakukan" ke dalam satu file `assets/data.js` (sekitar 370 KB) yang dimuat oleh
ketiga halaman dashboard. Ini membuat dashboard dapat di-hosting di GitHub Pages tanpa
biaya dan tanpa API key apa pun untuk PENGGUNA dashboard.

API key (Google Earth Engine, Global Fishing Watch) hanya dibutuhkan saat **memperbarui
data** (lihat bawah), bukan untuk melihat dashboard.

## Memperbarui data (refresh)

Memperbarui data dilakukan dalam beberapa tahap. Beberapa tahap memerlukan kredensial
yang bersifat personal (akun Google Earth Engine, token Global Fishing Watch) sehingga
**tidak dapat dijalankan otomatis di GitHub** &mdash; jalankan secara lokal di komputer
Anda, lalu commit hasilnya.

### Prasyarat

```bash
pip install pandas geopandas shapely earthengine-api requests --break-system-packages
```

Autentikasi Google Earth Engine (sekali saja per komputer):
```bash
earthengine authenticate
```

### Tahap 1 &mdash; Ambil data satelit (NDVI & NTL)

```bash
cd scripts/pipeline
python 01_fetch_satellite_timeseries.py
```
Mengambil NDVI & NTL per kecamatan per triwulan, 2010&ndash;sekarang, dari Google Earth
Engine. **Proses ini panjang** (puluhan periode x 14 kecamatan) dan mendukung resume
otomatis jika terhenti. Output: `indikator_timeseries_satelit_2010_2026.csv`.

### Tahap 2 &mdash; Bersihkan & flag kualitas data

```bash
python 02_clean_satellite_timeseries.py
```
Menandai periode dengan kualitas NTL rendah (`ntl_valid`), dan menambahkan kolom
rekomendasi (`ndvi_recommended`, `ntl_recommended`). Output:
`timeseries_satelit_cleaned.csv`, `timeseries_satelit_annual.csv`.

### Tahap 3 &mdash; NDVI dengan masking lahan pertanian

```bash
python 03_ndvi_cropland_masked.py
```
Menghitung ulang NDVI khusus untuk area "Cropland" (ESA WorldCover), yang terbukti
meningkatkan korelasi dengan PDRB Tanaman Pangan. Output:
`ndvi_cropland_masked_2017_2026.csv`.

### Tahap 4 &mdash; Ekstrak data PDRB resmi

```bash
python 04_extract_pdrb.py
```
Membutuhkan file `PDRB Kab Rembang triwulanan.xlsx` (publikasi BPS, sheet "3317") di
folder yang sama. Output: `pdrb_total_triwulanan.csv`,
`pdrb_tanaman_pangan_triwulanan.csv`, dan beberapa file PDRB per kategori lainnya.

### Tahap 5 &mdash; (Opsional) Hitung ulang korelasi

```bash
python 05_correlate_ndvi_pdrb.py
```
Mencetak ulang angka-angka korelasi yang ditampilkan di dashboard NDVI. Berguna untuk
verifikasi setelah data diperbarui.

### Tahap 6 &mdash; Ambil data Global Fishing Watch

```bash
export GFW_API_TOKEN="token_anda"   # daftar gratis di globalfishingwatch.org
python 06_fetch_gfw_fishing_effort.py
```
Output: `gfw_fishing_effort_rembang_raw.csv`, `gfw_fishing_effort_rembang_monthly.csv`.

### Tahap 7 &mdash; Gabungkan semua data ke dashboard

Salin semua file CSV output dari tahap 1&ndash;6 ke `data/raw/`, lalu jalankan:

```bash
cd ../  # ke folder scripts/
python build_data_js.py
```

Ini akan menghasilkan/memperbarui `assets/data.js`. Commit perubahan pada
`assets/data.js` dan `data/raw/*.csv` untuk memperbarui dashboard live.

## Deploy ke GitHub Pages

1. Push repo ini ke GitHub (lihat langkah git di bawah).
2. Di repo GitHub, buka **Settings &rarr; Pages**.
3. Pada **Source**, pilih branch `main` dan folder `/ (root)`.
4. Simpan. Dashboard akan tersedia di `https://<username>.github.io/<repo>/` dalam
   beberapa menit.

```bash
git init
git add .
git commit -m "Initial commit: SIMAK Rembang dashboard"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

## Keterbatasan & catatan metodologis

Ringkasan keterbatasan utama (penjelasan lengkap ada di artikel pendamping proyek):

- **NTL**: korelasi level dengan PDRB Total = 0,86 (kuat), tetapi korelasi growth = 0,07
  (sangat lemah) &mdash; cocok untuk perbandingan antar-kecamatan, belum untuk nowcasting
  triwulanan.
- **NDVI**: korelasi growth meningkat dari 0,31 (seluruh wilayah) menjadi 0,47 (lahan
  pertanian saja, ESA WorldCover 2021) terhadap PDRB Tanaman Pangan &mdash; kategori
  "sedang".
- **GFW**: data representatif baru tersedia sejak Juni 2024 (lonjakan adopsi AIS),
  sehingga belum dikorelasikan dengan PDRB Perikanan.
- Peta tutupan lahan (ESA WorldCover) adalah snapshot 2021 yang dipakai statis untuk
  seluruh periode &mdash; tidak menangkap perubahan penggunaan lahan dari waktu ke waktu.

## Lisensi & atribusi

Data bersumber dari Google Earth Engine (Copernicus Sentinel-2, NASA/NOAA VIIRS, ESA
WorldCover), Global Fishing Watch, dan publikasi resmi BPS Kabupaten Rembang. Batas
administrasi kecamatan dari Badan Informasi Geospasial (BIG).
