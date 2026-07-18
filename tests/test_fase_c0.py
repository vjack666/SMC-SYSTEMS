"""Tests Fase C0 (TDD) — plumbing HTF de PD arrays.

ROJO primero: este test DEBE fallar si htf_pd_index.py no hace lo que el
Contrato de no invasión exige. Luego se pone verde con la implementación.

No toca R7 ni decide nada: solo indexa lo que los detectores ya marcaron.
"""

import numpy as np
import pandas as pd
import pytest

from ict_backtest.htf_pd_index import HtfPdIndex, HtfPdZone


def _make_htf_df():
    """HTF mínimo con 3 velas: FVG bullish en i=2, OB bullish en i=1.

    Usa columnas que los detectores (fvg.py/ob.py) esperan de un DataFrame crudo.
    """
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = [
        # i=0
        dict(time=t0 + pd.Timedelta(hours=4 * 0), open=100.0, high=101.0, low=99.0, close=100.5, volume=1),
        # i=1: OB bullish de impulso (cuerpo fuerte, seguido de cierre mayor)
        dict(time=t0 + pd.Timedelta(hours=4 * 1), open=100.5, high=102.0, low=100.0, close=101.8, volume=1),
        # i=2: vela pequeña que deja FVG bullish respecto a i=0 (low > prev2_high)
        dict(time=t0 + pd.Timedelta(hours=4 * 2), open=101.8, high=102.0, low=101.5, close=101.9, volume=1),
    ]
    return pd.DataFrame(rows)


def test_index_lists_declared_timeframes():
    """El indice registra los TF HTF pasados (sin LTF)."""
    df = _make_htf_df()
    idx = HtfPdIndex({"H4": df})
    assert idx.timeframes == ["H4"]


def test_index_empty_timeframe_ignored():
    idx = HtfPdIndex({"H4": None})
    assert idx.timeframes == []


def test_zones_at_closed_only_no_lookahead():
    """A la vela H4 i=2 (donde nació el FVG), la zona debe estar vigente.

    Verifica que el indice consulta la barra HTF ya cerrada (closed-only),
    no inventa zonas (Contrato §1: C no crea zonas). Usa build_ltf_map
    (O(n)) + zonas_at(i) (O(1)).
    """
    df = _make_htf_df()
    idx = HtfPdIndex({"H4": df})
    # LTF cuya barra cae DENTRO de H4 i=2 (open=00:00+8h=08:00, +15min).
    # Con cutoff cerrado (resta 4h) el merge asof alcanza H4 i=2 ya cerrada.
    ltf_time = df.iloc[2]["time"] + pd.Timedelta(minutes=15)
    ltf = pd.DataFrame({"time": [ltf_time]})
    ltf_map = idx.build_ltf_map(ltf)
    zones = idx.zones_at(0, "H4", ltf_map)
    assert len(zones) >= 1
    bull = [z for z in zones if z.direction == 1]
    assert bull, "no se detectó zona bullish del HTF"
    assert all(z.pd_type in ("FVG", "OB", "BPR", "REJECTION_BLOCK", "MITIGATION_BLOCK", "BREAKER") for z in zones)


def test_no_future_leak_on_earlier_bar():
    """En una vela LTF que cae DENTRO de la barra H4 i=2 (aún no cerrada),
    el closed_merge_asof no debe devolver el FVG de i=2 (anti look-ahead)."""
    df = _make_htf_df()
    idx = HtfPdIndex({"H4": df})
    # LTF con 3 barras: idx 0..2. La barra i=2 del LTF cae DENTRO de la
    # barra H4 i=2 (no sumamos duración => el merge asof cerrado no la alcanza).
    ltf = pd.DataFrame({"time": [
        df.iloc[2]["time"] + pd.Timedelta(minutes=30),  # dentro de H4 i=2
    ]})
    ltf_map = idx.build_ltf_map(ltf)
    zones = idx.zones_at(0, "H4", ltf_map)
    # El FVG de i=2 (zone_high 102.0) NO debe aparecer como vigente aquí.
    fvg_at_i2 = [z for z in zones if z.pd_type == "FVG" and z.zone_high > 102.0]
    assert not fvg_at_i2, "look-ahead: se leyó FVG de barra HTF aún no cerrada"


def test_htf_pd_zone_frozen_semantics():
    z = HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2", direction=1,
                   zone_high=102.0, zone_low=101.5)
    assert z.tf == "H4"
    assert z.direction == 1
