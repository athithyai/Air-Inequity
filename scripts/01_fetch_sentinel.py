"""
01_fetch_sentinel.py
--------------------
Fetches monthly mean concentrations for NO2, SO2, CO, O3, HCHO from
Sentinel-5P TROPOMI via the Sentinel Hub Statistical API.

API KEY: Edit SH_CLIENT_ID and SH_CLIENT_SECRET in scripts/config.py

Output: data/raw/sentinel/{no2,so2,co,o3,hcho}_raw.csv
        columns: NUTS_ID, year, month, <POLLUTANT>

Runtime: ~1.5 hours with 4 workers (was ~17 hours sequential).
Progress is saved after every row — safe to interrupt and resume.

Usage:
    python scripts/01_fetch_sentinel.py
    python scripts/01_fetch_sentinel.py --workers 4
    python scripts/01_fetch_sentinel.py --pollutants NO2 --years 2023   # quick test
"""

import argparse
import calendar
import csv
import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
CDSE_S5P = DataCollection.define(
    name="CDSE_SENTINEL5P",
    api_id="sentinel-5p-l2",
    service_url="https://sh.dataspace.copernicus.eu",
)


# ── CLI args ───────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--pollutants", nargs="+", default=["NO2", "SO2", "CO", "O3", "HCHO"])
parser.add_argument("--years",      nargs="+", type=int, default=YEARS)
parser.add_argument("--workers",    type=int, default=4,
                    help="Number of parallel API threads (default 4; drop to 2 if rate-limited)")
args = parser.parse_args()

POLLUTANTS_TO_RUN = args.pollutants
YEARS_TO_RUN      = args.years
N_WORKERS         = args.workers


# ── Credentials check ─────────────────────────────────────────────────────────
if SH_CLIENT_ID == "YOUR_CDSE_CLIENT_ID":
    sys.exit("ERROR: Set SH_CLIENT_ID and SH_CLIENT_SECRET in scripts/config.py first.\n"
             "Register free at https://dataspace.copernicus.eu")


# ── Per-thread SHConfig (avoids OAuth token conflicts across threads) ──────────
_thread_local = threading.local()

def get_cfg() -> SHConfig:
    if not hasattr(_thread_local, "cfg"):
        c = SHConfig()
        c.sh_client_id     = SH_CLIENT_ID
        c.sh_client_secret = SH_CLIENT_SECRET
        c.sh_base_url      = "https://sh.dataspace.copernicus.eu"
        c.sh_token_url     = ("https://identity.dataspace.copernicus.eu"
                              "/auth/realms/CDSE/protocol/openid-connect/token")
        _thread_local.cfg = c
    return _thread_local.cfg


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
        config=get_cfg(),
    )

    for attempt in range(max_retries):
        try:
            data = request.get_data()[0]
            daily_means = [
                float(iv["outputs"]["value"]["bands"]["B0"]["stats"]["mean"])
                for iv in data.get("data", [])
                if iv.get("outputs")
            ]
            valid = [v for v in daily_means if not math.isnan(v)]
            return sum(valid) / len(valid) if valid else None
        except Exception as exc:
            msg = str(exc)
            if any(s in msg for s in ("no data", "No data", "empty", "404", "Bad Request")):
                return None
            wait = 10 * (2 ** attempt)  # 10s, 20s, 40s
            print(f"  [{nuts_id} {year}-{month:02d}] attempt {attempt+1} failed: {exc!r}. "
                  f"Retrying in {wait}s")
            time.sleep(wait)
    return None


# ── Worker function ───────────────────────────────────────────────────────────
def fetch_and_save(nuts_id, geom, year, month, pollutant, evalscript, out_path, csv_lock, counter):
    value = fetch_monthly_mean(nuts_id, geom, year, month, evalscript)
    with csv_lock:
        with open(out_path, "a", newline="") as f:
            csv.writer(f).writerow([nuts_id, year, month, value])
        counter["n"] += 1
        n = counter["n"]
        total = counter["total"]
    print(f"[{pollutant}] {n}/{total}  {nuts_id} {year}-{month:02d}: {value}")
    return value


# ── Main loop ─────────────────────────────────────────────────────────────────
nuts = gpd.read_file(DATA_PROCESSED / "nl_nuts3.geojson").to_crs("EPSG:4326")
print(f"Loaded {len(nuts)} NL NUTS-3 regions | {N_WORKERS} workers")

for pollutant in POLLUTANTS_TO_RUN:
    out_path = DATA_SENTINEL / f"{pollutant.lower()}_raw.csv"

    # Resume: read already-completed rows
    if out_path.exists():
        existing = pd.read_csv(out_path)
        done = set(zip(existing["NUTS_ID"], existing["year"], existing["month"]))
        print(f"\n[{pollutant}] Resuming — {len(done)} rows already done")
    else:
        done = set()
        # Write header
        with open(out_path, "w", newline="") as f:
            csv.writer(f).writerow(["NUTS_ID", "year", "month", pollutant])

    evalscript = EVALSCRIPTS[pollutant]
    regions = [(row["NUTS_ID"], row.geometry) for _, row in nuts.iterrows()]

    # Build task list — skip already done and pre-Sentinel-5P months
    tasks = [
        (nuts_id, geom, year, month)
        for nuts_id, geom in regions
        for year in YEARS_TO_RUN
        for month in MONTHS
        if (year, month) >= S5P_START and (nuts_id, year, month) not in done
    ]

    csv_lock = threading.Lock()
    counter  = {"n": len(done), "total": len(done) + len(tasks)}

    print(f"[{pollutant}] {len(tasks)} calls remaining ({N_WORKERS} workers)")

    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        futures = {
            pool.submit(
                fetch_and_save,
                nuts_id, geom, year, month,
                pollutant, evalscript, out_path, csv_lock, counter
            ): (nuts_id, year, month)
            for nuts_id, geom, year, month in tasks
        }
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                nuts_id, year, month = futures[fut]
                print(f"  ERROR [{nuts_id} {year}-{month:02d}]: {exc!r}")

    print(f"[{pollutant}] Done → {out_path}")

print("\n✓ 01_fetch_sentinel done")
