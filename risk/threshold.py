from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DynamicThresholdConfig:
    base_threshold: float = 0.60
    high_vol_add: float = 0.08
    chaotic_add: float = 0.15
    ranging_add: float = 0.03
    low_vol_add: float = 0.05
    trending_add: float = 0.00
    max_threshold: float = 0.90
    min_threshold: float = 0.50


def threshold_for_regime(regime: str, cfg: DynamicThresholdConfig | None = None) -> float:
    if cfg is None:
        cfg = DynamicThresholdConfig()

    regime_u = str(regime or "RANGING").upper()
    add = 0.0
    if regime_u == "HIGH_VOL":
        add = cfg.high_vol_add
    elif regime_u == "CHAOTIC":
        add = cfg.chaotic_add
    elif regime_u == "LOW_VOL":
        add = cfg.low_vol_add
    elif regime_u == "RANGING":
        add = cfg.ranging_add
    elif regime_u == "TRENDING":
        add = cfg.trending_add

    raw = cfg.base_threshold + add
    return max(cfg.min_threshold, min(cfg.max_threshold, raw))
