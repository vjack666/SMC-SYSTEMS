"""T4 — Reloj vela a vela."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.reloj.reloj import EventoReloj, RelojSesgo, VelaCerrada


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


def test_h1_closure_count():
    # 12 M15 bars = 00:00-02:45. The last H1 bucket (02:00-02:45) stays open
    # because there is no following bar to trigger the bucket change.
    idx = pd.date_range("2026-01-01 00:00", periods=12, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())
    eventos = reloj.run()

    closures = [
        c
        for evento in eventos
        for c in evento.tf_closures
        if c.timeframe == "H1"
    ]
    assert len(closures) == 2


def test_h4_not_available_in_formation():
    idx = pd.date_range("2026-01-01 00:00", periods=4, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())
    eventos = reloj.run()

    assert all(not any(c.timeframe == "H4" for c in ev.tf_closures) for ev in eventos)


def test_reloj_is_deterministic():
    idx = pd.date_range("2026-01-01 00:00", periods=96, freq="15min", tz="UTC")
    df = _make_m15(idx)

    first = RelojSesgo(df, SesgoConfig()).run()
    second = RelojSesgo(df, SesgoConfig()).run()

    assert len(first) == len(second)
    for a, b in zip(first, second):
        assert a.m15_timestamp == b.m15_timestamp
        assert [c.timestamp for c in a.tf_closures] == [c.timestamp for c in b.tf_closures]
