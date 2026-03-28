"""Test one Statistical API call against CDSE Sentinel-5P."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import SH_CLIENT_ID, SH_CLIENT_SECRET

import geopandas as gpd
from sentinelhub import SHConfig, DataCollection, SentinelHubStatistical, Geometry, CRS

cfg = SHConfig()
cfg.sh_client_id     = SH_CLIENT_ID
cfg.sh_client_secret = SH_CLIENT_SECRET
cfg.sh_base_url      = "https://sh.dataspace.copernicus.eu"
cfg.sh_token_url     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

CDSE_S5P = DataCollection.define(
    name="CDSE_SENTINEL5P",
    api_id="sentinel-5p-l2",
    service_url="https://sh.dataspace.copernicus.eu",
)

nuts = gpd.read_file(r"C:\Users\great\Documents\Lab\AirInequity\data\processed\nl_nuts3.geojson").to_crs("EPSG:4326")
region = nuts.iloc[0]
geom   = Geometry(geometry=region.geometry.__geo_interface__, crs=CRS.WGS84)

evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["NO2", "dataMask"] }],
    output: [
      { id: "value", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(samples) {
  return { value: [samples.NO2], dataMask: [samples.dataMask] };
}
"""

request = SentinelHubStatistical(
    aggregation=SentinelHubStatistical.aggregation(
        evalscript=evalscript,
        time_interval=("2023-06-01", "2023-06-30"),
        aggregation_interval="P1D",
        resolution=(3500, 3500),
    ),
    input_data=[SentinelHubStatistical.input_data(CDSE_S5P)],
    geometry=geom,
    config=cfg,
)

try:
    data = request.get_data()[0]
    intervals = data.get("data", [])
    print(f"✓ {region['NUTS_ID']}: {len(intervals)} daily intervals")
    if intervals:
        sample_val = intervals[0]["outputs"]["value"]["bands"]["B0"]["stats"]["mean"]
        print(f"  Sample NO2 mean: {sample_val}")
except Exception as e:
    print(f"ERROR: {e}")
