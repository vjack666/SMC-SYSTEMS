from __future__ import annotations

import pandas as pd


def add_ema(frame: pd.DataFrame, span: int, source_col: str = "close") -> pd.Series:
    """Compute EMA series for a selected source column."""
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


def add_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()
