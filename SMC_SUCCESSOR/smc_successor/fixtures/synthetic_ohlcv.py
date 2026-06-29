from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(
    n_bars: int = 200,
    seed: int = 42,
    start_price: float = 1.1000,
    vol: float = 0.001,
    trend: float = 0.0001,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = np.zeros(n_bars, dtype=float)
    closes[0] = start_price
    for i in range(1, n_bars):
        closes[i] = closes[i - 1] + trend + rng.normal(0.0, vol)

    closes = np.maximum(closes, start_price * 0.90)

    highs = closes + abs(rng.normal(0.0, vol * 2.0, size=n_bars))
    lows = closes - abs(rng.normal(0.0, vol * 2.0, size=n_bars))
    opens = np.zeros(n_bars, dtype=float)
    opens[0] = closes[0]
    for i in range(1, n_bars):
        opens[i] = closes[i - 1] + rng.normal(0.0, vol * 0.5)

    times = pd.date_range("2024-01-01", periods=n_bars, freq="15min", tz="UTC")
    volume = rng.integers(100, 10000, size=n_bars)

    return pd.DataFrame({
        "time": times,
        "open": opens,
        "high": np.maximum(highs, opens),
        "low": np.minimum(lows, opens),
        "close": closes,
        "tick_volume": volume,
    })
