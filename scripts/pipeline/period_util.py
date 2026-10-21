# -*- coding: utf-8 -*-
"""
period_util.py
==============
Menghitung batas akhir periode data secara otomatis, supaya pipeline ikut
maju sendiri tanpa perlu mengubah angka di skrip tiap triwulan/bulan.

- last_completed_quarter(): triwulan terakhir yang SUDAH selesai -> (tahun, q)
- last_completed_month():   bulan terakhir yang SUDAH selesai   -> (tahun, bulan)

Contoh: 22 Okt 2026 -> (2026, 3) dan (2026, 9);  5 Jan 2027 -> (2026, 4) dan (2026, 12).
"""

from datetime import date


def last_completed_quarter(today=None):
    today = today or date.today()
    done = (today.month - 1) // 3  # jumlah triwulan yang sudah selesai tahun ini
    if done == 0:
        return today.year - 1, 4
    return today.year, done


def last_completed_month(today=None):
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1
