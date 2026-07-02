from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smc_successor._data_legacy import load_frame
from smc_successor.indicators import add_atr

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SWING_LOOKBACK = 5
ATR_PERIOD = 14
INDUCEMENT_LOOKBACK = 8
STRENGTH_ATR_CAP = 3.0


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
        recent_sweeps = sweep_df.tail(INDUCEMENT_LOOKBACK)
        recent_sweep_count = int(recent_sweeps["liquidity_sweep_detected"].sum())

        sweep_strength_mean = float(
            sweep_df.loc[sweep_df["liquidity_sweep_detected"], "sweep_strength"].mean()
        ) if sweep_detected else 0.0

        # --- Inducements ---
        induce_df = _detect_inducements(frame, swing_high, swing_low, atr)
        induce_detected = bool(induce_df["inducement_detected"].any())
        last_induce = _last_non_null(induce_df, "inducement_type")
        recent_induce = induce_df.tail(INDUCEMENT_LOOKBACK)
        recent_induce_count = int(recent_induce["inducement_detected"].sum())

        induce_prob_mean = float(
            induce_df.loc[induce_df["inducement_detected"], "inducement_probability"].mean()
        ) if induce_detected else 0.0

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
                # TODO F14: displacement — pending implementation
                "displacement": {
                    "implementation": "not_implemented",
                    "proposed": [
                        "displacement_magnitude",
                        "displacement_bullish",
                        "displacement_bearish",
                        "displacement_continuation",
                    ],
                },
                # TODO F14: premium / discount arrays — pending implementation
                "premium_discount_arrays": {
                    "implementation": "not_implemented",
                    "proposed": [
                        "premium_array_zones",
                        "discount_array_zones",
                        "current_zone_type",
                        "distance_to_nearest_pd_boundary",
                    ],
                },
                # TODO F14: regime labels — pending implementation
                "regime_labels": {
                    "implementation": "not_implemented",
                    "proposed": [
                        "regime_trending_bullish",
                        "regime_trending_bearish",
                        "regime_ranging",
                        "regime_high_volatility",
                        "regime_low_volatility",
                        "regime_chaotic",
                    ],
                },
                # TODO F14: interaction features — pending implementation
                "interaction_features": {
                    "implementation": "not_implemented",
                    "proposed": [
                        "fvg_size_x_bos_strength",
                        "ob_distance_x_trend_confidence",
                        "displacement_x_volume",
                        "sweep_x_inducement",
                    ],
                },
            },
        }
