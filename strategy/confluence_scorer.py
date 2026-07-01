from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk.dynamic_threshold_engine import DynamicThresholdConfig


@dataclass(frozen=True)
class ConfluenceWeights:
    pac: float = 0.30
    wyckoff: float = 0.25
    exhaustion: float = 0.20
    structural_sl: float = 0.15
    ml_filter: float = 0.10


REGIME_BOOSTS = {
    "TRENDING": {"pac": 1.1, "wyckoff": 0.9, "exhaustion": 0.8, "structural_sl": 1.0, "ml_filter": 1.0},
    "RANGING": {"pac": 0.9, "wyckoff": 0.8, "exhaustion": 1.2, "structural_sl": 0.9, "ml_filter": 1.1},
    "HIGH_VOL": {"pac": 0.8, "wyckoff": 1.1, "exhaustion": 1.0, "structural_sl": 0.8, "ml_filter": 1.2},
    "LOW_VOL": {"pac": 1.0, "wyckoff": 0.7, "exhaustion": 0.7, "structural_sl": 1.2, "ml_filter": 0.9},
    "CHAOTIC": {"pac": 0.5, "wyckoff": 0.5, "exhaustion": 0.6, "structural_sl": 0.5, "ml_filter": 1.3},
}


def calculate_confluence_score(
    row: pd.Series | dict,
    weights: ConfluenceWeights | None = None,
    regime: str = "RANGING",
) -> float:
    if weights is None:
        weights = ConfluenceWeights()

    regime_boost = REGIME_BOOSTS.get(regime, REGIME_BOOSTS["RANGING"])

    pac_ready = int(row.get("pac_entry_ready", 0))
    exhaustion_conf = int(row.get("pac_exhaustion_confirmed", 0))
    wyckoff_acc = int(row.get("wyckoff_accumulation", 0))
    exhaustion_bull = int(row.get("exhaustion_bullish", 0))
    exhaustion_bear = int(row.get("exhaustion_bearish", 0))
    ml_prob = float(row.get("ml_probability", 0.5))

    exhaustion_active = exhaustion_bull or exhaustion_bear

    pac_weight = weights.pac * regime_boost["pac"]
    exhaustion_weight = weights.exhaustion * regime_boost["exhaustion"]
    wyckoff_weight = weights.wyckoff * regime_boost["wyckoff"]
    ml_weight = weights.ml_filter * regime_boost["ml_filter"]

    wyckoff_active = "wyckoff_accumulation" in row

    score = (
        pac_ready * pac_weight
        + exhaustion_conf * exhaustion_weight * 0.5
        + exhaustion_active * exhaustion_weight * 0.5
        + (wyckoff_acc * wyckoff_weight if wyckoff_active else 0.0)
        + ml_prob * ml_weight
    )

    total_available = pac_weight + exhaustion_weight + ml_weight
    if wyckoff_active:
        total_available += wyckoff_weight
    if total_available > 0:
        score = score / total_available

    return float(max(0.0, min(1.0, score)))


def confluence_to_signal_direction(
    row: pd.Series | dict,
    min_score: float = 0.40,
) -> int:
    macro = str(row.get("macro_direction", "RANGING"))
    regime = str(row.get("market_regime", "RANGING"))
    score = calculate_confluence_score(row, regime=regime)
    if score < min_score:
        return 0
    if macro == "BULLISH":
        return 1
    if macro == "BEARISH":
        return -1
    return 0
