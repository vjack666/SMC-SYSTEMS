from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules.stochastic_exhaustion.config import StochasticExhaustionConfig
from modules.stochastic_exhaustion.detector import detect_exhaustion


def backtest_exhaustion(
    data_dir: Path,
    symbol: str,
    timeframe: str = "M15",
    config: StochasticExhaustionConfig | None = None,
) -> dict[str, float | int]:
    if config is None:
        config = StochasticExhaustionConfig()

    path = data_dir / f"{symbol}_{timeframe}.parquet"
    frame = pd.read_parquet(path)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)

    from modules.indicators import add_atr
    frame["atr"] = add_atr(frame, 14)

    data = detect_exhaustion(frame, config)
    total = int(len(data))
    bull = int(data["exhaustion_bullish"].sum())
    bear = int(data["exhaustion_bearish"].sum())
    compressed = int(data["price_compressed"].sum())

    return {
        "total_bars": total,
        "bullish_exhaustion": bull,
        "bearish_exhaustion": bear,
        "price_compressed_bars": compressed,
        "exhaustion_share": (bull + bear) / max(total, 1),
    }
