from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from _data_legacy import load_frame


def _write_parquet(data_dir: Path, symbol: str, timeframe: str, hours_ago: float) -> Path:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    n = 10
    last = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=hours_ago)
    times = pd.date_range(end=last, periods=n, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open": 1.10,
        "high": 1.11,
        "low": 1.09,
        "close": 1.105,
        "tick_volume": 100,
        "spread": 1,
    })
    df.to_parquet(path, index=False)
    return path


def test_fresh_parquet_is_returned_as_is(tmp_path: Path) -> None:
    _write_parquet(tmp_path, "EURUSD", "M15", hours_ago=0.5)
    with patch("_data_legacy._download_frame") as mock:
        df = load_frame(tmp_path, "EURUSD", "M15")
        mock.assert_not_called()
        assert len(df) == 10


def test_stale_parquet_triggers_download(tmp_path: Path) -> None:
    _write_parquet(tmp_path, "EURUSD", "M15", hours_ago=10)
    fresh = pd.DataFrame({
        "time": pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=20, freq="15min", tz="UTC"),
        "open": 160.0,
        "high": 161.0,
        "low": 159.0,
        "close": 160.5,
        "tick_volume": 200,
        "spread": 1,
    })
    with patch("_data_legacy._download_frame", return_value=fresh) as mock:
        df = load_frame(tmp_path, "EURUSD", "M15")
        mock.assert_called_once()
        assert len(df) == 20
        assert df["close"].iloc[-1] == 160.5


def test_stale_parquet_falls_back_on_download_failure(tmp_path: Path) -> None:
    _write_parquet(tmp_path, "USDJPY", "M15", hours_ago=10)
    with patch("_data_legacy._download_frame", side_effect=RuntimeError("no mt5")) as mock:
        df = load_frame(tmp_path, "USDJPY", "M15")
        mock.assert_called_once()
        assert len(df) == 10
        assert df["close"].iloc[-1] == 1.105


def test_auto_download_false_skips_stale_check(tmp_path: Path) -> None:
    _write_parquet(tmp_path, "EURUSD", "M15", hours_ago=10)
    with patch("_data_legacy._download_frame") as mock:
        df = load_frame(tmp_path, "EURUSD", "M15", auto_download=False)
        mock.assert_not_called()
        assert len(df) == 10


def test_auto_download_false_missing_file_raises(tmp_path: Path) -> None:
    with patch("_data_legacy._download_frame") as mock:
        with pytest.raises(FileNotFoundError):
            load_frame(tmp_path, "EURUSD", "M15", auto_download=False)
        mock.assert_not_called()
