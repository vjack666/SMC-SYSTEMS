from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from smc_successor._data_legacy import load_frame as load_parquet_frame
from smc_successor._progress import ProgressTracker

ProgressCB = Callable[[str, int, int, str], None] | None

MT5_TIMEFRAMES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
}

REVERSE_TF: dict[int, str] = {v: k for k, v in MT5_TIMEFRAMES.items()}


def _mt5_timeframe(tf: str) -> int:
    value = MT5_TIMEFRAMES.get(tf.upper())
    if value is None:
        raise ValueError(f"Unsupported timeframe: {tf}. Use one of {list(MT5_TIMEFRAMES)}")
    return value


@dataclass
class ConnectionConfig:
    path: str | None = None
    timeout: int = 60_000
    retry_delay: float = 2.0
    max_retries: int = 3


@dataclass
class DownloadResult:
    symbol: str
    timeframe: str
    bars: int
    date_from: str
    date_to: str
    columns: list[str]
    file_path: str | None = None


class MT5Connector:
    def __init__(self, config: ConnectionConfig | None = None) -> None:
        self.config = config or ConnectionConfig()
        self._initialized = False

    def connect(self) -> bool:
        import MetaTrader5 as mt5

        kwargs: dict[str, Any] = {"timeout": self.config.timeout}
        if self.config.path:
            kwargs["path"] = self.config.path

        result = mt5.initialize(**kwargs)
        if result:
            self._initialized = True
            return True

        error = self._last_error()
        raise ConnectionError(f"MT5 initialize failed: {error}")

    def ensure_connected(self) -> None:
        if not self._initialized:
            self.connect()

    def disconnect(self) -> None:
        if self._initialized:
            import MetaTrader5 as mt5

            mt5.shutdown()
            self._initialized = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def is_connected(self) -> bool:
        if not self._initialized:
            return False
        import MetaTrader5 as mt5

        return mt5.terminal_info() is not None

    def terminal_info(self) -> dict[str, Any]:
        self.ensure_connected()
        import MetaTrader5 as mt5

        info = mt5.terminal_info()
        if info is None:
            raise ConnectionError(f"Terminal info unavailable: {self._last_error()}")
        return info._asdict()

    def account_info(self) -> dict[str, Any]:
        self.ensure_connected()
        import MetaTrader5 as mt5

        info = mt5.account_info()
        if info is None:
            raise ConnectionError(f"Account info unavailable: {self._last_error()}")
        return info._asdict()

    def available_symbols(self) -> list[str]:
        self.ensure_connected()
        import MetaTrader5 as mt5

        symbols = mt5.symbols_get()
        if symbols is None:
            raise ConnectionError(f"Cannot get symbols: {self._last_error()}")
        return sorted([s.name for s in symbols])

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        self.ensure_connected()
        import MetaTrader5 as mt5

        info = mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol not found: {symbol}")
        return info._asdict()

    def _last_error(self) -> str:
        import MetaTrader5 as mt5

        code, desc = mt5.last_error()
        if code == 0:
            return "unknown error"
        return f"[{code}] {desc}"

    def _rates_to_frame(self, rates: np.ndarray | tuple | None) -> pd.DataFrame:
        if rates is None or (isinstance(rates, (list, tuple)) and len(rates) == 0) or (isinstance(rates, np.ndarray) and len(rates) == 0):
            return pd.DataFrame()

        if isinstance(rates, tuple):
            rates_list = list(rates)
            if len(rates_list) == 0 or not isinstance(rates_list[0], np.ndarray):
                return pd.DataFrame()
            rates = rates_list[0]

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={
            "tick_volume": "tick_volume",
            "real_volume": "real_volume",
        })
        if "spread" not in df.columns:
            df["spread"] = 0
        df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
        return df.sort_values("time").reset_index(drop=True)

    def download_rates(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100_000,
        retries: int | None = None,
        progress_cb: ProgressCB = None,
    ) -> pd.DataFrame:
        self.ensure_connected()
        import MetaTrader5 as mt5

        tf = _mt5_timeframe(timeframe)
        max_retries = retries if retries is not None else self.config.max_retries
        chunk = min(count, 10_000)
        last_error = ""

        if progress_cb:
            progress_cb("download", 0, count, f"{symbol} {timeframe}")

        tracker = ProgressTracker(total=count, desc=f"{symbol} {timeframe}", unit="bars", ascii=True)

        all_chunks: list[np.ndarray] = []
        pos = 0
        while pos < count:
            remaining = count - pos
            chunk_size = min(chunk, remaining)
            attempt = 0
            rates = None
            while attempt < max_retries:
                rates = mt5.copy_rates_from_pos(symbol, tf, pos, chunk_size)
                if rates is not None and len(rates) > 0:
                    break
                last_error = self._last_error()
                attempt += 1
                if attempt < max_retries:
                    time.sleep(self.config.retry_delay)

            if rates is None or len(rates) == 0:
                if pos > 0:
                    break  # partial data is better than nothing
                raise RuntimeError(f"Failed to download {symbol} {timeframe} after {max_retries} attempts: {last_error}")

            all_chunks.append(rates)
            pos += len(rates)
            tracker.update(len(rates))

        tracker.close()

        if not all_chunks:
            raise RuntimeError(f"No data returned for {symbol} {timeframe}")

        combined = np.concatenate(all_chunks)
        df = self._rates_to_frame(combined)
        if progress_cb:
            progress_cb("download", len(df), count, f"{symbol} {timeframe} done ({len(df)} bars)")
        return df

    def download_rates_range(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime,
        date_to: datetime | None = None,
    ) -> pd.DataFrame:
        self.ensure_connected()
        import MetaTrader5 as mt5

        tf = _mt5_timeframe(timeframe)
        dt_to = date_to or datetime.now(datetime.now().astimezone().tzinfo)

        rates = mt5.copy_rates_range(symbol, tf, date_from, dt_to)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No data for {symbol} {timeframe} from {date_from}: {self._last_error()}")

        return self._rates_to_frame(rates)

    def save_parquet(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        output_dir: Path = Path("data/raw"),
    ) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{symbol}_{timeframe}.parquet"
        df.to_parquet(path, index=False)
        return path

    def download_and_save(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100_000,
        output_dir: Path = Path("data/raw"),
        progress_cb: ProgressCB = None,
    ) -> DownloadResult:
        df = self.download_rates(symbol, timeframe, count, progress_cb=progress_cb)
        if df.empty:
            raise RuntimeError(f"No data returned for {symbol} {timeframe}")

        path = self.save_parquet(df, symbol, timeframe, output_dir)
        result = DownloadResult(
            symbol=symbol,
            timeframe=timeframe,
            bars=int(len(df)),
            date_from=str(df["time"].iloc[0]),
            date_to=str(df["time"].iloc[-1]),
            columns=list(df.columns),
            file_path=str(path),
        )
        return result

    def download_all_timeframes(
        self,
        symbol: str,
        timeframes: list[str] | None = None,
        count: int = 100_000,
        output_dir: Path = Path("data/raw"),
        progress_cb: ProgressCB = None,
    ) -> list[DownloadResult]:
        if timeframes is None:
            timeframes = ["M15", "H1", "H4", "D1"]
        results: list[DownloadResult] = []
        for i, tf in enumerate(timeframes, 1):
            if progress_cb:
                progress_cb("timeframe", i - 1, len(timeframes), f"{symbol} {tf}")
            result = self.download_and_save(symbol, tf, count, output_dir, progress_cb=progress_cb)
            results.append(result)
        return results

    def download_multi_symbol(
        self,
        symbols: list[str],
        timeframes: list[str] | None = None,
        count: int = 100_000,
        output_dir: Path = Path("data/raw"),
        progress_cb: ProgressCB = None,
    ) -> dict[str, list[DownloadResult]]:
        results: dict[str, list[DownloadResult]] = {}
        for i, symbol in enumerate(symbols, 1):
            if progress_cb:
                progress_cb("symbol", i - 1, len(symbols), symbol)
            results[symbol] = self.download_all_timeframes(symbol, timeframes, count, output_dir, progress_cb=progress_cb)
        return results


def load_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    return load_parquet_frame(data_dir, symbol, timeframe)
