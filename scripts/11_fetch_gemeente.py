"""
11_fetch_gemeente.py
--------------------
Builds a gemeente-level (municipality) dataset for the dashboard.

Steps:
1. Download gemeente boundaries GeoJSON from PDOK (CBS generalized)
2. Fetch CBS 85318NED: gemeente-level income, density, low-income %
3. Fetch CBS 70262NED: gemeente-level land use (green %, industrial %)
4. Spatial join gemeente -> NUTS-3 to inherit Sentinel-5P pollution
5. Compute gemeente-level Air Inequity Index
6. Save:
     data/processed/nl_gemeente.geojson
     data/processed/gemeente_extended.csv

~342 gemeenten (2023 boundaries)
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PROCESSED, DATA_RAW

PROCESSED = DATA_PROCESSED
RAW = DATA_RAW

# ── 1. Download gemeente boundaries from PDOK ──────────────────────────────────
print("Fetching gemeente boundaries from PDOK...")

PDOK_WFS = (
    "https://service.pdok.nl/cbs/gebiedsindelingen/2023/wfs/v1_0"
    "?request=GetFeature&service=WFS&version=2.0.0"
    "&typeName=gemeente_gegeneraliseerd"
    "&outputFormat=application/json"
    "&srsName=EPSG:4326"
)

r = requests.get(PDOK_WFS, timeout=60)
r.raise_for_status()
geojson = r.json()

n_features = len(geojson["features"])
print(f"  Got {n_features} gemeente features")

# Inspect property keys
if geojson["features"]:
    props = geojson["features"][0]["properties"]
    print(f"  Properties: {list(props.keys())}")
    print(f"  Sample: {props}")

# Save raw GeoJSON
out_geojson = PROCESSED / "nl_gemeente.geojson"
import json
with open(out_geojson, "w", encoding="utf-8") as f:
    json.dump(geojson, f)
print(f"  Saved -> {out_geojson}")


# ── 2. Build gemeente code -> name mapping ─────────────────────────────────────
gem_codes = []
for feat in geojson["features"]:
    p = feat["properties"]
    # PDOK uses statcode (GM0003) and statnaam
    code = p.get("statcode") or p.get("gemeentecode") or p.get("GM_CODE")
    name = p.get("statnaam") or p.get("gemeentenaam") or p.get("GM_NAAM")
    if code:
        gem_codes.append({"GM_CODE": code, "GM_NAME": name})

gm_df = pd.DataFrame(gem_codes).drop_duplicates("GM_CODE")
print(f"\n  {len(gm_df)} unique gemeente codes (e.g. {gm_df['GM_CODE'].iloc[0]})")


# ── 3. CBS 85318NED — Socioeconomic data (gemeente level) ─────────────────────
print("\nFetching CBS socioeconomic data (85318NED)...")

# ODataApi doesn't support $skip — use ODataFeed endpoint for paginated queries
CBS_API  = "https://opendata.cbs.nl/ODataApi/odata"    # metadata / small lookups
CBS_FEED = "https://opendata.cbs.nl/ODataFeed/odata"   # paginated data

import urllib3
urllib3.disable_warnings()

def cbs_feed(table, filt, select, top=500, retries=3):
    """Fetch from CBS ODataFeed with pagination (supports $skip/$format)."""
    url  = f"{CBS_FEED}/{table}/TypedDataSet"
    hdrs = {"Accept": "application/json"}
    records, skip = [], 0
    while True:
        params = {"$filter": filt, "$select": select, "$top": top,
                  "$skip": skip, "$format": "json"}
        for attempt in range(retries):
            try:
                r = requests.get(url, params=params, headers=hdrs,
                                 timeout=30, verify=False)
                r.raise_for_status()
                rows = r.json().get("value", [])
                break
            except Exception as e:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(3)
                rows = []
        if not rows:
            break
        records.extend(rows)
        if len(rows) < top:
            break
        skip += top
        time.sleep(0.2)
    return records

# ── Socioeconomic: 85318NED (gemeente level) ──────────────────────────────────
# Use startswith(WijkenEnBuurten,'GM') — confirmed to return 345 rows
socio_records = cbs_feed(
    "85318NED",
    filt="startswith(WijkenEnBuurten,'GM')",
    select="WijkenEnBuurten,GemiddeldInkomenPerInwoner_72,HuishoudensMetEenLaagInkomen_78,PersonenautoSPerHuishouden_103,Omgevingsadressendichtheid_117",
)
print(f"  Fetched {len(socio_records)} socio rows")

socio_df = pd.DataFrame(socio_records)
if not socio_df.empty:
    socio_df["GM_CODE"] = socio_df["WijkenEnBuurten"].str.strip()
    socio_df = socio_df.rename(columns={
        "GemiddeldInkomenPerInwoner_72":   "avg_income",
        "HuishoudensMetEenLaagInkomen_78": "pct_low_income",
        "PersonenautoSPerHuishouden_103":  "cars_per_hh",
        "Omgevingsadressendichtheid_117":  "urban_density",
    })
    socio_df = socio_df[["GM_CODE","avg_income","pct_low_income","cars_per_hh","urban_density"]]
    print(f"  Sample: {socio_df.head(3).to_string()}")
else:
    print("  WARNING: No socio data")


# ── 4. CBS 70262NED — Land use (gemeente level) ────────────────────────────────
print("\nFetching CBS land use data (70262NED)...")

# Most recent period with actual data is 2017JJ00
LUSE_PERIOD = "2017JJ00"
print(f"  Using period: {LUSE_PERIOD}")

# 70262NED uses RegioS (not Codering_3) in ODataFeed
luse_records = cbs_feed(
    "70262NED",
    filt=f"startswith(RegioS,'GM') and Perioden eq '{LUSE_PERIOD}'",
    select="RegioS,TotaleOppervlakte_1,ParkEnPlantsoen_20,TotaalBosEnOpenNatuurlijkTerrein_28,TotaalRecreatieterrein_19,Bedrijventerrein_11",
)
print(f"  Fetched {len(luse_records)} land use rows")

luse_df = pd.DataFrame(luse_records)
if not luse_df.empty:
    luse_df["GM_CODE"] = luse_df["RegioS"].str.strip()
    luse_df = luse_df.rename(columns={
        "TotaleOppervlakte_1":                "total_area_ha",
        "ParkEnPlantsoen_20":                 "park_ha",
        "TotaalBosEnOpenNatuurlijkTerrein_28": "forest_ha",
        "TotaalRecreatieterrein_19":           "recreation_ha",
        "Bedrijventerrein_11":                 "industrial_ha",
    })
    for col in ["park_ha","forest_ha","recreation_ha","industrial_ha","total_area_ha"]:
        luse_df[col] = pd.to_numeric(luse_df[col], errors="coerce")
    area = luse_df["total_area_ha"].replace(0, np.nan)
    luse_df["green_pct"]      = ((luse_df["park_ha"] + luse_df["forest_ha"] + luse_df["recreation_ha"]) / area * 100).round(2)
    luse_df["industrial_pct"] = (luse_df["industrial_ha"] / area * 100).round(2)
    luse_df = luse_df[["GM_CODE","total_area_ha","green_pct","industrial_pct"]]
    print(f"  Sample: {luse_df.head(3).to_string()}")
else:
    print("  WARNING: No land use data")


# ── 5. Spatial join gemeente -> NUTS-3 ─────────────────────────────────────────
print("\nSpatial join gemeente -> NUTS-3...")

try:
    import geopandas as gpd

    gdf_gem  = gpd.read_file(out_geojson).to_crs("EPSG:4326")
    gdf_nuts = gpd.read_file(PROCESSED / "nl_nuts3.geojson").to_crs("EPSG:4326")

    # Use centroid of each gemeente to find its NUTS-3 parent
    gdf_gem["centroid"] = gdf_gem.geometry.centroid
    gdf_pts = gdf_gem.copy()
    gdf_pts["geometry"] = gdf_pts["centroid"]

    joined = gpd.sjoin(
        gdf_pts[["statcode", "geometry"]],
        gdf_nuts[["NUTS_ID", "NUTS_NAME", "geometry"]],
        how="left", predicate="within"
    )
    # Some centroids may fall outside (border effects) — fallback to nearest
    missing = joined["NUTS_ID"].isna()
    if missing.any():
        print(f"  {missing.sum()} centroids outside any NUTS-3 — using nearest")
        nearest = gpd.sjoin_nearest(
            gdf_pts[missing][["statcode","geometry"]],
            gdf_nuts[["NUTS_ID","NUTS_NAME","geometry"]],
            how="left"
        )
        joined.loc[missing, "NUTS_ID"]   = nearest["NUTS_ID"].values
        joined.loc[missing, "NUTS_NAME"] = nearest["NUTS_NAME"].values

    gdf_gem["NUTS_ID"]   = joined["NUTS_ID"].values
    gdf_gem["NUTS_NAME"] = joined["NUTS_NAME"].values

    assigned = gdf_gem["NUTS_ID"].notna().sum()
    print(f"  Assigned {assigned}/{len(gdf_gem)} gemeenten to NUTS-3")

    # Save updated GeoJSON with NUTS_ID
    gdf_gem_export = gdf_gem.drop(columns=["centroid"])
    gdf_gem_export.to_file(out_geojson, driver="GeoJSON")
    print(f"  Updated GeoJSON with NUTS_ID -> {out_geojson}")

    nuts_map = gdf_gem[["statcode","NUTS_ID","NUTS_NAME"]].copy()
    nuts_map.columns = ["GM_CODE","NUTS_ID","NUTS_NAME"]

except Exception as e:
    print(f"  Spatial join failed: {e}")
    nuts_map = pd.DataFrame(columns=["GM_CODE","NUTS_ID","NUTS_NAME"])


# ── 6. Load NUTS-3 pollution time series ──────────────────────────────────────
print("\nLoading NUTS-3 pollution base data...")
base = pd.read_csv(PROCESSED / "final_extended.csv")
base_cols = ["NUTS_ID","year","month","season",
             "NO2","SO2","CO","O3","HCHO","PM25",
             "NO2_quality","SO2_quality","CO_quality","O3_quality","HCHO_quality","PM25_quality",
             "PM25_weighted_quality","NO2_weighted_quality","O3_weighted_quality",
             "SO2_weighted_quality","CO_weighted_quality","HCHO_weighted_quality",
             "Index","GDP_per_capita","GDP_Normalized","Air_Inequity_Index"]
base = base[[c for c in base_cols if c in base.columns]]
print(f"  {len(base)} NUTS-3 rows, {base['NUTS_ID'].nunique()} regions, {base['year'].nunique()} years")


# ── 7. Merge everything at gemeente level ──────────────────────────────────────
print("\nBuilding gemeente dataset...")

# Start with gemeente code + NUTS-3 parent
gm = nuts_map.copy() if not nuts_map.empty else pd.DataFrame({"GM_CODE": gm_df["GM_CODE"], "NUTS_ID": None})

# Merge CBS data
if not socio_df.empty:
    gm = gm.merge(socio_df, on="GM_CODE", how="left")
if not luse_df.empty:
    gm = gm.merge(luse_df, on="GM_CODE", how="left")

# Merge GM_NAME
gm = gm.merge(gm_df, on="GM_CODE", how="left")

print(f"  {len(gm)} gemeente rows before time expansion")

# Cross-join with time: each gemeente x each (year, month) in base
time_grid = base[["NUTS_ID","year","month","season"]].drop_duplicates()
gm_time = gm.merge(time_grid, on="NUTS_ID", how="inner")
print(f"  After time expansion: {len(gm_time)} rows")

# Merge pollution from NUTS-3 base
poll_cols = [c for c in base.columns if c not in ["NUTS_ID","year","month","season"]]
gm_time = gm_time.merge(
    base[["NUTS_ID","year","month"] + poll_cols],
    on=["NUTS_ID","year","month"], how="left"
)


# ── 8. Compute gemeente-level GDP proxy from income ───────────────────────────
# CBS avg_income is in thousands of EUR; convert to annual
if "avg_income" in gm_time.columns:
    gm_time["income_eur"] = pd.to_numeric(gm_time["avg_income"], errors="coerce") * 1000
    # If income missing, fall back to NUTS-3 GDP_per_capita
    gm_time["income_eur"] = gm_time["income_eur"].fillna(gm_time.get("GDP_per_capita", np.nan))

    # Compute income_normalized per year (0=richest, 1=poorest)
    for yr in gm_time["year"].unique():
        mask = gm_time["year"] == yr
        inc = gm_time.loc[mask, "income_eur"]
        mn, mx = inc.min(), inc.max()
        if mx > mn:
            gm_time.loc[mask, "income_normalized"] = (inc - mn) / (mx - mn)
        else:
            gm_time.loc[mask, "income_normalized"] = 0.5
else:
    gm_time["income_normalized"] = gm_time.get("GDP_Normalized", 0.5)

# ── 9. Recompute Air Inequity Index at gemeente level ─────────────────────────
gm_time["GM_AII"] = (gm_time["Index"] * gm_time["income_normalized"]).round(4)

# Green Space Deficit
if "green_pct" in gm_time.columns:
    gmin = gm_time["green_pct"].min()
    gmax = gm_time["green_pct"].max()
    gm_time["GSD"] = (1 - (gm_time["green_pct"] - gmin) / (gmax - gmin + 1e-9)).round(4)

# COVID signal (2020 spring vs 2018-19)
spring = gm_time["month"].isin([3,4,5])
baseline = (
    gm_time[spring & gm_time["year"].isin([2018,2019])]
    .groupby("GM_CODE")["Index"].mean().rename("covid_baseline")
)
covid20 = (
    gm_time[spring & (gm_time["year"]==2020)]
    .groupby("GM_CODE")["Index"].mean().rename("covid_2020")
)
covid_sig = ((covid20 - baseline) / baseline.replace(0, np.nan)).rename("covid_signal").reset_index()
gm_time = gm_time.merge(covid_sig, on="GM_CODE", how="left")

# AII rank per year
gm_annual = (
    gm_time.groupby(["GM_CODE","year"])["GM_AII"].mean()
    .reset_index()
)
gm_annual["aii_rank"] = gm_annual.groupby("year")["GM_AII"].rank(method="min", ascending=False).astype(int)
gm_time = gm_time.merge(gm_annual[["GM_CODE","year","aii_rank"]], on=["GM_CODE","year"], how="left")


# ── 10. Save ───────────────────────────────────────────────────────────────────
out_csv = PROCESSED / "gemeente_extended.csv"
gm_time.to_csv(out_csv, index=False)
print(f"\nSaved {len(gm_time)} rows, {gm_time.shape[1]} cols -> {out_csv}")
print(f"Gemeenten: {gm_time['GM_CODE'].nunique()}  |  Years: {gm_time['year'].nunique()}")
print("\nSample:")
show_cols = [c for c in ["GM_CODE","GM_NAME","NUTS_ID","year","Index","income_eur","income_normalized","GM_AII","green_pct"] if c in gm_time.columns]
print(gm_time[show_cols].head(8).to_string())
print("\nDone: 11_fetch_gemeente")
