from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def apply_time_window(frame: pd.DataFrame, start_time: str | None, end_time: str | None) -> pd.DataFrame:
    data = frame.copy()
    if start_time is not None:
        data = data[data["time"] >= pd.to_datetime(start_time, utc=True)]
    if end_time is not None:
        data = data[data["time"] <= pd.to_datetime(end_time, utc=True)]
    return data.reset_index(drop=True)
