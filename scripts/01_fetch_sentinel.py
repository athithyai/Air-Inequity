"""
01_fetch_sentinel.py
--------------------
Fetches monthly mean concentrations for NO2, SO2, CO, O3, HCHO from
Sentinel-5P TROPOMI via the Sentinel Hub Statistical API.

API KEY: Edit SH_CLIENT_ID and SH_CLIENT_SECRET in scripts/config.py

Output: data/raw/sentinel/{no2,so2,co,o3,hcho}_raw.csv
        columns: NUTS_ID, year, month, <POLLUTANT>

Runtime: several hours (40 regions × 6 years × 12 months × 5 pollutants).
Progress is saved after every row — safe to interrupt and resume.

Usage:
    python scripts/01_fetch_sentinel.py
    python scripts/01_fetch_sentinel.py --pollutants NO2 --years 2023   # quick test
"""

import argparse
import calendar
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_PROCESSED,
    DATA_SENTINEL,
    MONTHS,
    S5P_START,
    SH_CLIENT_ID,
    SH_CLIENT_SECRET,
    YEARS,
)

import geopandas as gpd
import pandas as pd
from sentinelhub import (
    CRS,
    DataCollection,
    Geometry,
    SHConfig,
    SentinelHubStatistical,
)

# CDSE uses 'sentinel-5p-l2' as the collection ID.
# We define a custom DataCollection pointing at it so the library
# sends the correct API request to the CDSE endpoint.
CDSE_S5P = DataCollection.define(
    name="CDSE_SENTINEL5P",
    api_id="sentinel-5p-l2",
    service_url="https://sh.dataspace.copernicus.eu",
)


# ── CLI args for quick test runs ──────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--pollutants", nargs="+", default=["NO2", "SO2", "CO", "O3", "HCHO"])
parser.add_argument("--years",      nargs="+", type=int, default=YEARS)
parser.add_argument("--sleep",      type=float, default=5.0,
                    help="Seconds to wait between API calls (increase if rate-limited)")
args = parser.parse_args()

POLLUTANTS_TO_RUN = args.pollutants
YEARS_TO_RUN      = args.years
SLEEP_S           = args.sleep


# ── Sentinel Hub config ───────────────────────────────────────────────────────
if SH_CLIENT_ID == "YOUR_CDSE_CLIENT_ID":
    sys.exit("ERROR: Set SH_CLIENT_ID and SH_CLIENT_SECRET in scripts/config.py first.\n"
             "Register free at https://dataspace.copernicus.eu")

cfg = SHConfig()
cfg.sh_client_id     = SH_CLIENT_ID
cfg.sh_client_secret = SH_CLIENT_SECRET
cfg.sh_base_url      = "https://sh.dataspace.copernicus.eu"
cfg.sh_token_url     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


# ── Evalscripts ───────────────────────────────────────────────────────────────
def make_evalscript(band: str) -> str:
    return f"""
//VERSION=3
function setup() {{
  return {{
    input: [{{ bands: ["{band}", "dataMask"] }}],
    output: [
      {{ id: "value", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "dataMask", bands: 1 }}
    ]
  }};
}}
function evaluatePixel(samples) {{
  return {{
    value: [samples.{band}],
    dataMask: [samples.dataMask]
  }};
}}
"""

EVALSCRIPTS = {p: make_evalscript(p) for p in ["NO2", "SO2", "CO", "O3", "HCHO"]}


# ── Fetch one region / month ──────────────────────────────────────────────────
def fetch_monthly_mean(nuts_id, geometry, year, month, evalscript, max_retries=3):
    start   = f"{year}-{month:02d}-01"
    end_day = calendar.monthrange(year, month)[1]
    end     = f"{year}-{month:02d}-{end_day}"
    geom    = Geometry(geometry=geometry.__geo_interface__, crs=CRS.WGS84)

    request = SentinelHubStatistical(
        aggregation=SentinelHubStatistical.aggregation(
            evalscript=evalscript,
            time_interval=(start, end),
            aggregation_interval="P1D",
            resolution=(3500, 3500),
        ),
        input_data=[SentinelHubStatistical.input_data(CDSE_S5P)],
        geometry=geom,
        config=cfg,
    )

    for attempt in range(max_retries):
        try:
            import math
            data = request.get_data()[0]
            # Filter out NaN days (cloud cover / no valid pixels) before averaging
            daily_means = [
                float(iv["outputs"]["value"]["bands"]["B0"]["stats"]["mean"])
                for iv in data.get("data", [])
                if iv.get("outputs")
            ]
            valid = [v for v in daily_means if not math.isnan(v)]
            return sum(valid) / len(valid) if valid else None
        except Exception as exc:
            msg = str(exc)
            # No data available for this period — don't retry
            if any(s in msg for s in ("no data", "No data", "empty", "404", "Bad Request")):
                return None
            wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
            print(f"  [{nuts_id} {year}-{month:02d}] attempt {attempt+1} failed: {exc!r}. "
                  f"Retrying in {wait}s")
            time.sleep(wait)
    return None


# ── Main loop ─────────────────────────────────────────────────────────────────
nuts = gpd.read_file(DATA_PROCESSED / "nl_nuts3.geojson").to_crs("EPSG:4326")
print(f"Loaded {len(nuts)} NL NUTS-3 regions")

for pollutant in POLLUTANTS_TO_RUN:
    out_path = DATA_SENTINEL / f"{pollutant.lower()}_raw.csv"

    # Resume support
    if out_path.exists():
        existing = pd.read_csv(out_path)
        done     = set(zip(existing["NUTS_ID"], existing["year"], existing["month"]))
        rows     = existing.to_dict("records")
        print(f"\n[{pollutant}] Resuming — {len(done)} rows already done")
    else:
        done, rows = set(), []

    evalscript = EVALSCRIPTS[pollutant]
    total = len(nuts) * len(YEARS_TO_RUN) * len(MONTHS)
    n = 0

    for _, region in nuts.iterrows():
        nuts_id = region["NUTS_ID"]
        geom    = region.geometry

        for year in YEARS_TO_RUN:
            for month in MONTHS:
                # Skip months before Sentinel-5P became operational
                if (year, month) < S5P_START:
                    n += 1
                    continue

                if (nuts_id, year, month) in done:
                    n += 1
                    continue

                value = fetch_monthly_mean(nuts_id, geom, year, month, evalscript)
                rows.append({"NUTS_ID": nuts_id, "year": year, "month": month, pollutant: value})
                done.add((nuts_id, year, month))
                pd.DataFrame(rows).to_csv(out_path, index=False)

                n += 1
                print(f"[{pollutant}] {n}/{total}  {nuts_id} {year}-{month:02d}: {value}")
                time.sleep(SLEEP_S)

    print(f"[{pollutant}] ✓ Done → {out_path}")

print("\n✓ 01_fetch_sentinel done")
