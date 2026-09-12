"""
Shared parsing helpers for the ESB grid capacity pipeline.

The raw ESB "capacity heatmap" export packs several pieces of information
into free-text columns (e.g. "Constrained, otherwise capacity available
=380 kW" or "630 kVA  :Kiosk Substation"). These helpers pull structured
fields out of that text so downstream steps can work with clean numeric /
categorical columns.
"""

import math
import re


def _is_missing(value):
    """True for None, NaN, or a blank/whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False

# ---------------------------------------------------------------------------
# Constraint columns
# ---------------------------------------------------------------------------
# Example values:
#   None
#   "Constrained, otherwise capacity available =519 kVA"
#   "Constrained, otherwise capacity available =5.51 MW"
_CONSTRAINT_RE = re.compile(
    r"otherwise capacity available\s*=\s*([\d.]+)\s*(kVA|MVA|kW|MW)", re.IGNORECASE
)

_UNIT_TO_MEGA = {
    "kva": 1 / 1000,
    "mva": 1,
    "kw": 1 / 1000,
    "mw": 1,
}


def parse_constraint(value):
    """Parse a *Parent Constraint text field.

    Returns a tuple:
        is_constrained: bool
        available_if_freed: float | None   (normalised to MVA / MW)

    A null/blank value means "not constrained" in this dataset — the column
    is only populated when a parent-level bottleneck exists.
    """
    if _is_missing(value):
        return False, None

    match = _CONSTRAINT_RE.search(str(value))
    if not match:
        # Constrained but the free-text didn't match the expected pattern —
        # still flag as constrained, just without a numeric headroom value.
        return True, None

    amount, unit = match.groups()
    normalised = float(amount) * _UNIT_TO_MEGA[unit.lower()]
    return True, normalised


# ---------------------------------------------------------------------------
# Transformer Configuration column
# ---------------------------------------------------------------------------
# Two distinct formats depending on voltage class:
#   LV/MV substations:  "630 kVA  :Kiosk Substation"
#   MV/HV substations:  "2x5 MVA @ 20 kV"  (N units x rated size @ voltage)
_LV_CONFIG_RE = re.compile(
    r"([\d.]+)\s*kVA\s*:\s*(.+)", re.IGNORECASE
)
_HV_CONFIG_RE = re.compile(
    r"(\d+)\s*x\s*([\d.]+)\s*(MVA|kVA)\s*@\s*([\d.]+)\s*kV", re.IGNORECASE
)


def parse_transformer_configuration(value):
    """Parse the *Transformer Configuration* free-text field.

    Returns a dict with whichever of these can be extracted:
        transformer_count:   int | None
        unit_capacity_mva:   float | None  (per-transformer rating, in MVA)
        structure_type:      str | None    (e.g. "Kiosk Substation")
        config_voltage_kv:   float | None  (voltage named inside the config)
    """
    out = {
        "transformer_count": None,
        "unit_capacity_mva": None,
        "structure_type": None,
        "config_voltage_kv": None,
    }
    if _is_missing(value):
        return out

    text = str(value).strip()

    hv_match = _HV_CONFIG_RE.search(text)
    if hv_match:
        count, size, unit, voltage = hv_match.groups()
        size = float(size) * (1 / 1000 if unit.lower() == "kva" else 1)
        out["transformer_count"] = int(count)
        out["unit_capacity_mva"] = size
        out["config_voltage_kv"] = float(voltage)
        return out

    lv_match = _LV_CONFIG_RE.search(text)
    if lv_match:
        size, structure = lv_match.groups()
        out["transformer_count"] = 1
        out["unit_capacity_mva"] = float(size) / 1000
        out["structure_type"] = structure.strip()
        return out

    return out
