"""Download OHLCV data from MetaTrader 5 and persist parquet datasets."""

from __future__ import annotations

# pyright: reportCallIssue=false, reportAttributeAccessIssue=false
# pylint: disable=no-member,unnecessary-ellipsis

import argparse
import importlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Protocol, cast

import pandas as pd

mt5 = cast(Any, importlib.import_module("MetaTrader5"))


DEFAULT_TERMINAL_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
DEFAULT_TIMEFRAMES = ["M15", "H1", "H4", "D1"]
DEFAULT_YEARS = 2


class _Mt5Api(Protocol):
    """Typed contract for the subset of MetaTrader5 API used by this module."""

    TIMEFRAME_M1: int
    TIMEFRAME_M5: int
    TIMEFRAME_M15: int
    TIMEFRAME_M30: int
    TIMEFRAME_H1: int
    TIMEFRAME_H4: int
    TIMEFRAME_D1: int

    def initialize(self, *, path: str) -> bool:
        """Open connection to a MetaTrader 5 terminal executable path."""
        raise NotImplementedError

    def shutdown(self) -> None:
        """Close the active MetaTrader 5 connection."""
        raise NotImplementedError

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Enable or disable a symbol in the MarketWatch list."""
        raise NotImplementedError

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> Any:
        """Return rate bars for a symbol/timeframe and UTC range."""
        raise NotImplementedError

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any:
        """Return bars from terminal history by reverse index position."""
        raise NotImplementedError

    def last_error(self) -> tuple[int, str]:
        """Return the last terminal/library error as code and message."""
        raise NotImplementedError


MT5 = cast(_Mt5Api, mt5)


def _mt5_last_error() -> tuple[int, str]:
    """Read last MT5 error and normalize it into a typed tuple."""

    raw = MT5.last_error()
    if not isinstance(raw, tuple) or len(raw) != 2:
        return -1, "Unknown MT5 error"
    code, message = raw
    return int(code), str(message)


TIMEFRAME_MAP: Dict[str, int] = {
    "M1": int(MT5.TIMEFRAME_M1),
    "M5": int(MT5.TIMEFRAME_M5),
    "M15": int(MT5.TIMEFRAME_M15),
    "M30": int(MT5.TIMEFRAME_M30),
    "H1": int(MT5.TIMEFRAME_H1),
    "H4": int(MT5.TIMEFRAME_H4),
    "D1": int(MT5.TIMEFRAME_D1),
}


@dataclass(frozen=True)
class DownloadConfig:
    """Runtime configuration for multi-symbol/timeframe MT5 downloads."""

    terminal_path: str = DEFAULT_TERMINAL_PATH
    output_dir: Path = Path(__file__).resolve().parent
    symbols: List[str] = None  # type: ignore[assignment]
    timeframes: List[str] = None  # type: ignore[assignment]
    years: int = DEFAULT_YEARS

    def __post_init__(self) -> None:
        """Populate default symbols/timeframes when omitted by caller."""

        if self.symbols is None:
            object.__setattr__(self, "symbols", list(DEFAULT_SYMBOLS))
        if self.timeframes is None:
            object.__setattr__(self, "timeframes", list(DEFAULT_TIMEFRAMES))


def init_mt5(terminal_path: str) -> None:
    """Initialize MT5 terminal connection or raise with detailed error."""

    connected = bool(MT5.initialize(path=terminal_path))
    if not connected:
        code, message = _mt5_last_error()
        raise RuntimeError(f"MT5 initialization failed ({code}): {message}")


def shutdown_mt5() -> None:
    """Shut down MT5 connection."""

    MT5.shutdown()


def ensure_symbol(symbol: str) -> None:
    """Ensure a symbol is selected in MarketWatch before requesting rates."""

    if not bool(MT5.symbol_select(symbol, True)):
        code, message = _mt5_last_error()
        raise RuntimeError(f"Failed to enable symbol {symbol} ({code}): {message}")


def _bar_time_from_pos(symbol: str, timeframe_label: str, pos: int) -> datetime | None:
    timeframe = TIMEFRAME_MAP.get(timeframe_label)
    if timeframe is None:
        raise ValueError(f"Unsupported timeframe: {timeframe_label}")

    bars = MT5.copy_rates_from_pos(symbol, timeframe, int(pos), 1)
    if bars is None or len(bars) == 0:
        return None

    frame = pd.DataFrame(bars)
    if frame.empty or "time" not in frame.columns:
        return None
    return pd.to_datetime(frame.iloc[0]["time"], unit="s", utc=True).to_pydatetime()


def discover_available_range(symbol: str, timeframe_label: str) -> tuple[datetime, datetime]:
    """Discover oldest/newest available bar timestamps in MT5 for a symbol/timeframe."""

    newest = _bar_time_from_pos(symbol, timeframe_label, 0)
    if newest is None:
        raise RuntimeError(f"No history available for {symbol} {timeframe_label}")

    cache: dict[int, datetime | None] = {0: newest}

    def lookup(pos: int) -> datetime | None:
        if pos not in cache:
            cache[pos] = _bar_time_from_pos(symbol, timeframe_label, pos)
        return cache[pos]

    # Exponential search to bracket the last valid history position.
    low = 0
    high = 1
    while lookup(high) is not None:
        low = high
        high *= 2
        if high > 50_000_000:
            break

    # Binary search to find the maximum valid position.
    left = low
    right = high
    while left + 1 < right:
        mid = (left + right) // 2
        if lookup(mid) is None:
            right = mid
        else:
            left = mid

    oldest = lookup(left)
    if oldest is None:
        oldest = newest
    return oldest, newest


def fetch_rates(
    symbol: str,
    timeframe_label: str,
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    """Fetch rates from MT5 and return a normalized OHLCV dataframe.

    MT5 may reject very large date ranges (e.g. decades for M15) with
    "Invalid params". To keep downloads stable for long histories, this
    function pulls data in chunks and auto-reduces chunk size if needed.
    """

    timeframe = TIMEFRAME_MAP.get(timeframe_label)
    if timeframe is None:
        raise ValueError(f"Unsupported timeframe: {timeframe_label}")

    chunk_days_map = {
        "M1": 7,
        "M5": 30,
        "M15": 120,
        "M30": 240,
        "H1": 365,
        "H4": 1095,
        "D1": 3650,
    }
    chunk_days = int(chunk_days_map.get(timeframe_label, 120))

    cursor = start_utc
    chunks: list[pd.DataFrame] = []
    while cursor < end_utc:
        chunk_end = min(cursor + timedelta(days=chunk_days), end_utc)
        rates = MT5.copy_rates_range(symbol, timeframe, cursor, chunk_end)

        if rates is None:
            code, message = _mt5_last_error()
            if code == -2 and chunk_days > 1:
                # Retry same cursor with a smaller window when MT5 rejects params.
                chunk_days = max(1, chunk_days // 2)
                logging.warning(
                    "MT5 rejected %s %s chunk (%s to %s). Reducing chunk size to %s day(s).",
                    symbol,
                    timeframe_label,
                    cursor,
                    chunk_end,
                    chunk_days,
                )
                continue
            raise RuntimeError(
                f"Failed to download rates for {symbol} {timeframe_label} ({code}): {message}"
            )

        if len(rates) > 0:
            chunk_frame = pd.DataFrame(rates)
            chunk_frame["time"] = pd.to_datetime(chunk_frame["time"], unit="s", utc=True)
            chunks.append(chunk_frame)

        cursor = chunk_end

    if not chunks:
        raise RuntimeError(f"No rates returned for {symbol} {timeframe_label}")

    frame = pd.concat(chunks, ignore_index=True)
    frame = frame.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    frame.insert(0, "symbol", symbol)
    frame.insert(1, "timeframe", timeframe_label)
    return frame


def save_parquet(
    frame: pd.DataFrame,
    output_dir: Path,
    symbol: str,
    timeframe_label: str,
) -> Path:
    """Persist dataframe to a symbol/timeframe parquet file and return the path."""

    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{symbol}_{timeframe_label}.parquet"
    frame.to_parquet(file_path, index=False)
    return file_path


def iter_symbol_timeframes(
    symbols: Iterable[str],
    timeframes: Iterable[str],
) -> Iterable[tuple[str, str]]:
    """Yield all symbol/timeframe combinations in deterministic nested order."""

    for symbol in symbols:
        for timeframe in timeframes:
            yield symbol, timeframe


def run_download(config: DownloadConfig) -> List[Path]:
    """Run full download process for all configured symbol/timeframe pairs."""

    now_utc = datetime.now(tz=timezone.utc)
    start_utc = now_utc - timedelta(days=365 * config.years)

    logging.info("Initializing MT5 terminal: %s", config.terminal_path)
    init_mt5(config.terminal_path)
    logging.info("MT5 connected successfully")

    output_files: List[Path] = []
    try:
        for symbol, timeframe_label in iter_symbol_timeframes(config.symbols, config.timeframes):
            ensure_symbol(symbol)
            try:
                available_start, available_end = discover_available_range(symbol, timeframe_label)
            except RuntimeError:
                # Keep legacy behavior as fallback if MT5 range discovery is unavailable.
                available_start, available_end = start_utc, now_utc

            logging.info(
                "Downloading %s %s from %s to %s",
                symbol,
                timeframe_label,
                available_start,
                available_end,
            )
            frame = fetch_rates(symbol, timeframe_label, available_start, available_end)
            saved = save_parquet(frame, config.output_dir, symbol, timeframe_label)
            output_files.append(saved)
            logging.info("Saved %s rows to %s", len(frame), saved)
    finally:
        shutdown_mt5()
        logging.info("MT5 shutdown complete")

    return output_files


def parse_args() -> DownloadConfig:
    """Parse CLI arguments and build download configuration."""

    parser = argparse.ArgumentParser(description="Download MT5 data and save to parquet files.")
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL_PATH)
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS)
    args = parser.parse_args()

    return DownloadConfig(
        terminal_path=args.terminal_path,
        output_dir=Path(args.output_dir),
        symbols=list(args.symbols),
        timeframes=[item.upper() for item in args.timeframes],
        years=args.years,
    )


def main() -> None:
    """CLI entry point for MT5 data download."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    config = parse_args()
    files = run_download(config)
    logging.info("Finished. Generated %s parquet files.", len(files))


if __name__ == "__main__":
    main()