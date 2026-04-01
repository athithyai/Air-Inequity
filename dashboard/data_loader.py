"""Load and pre-aggregate all data once at startup."""

import json
from pathlib import Path

import pandas as pd

_BASE = Path(__file__).parent.parent / "data" / "processed"


def _load():
    # Prefer extended dataset; fall back to final.csv
    csv_path = _BASE / "final_extended.csv"
    if not csv_path.exists():
        csv_path = _BASE / "final.csv"

    df = pd.read_csv(csv_path)
    df["year"]  = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df["date"]  = pd.to_datetime(df[["year", "month"]].assign(day=1))

    with open(_BASE / "nl_nuts3.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    # NUTS_ID -> human-readable name
    name_map = {
        feat["properties"]["NUTS_ID"]: feat["properties"].get("NUTS_NAME", feat["properties"]["NUTS_ID"])
        for feat in geojson["features"]
    }
    df["region_name"] = df["NUTS_ID"].map(name_map)

    # Annual mean per region (choropleth)
    agg_cols = {
        "region_name":       ("region_name",       "first"),
        "GDP_per_capita":    ("GDP_per_capita",     "mean"),
        "Index":             ("Index",              "mean"),
        "Air_Inequity_Index":("Air_Inequity_Index", "mean"),
    }
    for col in ["HBI", "EJS", "GSD", "green_pct", "industrial_pct", "industrial_exposure"]:
        if col in df.columns:
            agg_cols[col] = (col, "mean")

    annual = (
        df.groupby(["NUTS_ID", "year"])
        .agg(**agg_cols)
        .reset_index()
    )

    # Region-level static data (for scatter / ranking — use last year)
    last_year = df["year"].max()
    region_static = (
        df[df["year"] == last_year]
        .groupby("NUTS_ID")
        .agg(
            region_name     =("region_name",       "first"),
            GDP_per_capita  =("GDP_per_capita",     "mean"),
            Air_Inequity_Index=("Air_Inequity_Index","mean"),
            Index           =("Index",              "mean"),
        )
    )
    for col in ["green_pct", "forest_pct", "industrial_pct", "GSD", "HBI", "EJS",
                "covid_signal", "industrial_exposure"]:
        if col in df.columns:
            region_static[col] = (
                df[df["year"] == last_year]
                .groupby("NUTS_ID")[col]
                .mean()
            )
    region_static = region_static.reset_index()

    return df, geojson, annual, name_map, region_static


DF, GEOJSON, ANNUAL, NAME_MAP, REGION_STATIC = _load()

NUTS_IDS   = sorted(DF["NUTS_ID"].unique())
YEARS      = sorted(DF["year"].unique())
POLLUTANTS = ["PM25", "NO2", "O3", "SO2", "CO", "HCHO"]
HAS_EXTENDED = "HBI" in DF.columns
