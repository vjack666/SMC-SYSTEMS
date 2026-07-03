from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smc_successor._data_legacy import load_frame
from smc_successor.detectors.displacement import detect_displacement, DisplacementConfig
from smc_successor.detectors.zones import compute_zones, ZoneConfig
from smc_successor.indicators import add_atr
from smc_successor.regime import detect_regimes, RegimeConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SWING_LOOKBACK = 5
ATR_PERIOD = 14
INDUCEMENT_LOOKBACK = 8
STRENGTH_ATR_CAP = 3.0
EMA_FAST_SPAN = 20
EMA_SLOW_SPAN = 50
ZONE_SWING_LOOKBACK = 20


# ---------------------------------------------------------------------------
# Swing Detection (same rolling-window pattern as bos.py)
# ---------------------------------------------------------------------------

def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    window = lookback * 2 + 1
    rolling_high = frame["high"].rolling(window=window, center=True)
    rolling_low = frame["low"].rolling(window=window, center=True)
    swing_high = frame["high"].where(frame["high"] == rolling_high.max())
    swing_low = frame["low"].where(frame["low"] == rolling_low.min())
    return swing_high.ffill(), swing_low.ffill()


def _swing_high_indices(swing_high: pd.Series) -> np.ndarray:
    return np.where(swing_high.notna() & (swing_high != swing_high.shift(1)))[0]


def _swing_low_indices(swing_low: pd.Series) -> np.ndarray:
    return np.where(swing_low.notna() & (swing_low != swing_low.shift(1)))[0]


# ---------------------------------------------------------------------------
# Liquidity Sweep Detection
# ---------------------------------------------------------------------------

def _detect_liquidity_sweeps(
    frame: pd.DataFrame, swing_high: pd.Series, swing_low: pd.Series, atr: pd.Series,
) -> pd.DataFrame:
    """Detect liquidity sweeps at swing-point level.

    A liquidity sweep occurs when price briefly exceeds a prior swing high/low
    and then closes back inside (failed breakout = liquidity grab).
    Returns a DataFrame with sweep flags + strength at each bar.
    """
    high_idx = _swing_high_indices(swing_high)
    low_idx = _swing_low_indices(swing_low)

    results: list[dict[str, Any]] = []
    for i in range(len(frame)):
        sweep_detected = False
        sweep_type: str | None = None
        sweep_strength = 0.0

        # --- Bearish sweep: price breaks above a prior swing high then closes below it ---
        recent_highs = high_idx[high_idx < i]
        if len(recent_highs) > 0:
            last_high_idx = recent_highs[-1]
            swing_level = float(swing_high.iloc[last_high_idx])
            bar_high = float(frame["high"].iloc[i])
            bar_close = float(frame["close"].iloc[i])
            atr_val = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else 0.0

            if bar_high > swing_level and bar_close < swing_level:
                sweep_detected = True
                sweep_type = "bearish"
                if atr_val > 0.0:
                    raw = (bar_high - swing_level) / atr_val
                    sweep_strength = min(raw / STRENGTH_ATR_CAP, 1.0)

        # --- Bullish sweep: price breaks below a prior swing low then closes above it ---
        if not sweep_detected:
            recent_lows = low_idx[low_idx < i]
            if len(recent_lows) > 0:
                last_low_idx = recent_lows[-1]
                swing_level = float(swing_low.iloc[last_low_idx])
                bar_low = float(frame["low"].iloc[i])
                bar_close = float(frame["close"].iloc[i])
                atr_val = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else 0.0

                if bar_low < swing_level and bar_close > swing_level:
                    sweep_detected = True
                    sweep_type = "bullish"
                    if atr_val > 0.0:
                        raw = (swing_level - bar_low) / atr_val
                        sweep_strength = min(raw / STRENGTH_ATR_CAP, 1.0)

        results.append({
            "liquidity_sweep_detected": sweep_detected,
            "sweep_type": sweep_type,
            "sweep_strength": round(sweep_strength, 4),
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Inducement Detection
# ---------------------------------------------------------------------------

def _detect_inducements(
    frame: pd.DataFrame, swing_high: pd.Series, swing_low: pd.Series, atr: pd.Series,
) -> pd.DataFrame:
    """Detect inducements (false breakouts).

    An inducement is a price move that temporarily breaks a swing level but
    reverses sharply, suggesting price was 'induced' to chase a false signal.
    Key criteria:
      1. Price must break a confirmed swing high/low.
      2. Close must be back on the original side of the swing level (failed breakout).
      3. The rejection wick must be > 0.3x ATR (significant rejection).
    """
    high_idx = _swing_high_indices(swing_high)
    low_idx = _swing_low_indices(swing_low)
    MIN_REJECTION_ATR = 0.3

    # --- First pass: detect only at the exact bar where the false breakout occurs ---
    results: list[dict[str, Any]] = []
    for i in range(len(frame)):
        inducement_detected = False
        inducement_type: str | None = None
        inducement_probability = 0.0
        atr_val = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else 0.0

        # Short inducement: false breakout above swing high
        recent_highs = high_idx[high_idx < i]
        if len(recent_highs) > 0:
            last_high_idx = recent_highs[-1]
            swing_level = float(swing_high.iloc[last_high_idx])
            bar_high = float(frame["high"].iloc[i])
            bar_close = float(frame["close"].iloc[i])
            bar_range = bar_high - float(frame["low"].iloc[i])
            upper_wick = bar_high - max(bar_close, float(frame["open"].iloc[i]))

            if bar_high > swing_level and bar_close < swing_level and upper_wick > MIN_REJECTION_ATR * atr_val and bar_range > 0:
                inducement_detected = True
                inducement_type = "short"
                reject_ratio = upper_wick / bar_range
                inducement_probability = min(max(reject_ratio * 1.5, 0.0), 1.0)

        # Long inducement: false breakout below swing low
        if not inducement_detected:
            recent_lows = low_idx[low_idx < i]
            if len(recent_lows) > 0:
                last_low_idx = recent_lows[-1]
                swing_level = float(swing_low.iloc[last_low_idx])
                bar_low = float(frame["low"].iloc[i])
                bar_close = float(frame["close"].iloc[i])
                bar_range = float(frame["high"].iloc[i]) - bar_low
                lower_wick = min(bar_close, float(frame["open"].iloc[i])) - bar_low

                if bar_low < swing_level and bar_close > swing_level and lower_wick > MIN_REJECTION_ATR * atr_val and bar_range > 0:
                    inducement_detected = True
                    inducement_type = "long"
                    reject_ratio = lower_wick / bar_range
                    inducement_probability = min(max(reject_ratio * 1.5, 0.0), 1.0)

        results.append({
            "inducement_detected": inducement_detected,
            "inducement_type": inducement_type,
            "inducement_probability": round(inducement_probability, 4),
        })

    # --- Second pass: propagate real inducements for INDUCEMENT_LOOKBACK bars ---
    original_indices = [i for i, r in enumerate(results) if r["inducement_detected"]]
    for orig_idx in original_indices:
        orig_type = results[orig_idx]["inducement_type"]
        orig_prob = results[orig_idx]["inducement_probability"]
        for offset in range(1, INDUCEMENT_LOOKBACK + 1):
            target = orig_idx + offset
            if target >= len(results):
                break
            if not results[target]["inducement_detected"]:
                results[target]["inducement_detected"] = True
                results[target]["inducement_type"] = orig_type
                results[target]["inducement_probability"] = round(orig_prob * (1.0 - offset / (INDUCEMENT_LOOKBACK + 1)), 4)

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Aggregation Helpers
# ---------------------------------------------------------------------------

def _aggregate_column(col: pd.Series) -> dict[str, Any]:
    if col.dtype == bool or col.dropna().dtype == bool:
        true_count = int(col.sum())
        return {"count": true_count, "pct": round(float(col.mean()), 4) if len(col) > 0 else 0.0}
    numeric = pd.to_numeric(col, errors="coerce").dropna()
    if len(numeric) == 0:
        return {"mean": 0.0, "max": 0.0, "last": 0.0}
    return {
        "mean": round(float(numeric.mean()), 4),
        "max": round(float(numeric.max()), 4),
        "last": round(float(numeric.iloc[-1]), 4),
    }


def _last_non_null(series: pd.Series, col: str, default: Any = None) -> Any:
    non_null = series[series[col].notna() & (series[col] != "NONE")]
    if len(non_null) == 0:
        return default
    return non_null[col].iloc[-1]


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class FeatureEnrichmentAdapter:
    name = "feature_enrichment"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        symbol = str(parameters.get("symbol", "EURUSD"))
        timeframe = str(parameters.get("timeframe", "M15"))
        data_dir = Path(str(parameters.get("data_dir", "data/raw")))

        try:
            frame = load_frame(data_dir, symbol, timeframe)
        except FileNotFoundError as exc:
            return {
                "module": self.name,
                "event_names": [],
                "status": "error",
                "symbol": symbol,
                "error": str(exc),
            }

        total_bars = int(len(frame))

        # --- Compute ATR ---
        atr = add_atr(frame, period=ATR_PERIOD)

        # --- Detect swing points (same pattern as bos.py) ---
        swing_high, swing_low = _swing_points(frame, SWING_LOOKBACK)

        # --- Liquidity Sweeps ---
        sweep_df = _detect_liquidity_sweeps(frame, swing_high, swing_low, atr)
        sweep_detected = bool(sweep_df["liquidity_sweep_detected"].any())
        last_sweep = _last_non_null(sweep_df, "sweep_type")
        recent_sweep_count = int(sweep_df.tail(INDUCEMENT_LOOKBACK)["liquidity_sweep_detected"].sum())
        sweep_strength_mean = float(
            sweep_df.loc[sweep_df["liquidity_sweep_detected"], "sweep_strength"].mean()
        ) if sweep_detected else 0.0

        # --- Inducements ---
        induce_df = _detect_inducements(frame, swing_high, swing_low, atr)
        induce_detected = bool(induce_df["inducement_detected"].any())
        last_induce = _last_non_null(induce_df, "inducement_type")
        recent_induce_count = int(induce_df.tail(INDUCEMENT_LOOKBACK)["inducement_detected"].sum())
        induce_prob_mean = float(
            induce_df.loc[induce_df["inducement_detected"], "inducement_probability"].mean()
        ) if induce_detected else 0.0

        # --- Displacement (strong impulsive bars) ---
        disp_frame = detect_displacement(frame, DisplacementConfig())
        disp_bullish = bool(disp_frame["displacement_bullish"].any())
        disp_bearish = bool(disp_frame["displacement_bearish"].any())
        disp_magnitude_mean = float(disp_frame.loc[
            disp_frame["displacement_bullish"] | disp_frame["displacement_bearish"],
            "displacement_magnitude"
        ].mean()) if (disp_bullish or disp_bearish) else 0.0
        recent_disp_bullish = int(disp_frame.tail(INDUCEMENT_LOOKBACK)["displacement_bullish"].sum())
        recent_disp_bearish = int(disp_frame.tail(INDUCEMENT_LOOKBACK)["displacement_bearish"].sum())

        # --- Premium / Discount Arrays (OTE zones) ---
        zones_frame = compute_zones(frame, ZoneConfig(swing_lookback=ZONE_SWING_LOOKBACK))
        last_zone_type = str(zones_frame["premium_discount_zone"].iloc[-1])
        last_premium_distance = float(zones_frame["premium_distance"].iloc[-1])
        zone_distribution = zones_frame["premium_discount_zone"].value_counts().to_dict()
        zone_distribution = {str(k): int(v) for k, v in zone_distribution.items()}

        # --- Regime Labels (market state classification) ---
        frame_with_indicators = frame.copy()
        atr_sma_20 = atr.rolling(20).mean().replace(0.0, np.nan)
        frame_with_indicators["atr_ratio"] = (atr / atr_sma_20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        frame_with_indicators["ema_fast"] = frame_with_indicators["close"].ewm(span=EMA_FAST_SPAN).mean()
        frame_with_indicators["ema_slow"] = frame_with_indicators["close"].ewm(span=EMA_SLOW_SPAN).mean()
        frame_with_indicators["atr"] = atr
        regime_frame = detect_regimes(frame_with_indicators, RegimeConfig())
        regime_list = regime_frame["market_regime"].tolist()
        regime_distribution = regime_frame["market_regime"].value_counts().to_dict()
        regime_distribution = {str(k): int(v) for k, v in regime_distribution.items()}
        current_regime = str(regime_list[-1]) if regime_list else "NONE"
        regime_recent = regime_list[-INDUCEMENT_LOOKBACK:] if len(regime_list) >= INDUCEMENT_LOOKBACK else regime_list
        dominant_recent_regime = max(set(regime_recent), key=regime_recent.count) if regime_recent else "NONE"

        # --- Interaction Features ---
        both_same = (sweep_df["liquidity_sweep_detected"] & induce_df["inducement_detected"])
        co_occurrence_count = int(both_same.sum())
        co_occurrence_pct = round(float(both_same.mean()), 4) if total_bars > 0 else 0.0
        last_both = bool(both_same.iloc[-1])

        return {
            "module": self.name,
            "event_names": [],
            "status": "ok",
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": total_bars,
            "features": {
                # --- F14: Liquidity Sweeps ---
                "liquidity_sweeps": {
                    "implementation": "active",
                    "sweep_detected": sweep_detected,
                    "last_sweep_type": last_sweep,
                    "sweep_strength_mean": round(sweep_strength_mean, 4),
                    "recent_sweep_count_8_bars": recent_sweep_count,
                    "sweep_bars_analyzed": total_bars,
                    "aggregate": _aggregate_column(sweep_df["liquidity_sweep_detected"]),
                    "strength_distribution": _aggregate_column(
                        sweep_df["sweep_strength"].where(sweep_df["liquidity_sweep_detected"])
                    ),
                },
                # --- F14: Inducements ---
                "inducements": {
                    "implementation": "active",
                    "inducement_detected": induce_detected,
                    "last_inducement_type": last_induce,
                    "inducement_probability_mean": round(induce_prob_mean, 4),
                    "recent_inducement_count_8_bars": recent_induce_count,
                    "inducement_bars_analyzed": total_bars,
                    "aggregate": _aggregate_column(induce_df["inducement_detected"]),
                    "probability_distribution": _aggregate_column(
                        induce_df["inducement_probability"].where(induce_df["inducement_detected"])
                    ),
                },
                # --- F14: Displacement (strong impulsive bars) ---
                "displacement": {
                    "implementation": "active",
                    "displacement_detected": bool(disp_bullish or disp_bearish),
                    "displacement_bullish": disp_bullish,
                    "displacement_bearish": disp_bearish,
                    "displacement_magnitude_mean": round(disp_magnitude_mean, 4),
                    "recent_bullish_count_8_bars": recent_disp_bullish,
                    "recent_bearish_count_8_bars": recent_disp_bearish,
                    "last_magnitude": round(float(disp_frame["displacement_magnitude"].iloc[-1]), 4),
                    "aggregate_bullish": _aggregate_column(disp_frame["displacement_bullish"]),
                    "aggregate_bearish": _aggregate_column(disp_frame["displacement_bearish"]),
                },
                # --- F14: Premium / Discount Arrays ---
                "premium_discount_arrays": {
                    "implementation": "active",
                    "current_zone_type": last_zone_type,
                    "current_premium_distance": round(last_premium_distance, 4),
                    "zone_distribution": zone_distribution,
                    "bars_analyzed": total_bars,
                },
                # --- F14: Regime Labels ---
                "regime_labels": {
                    "implementation": "active",
                    "current_regime": current_regime,
                    "dominant_recent_regime_8_bars": dominant_recent_regime,
                    "distribution": regime_distribution,
                    "bars_analyzed": total_bars,
                },
                # --- F14: Interaction Features ---
                "interaction_features": {
                    "implementation": "active",
                    "sweep_x_inducement_co_occurrence_count": co_occurrence_count,
                    "sweep_x_inducement_co_occurrence_pct": co_occurrence_pct,
                    "sweep_x_inducement_last_bar": last_both,
                },
            },
        }
