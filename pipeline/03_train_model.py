"""
Step 3: Train a classifier that predicts whether a substation sits behind
a constrained parent connection (`is_constrained`), using only its own
specifications - not the headroom figures the label is derived from.

Input:  data/interim/substations_clean.parquet
Output: models/constraint_classifier.joblib
        data/interim/model_metrics.json
        data/interim/feature_importance.json

IMPORTANT - leakage note:
  `demand_available_mva`, `gen_available_firm_mw`, `gen_available_nonfirm_mw`,
  `parent_available_mva`, and the parsed `*_available_if_freed_*` columns
  are mechanically derived from the same constraint logic as the label
  (they're ~0 whenever the corresponding constraint flag is True - see
  the groupby check run during development). They are EXCLUDED from the
  feature set for that reason. Everything used below describes the
  transformer's own specification or existing committed load, not a
  headroom outcome.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

IN_PATH = Path(__file__).parent.parent / "data" / "interim" / "substations_clean.parquet"
MODEL_PATH = Path(__file__).parent.parent / "models" / "constraint_classifier.joblib"
METRICS_PATH = Path(__file__).parent.parent / "data" / "interim" / "model_metrics.json"
IMPORTANCE_PATH = Path(__file__).parent.parent / "data" / "interim" / "feature_importance.json"

TARGET = "is_constrained"

NUMERIC_FEATURES = [
    "primary_kv_numeric",
    "transformer_count",
    "unit_capacity_mva",
    "config_voltage_kv",
    "installed_capacity_mva",
    "demand_firm_capacity_mva",
    "generation_firm_capacity_mw",
    "generation_nonfirm_capacity_mw",
    "generation_total_committed_mw",
    "sibling_count",
]
CATEGORICAL_FEATURES = ["voltage_class", "structure_type"]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # primary_kv is text ("10 kV") - pull the numeric value out
    df["primary_kv_numeric"] = (
        df["primary_kv"].str.extract(r"([\d.]+)").astype(float)
    )

    # How many substations share the same parent station - a proxy for
    # how loaded that shared upstream feeder/transformer is.
    sibling_counts = df.groupby("parent_station")["station_name"].transform("count")
    df["sibling_count"] = sibling_counts.fillna(0)

    return df


def build_pipeline(model):
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessor = ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("preprocess", preprocessor),
        ("model", model),
    ])


def evaluate(name, pipeline, X_test, y_test) -> dict:
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }
    print(f"\n--- {name} ---")
    print(classification_report(y_test, y_pred, target_names=["unconstrained", "constrained"]))
    return metrics


def get_feature_names(pipeline) -> list:
    return list(pipeline.named_steps["preprocess"].get_feature_names_out())


def main():
    print(f"Loading {IN_PATH.name} ...")
    df = pd.read_parquet(IN_PATH)
    df = engineer_features(df)

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[feature_cols]
    y = df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train):,}  Test: {len(X_test):,}")
    print(f"Base rate (constrained): {y.mean():.1%}")

    # --- Baseline: logistic regression, for interpretability reference ---
    baseline = build_pipeline(LogisticRegression(max_iter=1000, class_weight="balanced"))
    baseline.fit(X_train, y_train)
    baseline_metrics = evaluate("Logistic Regression (baseline)", baseline, X_test, y_test)

    # --- Main model ---
    if HAS_XGBOOST:
        main_model = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=42,
        )
        main_name = "XGBoost"
    else:
        main_model = RandomForestClassifier(
            n_estimators=300, max_depth=12, class_weight="balanced", random_state=42
        )
        main_name = "Random Forest (xgboost not installed)"

    main_pipeline = build_pipeline(main_model)
    main_pipeline.fit(X_train, y_train)
    main_metrics = evaluate(main_name, main_pipeline, X_test, y_test)

    # --- Feature importance (from the main model) ---
    feature_names = get_feature_names(main_pipeline)
    importances = main_pipeline.named_steps["model"].feature_importances_
    importance_pairs = sorted(
        zip(feature_names, importances), key=lambda p: p[1], reverse=True
    )

    print("\nTop features:")
    for name, imp in importance_pairs[:10]:
        print(f"  {imp:.3f}  {name}")

    # --- Save artifacts ---
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(main_pipeline, MODEL_PATH)
    print(f"\nWrote {MODEL_PATH}")

    metrics_out = {
        "base_rate_constrained": float(y.mean()),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "baseline_logistic_regression": baseline_metrics,
        "main_model": {"name": main_name, **main_metrics},
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_out, f, indent=2)
    print(f"Wrote {METRICS_PATH}")

    importance_out = [
        {"feature": name, "importance": float(imp)} for name, imp in importance_pairs
    ]
    with open(IMPORTANCE_PATH, "w") as f:
        json.dump(importance_out, f, indent=2)
    print(f"Wrote {IMPORTANCE_PATH}")


if __name__ == "__main__":
    main()
