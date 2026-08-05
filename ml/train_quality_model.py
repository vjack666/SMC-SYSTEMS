from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class TrainingConfig:
    dataset_path: Path = Path("results/ml_trade_dataset.csv")
    model_dir: Path = Path("ml/models")
    metrics_path: Path = Path("ml/model_metrics.json")
    importance_path: Path = Path("ml/feature_importance.csv")
    random_state: int = 42


def _pick_estimator() -> tuple[str, Any]:
    try:
        from xgboost import XGBClassifier

        return (
            "xgboost",
            XGBClassifier(
                n_estimators=220,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=42,
                objective="binary:logistic",
                eval_metric="logloss",
            ),
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMClassifier

        return (
            "lightgbm",
            LGBMClassifier(
                n_estimators=280,
                max_depth=-1,
                learning_rate=0.05,
                random_state=42,
            ),
        )
    except Exception:
        pass

    try:
        from catboost import CatBoostClassifier

        return (
            "catboost",
            CatBoostClassifier(
                iterations=260,
                depth=5,
                learning_rate=0.05,
                verbose=False,
                random_state=42,
            ),
        )
    except Exception:
        pass

    from sklearn.ensemble import HistGradientBoostingClassifier

    return (
        "hist_gradient_boosting",
        HistGradientBoostingClassifier(random_state=42),
    )


def train_quality_model(cfg: TrainingConfig | None = None) -> dict[str, Any]:
    if cfg is None:
        cfg = TrainingConfig()

    if not cfg.dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {cfg.dataset_path}")

    df = pd.read_csv(cfg.dataset_path)
    if "win" not in df.columns:
        raise ValueError("Dataset must contain 'win' target column")

    y = pd.to_numeric(df["win"], errors="coerce").fillna(0).astype(int)
    X = df.drop(
        columns=[
            c
            for c in [
                "win",
                "pnl_r",
                "exit_reason",
                "trade_id",
                "schema_version",
            ]
            if c in df.columns
        ],
        errors="ignore",
    )

    numeric = [c for c in X.columns if is_numeric_dtype(X[c])]
    categorical = [c for c in X.columns if c not in numeric]

    preprocess = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ]
    )

    model_name, estimator = _pick_estimator()

    pipeline = Pipeline(
        steps=[
            ("preprocess", preprocess),
            ("clf", estimator),
        ]
    )

    class_counts_full = y.value_counts()
    can_stratify = y.nunique() > 1 and int(class_counts_full.min()) >= 2
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=cfg.random_state,
        stratify=y if can_stratify else None,
    )

    # Rare-class datasets can produce a single-class train split; use full data fallback to keep pipeline running.
    if y_train.nunique() < 2:
        X_train, y_train = X.copy(), y.copy()
        X_test, y_test = X.copy(), y.copy()

    pipeline.fit(X_train, y_train)

    class_counts = y_train.value_counts()
    min_class_count = int(class_counts.min()) if len(class_counts) > 0 else 0
    calibration_cv = min(3, min_class_count)

    model_for_inference: Any
    calibration_used = False
    calibration_method = "none"
    if y_train.nunique() > 1 and calibration_cv >= 2:
        calibration_method = "isotonic" if calibration_cv >= 3 else "sigmoid"
        calibrated = CalibratedClassifierCV(pipeline, method=calibration_method, cv=calibration_cv)
        calibrated.fit(X_train, y_train)
        model_for_inference = calibrated
        calibration_used = True
    else:
        model_for_inference = pipeline

    proba = model_for_inference.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    metrics = {
        "model": model_name,
        "rows": int(len(df)),
        "logloss": float(log_loss(y_test, proba, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y_test, proba)) if len(np.unique(y_test)) > 1 else 0.5,
        "precision": float(precision_score(y_test, pred, zero_division=0)),
        "recall": float(recall_score(y_test, pred, zero_division=0)),
        "brier_score": float(brier_score_loss(y_test, proba)),
        "calibration_used": calibration_used,
        "calibration_method": calibration_method,
        "calibration_cv": int(calibration_cv),
    }

    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    model_path = cfg.model_dir / "quality_filter.pkl"
    joblib.dump(model_for_inference, model_path)

    # Permutation-like importance proxy based on numeric correlations to target.
    imp_rows = []
    for col in X.columns:
        if pd.api.types.is_numeric_dtype(X[col]):
            corr = np.corrcoef(pd.to_numeric(X[col], errors="coerce").fillna(0.0), y)[0, 1]
            val = 0.0 if not np.isfinite(corr) else abs(float(corr))
        else:
            val = 0.0
        imp_rows.append({"feature": col, "importance": val})
    imp_df = pd.DataFrame(imp_rows).sort_values("importance", ascending=False)
    imp_df.to_csv(cfg.importance_path, index=False)

    metrics_payload = {
        **metrics,
        "model_path": str(model_path),
        "importance_path": str(cfg.importance_path),
    }
    cfg.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    return metrics_payload


if __name__ == "__main__":
    out = train_quality_model()
    print(json.dumps(out, indent=2))
