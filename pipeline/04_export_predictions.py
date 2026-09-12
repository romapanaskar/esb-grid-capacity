"""
Step 4: Format the model artifacts from Step 3 into a single, site-ready
JSON file for the "What predicts constraint" section.

Input:  data/interim/model_metrics.json
        data/interim/feature_importance.json
Output: data/processed/model_results.json

This step does no computation of its own - it's purely a formatting/
renaming pass so site/js/charts.js can consume a clean, stable shape
without knowing anything about sklearn's internal column-naming
conventions (e.g. "cat__structure_type_Pole Substation").
"""

import json
from datetime import datetime, timezone
from pathlib import Path

METRICS_PATH = Path(__file__).parent.parent / "data" / "interim" / "model_metrics.json"
IMPORTANCE_PATH = Path(__file__).parent.parent / "data" / "interim" / "feature_importance.json"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "model_results.json"

TOP_N_FEATURES = 8

# Maps a raw preprocessed column name to a human-readable chart label.
# Anything not listed here falls back to a generic cleanup (see prettify()).
LABEL_OVERRIDES = {
    "num__sibling_count": "Substations sharing the same parent",
    "num__primary_kv_numeric": "Primary voltage (kV)",
    "num__unit_capacity_mva": "Transformer unit capacity (MVA)",
    "num__installed_capacity_mva": "Installed capacity (MVA)",
    "num__config_voltage_kv": "Configured voltage (kV)",
    "num__transformer_count": "Transformer count",
    "num__demand_firm_capacity_mva": "Demand firm capacity (MVA)",
    "num__generation_firm_capacity_mw": "Generation firm capacity (MW)",
    "num__generation_nonfirm_capacity_mw": "Generation non-firm capacity (MW)",
    "num__generation_total_committed_mw": "Generation committed (MW)",
    "cat__structure_type_Pole Substation": "Structure: pole substation",
    "cat__structure_type_Kiosk Substation": "Structure: kiosk substation",
    "cat__structure_type_Building Structure": "Structure: building structure",
    "cat__structure_type_missing": "Structure type unknown",
    "cat__voltage_class_LV": "Voltage class: LV",
    "cat__voltage_class_MV": "Voltage class: MV",
    "cat__voltage_class_38 kV": "Voltage class: 38 kV",
    "cat__voltage_class_110 kV": "Voltage class: 110 kV",
}


def prettify(raw_name: str) -> str:
    if raw_name in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[raw_name]
    # generic fallback: strip the sklearn prefix, swap underscores for spaces
    name = raw_name.split("__", 1)[-1]
    return name.replace("_", " ").capitalize()


def main():
    with open(METRICS_PATH) as f:
        metrics = json.load(f)
    with open(IMPORTANCE_PATH) as f:
        importances = json.load(f)

    top_features = [
        {
            "feature": item["feature"],
            "label": prettify(item["feature"]),
            "importance": round(item["importance"], 4),
        }
        for item in importances[:TOP_N_FEATURES]
    ]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": "is_constrained",
        "base_rate_constrained": round(metrics["base_rate_constrained"], 4),
        "n_train": metrics["n_train"],
        "n_test": metrics["n_test"],
        "models": [
            {
                "name": "Logistic Regression (baseline)",
                **{k: round(v, 4) for k, v in metrics["baseline_logistic_regression"].items()},
            },
            {
                "name": metrics["main_model"]["name"],
                **{
                    k: round(v, 4)
                    for k, v in metrics["main_model"].items()
                    if k != "name"
                },
            },
        ],
        "feature_importance": top_features,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {OUT_PATH}")
    print(f"  main model: {result['models'][1]['name']}  "
          f"f1={result['models'][1]['f1']}  roc_auc={result['models'][1]['roc_auc']}")
    print(f"  top feature: {top_features[0]['label']} ({top_features[0]['importance']})")


if __name__ == "__main__":
    main()
