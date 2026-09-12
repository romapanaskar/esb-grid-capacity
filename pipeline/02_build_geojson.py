"""
Step 2: Export a map-ready GeoJSON FeatureCollection from the cleaned
substation table.

Input:  data/interim/substations_clean.parquet
Output: data/processed/substations.geojson

Design notes:
  - Only the columns the frontend map actually needs are kept in
    `properties` (popups + color-by-headroom logic) — the full cleaned
    table has ~27 columns, most of which the map never touches. Trimming
    keeps the shipped file small.
  - Floats are rounded (capacity figures to 3 decimals, coordinates to
    5 decimals ~ 1m precision) purely to reduce file size; it doesn't
    affect any analysis, which reads from the parquet, not this file.
  - No server-side clustering/aggregation here — Leaflet.markercluster
    handles that client-side in site/js/map.js, so this file is just a
    straightforward point-per-substation export.

  TODO (optimize later): current output is ~16.5 MB, which is heavy for
  a static site's first load. Revisit once the map is working end-to-end -
  options considered: shorten property keys, drop station_name from the
  bulk payload, or (preferred) tier by zoom - aggregated view zoomed out,
  full per-point detail only once zoomed in.
"""

import json
import math
from pathlib import Path

import pandas as pd

IN_PATH = Path(__file__).parent.parent / "data" / "interim" / "substations_clean.parquet"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "substations.geojson"

# Columns copied into each GeoJSON feature's `properties`. Keep this list
# tight - every extra column here grows the shipped file for all users.
PROPERTY_COLS = [
    "station_name",
    "voltage_class",
    "installed_capacity_mva",
    "demand_available_mva",
    "gen_available_firm_mw",
    "demand_is_constrained",
    "generation_is_constrained",
    "is_constrained",
    "parent_station",
]

ROUND_3DP = {"installed_capacity_mva", "demand_available_mva", "gen_available_firm_mw"}


def _clean_value(col, value):
    """Convert a pandas cell into something json.dumps can handle."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (bool,)):
        return value
    if col in ROUND_3DP and isinstance(value, float):
        return round(value, 3)
    return value


def build_feature(row) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            # GeoJSON order is [longitude, latitude]
            "coordinates": [round(row["longitude"], 5), round(row["latitude"], 5)],
        },
        "properties": {col: _clean_value(col, row[col]) for col in PROPERTY_COLS},
    }


def main():
    print(f"Loading {IN_PATH.name} ...")
    df = pd.read_parquet(IN_PATH)
    print(f"  {len(df):,} rows")

    features = [build_feature(row) for _, row in df.iterrows()]
    collection = {"type": "FeatureCollection", "features": features}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        # separators trims whitespace - meaningful at 46k+ features
        json.dump(collection, f, separators=(",", ":"))

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {len(features):,} features to {OUT_PATH} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
