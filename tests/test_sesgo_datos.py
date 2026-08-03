"""T2 — Cargador y validador del parquet M15."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from ict_backtest.sesgo.reloj.datos import ValidatedM15, validate_m15_parquet


def _make_m15_df(index: list[pd.Timestamp], close: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.0001 for c in close],
            "low": [c - 0.0001 for c in close],
            "close": close,
        },
        index=pd.DatetimeIndex(index, tz=timezone.utc),
    )


def _write_tmp_parquet(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return path


def test_validate_m15_parquet_success(tmp_path):
    idx = pd.date_range("2026-01-01 00:00", periods=8, freq="15min", tz="UTC")
    df = _make_m15_df(list(idx), [1.0] * len(idx))
    path = _write_tmp_parquet(tmp_path / "EURUSD_M15.parquet", df)

    validated = validate_m15_parquet("EURUSD", raw_root=tmp_path)

    assert isinstance(validated, ValidatedM15)
    assert validated.symbol == "EURUSD"
    assert validated.timeframe == "M15"
    assert validated.tz == "UTC"
    assert validated.path == path
    assert len(validated.df) == len(df)


def test_validate_m15_parquet_detects_duplicates(tmp_path):
    idx = pd.date_range("2026-01-01 00:00", periods=8, freq="15min", tz="UTC")
    idx = list(idx) + [idx[-1]]
    df = _make_m15_df(idx, [1.0] * len(idx))
    _write_tmp_parquet(tmp_path / "EURUSD_M15.parquet", df)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        validate_m15_parquet("EURUSD", raw_root=tmp_path)


def test_validate_m15_parquet_detects_bad_order(tmp_path):
    base = pd.date_range("2026-01-01 00:00", periods=8, freq="15min", tz="UTC")
    idx = [base[4], base[0], base[1], base[2], base[3], base[5], base[6], base[7]]
    df = _make_m15_df(idx, [1.0] * len(idx))
    _write_tmp_parquet(tmp_path / "EURUSD_M15.parquet", df)

    with pytest.raises(ValueError, match="not sorted by time"):
        validate_m15_parquet("EURUSD", raw_root=tmp_path)


def test_validate_m15_parquet_missing_required_column(tmp_path):
    idx = pd.date_range("2026-01-01 00:00", periods=8, freq="15min", tz="UTC")
    df = pd.DataFrame({"close": [1.0] * len(idx)}, index=idx)
    _write_tmp_parquet(tmp_path / "EURUSD_M15.parquet", df)

    with pytest.raises(ValueError, match="missing required columns"):
        validate_m15_parquet("EURUSD", raw_root=tmp_path)
