---
title: Air Inequity NL
emoji: 🌍
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: true
---

# Air Inequity Index — Netherlands

![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Data](https://img.shields.io/badge/data-Sentinel--5P%20%7C%20CAMS%20%7C%20Eurostat%20%7C%20CBS-orange)
![Live](https://img.shields.io/badge/live-HuggingFace%20Spaces-yellow)

**Live dashboard → [huggingface.co/spaces/AthithyaLogan/air-inequity-nl](https://huggingface.co/spaces/AthithyaLogan/air-inequity-nl)**

A second iteration of the [EU Big Data Hackathon 2025 NSI_NL project](https://github.com/eurostat/eubd2025_results/tree/main/NSI_NL).

Combines Sentinel-5P satellite air quality data with regional economic and socioeconomic data to compute an **Air Inequity Index (AII)** — measuring how economically vulnerable regions experience disproportionate air pollution exposure across the Netherlands, at both NUTS-3 and municipality (gemeente) level.

---

## What it shows

The dashboard has 4 tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | Choropleth map (toggle NUTS-3 / 342 municipalities), monthly trend, pollutant quality box plot |
| **Environmental Justice** | GDP vs AII scatter, green space vs pollution, COVID-19 lockdown air quality signal |
| **Time Analysis** | Monthly AII heatmap (year × month), seasonal breakdown, best vs worst 5 regions over time |
| **Region Rankings** | Sortable table of all regions + radar profile chart per region |

### Metrics

| Metric | Description |
|--------|-------------|
| **Pollution Index** | Seasonal-weighted composite of 6 pollutants (PM2.5, NO2, O3, SO2, CO, HCHO) |
| **Air Inequity Index (AII)** | Pollution Index × GDP_Normalized — penalises poor regions more |
| **Health Burden Index (HBI)** | PM2.5 (40%) + NO2 (30%) + O3 (15%) + SO2 (15%) quality scores |
| **Environmental Justice Score (EJS)** | 0.5×HBI + 0.3×poverty + 0.2×green space deficit |
| **Green Space Deficit (GSD)** | Inverse of green space % from CBS land use data |
| **COVID Signal** | Spring 2020 pollution vs 2018/19 baseline — lockdown air quality effect |

---

## Data sources

| Source | Data | Resolution |
|--------|------|-----------|
| [Sentinel-5P TROPOMI](https://dataspace.copernicus.eu) via CDSE | NO2, SO2, CO, O3, HCHO | NUTS-3, monthly, 2018–2023 |
| [CAMS EAC4](https://ads.atmosphere.copernicus.eu) | PM2.5 | NUTS-3, monthly, 2018–2023 |
| [Eurostat](https://ec.europa.eu/eurostat) | GDP per capita, population, NUTS-3 GeoJSON | NUTS-3, annual |
| [CBS StatLine 85318NED](https://opendata.cbs.nl) | Avg income, urban density per municipality | Gemeente (342) |
| [CBS StatLine 70262NED](https://opendata.cbs.nl) | Land use: green space, industrial % | Gemeente (342) |
| [PDOK WFS](https://service.pdok.nl) | Municipality boundaries GeoJSON | Gemeente (342) |

---

## Quick start (local)

```bash
git clone https://github.com/athithyai/Air-Inequity
cd Air-Inequity
pip install -r requirements.txt
python dashboard/app.py
# → http://localhost:7860
```

The processed data files (`data/processed/`) are committed to the repo — no need to run the pipeline to view the dashboard.

---

## Data pipeline (optional — rebuild from scratch)

### Step 1 — API credentials

**Copernicus Data Space Ecosystem** (Sentinel-5P):
```bash
cp scripts/config.py.example scripts/config.py
# fill in SH_CLIENT_ID and SH_CLIENT_SECRET
# register free at https://dataspace.copernicus.eu
```

**Copernicus ADS** (PM2.5 / CAMS):
```
# create ~/.cdsapirc
url: https://ads.atmosphere.copernicus.eu/api
key: <your-key>
```

### Step 2 — Run scripts in order

```bash
python scripts/03_fetch_eurostat.py       # NUTS-3 boundaries + GDP (no key needed)
python scripts/01_fetch_sentinel.py       # Sentinel-5P — ~1.5h with 4 parallel workers
python scripts/02_fetch_pm25_cds.py       # CAMS PM2.5 — ~30 min
python scripts/04_merge_and_clean.py      # merge, fill gaps, add season
python scripts/05_compute_index.py        # quality scores + AII
python scripts/06_verify_output.py        # sanity checks
python scripts/07_fetch_cbs_stats.py      # CBS land use per NUTS-3
python scripts/10_compute_extended_index.py  # HBI, GSD, EJS, COVID signal
python scripts/11_fetch_gemeente.py       # gemeente boundaries + CBS income/land use
```

---

## Methodology

### Quality scoring

Each pollutant is converted to a score (1 = clean, 6 = most polluted) using WHO/EPA thresholds:

| Pollutant | Thresholds | Unit |
|-----------|-----------|------|
| PM2.5 | 10 / 15 / 20 / 30 / 50 | µg/m³ |
| NO2 | 50 / 100 / 200 / 500 / 1000 | µg/m² |
| SO2 | 50 / 100 / 150 / 200 / 300 | µg/m² |
| O3 | 0.05 / 0.10 / 0.15 / 0.20 / 0.30 | mol/m² |
| CO | 0.01 / 0.02 / 0.03 / 0.05 / 0.10 | mol/m² |
| HCHO | 5 / 10 / 15 / 20 / 30 | µg/m² |

### Seasonal weights

| Pollutant | Winter | Spring | Summer | Autumn |
|-----------|--------|--------|--------|--------|
| PM2.5 | 0.40 | 0.36 | 0.25 | 0.35 |
| NO2 | 0.25 | 0.22 | 0.15 | 0.23 |
| O3 | 0.10 | 0.15 | 0.30 | 0.15 |
| SO2 | 0.12 | 0.12 | 0.05 | 0.12 |
| CO | 0.06 | 0.07 | 0.10 | 0.07 |
| HCHO | 0.07 | 0.08 | 0.15 | 0.08 |

### Air Inequity Index formula

```
GDP_Normalized     = 1 − (GDP_per_capita − min) / (max − min)   # 0=richest, 1=poorest
Air_Inequity_Index = Pollution_Index × GDP_Normalized
```

High AII = high pollution + low economic resources = most inequitable exposure.

---

## Project structure

```
Air-Inequity/
├── dashboard/
│   ├── app.py              # Dash entry point
│   ├── callbacks.py        # 15 Plotly callbacks
│   ├── data_loader.py      # Loads all data at startup
│   ├── layout.py           # 4-tab layout
│   └── assets/style.css
├── scripts/
│   ├── 01_fetch_sentinel.py      # Sentinel-5P via CDSE (parallel, 4 workers)
│   ├── 02_fetch_pm25_cds.py      # CAMS PM2.5
│   ├── 03_fetch_eurostat.py      # NUTS-3 GDP + GeoJSON
│   ├── 04_merge_and_clean.py
│   ├── 05_compute_index.py
│   ├── 06_verify_output.py
│   ├── 07_fetch_cbs_stats.py     # CBS land use per NUTS-3
│   ├── 08_fetch_luchtmeetnet.py  # Ground station validation (optional)
│   ├── 10_compute_extended_index.py  # HBI, GSD, EJS, COVID signal
│   ├── 11_fetch_gemeente.py      # 342 gemeente boundaries + CBS income
│   └── config.py.example
├── data/processed/               # Pre-built data (committed)
│   ├── final_extended.csv        # 2880 rows × 52 cols (NUTS-3, 2018–2023)
│   ├── gemeente_extended.csv     # 24624 rows (342 gemeenten × 6 years)
│   ├── nl_nuts3.geojson          # 40 NUTS-3 boundaries
│   └── nl_gemeente.geojson       # 342 municipality boundaries
├── Dockerfile
├── wsgi.py
└── requirements.txt
```

---

## License

MIT — built for the EU Big Data Hackathon 2025, extended as an open research tool.
