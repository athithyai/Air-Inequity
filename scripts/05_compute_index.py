"""
05_compute_index.py
-------------------
Applies quality scoring, seasonal weighting, AQI computation,
GDP normalisation, and produces the final Air Inequity Index.

Output: data/processed/final.csv  (30-column schema)

Usage:
    python scripts/05_compute_index.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_INTERIM, DATA_PROCESSED

import pandas as pd


# ── Load ──────────────────────────────────────────────────────────────────────
src = DATA_INTERIM / "combined_with_gdp.csv"
if not src.exists():
    sys.exit(f"Missing: {src}  — run 04_merge_and_clean.py first")

df = pd.read_csv(src)
print(f"Loaded {len(df)} rows")


# ── 1. Quality scores (1–6) ───────────────────────────────────────────────────
# Thresholds from WHO guidelines and EPA NAAQS (as per original NSI_NL methodology).
# Score 1 = cleanest / safest, 6 = most polluted.
#
# Units after notebook 04:
#   NO2, SO2, HCHO  → µg/m²   (converted from mol/m² using molar mass)
#   CO, O3          → mol/m²  (kept in original Sentinel-5P units)
#   PM25            → µg/m³   (from CDS EAC4)

THRESHOLDS = {
    "NO2":  [50,   100,  200,  500,  1000],
    "SO2":  [50,   100,  150,  200,   300],
    "CO":   [0.01, 0.02, 0.03, 0.05,  0.10],
    "O3":   [0.05, 0.10, 0.15, 0.20,  0.30],
    "PM25": [10,   15,   20,   30,    50  ],
    "HCHO": [5,    10,   15,   20,    30  ],
}

def quality_score(value: float, thresholds: list) -> int:
    for i, t in enumerate(thresholds, start=1):
        if value <= t:
            return i
    return 6

for pollutant, thresholds in THRESHOLDS.items():
    df[f"{pollutant}_quality"] = df[pollutant].apply(quality_score, thresholds=thresholds)

print("Quality score ranges:")
for p in THRESHOLDS:
    col = f"{p}_quality"
    print(f"  {p}: {df[col].min()}–{df[col].max()}")


# ── 2. Seasonal weights ───────────────────────────────────────────────────────
# Weights reflect each pollutant's relative health impact per season.
# They are fixed constants derived from the original project methodology;
# they do NOT depend on GDP or economic data — they are health/epidemiological
# weights only. GDP is used separately in step 4 to normalise economic vulnerability.
#
# Design rationale:
#   - PM2.5 has highest weight (combustion heating peaks in winter)
#   - O3 weight rises in summer (photochemical smog peak)
#   - All weights per season must sum to exactly 1.0

SEASONAL_WEIGHTS = {
    "Winter": {"PM25": 0.40, "NO2": 0.25, "O3": 0.10, "SO2": 0.12, "CO": 0.06, "HCHO": 0.07},
    "Spring": {"PM25": 0.36, "NO2": 0.22, "O3": 0.15, "SO2": 0.12, "CO": 0.07, "HCHO": 0.08},
    "Summer": {"PM25": 0.25, "NO2": 0.15, "O3": 0.30, "SO2": 0.05, "CO": 0.10, "HCHO": 0.15},
    "Autumn": {"PM25": 0.35, "NO2": 0.23, "O3": 0.15, "SO2": 0.12, "CO": 0.07, "HCHO": 0.08},
}

for season, w in SEASONAL_WEIGHTS.items():
    total = sum(w.values())
    assert abs(total - 1.0) < 1e-9, f"{season} weights sum to {total}"
print("Seasonal weights validated ✓")

for pollutant in THRESHOLDS:
    df[f"{pollutant}_weighted_quality"] = df.apply(
        lambda row, p=pollutant: row[f"{p}_quality"] * SEASONAL_WEIGHTS[row["season"]][p],
        axis=1,
    )


# ── 3. Composite Pollution Index ──────────────────────────────────────────────
weighted_cols = [f"{p}_weighted_quality" for p in THRESHOLDS]
df["Index"] = df[weighted_cols].sum(axis=1)
print(f"Pollution Index range: [{df['Index'].min():.4f}, {df['Index'].max():.4f}]")


# ── 4. GDP normalisation (inverted within country-year) ────────────────────────
# GDP per capita is normalised to [0,1] within each country-year group,
# then INVERTED so that lower income → higher vulnerability score.
# This makes the AII sensitive to economic disadvantage, not just pollution.

g = df.groupby(["Country", "year"])["GDP_per_capita"]
mn = g.transform("min")
mx = g.transform("max")
denom = mx - mn
df["GDP_Normalized"]     = (1 - (df["GDP_per_capita"] - mn) / denom).where(denom > 0, 0.5)
df["GDP_per_capita_min"] = mn
df["GDP_per_capita_max"] = mx
print(f"GDP_Normalized range: [{df['GDP_Normalized'].min():.4f}, {df['GDP_Normalized'].max():.4f}]")


# ── 5. Air Inequity Index ─────────────────────────────────────────────────────
df["Air_Inequity_Index"] = df["Index"] * df["GDP_Normalized"]
print(f"AII range: [{df['Air_Inequity_Index'].min():.4f}, {df['Air_Inequity_Index'].max():.4f}]")


# ── 6. Save ───────────────────────────────────────────────────────────────────
COLUMNS = [
    "NUTS_ID", "Country", "year", "month", "season",
    "NO2", "SO2", "CO", "O3", "HCHO", "PM25",
    "GDP", "population", "GDP_per_capita",
    "O3_quality",  "CO_quality",  "NO2_quality",  "SO2_quality",  "PM25_quality",  "HCHO_quality",
    "PM25_weighted_quality", "NO2_weighted_quality", "O3_weighted_quality",
    "SO2_weighted_quality",  "CO_weighted_quality",  "HCHO_weighted_quality",
    "Index", "GDP_Normalized", "Air_Inequity_Index",
    "GDP_per_capita_min", "GDP_per_capita_max",
]

out = df[COLUMNS].sort_values(["NUTS_ID", "year", "month"]).reset_index(drop=True)
out.to_csv(DATA_PROCESSED / "final.csv", index=False)
print(f"\n✓ Saved {len(out)} rows × {len(out.columns)} cols → {DATA_PROCESSED / 'final.csv'}")
print("\n✓ 05_compute_index done")
