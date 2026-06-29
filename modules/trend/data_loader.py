from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

TIMEFRAMES: List[str] = ["M15", "H1", "H4", "D1"]
REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "tick_volume"}


@dataclass
class MultiTimeframeData:
    """Container for all timeframes of a single symbol."""

    symbol: str
    m15: pd.DataFrame
    h1: pd.DataFrame
    h4: pd.DataFrame
    d1: pd.DataFrame


def _load_single(base_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    file_path = base_dir / f"{symbol}_{timeframe}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    frame = pd.read_parquet(file_path).copy()
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing columns in {file_path.name}: {missing}")

    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)
    frame["symbol"] = symbol
    frame["timeframe"] = timeframe
    return frame


def load_symbol(base_dir: Path, symbol: str) -> MultiTimeframeData:
    """Load M15, H1, H4, D1 data for a single symbol."""
    return MultiTimeframeData(
        symbol=symbol,
        m15=_load_single(base_dir, symbol, "M15"),
        h1=_load_single(base_dir, symbol, "H1"),
        h4=_load_single(base_dir, symbol, "H4"),
        d1=_load_single(base_dir, symbol, "D1"),
    )


def load_all(
    base_dir: Path,
    symbols: List[str],
) -> Dict[str, MultiTimeframeData]:
    """Load all timeframes for every symbol in the list."""
    return {symbol: load_symbol(base_dir, symbol) for symbol in symbols}
