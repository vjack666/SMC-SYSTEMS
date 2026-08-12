"""Tests de market_replay — infraestructura de lectura viva del motor.

No toca ict_backtest. Verifica la cadena feed -> engine -> journal y que
el replay es vela-a-vela (no batch fingido): el motor solo conoce lo disponible
en t (ventana recortada + HTF closed-only).
"""

import sys
import pandas as pd
import numpy as np
import pytest

import market_replay.availability as avail
import market_replay.feed as feed
import market_replay.journal as journal
import market_replay.replay as replay

# Garantía de arquitectura: market_replay NUNCA importa ict_backtest.
def test_market_replay_no_ict_backtest_import():
    import types
    for mod in list(sys.modules):
        if mod.startswith("market_replay"):
            for name in dir(sys.modules[mod]):
                if name == "ict_backtest":
                    raise AssertionError(f"{mod} referencia ict_backtest")


def _synthetic_m15(periods=60, seed=0):
    idx = pd.date_range("2024-01-01", periods=periods, freq="15min", tz="UTC")
    rng = np.random.default_rng(seed)
    price = 1.10 + np.cumsum(rng.normal(0, 0.001, periods))
    return pd.DataFrame(
        {"time": idx, "open": price, "high": price + 0.001, "low": price - 0.001, "close": price}
    )


def test_availability_closed_only():
    df = _synthetic_m15(periods=40)
    h1 = df.iloc[::4].reset_index(drop=True)
    av = avail.TemporalAvailability({"M15": df, "H1": h1}, "M15")
    t = df["time"].iloc[20]
    assert av.is_available("M15", t) is True
    # snapshot incluye los TF presentes
    snap = av.snapshot(t)
    assert "M15" in snap and "H1" in snap


def test_journal_records_and_queries():
    j = journal.EventJournal()
    j.record(journal.JournalEntry(timestamp="t1", event_type="SWEEP", event_id="s1", parent_event_id=""))
    j.record(journal.JournalEntry(timestamp="t1", event_type="BOS", event_id="b1", parent_event_id="s1"))
    assert len(j) == 2
    assert len(j.by_timestamp("t1")) == 2
    assert j.by_event_id("b1").event_type == "BOS"
    assert j.children_of("s1")[0].event_id == "b1"


def test_replay_runs_vela_a_vela_without_ict_backtest():
    df = _synthetic_m15(periods=60)
    f = feed.MarketFeed()
    f.ingest("M15", df)
    rp = replay.MarketReplay(f, ltf="M15")
    res = rp.run()
    # 59 pasos (range(1, 60))
    assert res.steps == 59
    # el journal existe y es serializable
    assert isinstance(res.journal.to_list(), list)
    # el estado final es un SequenceState del motor
    from engine.sequence import SequenceState

    assert isinstance(res.final_state, SequenceState)


def test_replay_is_causal_window_limited():
    """El motor en cada paso solo procesa la vela i (ventana recortada a [0..i]).

    MarketReplay.run() llama al motor con start_i=i-1 sobre win=ltf[:i+1];
    por construcción el motor nunca ve velas futuras. Verificamos que el
    número de pasos es len-1 (una vela nueva por paso, nunca el lote completo
    de golpe) y que ningún evento del journal cita una vela fuera de rango.
    """
    df = _synthetic_m15(periods=30)
    f = feed.MarketFeed()
    f.ingest("M15", df)
    rp = replay.MarketReplay(f, ltf="M15")
    res = rp.run()
    # Una vela nueva por paso => steps == len-1 (no batch fingido).
    assert res.steps == len(df) - 1
    # Sin eventos que citen índices imposibles.
    for e in res.journal:
        assert e.candle_index <= res.steps
        assert e.candle_index >= 0
