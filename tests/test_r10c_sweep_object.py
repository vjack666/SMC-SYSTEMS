"""tests/test_r10c_sweep_object.py — SWEEP como MarketObject persistente.

RED: df_to_objects (via build_objects) DEBE producir MarketObject(type=SWEEP)
con zona (mecha que tomo la liquidez) y direccion coherente. Hoy no los produce.

Fuente unica de deteccion: canonical_sweep (columnas liquidity_sweep_* ya
presentes en el df). No se crea detector paralelo.
"""
from __future__ import annotations

import warnings

import pytest


@pytest.fixture(scope="module")
def h4_objs():
    warnings.filterwarnings("ignore")
    from ict_backtest.data_feed import load_frames, build_objects
    from ict_backtest.market_structure import detect_market_structure

    fr = load_frames("XAUUSD", ("H4",))
    h4 = detect_market_structure(fr["H4"]).iloc[:2000].reset_index(drop=True)
    return build_objects({"H4": h4}, symbol="XAUUSD")


def test_build_objects_produces_sweep_objects(h4_objs):
    from ict_backtest.market_object import ObjectType

    sweeps = [o for o in h4_objs if o.type == ObjectType.SWEEP]
    assert len(sweeps) > 0, "df_to_objects debe emitir SWEEP persistentes"


def test_sweep_has_zone_and_direction(h4_objs):
    from ict_backtest.market_object import ObjectType

    sweeps = [o for o in h4_objs if o.type == ObjectType.SWEEP]
    for s in sweeps:
        assert s.zone_high > 0 and s.zone_low > 0, "sweep debe tener zona de mecha"
        assert s.direction in (1, -1), "sweep debe tener direccion de setup"
        assert isinstance(s.bar_index, int) and s.bar_index >= 0


def test_sweep_direction_coherent_with_liquidity_side(h4_objs):
    from ict_backtest.market_object import ObjectType

    sweeps = [o for o in h4_objs if o.type == ObjectType.SWEEP]
    # sweep_down (barre SSL) => setup LONG (+1); sweep_up (barre BSL) => SHORT (-1).
    # Coherente con sequence._has_sweep (long busca sweep_down).
    for s in sweeps:
        side = s.meta.get("sweep_side")
        if side == "down":
            assert s.direction == 1
        elif side == "up":
            assert s.direction == -1
