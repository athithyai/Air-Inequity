"""
10_compute_extended_index.py
----------------------------
Extends final.csv with new composite metrics:

  Green Space Deficit (GSD)
    = 1 - min-max(green_pct)   [high = little green space = bad]

  Health Burden Index (HBI)
    = 0.4 * PM25_quality_norm + 0.3 * NO2_quality_norm
      + 0.15 * O3_quality_norm + 0.15 * SO2_quality_norm
    (normalized quality scores, so 0=clean → 1=worst)

  Environmental Justice Score (EJS)
    = 0.5 * HBI + 0.3 * GDP_Normalized + 0.2 * GSD
    (higher = more environmental injustice)

  Seasonal Risk Flag
    = "High" if Index > regional_90th_percentile in that season, else "Normal"

  COVID Lockdown Signal (2020 anomaly)
    = (Index_2020_spring - Index_baseline_spring) / Index_baseline_spring
    where baseline = mean of 2018 & 2019 spring

Output: data/processed/final_extended.csv
        (all columns of final.csv + new columns)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PROCESSED, DATA_RAW

# ── Load base data ─────────────────────────────────────────────────────────────
print("Loading final.csv…")
df = pd.read_csv(DATA_PROCESSED / "final.csv")
print(f"  {len(df)} rows, {df.shape[1]} columns")

# ── Load CBS land use data ─────────────────────────────────────────────────────
cbs_path = DATA_RAW / "cbs_stats.csv"
if cbs_path.exists():
    cbs = pd.read_csv(cbs_path)
    print(f"  Loaded CBS land use: {len(cbs)} regions")
    df = df.merge(cbs, on="NUTS_ID", how="left")
    print(f"  After CBS merge: {df.shape[1]} columns")
else:
    print("  WARNING: cbs_stats.csv not found — GSD will be zero")
    df["green_pct"] = 0.0
    df["forest_pct"] = 0.0
    df["industrial_pct"] = 0.0

# ── Load Luchtmeetnet ground truth (optional) ──────────────────────────────────
lm_path = DATA_RAW / "luchtmeetnet_annual.csv"
if lm_path.exists():
    lm = pd.read_csv(lm_path)
    if not lm.empty and "NUTS_ID" in lm.columns:
        df = df.merge(lm, on=["NUTS_ID", "year"], how="left")
        print(f"  Loaded Luchtmeetnet: {lm['NUTS_ID'].nunique()} regions")
    else:
        print("  Luchtmeetnet file empty — skipping merge")
else:
    print("  luchtmeetnet_annual.csv not found — skipping")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Green Space Deficit (GSD)
# ══════════════════════════════════════════════════════════════════════════════
# CBS land use is static (one value per region); replicate across time
if "green_pct" in df.columns and df["green_pct"].notna().any():
    gmin = df["green_pct"].min()
    gmax = df["green_pct"].max()
    df["GSD"] = (1 - (df["green_pct"] - gmin) / (gmax - gmin)).round(4)
else:
    df["GSD"] = 0.5

print(f"GSD: min={df['GSD'].min():.3f}  max={df['GSD'].max():.3f}  mean={df['GSD'].mean():.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Health Burden Index (HBI)
# ══════════════════════════════════════════════════════════════════════════════
# Normalize quality scores (1–6) → (0–1) then weight
pollutant_weights = {
    "PM25": 0.40,
    "NO2":  0.30,
    "O3":   0.15,
    "SO2":  0.15,
}

hbi = pd.Series(0.0, index=df.index)
for poll, weight in pollutant_weights.items():
    col = f"{poll}_quality"
    if col in df.columns:
        norm = (df[col] - 1) / 5.0   # 1→0, 6→1
        hbi += weight * norm

df["HBI"] = hbi.round(4)
print(f"HBI: min={df['HBI'].min():.3f}  max={df['HBI'].max():.3f}  mean={df['HBI'].mean():.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Environmental Justice Score (EJS)
# ══════════════════════════════════════════════════════════════════════════════
# GDP_Normalized is already in [0,1] where 1 = poorest region
df["EJS"] = (
    0.5  * df["HBI"]
    + 0.3 * df["GDP_Normalized"]
    + 0.2 * df["GSD"]
).round(4)

print(f"EJS: min={df['EJS'].min():.3f}  max={df['EJS'].max():.3f}  mean={df['EJS'].mean():.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Seasonal Risk Flag
# ══════════════════════════════════════════════════════════════════════════════
# Per region, per season: flag months above regional 90th percentile
p90 = df.groupby(["NUTS_ID", "season"])["Index"].transform(lambda x: x.quantile(0.90))
df["risk_flag"] = (df["Index"] > p90).map({True: "High", False: "Normal"})

high_pct = (df["risk_flag"] == "High").mean() * 100
print(f"Risk flags: {high_pct:.1f}% of rows flagged as High")


# ══════════════════════════════════════════════════════════════════════════════
# 5. COVID Lockdown Signal (2020 spring anomaly)
# ══════════════════════════════════════════════════════════════════════════════
# Spring = months 3,4,5
spring_mask = df["month"].isin([3, 4, 5])

# Baseline: mean of 2018 & 2019 spring Index per region
baseline = (
    df[spring_mask & df["year"].isin([2018, 2019])]
    .groupby("NUTS_ID")["Index"]
    .mean()
    .rename("covid_baseline_index")
)

# 2020 spring Index per region
covid_2020 = (
    df[spring_mask & (df["year"] == 2020)]
    .groupby("NUTS_ID")["Index"]
    .mean()
    .rename("covid_2020_index")
)

covid_signal = ((covid_2020 - baseline) / baseline.replace(0, np.nan)).rename("covid_signal")
covid_df = covid_signal.reset_index()

# Merge back — covid_signal is region-level, broadcast to all rows
df = df.merge(covid_df, on="NUTS_ID", how="left")
print(f"COVID signal: {df['covid_signal'].describe().to_dict()}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Industrial Exposure Index
# ══════════════════════════════════════════════════════════════════════════════
if "industrial_pct" in df.columns and df["industrial_pct"].notna().any():
    imin = df["industrial_pct"].min()
    imax = df["industrial_pct"].max()
    df["industrial_exposure"] = ((df["industrial_pct"] - imin) / (imax - imin)).round(4)
else:
    df["industrial_exposure"] = 0.5

print(f"Industrial exposure: min={df['industrial_exposure'].min():.3f}  max={df['industrial_exposure'].max():.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Rank by Air Inequity Index (per year)
# ══════════════════════════════════════════════════════════════════════════════
df["aii_rank"] = (
    df.groupby("year")["Air_Inequity_Index"]
    .rank(method="min", ascending=False)
    .astype(int)
)


# ── Save ───────────────────────────────────────────────────────────────────────
out = DATA_PROCESSED / "final_extended.csv"
df.to_csv(out, index=False)
print(f"\n✓ Saved {len(df)} rows, {df.shape[1]} columns → {out}")

# Summary of new columns
new_cols = ["GSD", "HBI", "EJS", "risk_flag", "covid_signal", "industrial_exposure",
            "green_pct", "forest_pct", "industrial_pct", "aii_rank"]
available = [c for c in new_cols if c in df.columns]
print("\nNew columns added:")
print(df[["NUTS_ID", "year", "month"] + available].head(12).to_string())
print("\n✓ 10_compute_extended_index done")
