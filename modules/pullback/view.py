from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from modules.bos.detector import BosConfig, detect_bos
from modules.choch.detector import CHOCH_BEARISH, CHOCH_BULLISH, detect_choch
from modules.fvg.detector import detect_fvg
from modules.indicators import add_atr, add_ema, add_rsi
from modules.ob.detector import detect_order_blocks
from modules.trend.context_engine import build_trend_context_frame


def _load_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _last_anchor(series: pd.Series, condition: pd.Series) -> pd.Series:
    marker = pd.Series(np.nan, index=series.index, dtype=float)
    marker.loc[condition] = series.loc[condition].astype(float)
    return marker.ffill()


def _safe_atr_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def build_pullback_view(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    use_rsi: bool = True,
) -> pd.DataFrame:
    data = _load_frame(data_dir, symbol, timeframe)

    data = detect_bos(data, BosConfig(followthrough_bars=18))
    data = detect_choch(data)
    data = detect_fvg(data)
    data = detect_order_blocks(data)

    data["atr"] = add_atr(data, 14)
    data["ema_fast"] = add_ema(data, 20)
    data["ema_slow"] = add_ema(data, 50)
    data["rsi"] = add_rsi(data, 14)
    data["atr_ratio"] = data["atr"] / data["atr"].rolling(20, min_periods=1).mean().replace(0.0, np.nan)

    trend_ctx = build_trend_context_frame(symbol=symbol, ltf_frame=data, data_dir=data_dir)
    data = pd.merge_asof(data.sort_values("time"), trend_ctx.sort_values("time"), on="time", direction="backward")

    data["macro_direction"] = np.where(
        data["trend_score"] >= 30.0,
        "BULLISH",
        np.where(data["trend_score"] <= -30.0, "BEARISH", "RANGING"),
    )

    swing_high_ref = data["high"].rolling(20, min_periods=5).max().shift(1)
    swing_low_ref = data["low"].rolling(20, min_periods=5).min().shift(1)
    data["pullback_depth_up_atr"] = _safe_atr_div((swing_high_ref - data["close"]).clip(lower=0.0), data["atr"])
    data["pullback_depth_down_atr"] = _safe_atr_div((data["close"] - swing_low_ref).clip(lower=0.0), data["atr"])

    bullish_anchor = _last_anchor(data["close"], data["fvg_bullish"] | data["ob_bullish"])
    bearish_anchor = _last_anchor(data["close"], data["fvg_bearish"] | data["ob_bearish"])

    bull_anchor_dist = _safe_atr_div((data["close"] - bullish_anchor).abs(), data["atr"])
    bear_anchor_dist = _safe_atr_div((data["close"] - bearish_anchor).abs(), data["atr"])
    bull_anchor_near = bull_anchor_dist.fillna(99.0) <= 1.8
    bear_anchor_near = bear_anchor_dist.fillna(99.0) <= 1.8

    recent_bear_choch = (data["choch_signal"] == CHOCH_BEARISH).rolling(8, min_periods=1).max().astype(bool)
    recent_bull_choch = (data["choch_signal"] == CHOCH_BULLISH).rolling(8, min_periods=1).max().astype(bool)

    regime_ok = ~data["regime_state"].isin(["LOW_VOL", "CHAOTIC"])
    trend_ok = data["trend_confidence"].fillna(0.0) >= 0.35

    # Pullback is a counter-move inside directional context, not a reversal.
    if use_rsi:
        bull_rsi_ok = data["rsi"].between(32, 58)
        bear_rsi_ok = data["rsi"].between(42, 68)
    else:
        bull_rsi_ok = pd.Series(True, index=data.index)
        bear_rsi_ok = pd.Series(True, index=data.index)

    bull_pullback_zone = (
        (data["macro_direction"] == "BULLISH")
        & (data["close"] <= data["ema_fast"])
        & (data["close"] >= data["ema_slow"])
        & bull_rsi_ok
    )
    bear_pullback_zone = (
        (data["macro_direction"] == "BEARISH")
        & (data["close"] >= data["ema_fast"])
        & (data["close"] <= data["ema_slow"])
        & bear_rsi_ok
    )

    bull_invalid = recent_bear_choch | (data["bos_direction"] < 0)
    bear_invalid = recent_bull_choch | (data["bos_direction"] > 0)

    bull_valid = bull_pullback_zone & bull_anchor_near & regime_ok & trend_ok & (~bull_invalid)
    bear_valid = bear_pullback_zone & bear_anchor_near & regime_ok & trend_ok & (~bear_invalid)

    data["pullback_side"] = "NONE"
    data.loc[bull_pullback_zone, "pullback_side"] = "BULLISH"
    data.loc[bear_pullback_zone, "pullback_side"] = "BEARISH"

    data["pullback_state"] = "NO_PULLBACK"
    data.loc[bull_pullback_zone, "pullback_state"] = "BULLISH_PULLBACK_WIP"
    data.loc[bear_pullback_zone, "pullback_state"] = "BEARISH_PULLBACK_WIP"
    data.loc[bull_valid, "pullback_state"] = "BULLISH_PULLBACK_VALID"
    data.loc[bear_valid, "pullback_state"] = "BEARISH_PULLBACK_VALID"
    data.loc[bull_pullback_zone & bull_invalid, "pullback_state"] = "BULLISH_PULLBACK_INVALID"
    data.loc[bear_pullback_zone & bear_invalid, "pullback_state"] = "BEARISH_PULLBACK_INVALID"

    depth_quality_bull = (1.0 - (data["pullback_depth_up_atr"].fillna(2.5) / 2.5)).clip(lower=0.0, upper=1.0)
    depth_quality_bear = (1.0 - (data["pullback_depth_down_atr"].fillna(2.5) / 2.5)).clip(lower=0.0, upper=1.0)
    depth_quality = np.where(data["pullback_side"] == "BULLISH", depth_quality_bull, depth_quality_bear)

    anchor_quality = np.where(data["pullback_side"] == "BULLISH", 1.0 - (bull_anchor_dist / 2.0), 1.0 - (bear_anchor_dist / 2.0))
    anchor_quality = pd.Series(anchor_quality, index=data.index).clip(lower=0.0, upper=1.0).fillna(0.0)

    score = (
        0.45 * data["trend_confidence"].fillna(0.0)
        + 0.30 * pd.Series(depth_quality, index=data.index).fillna(0.0)
        + 0.25 * anchor_quality
    )
    data["pullback_score"] = (score * 100.0).clip(lower=0.0, upper=100.0)
    data["pullback_ready"] = data["pullback_state"].isin(["BULLISH_PULLBACK_VALID", "BEARISH_PULLBACK_VALID"])

    return data


def summarize_pullback_view(view: pd.DataFrame) -> dict[str, int | float]:
    total = int(len(view))
    valid = int(view["pullback_ready"].sum()) if "pullback_ready" in view.columns else 0
    bullish = int((view.get("pullback_state", "") == "BULLISH_PULLBACK_VALID").sum())
    bearish = int((view.get("pullback_state", "") == "BEARISH_PULLBACK_VALID").sum())
    invalid = int(view.get("pullback_state", pd.Series([], dtype=object)).isin(["BULLISH_PULLBACK_INVALID", "BEARISH_PULLBACK_INVALID"]).sum())

    avg_score = float(pd.to_numeric(view.get("pullback_score", 0.0), errors="coerce").fillna(0.0).mean()) if total > 0 else 0.0
    valid_rate = float(valid / total) if total > 0 else 0.0

    return {
        "total_bars": total,
        "valid_pullbacks": valid,
        "bullish_valid_pullbacks": bullish,
        "bearish_valid_pullbacks": bearish,
        "invalid_pullbacks": invalid,
        "valid_rate": valid_rate,
        "avg_pullback_score": avg_score,
    }
