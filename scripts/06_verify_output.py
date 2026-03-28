"""
06_verify_output.py
-------------------
Sanity checks on data/processed/final.csv before running the dashboard.

Usage:
    python scripts/06_verify_output.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PROCESSED

import pandas as pd

path = DATA_PROCESSED / "final.csv"
if not path.exists():
    sys.exit(f"Missing: {path}  — run 05_compute_index.py first")

df = pd.read_csv(path)
errors = []

print(f"Shape: {df.shape}")
print(f"Years: {sorted(df['year'].unique())}")
print(f"Regions ({df['NUTS_ID'].nunique()}): {sorted(df['NUTS_ID'].unique())}")


# ── Row count ─────────────────────────────────────────────────────────────────
expected = df["NUTS_ID"].nunique() * df["year"].nunique() * df["month"].nunique()
if len(df) != expected:
    errors.append(f"Row count {len(df)} ≠ expected {expected}")
else:
    print(f"✓ Row count: {len(df)}")


# ── No nulls in critical columns ──────────────────────────────────────────────
critical = ["Air_Inequity_Index", "Index", "GDP_Normalized"]
nulls    = df[critical].isnull().sum()
if nulls.sum() > 0:
    errors.append(f"Nulls in critical columns:\n{nulls[nulls > 0]}")
else:
    print("✓ No nulls in critical columns")


# ── Quality scores in [1, 6] ──────────────────────────────────────────────────
quality_cols = [c for c in df.columns if c.endswith("_quality") and "weighted" not in c]
for col in quality_cols:
    if not df[col].between(1, 6).all():
        errors.append(f"{col} has values outside [1, 6]")
if not errors:
    print("✓ All quality scores in [1, 6]")


# ── GDP_Normalized in [0, 1] ──────────────────────────────────────────────────
if not df["GDP_Normalized"].between(0, 1).all():
    errors.append("GDP_Normalized has values outside [0, 1]")
else:
    print("✓ GDP_Normalized in [0, 1]")


# ── Index reconstruction ──────────────────────────────────────────────────────
weighted_cols = [c for c in df.columns if c.endswith("_weighted_quality")]
reconstructed = df[weighted_cols].sum(axis=1)
max_err = (df["Index"] - reconstructed).abs().max()
if max_err > 1e-6:
    errors.append(f"Index reconstruction error: {max_err:.2e}")
else:
    print(f"✓ Index = Σ weighted_quality (max error: {max_err:.2e})")


# ── AII = Index × GDP_Normalized ─────────────────────────────────────────────
aii_err = (df["Air_Inequity_Index"] - df["Index"] * df["GDP_Normalized"]).abs().max()
if aii_err > 1e-6:
    errors.append(f"AII ≠ Index × GDP_Normalized (max error: {aii_err:.2e})")
else:
    print(f"✓ AII = Index × GDP_Normalized (max error: {aii_err:.2e})")


# ── Summary stats ─────────────────────────────────────────────────────────────
print("\nSummary statistics:")
print(df[["Air_Inequity_Index", "Index", "GDP_per_capita"]].describe().round(3).to_string())


# ── Exit ──────────────────────────────────────────────────────────────────────
if errors:
    print("\n✗ FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\n✓ All checks passed — final.csv is ready for the dashboard")
