"""T5 — Test anti-look-ahead en el límite exacto del reloj."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.reloj.reloj import RelojSesgo


def _make_m15(index):
    return pd.DataFrame(
        {
            "open": [1.0] * len(index),
            "high": [1.0001] * len(index),
            "low": [0.9999] * len(index),
            "close": [1.0] * len(index),
        },
        index=pd.DatetimeIndex(index, tz=timezone.utc),
    )


def test_h4_not_visible_until_last_m15_closes():
    # 80 M15 bars = 00:00-19:45, so 5 full H4 buckets.
    # The first H4 closure should be at 03:45 (end of first 16 M15 bars).
    idx = pd.date_range("2026-01-01 00:00", periods=80, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())
    eventos = reloj.run()

    first_h4 = [c for ev in eventos for c in ev.tf_closures if c.timeframe == "H4"][0]
    assert first_h4.timestamp == pd.Timestamp("2026-01-01 03:45:00", tz="UTC")

    # Before 03:45, no H4 closure must be visible
    pre_boundary = [ev for ev in eventos if ev.m15_timestamp < first_h4.timestamp]
    assert all(not any(c.timeframe == "H4" for c in ev.tf_closures) for ev in pre_boundary)


def test_no_future_bar_read():
    # At any M15 event, the highest closed HTF timestamp must be <= current M15 timestamp
    idx = pd.date_range("2026-01-01 00:00", periods=96, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())

    for ev in reloj.iter_eventos():
        for c in ev.tf_closures:
            assert c.timestamp <= ev.m15_timestamp, (
                f"look-ahead: {c.timeframe} {c.timestamp} > m15 {ev.m15_timestamp}"
            )
