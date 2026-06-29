from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd


@dataclass(frozen=True)
class MarketDataRequest:
    symbol: str
    timeframe: str


def _validate_columns(frame: pd.DataFrame, file_path: Path) -> None:
    required = {"time", "open", "high", "low", "close", "tick_volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing columns in {file_path.name}: {missing}")


def load_parquet(base_dir: Path, request: MarketDataRequest) -> pd.DataFrame:
    file_path = base_dir / f"{request.symbol}_{request.timeframe}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    frame = pd.read_parquet(file_path).copy()
    _validate_columns(frame, file_path)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)
    frame["symbol"] = request.symbol
    frame["timeframe"] = request.timeframe
    return frame


def load_batch(base_dir: Path, requests: Iterable[MarketDataRequest]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = [load_parquet(base_dir, item) for item in requests]
    if not frames:
        raise ValueError("No data requests were provided")
    return pd.concat(frames, ignore_index=True)