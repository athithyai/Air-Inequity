"""Load and pre-aggregate all data once at startup."""

import json
from pathlib import Path

import pandas as pd

_BASE = Path(__file__).parent.parent / "data" / "processed"


def _load():
    # ── NUTS-3 base ────────────────────────────────────────────────────────────
    csv_path = _BASE / "final_extended.csv"
    if not csv_path.exists():
        csv_path = _BASE / "final.csv"

    df = pd.read_csv(csv_path)
    df["year"]  = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df["date"]  = pd.to_datetime(df[["year", "month"]].assign(day=1))

    with open(_BASE / "nl_nuts3.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    name_map = {
        feat["properties"]["NUTS_ID"]: feat["properties"].get("NUTS_NAME", feat["properties"]["NUTS_ID"])
        for feat in geojson["features"]
    }
    df["region_name"] = df["NUTS_ID"].map(name_map)

    # Annual mean per NUTS-3 region
    agg_cols = {
        "region_name":        ("region_name",        "first"),
        "GDP_per_capita":     ("GDP_per_capita",      "mean"),
        "Index":              ("Index",               "mean"),
        "Air_Inequity_Index": ("Air_Inequity_Index",  "mean"),
    }
    for col in ["HBI", "EJS", "GSD", "green_pct", "industrial_pct", "industrial_exposure"]:
        if col in df.columns:
            agg_cols[col] = (col, "mean")

    annual = (
        df.groupby(["NUTS_ID", "year"])
        .agg(**agg_cols)
        .reset_index()
    )

    # Region-level static data
    last_year = df["year"].max()
    region_static = (
        df[df["year"] == last_year]
        .groupby("NUTS_ID")
        .agg(
            region_name       =("region_name",        "first"),
            GDP_per_capita    =("GDP_per_capita",      "mean"),
            Air_Inequity_Index=("Air_Inequity_Index",  "mean"),
            Index             =("Index",               "mean"),
        )
    )
    for col in ["green_pct", "forest_pct", "industrial_pct", "GSD", "HBI", "EJS",
                "covid_signal", "industrial_exposure"]:
        if col in df.columns:
            region_static[col] = df[df["year"] == last_year].groupby("NUTS_ID")[col].mean()
    region_static = region_static.reset_index()

    # ── Gemeente level (optional) ──────────────────────────────────────────────
    gm_csv = _BASE / "gemeente_extended.csv"
    gm_geojson_path = _BASE / "nl_gemeente.geojson"

    if gm_csv.exists() and gm_geojson_path.exists():
        gm_df = pd.read_csv(gm_csv)
        gm_df["year"]  = gm_df["year"].astype(int)
        gm_df["month"] = gm_df["month"].astype(int)
        gm_df["date"]  = pd.to_datetime(gm_df[["year","month"]].assign(day=1))

        with open(gm_geojson_path, encoding="utf-8") as f:
            gm_geojson = json.load(f)

        # Annual mean per gemeente
        gm_agg_cols = {
            "GM_NAME":  ("GM_NAME",  "first"),
            "NUTS_ID":  ("NUTS_ID",  "first"),
            "Index":    ("Index",    "mean"),
            "GM_AII":   ("GM_AII",   "mean"),
        }
        for col in ["income_eur", "income_normalized", "green_pct", "industrial_pct",
                    "GSD", "covid_signal"]:
            if col in gm_df.columns:
                gm_agg_cols[col] = (col, "mean")

        gm_annual = (
            gm_df.groupby(["GM_CODE", "year"])
            .agg(**gm_agg_cols)
            .reset_index()
        )
    else:
        gm_df = None
        gm_geojson = None
        gm_annual = None

    return df, geojson, annual, name_map, region_static, gm_df, gm_geojson, gm_annual


DF, GEOJSON, ANNUAL, NAME_MAP, REGION_STATIC, GM_DF, GM_GEOJSON, GM_ANNUAL = _load()

NUTS_IDS      = sorted(DF["NUTS_ID"].unique())
YEARS         = sorted(DF["year"].unique())
POLLUTANTS    = ["PM25", "NO2", "O3", "SO2", "CO", "HCHO"]
HAS_EXTENDED  = "HBI" in DF.columns
HAS_GEMEENTE  = GM_DF is not None
