# -*- coding: utf-8 -*-
"""
extract_pdrb_timeseries_v2.py
================================
Versi perbaikan: file punya 2 tabel (TABEL 1 = ADHB baris ~8-74,
TABEL 2 = ADHK seri 2010 baris ~85-151). Setiap tabel punya 17 kategori
lapangan usaha (A-Q, M,N gabung, R,S,T,U gabung) + baris total
" PRODUK DOMESTIK REGIONAL BRUTO".

Output:
  - pdrb_rembang_long_adhb.csv  : 17 kategori x periode, ADHB
  - pdrb_rembang_long_adhk.csv  : 17 kategori x periode, ADHK (riil)
  - pdrb_total_triwulanan.csv   : PDRB total (ADHB & ADHK) per triwulan,
    dari baris resmi "PRODUK DOMESTIK REGIONAL BRUTO"
  - pdrb_kategori_A_triwulanan.csv : kategori A (Pertanian) ADHK, untuk
    korelasi dengan NDVI
"""

import pandas as pd

raw = pd.read_excel("PDRB_Kab_Rembang_triwulanan.xlsx", sheet_name="3317", header=None)

triwulan_order = {"I": 1, "II": 2, "III": 3, "IV": 4}

# ---------------------------------------------------------------------------
# 1. Kolom triwulanan (sama untuk kedua tabel, header di baris 3-4)
# ---------------------------------------------------------------------------
year_header_row = raw.iloc[3]
quarter_header_row = raw.iloc[4]

col_map = []
current_year = None
for col_idx in range(4, raw.shape[1]):
    val = year_header_row[col_idx]
    if isinstance(val, str) and val.startswith("Triwulanan"):
        current_year = int(val.split()[-1])
    q_label = quarter_header_row[col_idx]
    if isinstance(q_label, str) and q_label.strip() in ("I", "II", "III", "IV"):
        col_map.append((col_idx, current_year, q_label.strip()))

print(f"Total kolom triwulanan: {len(col_map)} (periode {col_map[0][1]}{col_map[0][2]} - {col_map[-1][1]}{col_map[-1][2]})")

# ---------------------------------------------------------------------------
# 2. Kategori 1-17 huruf (termasuk gabungan M,N dan R,S,T,U)
# ---------------------------------------------------------------------------
KATEGORI_VALID = set("ABCDEFGHIJKLOPQ") | {"M,N", "R,S,T,U"}


def find_table_rows(start_row, end_row):
    """Cari baris kategori dan baris total PDRB dalam rentang baris tertentu."""
    rows_kategori = []
    row_total = None
    for row_idx in range(start_row, end_row):
        val = raw.iloc[row_idx, 0]
        if isinstance(val, str) and val.strip() in KATEGORI_VALID:
            deskripsi = raw.iloc[row_idx, 1]
            if pd.isna(deskripsi):
                deskripsi = raw.iloc[row_idx, 2]
            rows_kategori.append((row_idx, val.strip(), str(deskripsi)))
        # baris total: kolom 1 mengandung "PRODUK DOMESTIK REGIONAL BRUTO"
        # tapi BUKAN "TANPA MIGAS"
        val1 = raw.iloc[row_idx, 1]
        if isinstance(val1, str) and "PRODUK DOMESTIK REGIONAL BRUTO" in val1 and "TANPA" not in val1.upper():
            row_total = row_idx
    return rows_kategori, row_total


def reshape_long(rows_kategori, row_total, label):
    long_rows = []
    for row_idx, kategori, deskripsi in rows_kategori:
        for col_idx, tahun, triwulan in col_map:
            val = raw.iloc[row_idx, col_idx]
            long_rows.append({
                "kategori": kategori, "deskripsi": deskripsi,
                "tahun": tahun, "triwulan": triwulan, "nilai_juta_rupiah": val,
            })
    long_df = pd.DataFrame(long_rows)

    total_rows = []
    if row_total is not None:
        for col_idx, tahun, triwulan in col_map:
            val = raw.iloc[row_total, col_idx]
            total_rows.append({"tahun": tahun, "triwulan": triwulan, "pdrb_total_juta_rupiah": val})
    total_df = pd.DataFrame(total_rows)

    for d in (long_df, total_df):
        d["triwulan_num"] = d["triwulan"].map(triwulan_order)
        d["periode"] = d["tahun"].astype(str) + "Q" + d["triwulan_num"].astype(str)
        d.sort_values(["tahun", "triwulan_num"], inplace=True)

    return long_df, total_df


# ---------------------------------------------------------------------------
# 3. Proses TABEL 1 (ADHB) dan TABEL 2 (ADHK)
# ---------------------------------------------------------------------------
rows_adhb, total_adhb_row = find_table_rows(8, 76)
rows_adhk, total_adhk_row = find_table_rows(85, 152)

print(f"\nADHB: {len(rows_adhb)} kategori, baris total = {total_adhb_row}")
print(f"ADHK: {len(rows_adhk)} kategori, baris total = {total_adhk_row}")
print("\nKategori ADHB:", [(k, d[:40]) for _, k, d in rows_adhb])

long_adhb, total_adhb = reshape_long(rows_adhb, total_adhb_row, "ADHB")
long_adhk, total_adhk = reshape_long(rows_adhk, total_adhk_row, "ADHK")

long_adhb.to_csv("pdrb_rembang_long_adhb.csv", index=False)
long_adhk.to_csv("pdrb_rembang_long_adhk.csv", index=False)
print(f"\nADHB long tersimpan ({len(long_adhb)} baris), ADHK long tersimpan ({len(long_adhk)} baris)")

# ---------------------------------------------------------------------------
# 4. Gabungkan total ADHB & ADHK
# ---------------------------------------------------------------------------
total_adhb = total_adhb.rename(columns={"pdrb_total_juta_rupiah": "pdrb_total_adhb"})
total_adhk = total_adhk.rename(columns={"pdrb_total_juta_rupiah": "pdrb_total_adhk"})
total_merged = total_adhb[["periode", "tahun", "triwulan_num", "pdrb_total_adhb"]].merge(
    total_adhk[["periode", "pdrb_total_adhk"]], on="periode", how="outer"
).sort_values(["tahun", "triwulan_num"])
total_merged.to_csv("pdrb_total_triwulanan.csv", index=False)
print(f"\nPDRB total tersimpan: pdrb_total_triwulanan.csv ({len(total_merged)} baris)")
print(total_merged.tail(10).to_string(index=False))

# ---------------------------------------------------------------------------
# 5. Kategori A (ADHK) - untuk korelasi NDVI
# ---------------------------------------------------------------------------
pdrb_a_adhk = long_adhk[long_adhk["kategori"] == "A"][["periode", "nilai_juta_rupiah"]]
pdrb_a_adhk.to_csv("pdrb_kategori_A_triwulanan.csv", index=False)
print(f"\nPDRB kategori A (ADHK) tersimpan: pdrb_kategori_A_triwulanan.csv ({len(pdrb_a_adhk)} baris)")
print(pdrb_a_adhk.head(8).to_string(index=False))
