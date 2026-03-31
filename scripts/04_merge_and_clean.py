"""
04_merge_and_clean.py
---------------------
Joins all raw pollutant CSVs with GDP/population, builds a complete
region-year-month grid, fills missing values, and adds season/country columns.

Output: data/interim/combined_with_gdp.csv

Usage:
    python scripts/04_merge_and_clean.py
"""

import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_INTERIM, DATA_PM25, DATA_PROCESSED, DATA_RAW, DATA_SENTINEL, MONTHS, YEARS

import geopandas as gpd
import pandas as pd

KEYS       = ["NUTS_ID", "year", "month"]
POLLUTANTS = ["NO2", "SO2", "CO", "O3", "HCHO", "PM25"]
SEASON_MAP = {
    12: "Winter", 1: "Winter", 2: "Winter",
     3: "Spring", 4: "Spring", 5: "Spring",
     6: "Summer", 7: "Summer", 8: "Summer",
     9: "Autumn",10: "Autumn",11: "Autumn",
}
# Molar masses for µg/m² conversion (NO2, SO2, HCHO from mol/m²)
MOLAR_MASS = {"NO2": 46.005, "SO2": 64.06, "HCHO": 30.03}


# ── 1. Load and outer-merge all pollutants ────────────────────────────────────
print("Loading pollutant CSVs…")
frames = {}
for p in ["NO2", "SO2", "CO", "O3", "HCHO"]:
    path = DATA_SENTINEL / f"{p.lower()}_raw.csv"
    if not path.exists():
        sys.exit(f"Missing: {path}  — run 01_fetch_sentinel.py first")
    frames[p] = pd.read_csv(path)

pm25_path = DATA_PM25 / "pm25_combined.csv"
if not pm25_path.exists():
    sys.exit(f"Missing: {pm25_path}  — run 02_fetch_pm25_cds.py first")
frames["PM25"] = pd.read_csv(pm25_path)

df = frames["NO2"]
for p in ["SO2", "CO", "O3", "HCHO", "PM25"]:
    df = df.merge(frames[p], on=KEYS, how="outer")
print(f"  After merge: {len(df)} rows")


# ── 2. Complete region × year × month grid ────────────────────────────────────
nuts_ids = gpd.read_file(DATA_PROCESSED / "nl_nuts3.geojson")["NUTS_ID"].tolist()
grid = pd.DataFrame(list(product(nuts_ids, YEARS, MONTHS)), columns=KEYS)
df   = grid.merge(df, on=KEYS, how="left")
print(f"  After grid: {len(df)} rows  (expected {len(nuts_ids) * len(YEARS) * len(MONTHS)})")


# ── 3. Unit conversions ────────────────────────────────────────────────────────
# Sentinel-5P delivers mol/m². Convert NO2, SO2, HCHO → µg/m².
# CO and O3 stay in mol/m² (thresholds in notebook 05 use that unit).
for col, mass in MOLAR_MASS.items():
    df[col] = df[col].abs() * mass * 1e6
for col in POLLUTANTS:
    df[col] = df[col].round(6)


# ── 4. Fill missing values ─────────────────────────────────────────────────────
print("Imputing missing values…")
print("  Before:", df[POLLUTANTS].isnull().sum().to_dict())

def fill_missing(df: pd.DataFrame, col: str) -> pd.DataFrame:
    # Pass 1: same region + same calendar month, cross-year mean
    climatology = df.groupby(["NUTS_ID", "month"])[col].transform("mean")
    df[col] = df[col].fillna(climatology)
    # Pass 2: polynomial interpolation along time axis per region
    df[col] = (
        df.sort_values(KEYS)
          .groupby("NUTS_ID")[col]
          .transform(lambda s: s.interpolate(method="polynomial", order=2).bfill().ffill())
    )
    return df

for col in POLLUTANTS:
    df = fill_missing(df, col)

print("  After: ", df[POLLUTANTS].isnull().sum().to_dict())


# ── 5. Merge GDP and population ────────────────────────────────────────────────
gdp_path = DATA_RAW / "gdp_raw.csv"
pop_path = DATA_RAW / "population_raw.csv"
if not gdp_path.exists() or not pop_path.exists():
    sys.exit("Missing GDP/population files — run 03_fetch_eurostat.py first")

gdp = pd.read_csv(gdp_path)
pop = pd.read_csv(pop_path)
gdp_pop = gdp.merge(pop, on=["NUTS_ID", "year"], how="outer")
gdp_pop["GDP_per_capita"] = gdp_pop["GDP"] / gdp_pop["population"]

df = df.merge(gdp_pop, on=["NUTS_ID", "year"], how="left")

# Some NUTS-3 regions lack Eurostat GDP data (structural gaps or recent revisions).
# Fix: forward-fill then backward-fill within each region across years, then
# fall back to the NL annual mean for any still-missing values.
for col in ["GDP", "population", "GDP_per_capita"]:
    df[col] = (df.sort_values(["NUTS_ID", "year"])
                 .groupby("NUTS_ID")[col]
                 .transform(lambda s: s.ffill().bfill()))
    nl_annual_mean = df.groupby("year")[col].transform("mean")
    df[col] = df[col].fillna(nl_annual_mean)


# ── 6. Add season and country ─────────────────────────────────────────────────
df["season"]  = df["month"].map(SEASON_MAP)
df["Country"] = df["NUTS_ID"].str[:2]  # always 'NL'
df = df.sort_values(KEYS).reset_index(drop=True)


# ── 7. Save ───────────────────────────────────────────────────────────────────
out = DATA_INTERIM / "combined_with_gdp.csv"
df.to_csv(out, index=False)
print(f"\n✓ Saved {len(df)} rows → {out}")
print("\n✓ 04_merge_and_clean done")
