"""
07_fetch_cbs_stats.py
---------------------
Fetches regional statistics from CBS (Dutch national statistics) OData API.

Data fetched (all at COROP / NUTS-3 level):
  - Land use: green space %, forest %, industrial %, park area  [70262NED]
  - Socioeconomic: income per person, poverty rate, car ownership [85318NED]

Output: data/raw/cbs_stats.csv
        columns: NUTS_ID, green_pct, forest_pct, park_pct, industrial_pct,
                 avg_income, pct_low_income, cars_per_household, urban_density,
                 woz_value (avg house value proxy)
"""

import sys
import time
import urllib3
from pathlib import Path

import pandas as pd
import requests

urllib3.disable_warnings()
sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_RAW

CBS = "https://opendata.cbs.nl/ODataApi/odata"


# ── COROP code → NUTS-3 ID crosswalk ─────────────────────────���────────────────
COROP_TO_NUTS = {
    "CR01": "NL114", "CR02": "NL112", "CR03": "NL115",
    "CR04": "NL127", "CR05": "NL128", "CR06": "NL126",
    "CR07": "NL131", "CR08": "NL132", "CR09": "NL133",
    "CR10": "NL211", "CR11": "NL212", "CR12": "NL213",
    "CR13": "NL221", "CR14": "NL225", "CR15": "NL226",
    "CR16": "NL224", "CR17": "NL350", "CR18": "NL321",
    "CR19": "NL328", "CR20": "NL323", "CR21": "NL32A",
    "CR22": "NL325", "CR23": "NL32B", "CR24": "NL327",
    "CR25": "NL363", "CR26": "NL361", "CR27": "NL362",
    "CR28": "NL365", "CR29": "NL366", "CR30": "NL364",
    "CR31": "NL341", "CR32": "NL342", "CR33": "NL411",
    "CR34": "NL415", "CR35": "NL416", "CR36": "NL414",
    "CR37": "NL421", "CR38": "NL422", "CR39": "NL423",
    "CR40": "NL230",
}

COROP_FILTER = " or ".join([f"RegioS eq '{k}  '" for k in COROP_TO_NUTS])


def cbs_fetch(table, entity, params=None, retries=3):
    url = f"{CBS}/{table}/{entity}"
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30, verify=False)
            r.raise_for_status()
            return r.json().get("value", [])
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(5)
    return []


# ── 1. Land use from 70262NED (Bodemgebruik per gemeente → COROP) ─────────────
print("Fetching CBS land use data (70262NED)…")

# Get most recent period
periods = cbs_fetch("70262NED", "Perioden?$orderby=Key desc&$top=5")
latest_period = periods[0]["Key"].strip() if periods else "2023JJ00"
print(f"  Using period: {latest_period}")

# Fetch all COROP rows for latest period
land_rows = []
for cr, nuts_id in COROP_TO_NUTS.items():
    cr_padded = cr.ljust(6)  # CBS pads codes to 6 chars
    params = {
        "$filter": f"RegioS eq '{cr_padded}' and Perioden eq '{latest_period}'",
        "$select": (
            "RegioS,TotaleOppervlakte_1,TotaalBebouwdTerrein_6,"
            "Bedrijventerrein_11,TotaalRecreatieterrein_19,"
            "ParkEnPlantsoen_20,TotaalBosEnOpenNatuurlijkTerrein_28,"
            "Bos_29,OpenDroogNatuurlijkTerrein_30,OpenNatNatuurlijkTerrein_31,"
            "Wegverkeersterrein_4"
        ),
    }
    rows = cbs_fetch("70262NED", "TypedDataSet", params)
    if rows:
        r = rows[0]
        total = r.get("TotaleOppervlakte_1") or 1
        green_area = (
            (r.get("ParkEnPlantsoen_20") or 0)
            + (r.get("TotaalBosEnOpenNatuurlijkTerrein_28") or 0)
            + (r.get("TotaalRecreatieterrein_19") or 0)
        )
        forest_area = (r.get("Bos_29") or 0)
        park_area   = (r.get("ParkEnPlantsoen_20") or 0)
        industrial  = (r.get("Bedrijventerrein_11") or 0)
        road        = (r.get("Wegverkeersterrein_4") or 0)

        land_rows.append({
            "NUTS_ID":       nuts_id,
            "corop":         cr,
            "total_area_ha": total,
            "green_pct":     round(green_area / total * 100, 2),
            "forest_pct":    round(forest_area / total * 100, 2),
            "park_pct":      round(park_area / total * 100, 2),
            "industrial_pct":round(industrial / total * 100, 2),
            "road_pct":      round(road / total * 100, 2),
        })
        print(f"  {nuts_id} ({cr}): green={green_area/total*100:.1f}%  forest={forest_area/total*100:.1f}%  industrial={industrial/total*100:.1f}%")
    else:
        print(f"  {nuts_id} ({cr}): no data")
    time.sleep(0.3)

land_df = pd.DataFrame(land_rows)
print(f"Land use: {len(land_df)} COROP regions")


# ── 2. Socioeconomic data from 85318NED (Kerncijfers wijken en buurten) ────────
print("\nFetching CBS socioeconomic data (85318NED)…")

# This table uses Codering_3 that matches COROP codes like 'CR01'
socio_rows = []
for cr, nuts_id in COROP_TO_NUTS.items():
    params = {
        "$filter": f"startswith(Codering_3,'{cr}')",
        "$select": (
            "WijkenEnBuurten,Codering_3,SoortRegio_2,"
            "GemiddeldInkomenPerInwoner_72,"
            "GemGestandaardiseerdInkomenVanHuish_75,"
            "HuishoudensMetEenLaagInkomen_78,"
            "PersonenautoSPerHuishouden_103,"
            "Omgevingsadressendichtheid_117,"
            "GemiddeldeWOZWaardeVanWoningen_35,"
            "OpleidingsniveauHoog_66,"
            "Nettoarbeidsparticipatie_67"
        ),
        "$top": 5,
    }
    rows = cbs_fetch("85318NED", "TypedDataSet", params)
    # Filter to COROP level (SoortRegio_2 = 'Corop')
    corop_rows = [r for r in rows if "corop" in str(r.get("SoortRegio_2", "")).lower()
                  or str(r.get("Codering_3", "")).strip().upper() == cr]
    if not corop_rows and rows:
        corop_rows = rows[:1]  # fallback: take first result

    if corop_rows:
        r = corop_rows[0]
        socio_rows.append({
            "NUTS_ID":            nuts_id,
            "avg_income":         r.get("GemiddeldInkomenPerInwoner_72"),
            "median_hh_income":   r.get("GemGestandaardiseerdInkomenVanHuish_75"),
            "pct_low_income":     r.get("HuishoudensMetEenLaagInkomen_78"),
            "cars_per_household": r.get("PersonenautoSPerHuishouden_103"),
            "urban_density":      r.get("Omgevingsadressendichtheid_117"),
            "avg_woz_value":      r.get("GemiddeldeWOZWaardeVanWoningen_35"),
            "pct_high_education": r.get("OpleidingsniveauHoog_66"),
            "labour_participation": r.get("Nettoarbeidsparticipatie_67"),
        })
        inc = r.get("GemiddeldInkomenPerInwoner_72", "?")
        dns = r.get("Omgevingsadressendichtheid_117", "?")
        print(f"  {nuts_id} ({cr}): income={inc}  density={dns}")
    else:
        socio_rows.append({"NUTS_ID": nuts_id})
        print(f"  {nuts_id} ({cr}): no data")
    time.sleep(0.3)

socio_df = pd.DataFrame(socio_rows)
print(f"Socioeconomic: {len(socio_df)} COROP regions")


# ── 3. Merge and save ──────────────────────────────────────────────────────────
df = land_df.merge(socio_df, on="NUTS_ID", how="outer")
df = df.drop(columns=["corop"], errors="ignore")

out = DATA_RAW / "cbs_stats.csv"
df.to_csv(out, index=False)
print(f"\n✓ Saved {len(df)} rows → {out}")
print(df[["NUTS_ID","green_pct","industrial_pct","avg_income"]].to_string())
print("\n✓ 07_fetch_cbs_stats done")
