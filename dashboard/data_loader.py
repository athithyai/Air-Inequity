"""Load and pre-aggregate all data once at startup."""

import json
from pathlib import Path

import pandas as pd

_BASE = Path(__file__).parent.parent / "data" / "processed"


def _load() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    df = pd.read_csv(_BASE / "final.csv")
    df["year"]  = df["year"].astype(int)
    df["month"] = df["month"].astype(int)

    # Synthetic date column (first of each month) for time-series axes
    df["date"] = pd.to_datetime(
        df[["year", "month"]].assign(day=1)
    )

    with open(_BASE / "nl_nuts3.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    # Annual mean per region (for the choropleth default view)
    annual = (
        df.groupby(["NUTS_ID", "year"])
        .agg(
            GDP_per_capita=("GDP_per_capita", "mean"),
            Index=("Index", "mean"),
            Air_Inequity_Index=("Air_Inequity_Index", "mean"),
        )
        .reset_index()
    )

    return df, geojson, annual


DF, GEOJSON, ANNUAL = _load()

NUTS_IDS = sorted(DF["NUTS_ID"].unique())
YEARS    = sorted(DF["year"].unique())

POLLUTANTS = ["PM25", "NO2", "O3", "SO2", "CO", "HCHO"]
QUALITY_COLS  = [f"{p}_quality" for p in POLLUTANTS]
WEIGHTED_COLS = [f"{p}_weighted_quality" for p in POLLUTANTS]
