"""Tests engine/micro.py -- microestructura M1 (geometria pura, anti look-ahead)."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.micro import (
    detect_m1_liquidity_sweeps,
    is_m1_fakeout,
    m1_micro_momentum,
    m1_swing_levels,
    normalize_parent_swings,
)


def _mk(rows):
    times = pd.date_range("2024-01-01", periods=len(rows), freq="1min", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "time", times)
    return df


@pytest.fixture()
def m1_zigzag():
    """Zigzag M1 determinista con UN sweep buyside (i=6) y UN fakeout (i=12).

    Rango base 100-101. i=6 perfora 101.5 (swing padre M5) y cierra en 100.6.
    i=12 rompe el rango previo por arriba y cierra dentro -> fakeout.
    """
    rows = [
        (100.0, 100.4, 99.9, 100.2),   # 0
        (100.2, 100.6, 100.0, 100.5),  # 1
        (100.5, 100.7, 100.1, 100.2),  # 2
        (100.2, 100.5, 99.8, 100.0),   # 3
        (100.0, 100.9, 99.9, 100.8),   # 4
        (100.8, 101.2, 100.6, 101.0),  # 5
        (101.0, 101.9, 100.5, 100.6),  # 6  <-- SWEEP buyside de 101.5
        (100.6, 100.8, 100.1, 100.3),  # 7
        (100.3, 100.5, 99.5, 99.6),    # 8
        (99.6, 99.9, 99.2, 99.8),      # 9
        (99.8, 100.1, 99.7, 100.0),    # 10
        (100.0, 100.3, 99.9, 100.2),   # 11
        (100.2, 101.0, 100.1, 100.25), # 12 <-- FAKEOUT (rompe max previo, cierra dentro)
        (100.25, 100.4, 100.0, 100.1), # 13
    ]
    return _mk(rows)


PARENT_SWINGS = [
    {"price": 101.5, "side": "high", "tf": "M5"},
    {"price": 99.0, "side": "low", "tf": "M15"},
]


# --- normalizacion -------------------------------------------------------


def test_normalize_parent_swings_formats():
    a = normalize_parent_swings(PARENT_SWINGS)
    b = normalize_parent_swings([("high", 101.5), ("low", 99.0)])
    c = normalize_parent_swings({"highs": [101.5], "lows": [99.0]})
    for got in (a, b, c):
        assert [(x["side"], x["price"]) for x in got] == [
            ("high", 101.5),
            ("low", 99.0),
        ]
    assert normalize_parent_swings(None) == []
    assert normalize_parent_swings([{"price": None, "side": "high"}]) == []


# --- sweeps --------------------------------------------------------------


def test_detect_sweep_buyside(m1_zigzag):
    ev = detect_m1_liquidity_sweeps(m1_zigzag, PARENT_SWINGS)
    assert len(ev) == 1
    e = ev[0]
    assert e["index"] == 6
    assert e["side"] == "buyside"
    assert e["level"] == 101.5
    assert e["direction"] == -1
    assert e["penetration"] == pytest.approx(0.4)
    assert e["tf"] == "M5"


def test_detect_sweep_sellside():
    rows = [
        (100.0, 100.3, 99.9, 100.1),
        (100.1, 100.2, 99.8, 100.0),
        (100.0, 100.1, 98.5, 99.4),  # 2 barre 99.0 y cierra por encima
        (99.4, 99.6, 99.2, 99.5),
    ]
    df = _mk(rows)
    ev = detect_m1_liquidity_sweeps(df, [{"price": 99.0, "side": "low"}])
    assert [(e["index"], e["side"], e["direction"]) for e in ev] == [(2, "sellside", 1)]


def test_no_sweep_when_close_beyond_level():
    """Rotura sostenida (cierra mas alla) NO es sweep."""
    rows = [
        (100.0, 100.5, 99.9, 100.4),
        (100.4, 102.0, 100.3, 101.9),  # cierra por encima de 101.5 -> breakout real
    ]
    df = _mk(rows)
    assert detect_m1_liquidity_sweeps(df, [{"price": 101.5, "side": "high"}]) == []


def test_sweeps_sin_niveles_o_df_vacio(m1_zigzag):
    assert detect_m1_liquidity_sweeps(m1_zigzag, []) == []
    assert detect_m1_liquidity_sweeps(m1_zigzag.iloc[0:0], PARENT_SWINGS) == []


def test_sweeps_anti_look_ahead(m1_zigzag):
    """max_index recorta: nada antes de la vela del sweep; y prefijo == recorte."""
    assert detect_m1_liquidity_sweeps(m1_zigzag, PARENT_SWINGS, max_index=5) == []
    full = detect_m1_liquidity_sweeps(m1_zigzag, PARENT_SWINGS, max_index=6)
    assert [e["index"] for e in full] == [6]
    # detectar sobre el df truncado da el mismo resultado -> sin look-ahead
    trunc = detect_m1_liquidity_sweeps(m1_zigzag.iloc[:7], PARENT_SWINGS)
    assert [e["index"] for e in trunc] == [e["index"] for e in full]


# --- fakeouts ------------------------------------------------------------


def test_is_m1_fakeout_detecta_i12(m1_zigzag):
    assert is_m1_fakeout(m1_zigzag, 12, lookback=5) is True


def test_is_m1_fakeout_falso_en_vela_normal(m1_zigzag):
    assert is_m1_fakeout(m1_zigzag, 11, lookback=5) is False
    assert is_m1_fakeout(m1_zigzag, 13, lookback=5) is False


def test_is_m1_fakeout_bordes(m1_zigzag):
    assert is_m1_fakeout(m1_zigzag, 0, lookback=5) is False
    assert is_m1_fakeout(m1_zigzag, 2, lookback=5) is False  # lookback no cabe
    assert is_m1_fakeout(m1_zigzag, 999, lookback=5) is False
    assert is_m1_fakeout(m1_zigzag.iloc[0:0], 3) is False


def test_is_m1_fakeout_anti_look_ahead(m1_zigzag):
    """El resultado en i no cambia si se borran las velas posteriores a i."""
    for i in range(1, len(m1_zigzag)):
        full = is_m1_fakeout(m1_zigzag, i, lookback=4)
        cut = is_m1_fakeout(m1_zigzag.iloc[: i + 1], i, lookback=4)
        assert full == cut, f"look-ahead en i={i}"


def test_fakeout_bajista():
    rows = [
        (100.0, 100.4, 100.0, 100.3),
        (100.3, 100.5, 100.1, 100.2),
        (100.2, 100.4, 100.0, 100.1),
        (100.1, 100.3, 99.0, 100.2),  # rompe minimo 100.0 y cierra dentro
    ]
    df = _mk(rows)
    assert is_m1_fakeout(df, 3, lookback=3) is True


# --- momentum fino -------------------------------------------------------


def test_micro_momentum():
    rows = [
        (100.0, 100.3, 99.9, 100.2),
        (100.2, 100.6, 100.1, 100.5),
        (100.5, 100.9, 100.4, 100.8),
        (100.8, 100.9, 100.2, 100.3),
    ]
    df = _mk(rows)
    assert m1_micro_momentum(df, 2, window=3) == 1
    assert m1_micro_momentum(df, 3, window=3) == 0
    assert m1_micro_momentum(df, 0, window=3) == 0
    assert m1_micro_momentum(df.iloc[0:0], 0) == 0


def test_micro_momentum_bajista():
    rows = [
        (100.8, 100.9, 100.5, 100.6),
        (100.6, 100.7, 100.2, 100.3),
        (100.3, 100.4, 99.8, 99.9),
    ]
    df = _mk(rows)
    assert m1_micro_momentum(df, 2, window=3) == -1


# --- swings M1 -----------------------------------------------------------


def test_m1_swing_levels_anti_look_ahead(m1_zigzag):
    lv = m1_swing_levels(m1_zigzag, upto=8)
    lv_cut = m1_swing_levels(m1_zigzag.iloc[:9])
    assert lv == lv_cut
    assert m1_swing_levels(m1_zigzag.iloc[0:0]) == {"swing_high": None, "swing_low": None}
