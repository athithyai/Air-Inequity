"""
08_fetch_luchtmeetnet.py
------------------------
Fetches ground-station air quality data from Luchtmeetnet
(Dutch national air quality monitoring network).

Strategy (fast):
  - Get all station numbers + details (lat/lon)
  - Spatial join to NUTS-3
  - For each year 2018-2023: fetch 2 sample months (Jan + Jul) per station
    and average to annual proxy — reduces total API calls to manageable count

Output: data/raw/luchtmeetnet_stations.csv
        data/raw/luchtmeetnet_annual.csv  (NUTS_ID, year, NO2_ground, PM25_ground)
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_RAW

BASE = "https://api.luchtmeetnet.nl/open_api"
COMPONENTS = ["NO2", "PM25"]
YEARS = range(2018, 2024)
# Sample months to estimate annual mean (Jan=winter, Apr=spring, Jul=summer, Oct=autumn)
SAMPLE_MONTHS = [1, 4, 7, 10]


def api_get(path, params=None, retries=3):
    url = f"{BASE}{path}"
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                return data.get("data", data)
            return data
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(5)
    return []


# ── 1. Fetch all station numbers (5 pages) ─────────────────────────────────────
print("Fetching station list...")
station_numbers = []
for page in range(1, 10):
    rows = api_get("/stations", params={"page": page, "per_page": 100})
    if not rows:
        break
    batch = rows if isinstance(rows, list) else [rows]
    for s in batch:
        station_numbers.append(s["number"])
    if len(batch) < 100:
        break
    time.sleep(0.2)

print(f"  Found {len(station_numbers)} stations")


# ── 2. Fetch station details (lat/lon, components) ─────────────────────────────
print("Fetching station details...")
stations = []
for i, num in enumerate(station_numbers):
    detail = api_get(f"/stations/{num}")
    if not detail:
        continue
    if isinstance(detail, list):
        detail = detail[0] if detail else {}
    geom = detail.get("geometry", {})
    coords = geom.get("coordinates", [None, None])
    components = detail.get("components", [])
    stations.append({
        "station_number": num,
        "location":       detail.get("location"),
        "municipality":   detail.get("municipality"),
        "organisation":   detail.get("organisation"),
        "lon":            coords[0] if coords else None,
        "lat":            coords[1] if coords else None,
        "has_NO2":        "NO2"  in components,
        "has_PM25":       "PM25" in components,
    })
    if (i + 1) % 20 == 0:
        print(f"  {i+1}/{len(station_numbers)}")
    time.sleep(0.15)

stations_df = pd.DataFrame(stations).dropna(subset=["lon", "lat"])
print(f"  Got coordinates for {len(stations_df)} stations")

out_stations = DATA_RAW / "luchtmeetnet_stations.csv"
stations_df.to_csv(out_stations, index=False)
print(f"  Saved stations -> {out_stations}")


# ── 3. Spatial join to NUTS-3 ──────────────────────────────────────────────────
processed = Path(__file__).parent.parent / "data" / "processed"
try:
    import geopandas as gpd
    from shapely.geometry import Point

    gdf = gpd.read_file(processed / "nl_nuts3.geojson").to_crs("EPSG:4326")
    pts = gpd.GeoDataFrame(
        stations_df,
        geometry=[Point(row.lon, row.lat) for row in stations_df.itertuples()],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(pts, gdf[["NUTS_ID", "geometry"]], how="left", predicate="within")
    stations_df["NUTS_ID"] = joined["NUTS_ID"].values
    assigned = stations_df["NUTS_ID"].notna().sum()
    print(f"  Assigned {assigned}/{len(stations_df)} stations to NUTS-3 regions")
except Exception as e:
    print(f"  Spatial join failed: {e} — NUTS_ID left blank")
    stations_df["NUTS_ID"] = None

# Re-save with NUTS_ID
stations_df.to_csv(out_stations, index=False)


# ── 4. Fetch sample measurements and compute annual proxy ──────────────────────
print("\nFetching measurements (sample months)...")
records = []

# Only stations with desired components and a NUTS_ID
for comp in COMPONENTS:
    comp_col = f"has_{comp}"
    eligible = stations_df[
        stations_df["NUTS_ID"].notna() &
        stations_df.get(comp_col, pd.Series(True, index=stations_df.index))
    ]["station_number"].tolist()

    print(f"  {comp}: {len(eligible)} eligible stations")

    for yr in YEARS:
        monthly_vals = {stn: [] for stn in eligible}
        for mo in SAMPLE_MONTHS:
            start = f"{yr}-{mo:02d}-01T00:00:00"
            # last day of month
            import calendar
            last = calendar.monthrange(yr, mo)[1]
            end = f"{yr}-{mo:02d}-{last}T23:59:59"

            for stn in eligible:
                data = api_get("/measurements", params={
                    "station_number": stn,
                    "formula":        comp,
                    "start":          start,
                    "end":            end,
                    "page":           1,
                    "per_page":       500,
                })
                if data:
                    vals = [float(d["value"]) for d in (data if isinstance(data, list) else []) if d.get("value") is not None]
                    if vals:
                        monthly_vals[stn].append(sum(vals) / len(vals))
                time.sleep(0.1)

        # Average sampled months → annual proxy
        for stn, vals in monthly_vals.items():
            if vals:
                records.append({
                    "station_number": stn,
                    "year":           yr,
                    "component":      comp,
                    "annual_mean":    round(sum(vals) / len(vals), 3),
                })

        print(f"    {comp} {yr}: {sum(1 for v in monthly_vals.values() if v)} stations with data")

print(f"\nTotal records: {len(records)}")

if records:
    meas_df = pd.DataFrame(records)
    pivot = meas_df.pivot_table(
        index=["station_number", "year"],
        columns="component",
        values="annual_mean",
        aggfunc="mean",
    ).reset_index()
    pivot.columns.name = None
    rename = {c: f"{c}_ground" for c in COMPONENTS if c in pivot.columns}
    pivot = pivot.rename(columns=rename)

    pivot = pivot.merge(stations_df[["station_number", "NUTS_ID"]], on="station_number", how="left")

    regional = (
        pivot.groupby(["NUTS_ID", "year"])[
            [f"{c}_ground" for c in COMPONENTS if f"{c}_ground" in pivot.columns]
        ]
        .mean()
        .reset_index()
    )
else:
    print("No measurement data fetched — creating empty output")
    regional = pd.DataFrame(columns=["NUTS_ID", "year", "NO2_ground", "PM25_ground"])

out_annual = DATA_RAW / "luchtmeetnet_annual.csv"
regional.to_csv(out_annual, index=False)
print(f"Saved {len(regional)} regional rows -> {out_annual}")
if not regional.empty:
    print(regional.head(8).to_string())

print("\nDone: 08_fetch_luchtmeetnet")
