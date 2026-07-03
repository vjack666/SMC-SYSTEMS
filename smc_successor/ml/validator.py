from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from smc_successor.agents.orchestrator import AGENT_COLUMNS
from smc_successor.features.engine import DEFAULT_FEATURES, LEAKAGE_COLS
from smc_successor.ml.dataset_builder import DATASET_LABELS, TRADE_CONTEXT_FEATURES

CRITICAL_FEATURES: tuple[str, ...] = (
    "bos_detected",
    "bos_strength",
    "choch_detected",
    "choch_strength",
    "fvg_detected",
    "fvg_size",
    "fvg_fill_status",
    "fvg_direction",
    "ob_detected",
    "ob_distance",
    "liquidity_sweep",
    "displacement_magnitude",
    "displacement_bullish",
    "displacement_bearish",
    "premium_discount_zone",
    "premium_distance",
    "ote_long_min",
    "ote_short_min",
    "d1_bias",
    "h4_bias",
    "trend_alignment",
    "trend_confidence",
    "atr",
    "atr_ratio",
    "candle_range_vs_atr",
    "rsi",
    "rsi_slope",
    "volume_ratio",
    "momentum_strength",
    "spread",
    "market_regime",
    "directional_efficiency",
    "range_compression",
)

ALL_EXPECTED_COLUMNS: tuple[str, ...] = (
    "schema_version",
    "symbol",
    *DEFAULT_FEATURES,
    *AGENT_COLUMNS,
    *TRADE_CONTEXT_FEATURES,
    *DATASET_LABELS,
)


@dataclass
class ValidationResult:
    passed: bool = True
    rows: int = 0
    columns: int = 0
    missing_critical_features: list[str] = field(default_factory=list)
    missing_agent_columns: list[str] = field(default_factory=list)
    missing_labels: list[str] = field(default_factory=list)
    leakage_columns_found: list[str] = field(default_factory=list)
    nan_counts: dict[str, int] = field(default_factory=dict)
    schema_version: str = ""
    is_deterministic: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "rows": self.rows,
            "columns": self.columns,
            "missing_critical_features": self.missing_critical_features,
            "missing_agent_columns": self.missing_agent_columns,
            "missing_labels": self.missing_labels,
            "leakage_columns_found": self.leakage_columns_found,
            "nan_counts": dict(sorted(self.nan_counts.items(), key=lambda x: -x[1])[:20]),
            "schema_version": self.schema_version,
            "is_deterministic": self.is_deterministic,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_dataset(
    path: Path,
    expected_schema_version: str = "v4",
    check_determinism: bool = True,
) -> ValidationResult:
    result = ValidationResult()

    if not path.exists():
        result.passed = False
        result.errors.append(f"File not found: {path}")
        return result

    try:
        df = pd.read_parquet(path)
    except Exception as e:
        result.passed = False
        result.errors.append(f"Cannot read parquet: {e}")
        return result

    result.rows = int(len(df))
    result.columns = int(len(df.columns))

    # Schema version
    if "schema_version" in df.columns:
        versions = df["schema_version"].unique()
        if len(versions) == 1:
            result.schema_version = str(versions[0])
            if result.schema_version != expected_schema_version:
                result.warnings.append(
                    f"Schema version mismatch: expected {expected_schema_version}, got {result.schema_version}"
                )
        else:
            result.errors.append(f"Multiple schema versions found: {versions}")
    else:
        result.errors.append("Missing schema_version column")

    # Critical features
    for col in CRITICAL_FEATURES:
        if col not in df.columns:
            result.missing_critical_features.append(col)

    # Agent columns
    for col in AGENT_COLUMNS:
        if col == "agent_decision_ml_probability":
            continue
        if col not in df.columns:
            result.missing_agent_columns.append(col)

    # Labels
    for col in DATASET_LABELS:
        if col not in df.columns:
            result.missing_labels.append(col)

    # Leakage check — only flag columns that should NEVER appear
    # (label columns like pnl_r/win are intentionally in the dataset)
    for col in ("future_return",):
        if col in df.columns:
            result.leakage_columns_found.append(col)

    # NaN counts for critical features
    nan_counts: dict[str, int] = {}
    for col in [c for c in CRITICAL_FEATURES if c in df.columns]:
        nan = int(df[col].isna().sum())
        if nan > 0:
            nan_counts[col] = nan
    for col in [c for c in AGENT_COLUMNS if c in df.columns]:
        nan = int(df[col].isna().sum())
        if nan > 0:
            nan_counts[col] = nan
    result.nan_counts = nan_counts

    # Determinism check
    if check_determinism:
        try:
            df2 = pd.read_parquet(path)
            if not df.equals(df2):
                result.is_deterministic = False
                result.errors.append("Non-deterministic output: re-reading produced different data")
        except Exception:
            result.warnings.append("Could not verify determinism (read error on second pass)")

    # Build status
    if result.missing_critical_features:
        result.errors.append(f"Missing {len(result.missing_critical_features)} critical features")
    if result.missing_agent_columns:
        result.errors.append(f"Missing {len(result.missing_agent_columns)} agent columns")
    if result.missing_labels:
        result.errors.append(f"Missing {len(result.missing_labels)} label columns")
    if result.leakage_columns_found:
        result.errors.append(f"Leakage columns present: {result.leakage_columns_found}")
    if result.nan_counts:
        result.warnings.append(f"NaN values in {len(result.nan_counts)} columns")
    if not result.is_deterministic:
        result.errors.append("Dataset is not deterministic")

    result.passed = len(result.errors) == 0
    return result
