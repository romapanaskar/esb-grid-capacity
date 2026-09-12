"""
Step 1: Load the raw ESB capacity heatmap export and produce a clean,
analysis-ready table.

Input:  data/raw/customer-heatmap-download-july-2026.xlsx  (sheet: "Heatmap data")
Output: data/interim/substations_clean.parquet

What this does:
  - Reads the "Heatmap data" sheet (header spans row 2; row 1 is a merged
    section title, so we skip it)
  - Drops columns that carry no information (arrow "flag" columns,
    the 98%-null Transformer GroupID, the constant "_" secondary voltage)
  - Parses the free-text "Parent Constraint" columns into a boolean +
    numeric headroom-if-freed value (see utils.parse_constraint)
  - Parses the free-text "Transformer Configuration" column into
    transformer count / unit capacity / structure type (see
    utils.parse_transformer_configuration)
  - Casts numeric-looking string columns to floats
  - Drops fully-empty rows
"""

import pandas as pd
from pathlib import Path

from utils import parse_constraint, parse_transformer_configuration

RAW_PATH = Path(__file__).parent.parent / "data" / "raw" / "customer-heatmap-download-july-2026.xlsx"
OUT_PATH = Path(__file__).parent.parent / "data" / "interim" / "substations_clean.parquet"

RENAME = {
    "Station Name": "station_name",
    "Primary kV": "primary_kv",
    "Voltage Class": "voltage_class",
    "Transformer Configuration": "transformer_configuration_raw",
    "Installed Capacity MVA": "installed_capacity_mva",
    "Demand FirmCapacity MVA": "demand_firm_capacity_mva",
    "Demand Available MVA": "demand_available_mva",
    "Parent Available MVA": "parent_available_mva",
    "Demand Parent Constraint": "demand_parent_constraint_raw",
    "Generation Firm Capacity MW": "generation_firm_capacity_mw",
    "Generation NonFirm Capacity MW": "generation_nonfirm_capacity_mw",
    "Generation Total Committed MW": "generation_total_committed_mw",
    "Gen Available Firm MW": "gen_available_firm_mw",
    "Gen Available NonFirm MW": "gen_available_nonfirm_mw",
    "Generation Parent Constraint": "generation_parent_constraint_raw",
    "Parent Feeder": "parent_feeder",
    "Parent Station": "parent_station",
    "TSO Interface Station": "tso_interface_station",
    "Comment": "comment",
    "Latitude": "latitude",
    "Longitude": "longitude",
}

# Columns present in the raw sheet that we intentionally drop:
#   Transformer GroupID   - 98.6% null, not usable
#   Secondary voltage(s)  - constant "_" for every row
#   Demand Data / Generation Data / General Data - decorative " -->" arrows

NUMERIC_COLS = [
    "installed_capacity_mva",
    "demand_firm_capacity_mva",
    "demand_available_mva",
    "parent_available_mva",
    "generation_firm_capacity_mw",
    "generation_nonfirm_capacity_mw",
    "generation_total_committed_mw",
    "gen_available_firm_mw",
    "gen_available_nonfirm_mw",
    "latitude",
    "longitude",
]


def load_raw(path: Path) -> pd.DataFrame:
    # Row 1 is a merged section title ("Transformer Available Capacity"),
    # the real header is row 2 -> header=1 (0-indexed)
    return pd.read_excel(path, sheet_name="Heatmap data", header=1)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME)
    df = df[list(RENAME.values())]

    # Drop rows with no station name (the 1-2 fully-blank trailing rows)
    df = df.dropna(subset=["station_name"]).reset_index(drop=True)

    # Numeric casts (source sheet stores several of these as text)
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse constraint free-text into boolean + numeric headroom-if-freed
    dem_parsed = df["demand_parent_constraint_raw"].apply(parse_constraint)
    df["demand_is_constrained"] = dem_parsed.apply(lambda t: t[0])
    df["demand_available_if_freed_mva"] = dem_parsed.apply(lambda t: t[1])

    gen_parsed = df["generation_parent_constraint_raw"].apply(parse_constraint)
    df["generation_is_constrained"] = gen_parsed.apply(lambda t: t[0])
    df["generation_available_if_freed_mw"] = gen_parsed.apply(lambda t: t[1])

    # Combined convenience flag used for Part 2's classifier target
    df["is_constrained"] = df["demand_is_constrained"] | df["generation_is_constrained"]

    # Parse transformer configuration into structured fields
    config_parsed = df["transformer_configuration_raw"].apply(parse_transformer_configuration)
    config_df = pd.DataFrame(list(config_parsed), index=df.index)
    df = pd.concat([df, config_df], axis=1)

    # Drop rows missing coordinates - can't be placed on the map
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} row(s) with missing coordinates")

    return df


def main():
    print(f"Loading {RAW_PATH.name} ...")
    raw = load_raw(RAW_PATH)
    print(f"  {len(raw):,} raw rows")

    df = clean(raw)
    print(f"  {len(df):,} clean rows after processing")
    print(f"  {df['is_constrained'].sum():,} constrained substations "
          f"({df['is_constrained'].mean():.1%})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
