from __future__ import annotations

import numpy as np
import pandas as pd


def add_ema(frame: pd.DataFrame, span: int, source_col: str = "close") -> pd.Series:
    if source_col not in frame.columns:
        raise ValueError(f"Column not found: {source_col}")
    return frame[source_col].ewm(span=span, adjust=False).mean()


def add_rsi(frame: pd.DataFrame, period: int = 14, source_col: str = "close") -> pd.Series:
    if source_col not in frame.columns:
        raise ValueError(f"Column not found: {source_col}")
    delta = frame[source_col].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0.0, pd.NA)
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def add_stochastic(
    frame: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    smooth_k: int = 3,
) -> pd.DataFrame:
    low_min = frame["low"].rolling(k_period).min()
    high_max = frame["high"].rolling(k_period).max()
    denom = (high_max - low_min).replace(0.0, pd.NA)
    raw_k = 100.0 * (frame["close"] - low_min) / denom
    stoch_k = raw_k.rolling(smooth_k).mean()
    stoch_d = stoch_k.rolling(d_period).mean()
    return pd.DataFrame({"stoch_k": stoch_k, "stoch_d": stoch_d, "stoch_k_raw": raw_k})


def add_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_order_blocks(
    frame: pd.DataFrame,
    lookback: int = 5,
    min_strength: int = 2,
) -> pd.DataFrame:
    if len(frame) < 4:
        return pd.DataFrame(columns=["ob_type", "ob_high", "ob_low", "ob_price", "ob_index"])

    atr = add_atr(frame)
    closes = frame["close"].to_numpy()
    highs = frame["high"].to_numpy()
    lows = frame["low"].to_numpy()
    opens_ = frame["open"].to_numpy()
    bullish = closes > opens_

    results: list[dict] = []

    i = 0
    while i < len(frame):
        if i + 2 >= len(frame):
            break

        if all(bullish[i : i + 3]):
            seq_start = i
            seq_end = i + 2
            while seq_end + 1 < len(frame) and bullish[seq_end + 1]:
                seq_end += 1

            total_move = closes[seq_end] - closes[seq_start]

            ob_idx: int | None = None
            for j in range(seq_start - 1, max(-1, seq_start - lookback - 1), -1):
                if j >= 0 and not bullish[j]:
                    ob_idx = j
                    break

            if ob_idx is not None:
                a = atr.iloc[seq_end]
                threshold = min_strength * (a if not pd.isna(a) else (highs[seq_end] - lows[seq_end]))
                if total_move > threshold:
                    results.append({
                        "ob_type": "bullish",
                        "ob_high": highs[ob_idx],
                        "ob_low": lows[ob_idx],
                        "ob_price": closes[ob_idx],
                        "ob_index": ob_idx,
                    })
            i = seq_end + 1

        elif all(~bullish[i : i + 3]):
            seq_start = i
            seq_end = i + 2
            while seq_end + 1 < len(frame) and not bullish[seq_end + 1]:
                seq_end += 1

            total_move = closes[seq_start] - closes[seq_end]

            ob_idx = None
            for j in range(seq_start - 1, max(-1, seq_start - lookback - 1), -1):
                if j >= 0 and bullish[j]:
                    ob_idx = j
                    break

            if ob_idx is not None:
                a = atr.iloc[seq_end]
                threshold = min_strength * (a if not pd.isna(a) else (highs[seq_end] - lows[seq_end]))
                if total_move > threshold:
                    results.append({
                        "ob_type": "bearish",
                        "ob_high": highs[ob_idx],
                        "ob_low": lows[ob_idx],
                        "ob_price": closes[ob_idx],
                        "ob_index": ob_idx,
                    })
            i = seq_end + 1

        else:
            i += 1

    return pd.DataFrame(results)


def add_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    if len(frame) < 3:
        return pd.DataFrame(columns=["fvg_type", "fvg_top", "fvg_bottom", "fvg_midpoint", "fvg_filled", "fvg_index"])

    highs = frame["high"].to_numpy()
    lows = frame["low"].to_numpy()

    results: list[dict] = []

    for i in range(len(frame) - 2):
        if highs[i] < lows[i + 2]:
            bottom = highs[i]
            top = lows[i + 2]
            midpoint = (top + bottom) / 2.0
            filled = False
            for j in range(i + 3, len(frame)):
                if lows[j] <= top and highs[j] >= bottom:
                    filled = True
                    break
            results.append({
                "fvg_type": "bullish",
                "fvg_top": top,
                "fvg_bottom": bottom,
                "fvg_midpoint": midpoint,
                "fvg_filled": filled,
                "fvg_index": i,
            })

        if lows[i] > highs[i + 2]:
            bottom = highs[i + 2]
            top = lows[i]
            midpoint = (top + bottom) / 2.0
            filled = False
            for j in range(i + 3, len(frame)):
                if highs[j] >= bottom and lows[j] <= top:
                    filled = True
                    break
            results.append({
                "fvg_type": "bearish",
                "fvg_top": top,
                "fvg_bottom": bottom,
                "fvg_midpoint": midpoint,
                "fvg_filled": filled,
                "fvg_index": i,
            })

    return pd.DataFrame(results)
