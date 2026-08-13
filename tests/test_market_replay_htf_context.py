"""M3 FASE 1: congelar el comportamiento ACTUAL de MarketReplay (foto antes).

Autorizacion: maestro (2026-08-12), capa de observacion. NO toca engine.

Este test documenta el estado previo a cablear build_context_stack:
- el snapshot HTF que recibe el motor tiene trend=None (parquet no almacena
  trend; la capa de observacion no lo calculaba).
- por tanto el motor no autoriza entradas => 0 setups en replay real.

Sirve de RED DE SEGURIDAD: tras cablear el contexto real (M3 FASE 2), este
test DEBE cambiar (trend ya no None, setups > 0). Si tras el cambio este test
sigue pasando IGUAL, significa que el cableado no tuvo efecto => CASO C.
"""

import pandas as pd
import pytest

from engine.data_feed import load_frames
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay


def _build_replay(symbol, n):
    frames = load_frames(symbol=symbol, timeframes=("D1", "H4", "H1", "M15"))
    m15 = frames["M15"]
    last = m15["time"].iloc[n - 1]
    fwd = {tf: frames[tf][frames[tf]["time"] <= last].reset_index(drop=True)
           for tf in ("D1", "H4", "H1", "M15")}
    feed = MarketFeed()
    for tf, f in fwd.items():
        feed.ingest(tf, f)
    return MarketReplay(feed, ltf="M15")


@pytest.mark.parametrize("symbol,n", [("EURUSD", 8000)])
def test_htf_snapshot_has_no_trend_before_cable(symbol, n):
    """FOTO ANTES: el snapshot HTF entregado al motor trae trend=None."""
    rp = _build_replay(symbol, n)
    m15 = rp.feed.window("M15")
    i = min(7999, n - 1)
    t = m15["time"].iloc[i]
    snap = rp.avail.snapshot(t, include_ltf=False)
    # Sin cablear contexto real, la capa de observacion no calcula trend.
    for tf in ("D1", "H4", "H1"):
        row = snap.get(tf)
        if row is not None:
            assert row.get("trend", "RANGING") in (None, "RANGING"), (
                f"{tf} trae trend calculado ({row.get('trend')}) ANTES de cablear: "
                f"el test de congelacion quedo obsoleto."
            )


@pytest.mark.parametrize("symbol,n", [("EURUSD", 8000)])
def test_replay_emits_zero_setups_before_cable(symbol, n):
    """FOTO ANTES: sin contexto HTF real, el motor no autoriza entradas."""
    rp = _build_replay(symbol, n)
    res = rp.run()
    signals = res.signals or []
    setups = [s for s in signals if s.get("direction") not in (0, None)
              and s.get("entry") is not None]
    # Estado previo documentado: 0 setups (motor ciego a HTF).
    # Si esto falla (setups > 0) significa que el entorno ya cableo contexto
    # y este test de congelacion debe actualizarse.
    assert len(setups) == 0, (
        f"Se esperaban 0 setups antes de cablear; aparecieron {len(setups)}. "
        f"Actualizar la linea base de M3 FASE 1."
    )
