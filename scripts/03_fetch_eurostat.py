"""
03_fetch_eurostat.py
--------------------
Downloads:
  - NL NUTS-3 boundary GeoJSON  → data/processed/nl_nuts3.geojson
  - GDP per NUTS-3 region       → data/raw/gdp_raw.csv
  - Population per NUTS-3 region→ data/raw/population_raw.csv

No API key required. Run this script FIRST — the GeoJSON is needed by the
Sentinel Hub and CDS scripts.

Usage:
    python scripts/03_fetch_eurostat.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PROCESSED, DATA_RAW, YEARS

import eurostat
import geopandas as gpd
import pandas as pd


# ── 1. NUTS-3 GeoJSON ─────────────────────────────────────────────────────────
GEOJSON_PATH = DATA_PROCESSED / "nl_nuts3.geojson"

if GEOJSON_PATH.exists():
    print(f"GeoJSON already exists: {GEOJSON_PATH}")
else:
    url = (
        "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
        "NUTS_RG_01M_2024_4326_LEVL_3.geojson"
    )
    print("Downloading NUTS-3 GeoJSON from Eurostat GISCO…")
    all_nuts = gpd.read_file(url)
    nl_nuts  = all_nuts[all_nuts["CNTR_CODE"] == "NL"].copy()
    nl_nuts.to_file(GEOJSON_PATH, driver="GeoJSON")
    print(f"  Saved {len(nl_nuts)} NL NUTS-3 regions → {GEOJSON_PATH}")

nuts    = gpd.read_file(GEOJSON_PATH)
nl_codes = nuts["NUTS_ID"].tolist()
print(f"  {len(nl_codes)} regions: {nl_codes[:5]} …")


# ── helper: fetch + melt a Eurostat dataset ────────────────────────────────────
def fetch_eurostat(dataset: str, filter_pars: dict, value_col: str) -> pd.DataFrame:
    raw = eurostat.get_data_df(dataset, flags=False, filter_pars=filter_pars)
    raw.columns = raw.columns.str.replace(r"\\TIME_PERIOD", "", regex=True)
    raw = raw.rename(columns={"geo": "NUTS_ID"})
    raw = raw[raw["NUTS_ID"].isin(nl_codes)]
    year_cols = [c for c in raw.columns if str(c).isdigit()]
    long = raw.melt(id_vars=["NUTS_ID"], value_vars=year_cols,
                    var_name="year", value_name=value_col)
    long["year"] = long["year"].astype(int)
    long[value_col] = pd.to_numeric(long[value_col], errors="coerce")
    return long.sort_values(["NUTS_ID", "year"]).reset_index(drop=True)


# ── 2. GDP ────────────────────────────────────────────────────────────────────
print("\nFetching GDP (nama_10r_3gdp)…")
gdp = fetch_eurostat("nama_10r_3gdp", {"unit": ["MIO_EUR"]}, "GDP")
gdp["GDP"] *= 1_000_000  # MIO_EUR → EUR

# Forward-fill 2023 from 2022 if not yet published (typical 2-year lag)
if gdp[gdp["year"] == 2023]["GDP"].isnull().all():
    print("  2023 GDP not available — forward-filling from 2022")
    ref = gdp[gdp["year"] == 2022].copy()
    ref["year"] = 2023
    gdp = pd.concat([gdp[gdp["year"] != 2023], ref], ignore_index=True)

gdp_path = DATA_RAW / "gdp_raw.csv"
gdp.to_csv(gdp_path, index=False)
print(f"  Saved {len(gdp)} rows → {gdp_path}")


# ── 3. Population ─────────────────────────────────────────────────────────────
print("\nFetching population (demo_r_pjangrp3)…")
pop = fetch_eurostat("demo_r_pjangrp3", {"sex": ["T"], "age": ["TOTAL"]}, "population")

if pop[pop["year"] == 2023]["population"].isnull().all():
    print("  2023 population not available — forward-filling from 2022")
    ref = pop[pop["year"] == 2022].copy()
    ref["year"] = 2023
    pop = pd.concat([pop[pop["year"] != 2023], ref], ignore_index=True)

pop_path = DATA_RAW / "population_raw.csv"
pop.to_csv(pop_path, index=False)
print(f"  Saved {len(pop)} rows → {pop_path}")


# ── 4. Quick check ────────────────────────────────────────────────────────────
merged = gdp.merge(pop, on=["NUTS_ID", "year"])
merged["GDP_per_capita"] = merged["GDP"] / merged["population"]
sample = (merged[merged["year"] == merged["year"].max()]
          [["NUTS_ID", "GDP_per_capita"]]
          .sort_values("GDP_per_capita", ascending=False))
print(f"\nGDP per capita ({merged['year'].max()}):")
print(sample.to_string(index=False))
print("\n✓ 03_fetch_eurostat done")
