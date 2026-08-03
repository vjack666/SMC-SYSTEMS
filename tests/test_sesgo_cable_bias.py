"""T6 — Cablear el motor bias al reloj."""

from __future__ import annotations

from datetime import timezone

import pandas as pd
import pytest

from engine.bias.narrative import HtfBias, NEUTRAL
from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.motor_cable.cable_bias import CableBias, SesgoVigente
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


def test_bias_changes_only_on_d1_close():
    idx = pd.date_range("2026-01-01 00:00", periods=96 * 20, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())
    cable = CableBias()

    last_bias = None
    for ev in reloj.iter_eventos():
        vigente = cable.procesar_evento(ev)
        if vigente is None:
            continue
        current_bias = vigente.bias.direction
        if last_bias is not None:
            assert current_bias == last_bias, (
                f"bias changed at {ev.m15_timestamp} without D1 close: {last_bias} -> {current_bias}"
            )
        if vigente.updated_by_d1:
            last_bias = current_bias


def test_cable_produces_htf_bias_object_after_d1_close():
    idx = pd.date_range("2026-01-01 00:00", periods=96 * 25, freq="15min", tz="UTC")
    df = _make_m15(idx)
    reloj = RelojSesgo(df, SesgoConfig())
    cable = CableBias()

    found = None
    for ev in reloj.iter_eventos():
        cable.procesar_evento(ev)
        if cable.esta_disponible():
            found = cable.sesgo_vigente()
            break

    assert found is not None
    assert isinstance(found.bias, HtfBias)
    assert found.bias.direction in {NEUTRAL, "BULLISH", "BEARISH"}
    assert isinstance(found.updated_at, pd.Timestamp)
    assert found.updated_by_d1 is True


def test_aligned_true_when_three_tfs_same_direction():
    bias = HtfBias(d1="BULLISH", h4="BULLISH", h1="BULLISH")
    assert bias.aligned is True
    assert bias.direction == "BULLISH"


def test_cable_warmup_is_exposed():
    cable = CableBias()

    for _ in range(20):
        cable.warmup.record_closure("D1")
    for _ in range(60):
        cable.warmup.record_closure("H4")
    for _ in range(100):
        cable.warmup.record_closure("H1")

    assert cable.esta_disponible() is True
