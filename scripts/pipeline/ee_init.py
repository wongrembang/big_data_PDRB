# -*- coding: utf-8 -*-
"""
ee_init.py
==========
Helper inisialisasi Google Earth Engine, dipakai oleh skrip pipeline.

- Di GitHub Actions: jika env GEE_SERVICE_ACCOUNT_KEY (isi JSON key service
  account) tersedia, login memakai service account tersebut.
- Di laptop: jika env itu tidak ada, memakai kredensial hasil
  `earthengine authenticate` seperti biasa.
"""

import json
import os

import ee

PROJECT = "pdrb-big-data-extraction"


def init():
    key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "").strip()
    if key:
        email = json.loads(key)["client_email"]
        creds = ee.ServiceAccountCredentials(email, key_data=key)
        ee.Initialize(creds, project=PROJECT)
    else:
        ee.Initialize(project=PROJECT)
