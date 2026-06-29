from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


REGIMES = ("TRENDING", "RANGING", "HIGH_VOL", "LOW_VOL", "CHAOTIC")


@dataclass(frozen=True)
class RegimeConfig:
    high_vol_atr_ratio: float = 1.35
    low_vol_atr_ratio: float = 0.80
    trend_slope_threshold: float = 0.20
    chaotic_efficiency_threshold: float = 0.10
    compression_threshold: float = 0.65


def _safe_num(v: object, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(x):
        return default
    return x


def _directional_efficiency(close: pd.Series, window: int = 20) -> pd.Series:
    delta = close.diff(window).abs()
    path = close.diff().abs().rolling(window).sum()
    return (delta / path.replace(0.0, np.nan)).fillna(0.0)


def detect_regimes(frame: pd.DataFrame, cfg: RegimeConfig | None = None) -> pd.DataFrame:
    if cfg is None:
        cfg = RegimeConfig()

    out = frame.copy()
    atr_ratio = pd.to_numeric(out.get("atr_ratio", 0.0), errors="coerce").fillna(0.0)
    ema_fast = pd.to_numeric(out.get("ema_fast", out.get("close", 0.0)), errors="coerce").fillna(0.0)
    ema_slow = pd.to_numeric(out.get("ema_slow", out.get("close", 0.0)), errors="coerce").fillna(0.0)
    close = pd.to_numeric(out.get("close", 0.0), errors="coerce").fillna(0.0)

    ema_distance = (ema_fast - ema_slow).abs()
    ema_slope = ema_fast.diff(5).fillna(0.0)
    directional_eff = _directional_efficiency(close, window=20)
    range_vs_atr = ((pd.to_numeric(out.get("high", 0.0), errors="coerce") - pd.to_numeric(out.get("low", 0.0), errors="coerce")) / pd.to_numeric(out.get("atr", 1.0), errors="coerce").replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    compression = range_vs_atr.rolling(10).mean().fillna(range_vs_atr)

    regime = pd.Series("RANGING", index=out.index, dtype=object)
    high_vol = atr_ratio >= cfg.high_vol_atr_ratio
    low_vol = atr_ratio <= cfg.low_vol_atr_ratio
    trending = (ema_distance > ema_distance.rolling(20, min_periods=1).median()) & (ema_slope.abs() > cfg.trend_slope_threshold)
    chaotic = (directional_eff <= cfg.chaotic_efficiency_threshold) & high_vol
    compressed = compression <= cfg.compression_threshold

    regime.loc[low_vol | compressed] = "LOW_VOL"
    regime.loc[high_vol] = "HIGH_VOL"
    regime.loc[trending & ~high_vol] = "TRENDING"
    regime.loc[chaotic] = "CHAOTIC"
    regime.loc[(~trending) & (~high_vol) & (~low_vol) & (~chaotic)] = "RANGING"

    out["market_regime"] = regime.where(regime.isin(REGIMES), "RANGING")
    out["ema_slope"] = ema_slope
    out["directional_efficiency"] = directional_eff
    out["range_compression"] = compression

    min_regime_score = 0.20
    max_regime_score = 1.00
    regime_scores = pd.Series(min_regime_score, index=out.index, dtype=float)
    regime_scores.loc[regime == "TRENDING"] = max_regime_score
    regime_scores.loc[regime == "RANGING"] = 0.50
    regime_scores.loc[regime == "HIGH_VOL"] = 0.70
    regime_scores.loc[regime == "LOW_VOL"] = min_regime_score
    regime_scores.loc[regime == "CHAOTIC"] = 0.10
    out["regime_score"] = regime_scores
    return out


def classify_row(row: pd.Series, cfg: RegimeConfig | None = None) -> str:
    if cfg is None:
        cfg = RegimeConfig()

    atr_ratio = _safe_num(row.get("atr_ratio", 0.0))
    ema_slope = abs(_safe_num(row.get("ema_slope", 0.0)))
    directional_eff = _safe_num(row.get("directional_efficiency", 0.0))
    compression = _safe_num(row.get("range_compression", 1.0), default=1.0)

    if atr_ratio >= cfg.high_vol_atr_ratio and directional_eff <= cfg.chaotic_efficiency_threshold:
        return "CHAOTIC"
    if atr_ratio >= cfg.high_vol_atr_ratio:
        return "HIGH_VOL"
    if atr_ratio <= cfg.low_vol_atr_ratio or compression <= cfg.compression_threshold:
        return "LOW_VOL"
    if ema_slope > cfg.trend_slope_threshold:
        return "TRENDING"
    return "RANGING"
