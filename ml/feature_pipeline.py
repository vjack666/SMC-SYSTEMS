from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_SCHEMA_PATH = Path("ml/features_schema.json")


def _safe_num_col(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def validate_required_columns(frame: pd.DataFrame, required: list[str]) -> list[str]:
    missing = [c for c in required if c not in frame.columns]
    return missing


def build_feature_pipeline(
    dataset: pd.DataFrame,
    output_schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = dataset.copy()

    numeric_cols = [
        "trend_confidence",
        "atr_ratio",
        "bos_strength",
        "choch_strength",
        "fvg_size",
        "ob_distance",
        "displacement_strength",
        "ema_distance",
        "ema_slope",
        "candle_range_vs_atr",
        "rsi",
        "rsi_slope",
        "volume_ratio",
        "spread",
        "rr_ratio",
        "expected_hold_bars",
        # NEW: Structural SL features
        "structural_stop_distance",
        "structural_stop_atr_ratio",
        "distance_to_origin_swing",
        "distance_to_sweep",
        "bos_displacement_size",
        "bos_displacement_atr",
        "liquidity_sweep_size",
        "liquidity_sweep_atr",
        "exhaustion_score",
        "exhaustion_cycles",
        "price_compressed",
        "exhaustion_compression_ratio",
        "wyckoff_event_score",
        "distance_to_fvg_zone",
        "distance_to_ob_zone",
        "distance_to_swing_high",
        "distance_to_swing_low",
        "temporal_alignment_score",
        "pac_completion_rate",
        "exhaustion_confluence_ratio",
    ]
    categorical_cols = [
        "symbol",
        "session",
        "weekday",
        "market_regime",
        "d1_bias",
        "h4_bias",
        "trend_alignment",
        "direction",
        "wyckoff_phase",
        "accumulation_phase",
    ]

    for col in numeric_cols:
        df[col] = _safe_num_col(df, col, 0.0)

    for col in categorical_cols:
        if col not in df.columns:
            df[col] = "UNKNOWN"
        df[col] = df[col].astype(str)

    # Light leakage guard
    leakage_cols = [
        "pnl_r",
        "win",
        "exit_reason",
        "max_favorable_excursion",
        "max_adverse_excursion",
    ]

    feature_cols = [c for c in numeric_cols + categorical_cols if c not in leakage_cols]

    # Remove highly correlated numeric features > 0.97
    num_df = df[numeric_cols].copy()
    corr = num_df.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    drop_corr = [column for column in upper.columns if any(upper[column] > 0.97)]
    feature_cols = [c for c in feature_cols if c not in drop_corr]

    drift_report: dict[str, float] = {}
    if "timestamp" in df.columns and len(df) > 200:
        ordered = df.sort_values("timestamp").reset_index(drop=True)
        mid = len(ordered) // 2
        left = ordered.iloc[:mid]
        right = ordered.iloc[mid:]
        for col in [c for c in feature_cols if c in numeric_cols]:
            l = float(left[col].mean()) if len(left) else 0.0
            r = float(right[col].mean()) if len(right) else 0.0
            denom = max(abs(l), 1e-9)
            drift_report[col] = float(abs(r - l) / denom)

    schema = {
        "version": "v1",
        "rows": int(len(df)),
        "feature_columns": feature_cols,
        "numeric_columns": [c for c in feature_cols if c in numeric_cols],
        "categorical_columns": [c for c in feature_cols if c in categorical_cols],
        "dropped_correlated": drop_corr,
        "drift_report": drift_report,
    }

    output_schema_path.parent.mkdir(parents=True, exist_ok=True)
    output_schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    return df, schema
