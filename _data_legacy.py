from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Terminal path for mt5.initialize(). Set via env var or before calling load_frame.
MT5_TERMINAL_PATH: str | None = os.environ.get(
    "SMC_MT5_TERMINAL",
    r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe",
)

TF_MAP: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}

STALE_THRESHOLD_HOURS: dict[str, float] = {
    "M1": 0.5,
    "M5": 1,
    "M15": 2,
    "M30": 4,
    "H1": 6,
    "H4": 12,
    "D1": 48,
}


def _ensure_symbol_in_market_watch(symbol: str) -> None:
    import MetaTrader5 as mt5

    info = mt5.symbol_info(symbol)
    if info is None:
        mt5.symbol_select(symbol, True)
    elif not info.visible:
        mt5.symbol_select(symbol, True)


def _download_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    import MetaTrader5 as mt5

    if not mt5.initialize(path=MT5_TERMINAL_PATH):
        raise RuntimeError(f"MT5 initialize failed for {MT5_TERMINAL_PATH}")

    tf_val = TF_MAP.get(timeframe.upper())
    if tf_val is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    _ensure_symbol_in_market_watch(symbol)
    rates = mt5.copy_rates_range(symbol, tf_val, datetime(2020, 1, 1), datetime.now(timezone.utc))
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, 50_000)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]].sort_values("time").reset_index(drop=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(data_dir / f"{symbol}_{timeframe}.parquet", index=False)
    return df


def _is_stale(frame: pd.DataFrame, timeframe: str, max_stale_hours: float | None = None) -> bool:
    threshold = max_stale_hours if max_stale_hours is not None else STALE_THRESHOLD_HOURS.get(timeframe.upper())
    if threshold is None:
        return False
    last_time = frame["time"].max()
    hours_since = (pd.Timestamp.now(tz="UTC") - last_time).total_seconds() / 3600
    return hours_since > threshold


def load_frame(data_dir: Path | str, symbol: str, timeframe: str, auto_download: bool = True, max_stale_hours: float | None = None) -> pd.DataFrame:
    data_dir = Path(data_dir)
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        if auto_download:
            try:
                return _download_frame(data_dir, symbol, timeframe)
            except Exception:
                pass
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)
    if auto_download and _is_stale(frame, timeframe, max_stale_hours):
        try:
            frame = _download_frame(data_dir, symbol, timeframe)
        except Exception:
            logging.getLogger(__name__).warning(f"Failed to refresh stale data for {symbol} {timeframe}, using cached")
    return frame


def apply_time_window(frame: pd.DataFrame, start_time: str | None, end_time: str | None) -> pd.DataFrame:
    data = frame.copy()
    if start_time is not None:
        data = data[data["time"] >= pd.to_datetime(start_time, utc=True)]
    if end_time is not None:
        data = data[data["time"] <= pd.to_datetime(end_time, utc=True)]
    return data.reset_index(drop=True)
