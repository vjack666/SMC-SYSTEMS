"""tests/test_engine_poi_anchor.py — Ancla narrativa de POI (Brecha B, tesis 18).

Determinista y sintetico (P4 VISION): datos generados, sin red ni MT5.
Verifica el contrato de engine.poi_anchor:
  - build_htf_structure_index extrae eventos BOS/CHOCH de los TF padre
  - make_htf_poi_fn devuelve True si hay evento padre en la MISMA direccion
    ya cerrado (anti look-ahead por timestamp) en la vela LTF i
  - make_htf_poi_fn NO veta cuando no hay eventos padre (comportamiento
    historico intacto: el POI es bonus, no gate duro)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.poi_anchor import build_htf_structure_index, make_htf_poi_fn


def _frame(highs, lows, closes, start: str = "2026-01-01",
           freq: str = "h") -> pd.DataFrame:
    """Velas con OHLC explicito + columna time (estilo test_engine_bos)."""
    n = len(highs)
    return pd.DataFrame(
        {
            "time": pd.date_range(start, periods=n, freq=freq, tz="UTC"),
            "open": list(closes),
            "high": list(highs),
            "low": list(lows),
            "close": list(closes),
        }
    )


def _bull_then_bear() -> pd.DataFrame:
    """Sube (BOS alcista) y luego baja (BOS/CHOCH bajista), con swings reales.

    Pico en i=3 y valle en i=11 -> produce BOS alcista y luego bajista.
    """
    highs = [1.00, 1.02, 1.06, 1.10, 1.08, 1.07, 1.12, 1.13,
             1.09, 1.05, 1.02, 0.98, 0.97, 0.96, 0.95, 0.94]
    lows = [0.99, 1.01, 1.05, 1.06, 1.06, 1.06, 1.07, 1.10,
            1.04, 1.00, 0.97, 0.93, 0.92, 0.91, 0.90, 0.89]
    closes = [0.995, 1.015, 1.055, 1.07, 1.075, 1.065, 1.115, 1.125,
              1.085, 1.045, 1.015, 0.975, 0.965, 0.955, 0.945, 0.935]
    return _frame(highs, lows, closes)


def test_build_htf_structure_index_finds_events():
    htf = {"H1": _bull_then_bear()}
    events = build_htf_structure_index(htf, parents=("H1",))
    # debe haber al menos un BOS alcista y uno bajista
    dirs = {e.direction for e in events}
    assert 1 in dirs and -1 in dirs
    # todos con timestamp
    assert all(e.time is not None for e in events)


def test_make_htf_poi_fn_anchors_same_direction():
    htf = {"H1": _bull_then_bear()}
    # LTF con la misma forma; ultima vela es bajista -> debe anclar BEAR
    ltf = _bull_then_bear()
    fn = make_htf_poi_fn(ltf, htf, parents=("H1",))
    i = len(ltf) - 1
    assert fn(i, -1) is True   # hay BOS/CHOCH bajista padre ya cerrado
    # direccion opuesta (alcista) en la cola bajista: depende de si hay BOS
    # alcista padre previo; en este set sintetico SI lo hay (subio primero).
    assert fn(i, 1) is True


def test_make_htf_poi_fn_no_veto_without_parents():
    htf = {"H1": _bull_then_bear()}
    ltf = _bull_then_bear()
    fn = make_htf_poi_fn(ltf, htf, parents=("H1",))
    # vela temprana (i=2) ANTES de cualquier evento padre (BOS alcista en i=7)
    # -> no hay ancla previa -> devuelve False (no bonus: hay eventos cargados,
    # solo que aun no ocurren en t). El "no bloquea" aplica solo sin TF padre.
    assert fn(2, 1) is False
    # en la cola (i final) ya hay BOS alcista padre -> ancla alcista
    assert fn(len(ltf) - 1, 1) is True


def test_make_htf_poi_fn_anti_lookahead_by_time():
    # LTF bajista desde el inicio; el padre bajista ocurre mas tarde en el
    # tiempo. En t temprano NO debe anclar (anti look-ahead por timestamp).
    ltf = _frame(list(np.linspace(1.20, 1.10, 40)),
                 list(np.linspace(1.19, 1.09, 40)),
                 list(np.linspace(1.20, 1.10, 40)))
    parent = _bull_then_bear()  # BOS bajista padre aparece en i=~11
    fn = make_htf_poi_fn(ltf, {"H1": parent}, parents=("H1",))
    early = fn(1, -1)
    late = fn(len(ltf) - 1, -1)
    # al inicio no hay evento padre bajista ya cerrado respecto a t -> False
    assert early is False
    # al final, el padre bajista ya cerro antes -> debe anclar
    assert late is True
    assert isinstance(early, bool) and isinstance(late, bool)


def test_make_htf_poi_fn_empty_htf_returns_true_no_block():
    ltf = _bull_then_bear()
    fn = make_htf_poi_fn(ltf, {}, parents=("D1", "H4", "H1"))
    # sin TF padre cargados -> no bloquea (comportamiento historico)
    i = len(ltf) - 1
    assert fn(i, 1) is True
    assert fn(i, -1) is True
