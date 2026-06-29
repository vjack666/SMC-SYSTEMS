from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from smc_successor.data import load_frame
from smc_successor.indicators import add_atr, add_ema
from smc_successor.regime import detect_regimes


def _clip(series: pd.Series, low: float = -1.0, high: float = 1.0) -> pd.Series:
    return series.astype(float).clip(lower=low, upper=high)


def _to_bias(score: pd.Series, threshold: float = 0.20) -> pd.Series:
    return pd.Series(
        np.where(
            score > threshold,
            "BULLISH",
            np.where(score < -threshold, "BEARISH", "RANGING"),
        ),
        index=score.index,
        dtype=object,
    )


def _build_tf_state(frame: pd.DataFrame, slope_bars: int, structure_bars: int) -> pd.DataFrame:
    data = frame[["time", "open", "high", "low", "close", "tick_volume"]].copy().reset_index(drop=True)
    data["atr"] = add_atr(data, 14)
    data["ema_fast"] = add_ema(data, 20)
    data["ema_slow"] = add_ema(data, 50)

    atr_safe = data["atr"].replace(0.0, np.nan)
    data["atr_ratio"] = data["atr"] / data["atr"].rolling(20, min_periods=1).mean().replace(0.0, np.nan)

    ema_alignment = _clip((data["ema_fast"] - data["ema_slow"]) / atr_safe)
    slope_norm = _clip((data["ema_fast"] - data["ema_fast"].shift(slope_bars)) / (atr_safe * float(slope_bars)))

    hh = (data["high"] > data["high"].rolling(structure_bars, min_periods=1).max().shift(1)).astype(float)
    ll = (data["low"] < data["low"].rolling(structure_bars, min_periods=1).min().shift(1)).astype(float)
    hl = (data["low"] > data["low"].shift(1)).astype(float)
    lh = (data["high"] < data["high"].shift(1)).astype(float)

    bull_structure = (hh + hl).rolling(4, min_periods=1).mean()
    bear_structure = (ll + lh).rolling(4, min_periods=1).mean()
    structure_score = _clip((bull_structure - bear_structure) / 2.0)

    vol_raw = data["atr_ratio"].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    vol_filter = vol_raw.between(0.75, 1.90)

    direction_raw = _clip(0.45 * ema_alignment + 0.35 * slope_norm + 0.20 * structure_score)
    strength = (direction_raw.abs() * 100.0 * np.minimum(1.25, np.maximum(0.50, vol_raw))).clip(lower=0.0, upper=100.0)

    return pd.DataFrame(
        {
            "time": data["time"],
            "bias": _to_bias(direction_raw),
            "direction_score": direction_raw,
            "trend_strength": strength.fillna(0.0),
            "slope_norm": slope_norm.fillna(0.0),
            "ema_alignment": ema_alignment.fillna(0.0),
            "structure_score": structure_score.fillna(0.0),
            "vol_filter": vol_filter.fillna(False),
            "atr_ratio": vol_raw.fillna(1.0),
            "ema_fast": data["ema_fast"].ffill().fillna(data["close"]),
            "ema_slow": data["ema_slow"].ffill().fillna(data["close"]),
            "atr": data["atr"].ffill().fillna(0.0),
        }
    )


def build_trend_context_frame(
    symbol: str,
    ltf_frame: pd.DataFrame,
    data_dir: Path = Path("data/mt5"),
) -> pd.DataFrame:
    d1 = load_frame(data_dir, symbol, "D1")
    h4 = load_frame(data_dir, symbol, "H4")

    d1_state = _build_tf_state(d1, slope_bars=4, structure_bars=8).rename(
        columns={
            "bias": "d1_trend",
            "direction_score": "d1_score",
            "trend_strength": "d1_strength",
            "slope_norm": "d1_slope_norm",
            "ema_alignment": "d1_ema_alignment",
            "structure_score": "d1_structure_score",
            "vol_filter": "d1_vol_filter",
        }
    )
    h4_state = _build_tf_state(h4, slope_bars=8, structure_bars=10).rename(
        columns={
            "bias": "h4_trend",
            "direction_score": "h4_score",
            "trend_strength": "h4_strength",
            "slope_norm": "h4_slope_norm",
            "ema_alignment": "h4_ema_alignment",
            "structure_score": "h4_structure_score",
            "vol_filter": "h4_vol_filter",
        }
    )

    ltf = _build_tf_state(ltf_frame, slope_bars=6, structure_bars=12)
    atr_safe = ltf["atr"].replace(0.0, np.nan)
    momentum = _clip((ltf_frame["close"] - ltf_frame["close"].shift(3)) / (atr_safe * 3.0))
    acceleration = _clip(momentum.diff(3).fillna(0.0))

    higher_high = (ltf_frame["high"] > ltf_frame["high"].shift(1)).astype(float)
    higher_low = (ltf_frame["low"] > ltf_frame["low"].shift(1)).astype(float)
    lower_high = (ltf_frame["high"] < ltf_frame["high"].shift(1)).astype(float)
    lower_low = (ltf_frame["low"] < ltf_frame["low"].shift(1)).astype(float)
    micro_bull = (higher_high + higher_low).rolling(4, min_periods=1).mean()
    micro_bear = (lower_high + lower_low).rolling(4, min_periods=1).mean()
    micro_structure = _clip((micro_bull - micro_bear) / 2.0)

    dist_to_slow = ((ltf_frame["close"] - ltf["ema_slow"]).abs() / atr_safe).replace([np.inf, -np.inf], np.nan)
    pullback_quality = _clip(1.0 - (dist_to_slow / 2.5).fillna(1.0), low=0.0, high=1.0)

    ltf_score = _clip(
        0.40 * ltf["direction_score"]
        + 0.25 * momentum.fillna(0.0)
        + 0.10 * acceleration.fillna(0.0)
        + 0.15 * micro_structure.fillna(0.0)
        + 0.10 * (pullback_quality * np.sign(ltf["direction_score"]).fillna(0.0))
    )

    base = pd.DataFrame({"time": pd.to_datetime(ltf_frame["time"], utc=True)})
    base = pd.merge_asof(base.sort_values("time"), d1_state.sort_values("time"), on="time", direction="backward")
    base = pd.merge_asof(base.sort_values("time"), h4_state.sort_values("time"), on="time", direction="backward")

    htf_score = _clip((base["d1_score"].fillna(0.0) * 0.60) + (base["h4_score"].fillna(0.0) * 0.40))
    htf_strength = ((base["d1_strength"].fillna(0.0) * 0.60) + (base["h4_strength"].fillna(0.0) * 0.40)).clip(0.0, 100.0)
    htf_bias = _to_bias(htf_score)

    ltf_bias = _to_bias(ltf_score)
    trend_alignment = pd.Series(
        np.where(
            (htf_bias == ltf_bias) & htf_bias.isin(["BULLISH", "BEARISH"]),
            "ALIGNED",
            np.where(
                htf_bias.isin(["BULLISH", "BEARISH"]) & ltf_bias.isin(["BULLISH", "BEARISH"]),
                "DIVERGENT",
                "NEUTRAL",
            ),
        ),
        index=base.index,
        dtype=object,
    )
    alignment_score = pd.Series(
        np.where(
            trend_alignment == "ALIGNED",
            np.sign(htf_score) * 1.0,
            np.where(trend_alignment == "DIVERGENT", -np.sign(htf_score), 0.0),
        ),
        index=base.index,
        dtype=float,
    )

    regime_input = ltf_frame[["time", "open", "high", "low", "close"]].copy()
    regime_input["atr"] = ltf["atr"].fillna(0.0)
    regime_input["atr_ratio"] = ltf["atr_ratio"].fillna(1.0)
    regime_input["ema_fast"] = ltf["ema_fast"].fillna(ltf_frame["close"])
    regime_input["ema_slow"] = ltf["ema_slow"].fillna(ltf_frame["close"])
    regime = detect_regimes(regime_input)
    regime_state = regime["market_regime"].astype(str).fillna("RANGING")
    regime_multiplier = regime_state.map(
        {
            "TRENDING": 1.00,
            "HIGH_VOL": 0.90,
            "RANGING": 0.65,
            "LOW_VOL": 0.50,
            "CHAOTIC": 0.40,
        }
    ).fillna(0.65)

    trend_strength = (0.55 * htf_strength + 0.45 * (ltf_score.abs() * 100.0)).clip(0.0, 100.0)
    trend_score = (
        (0.55 * htf_score + 0.35 * ltf_score + 0.10 * alignment_score)
        * regime_multiplier
        * 100.0
    ).clip(-100.0, 100.0)

    trend_confidence = (trend_strength / 100.0).clip(0.0, 1.0)
    trend_agreement = (trend_alignment == "ALIGNED")

    return pd.DataFrame(
        {
            "time": base["time"],
            "d1_trend": base["d1_trend"].fillna("RANGING"),
            "h4_trend": base["h4_trend"].fillna("RANGING"),
            "d1_conf": (base["d1_strength"].fillna(0.0) / 100.0).clip(0.0, 1.0),
            "h4_conf": (base["h4_strength"].fillna(0.0) / 100.0).clip(0.0, 1.0),
            "htf_bias": htf_bias,
            "ltf_bias": ltf_bias,
            "trend_strength": trend_strength,
            "trend_alignment": trend_alignment,
            "regime_state": regime_state,
            "trend_score": trend_score,
            "trend_agreement": trend_agreement,
            "trend_confidence": trend_confidence,
            "macro_trend": htf_bias,
        }
    )
