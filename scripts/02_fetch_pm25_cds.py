"""
02_fetch_pm25_cds.py
--------------------
Downloads monthly PM2.5 from the CAMS Global Reanalysis (EAC4) via the
Copernicus Atmosphere Data Store, then spatially aggregates to NL NUTS-3.

API KEY: No key in this file — the CDS client reads ~/.cdsapirc automatically.
Create that file:
    url: https://ads.atmosphere.copernicus.eu/api
    key: <your-key>
Get your key at: https://ads.atmosphere.copernicus.eu → My account → API key

Output: data/raw/pm25/pm25_combined.csv  (columns: NUTS_ID, year, month, PM25)

Usage:
    python scripts/02_fetch_pm25_cds.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PM25, DATA_PROCESSED, MONTHS, YEARS

import cdsapi
import geopandas as gpd
import pandas as pd
import xarray as xr
from rasterio.transform import from_bounds
from rasterstats import zonal_stats


NC_PATH  = DATA_PM25 / "pm25_eac4.nc"
OUT_PATH = DATA_PM25 / "pm25_combined.csv"


# ── 1. Download NetCDF (single bulk request) ──────────────────────────────────
if NC_PATH.exists():
    print(f"NetCDF already at {NC_PATH} — skipping download.")
else:
    print("Requesting PM2.5 from Copernicus ADS (this may take 10–30 min)…")
    c = cdsapi.Client()
    c.retrieve(
        "cams-global-reanalysis-eac4-monthly",
        {
            "variable":      "particulate_matter_2.5um",
            "year":          [str(y) for y in YEARS],
            "month":         [f"{m:02d}" for m in range(1, 13)],
            "product_type":  "monthly_mean",
            "format":        "netcdf",
        },
        str(NC_PATH),
    )
    print(f"Downloaded → {NC_PATH}  ({NC_PATH.stat().st_size / 1e6:.1f} MB)")


# ── 2. Open and inspect ───────────────────────────────────────────────────────
ds = xr.open_dataset(NC_PATH)
print(f"\nVariables: {list(ds.data_vars)}")
print(f"Time steps: {len(ds.coords['time'])}  ({ds.coords['time'].values[0]} … {ds.coords['time'].values[-1]})")

# EAC4 uses 'pm2p5' for PM2.5
PM25_VAR = "pm2p5"
if PM25_VAR not in ds:
    available = list(ds.data_vars)
    sys.exit(f"Expected variable '{PM25_VAR}' not found. Available: {available}")


# ── 3. Load NUTS-3 geometries ─────────────────────────────────────────────────
nuts = gpd.read_file(DATA_PROCESSED / "nl_nuts3.geojson").to_crs("EPSG:4326")
print(f"\n{len(nuts)} NL NUTS-3 regions loaded")


# ── 4. Spatial aggregation ────────────────────────────────────────────────────
lons = ds.coords["longitude"].values
lats = ds.coords["latitude"].values
res_lon = float(lons[1] - lons[0])
res_lat = float(lats[1] - lats[0])

# Build affine transform from grid bounds
transform = from_bounds(
    left   = float(lons.min()) - abs(res_lon) / 2,
    bottom = float(lats.min()) - abs(res_lat) / 2,
    right  = float(lons.max()) + abs(res_lon) / 2,
    top    = float(lats.max()) + abs(res_lat) / 2,
    width  = len(lons),
    height = len(lats),
)

rows = []
times = pd.DatetimeIndex(ds.coords["time"].values)
total = len(times)

for i, t in enumerate(times, 1):
    year  = t.year
    month = t.month

    arr = ds[PM25_VAR].sel(time=t).values  # shape: (lat, lon)

    # rasterstats expects top→bottom latitude order
    if res_lat > 0:      # ascending lat → flip
        arr = arr[::-1, :]

    arr = arr * 1e9      # kg/m³ → µg/m³

    stats = zonal_stats(nuts, arr, affine=transform, stats=["mean"], nodata=np.nan)

    for region, stat in zip(nuts.itertuples(), stats):
        rows.append({
            "NUTS_ID": region.NUTS_ID,
            "year":    year,
            "month":   month,
            "PM25":    stat["mean"],
        })

    print(f"  [{i}/{total}] {year}-{month:02d} done")

pm25_df = pd.DataFrame(rows)
pm25_df.to_csv(OUT_PATH, index=False)
print(f"\n✓ Saved {len(pm25_df)} rows → {OUT_PATH}")
print(f"  PM25 range: [{pm25_df['PM25'].min():.2f}, {pm25_df['PM25'].max():.2f}] µg/m³")
print("\n✓ 02_fetch_pm25_cds done")
