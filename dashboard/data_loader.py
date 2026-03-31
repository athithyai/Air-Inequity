"""Load and pre-aggregate all data once at startup."""

import json
from pathlib import Path

import pandas as pd

_BASE = Path(__file__).parent.parent / "data" / "processed"


def _load():
    df = pd.read_csv(_BASE / "final.csv")
    df["year"]  = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df["date"]  = pd.to_datetime(df[["year", "month"]].assign(day=1))

    with open(_BASE / "nl_nuts3.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    # Build NUTS_ID → human-readable name lookup from GeoJSON
    name_map = {
        feat["properties"]["NUTS_ID"]: feat["properties"].get("NUTS_NAME", feat["properties"]["NUTS_ID"])
        for feat in geojson["features"]
    }
    df["region_name"] = df["NUTS_ID"].map(name_map)

    # Annual mean per region — used by the choropleth
    annual = (
        df.groupby(["NUTS_ID", "year"])
        .agg(
            region_name=("region_name", "first"),
            GDP_per_capita=("GDP_per_capita", "mean"),
            Index=("Index", "mean"),
            Air_Inequity_Index=("Air_Inequity_Index", "mean"),
        )
        .reset_index()
    )

    return df, geojson, annual, name_map


DF, GEOJSON, ANNUAL, NAME_MAP = _load()

NUTS_IDS   = sorted(DF["NUTS_ID"].unique())
YEARS      = sorted(DF["year"].unique())
POLLUTANTS = ["PM25", "NO2", "O3", "SO2", "CO", "HCHO"]
