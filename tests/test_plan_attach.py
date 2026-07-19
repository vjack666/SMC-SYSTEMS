"""RED — plan_attach: adjunta AlignmentReport a cada senal (Brecha A1, modo OBSERVE).

Loop driver nivel 2: por cada senal de generate_sequence_signals, calcula el
AlignmentReport multi-TF usando objetos/estructuras cerradas en sig.time y lo
ADJUNTA (no filtra). Funcion pura, testeable con datos sinteticos. El backtest
real (run_backtest.py) lo llamara solo con flag --attach-plan (default off).

Test FALLA hasta implementar ict_backtest/plan_attach.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)


def _obj(type, direction, tf, bar_index, role, oid, zh=0.0, zl=0.0):
    return MarketObject(type=type, direction=direction, origin_tf=tf, role=role,
                        state=ObjectState.ACTIVE, bar_index=bar_index, id=oid,
                        zone_high=zh, zone_low=zl)


def test_attach_alignment_marca_senal():
    from ict_backtest.plan_attach import attach_alignment

    senal = {"direction": 1, "time": 100, "bar_index": 100,
             "phase_log": ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]}
    # objetos por TF (cerrados, direction=1)
    objetos = {
        "D1": [_obj(ObjectType.LIQUIDITY, 1, "D1", 10, Role.CONTEXT, "d1")],
        "H4": [_obj(ObjectType.BOS, 1, "H4", 20, Role.REFINEMENT, "h4")],
        "H1": [_obj(ObjectType.ORDER_BLOCK, 1, "H1", 30, Role.POI, "h1")],
        "M15": [_obj(ObjectType.FVG, 1, "M15", 100, Role.REFINEMENT, "fvg",
                     zh=1.1030, zl=1.1020)],
    }
    # BOS H4 padre del FVG M15 -> ancla; zona discount -> ok zona
    attached = attach_alignment(senal, objetos, swing=(1.1100, 1.1000))
    rep = attached["alignment"]
    assert rep["d1"] is True and rep["h4"] is True and rep["h1"] is True
    assert rep["m15"] is True
    assert rep["m15_anchored"] is True
    # base 4 + 0.5 ancla + 0.5 zona discount = 5.0
    assert rep["score"] == 5.0


def test_attach_alignment_sin_ancla_marca_suelto():
    from ict_backtest.plan_attach import attach_alignment

    senal = {"direction": 1, "time": 100, "bar_index": 100,
             "phase_log": ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]}
    objetos = {
        "D1": [_obj(ObjectType.LIQUIDITY, 1, "D1", 10, Role.CONTEXT, "d1")],
        # H4 con CHOCH bajista (h4=True por ser estructural) pero direccion
        # opuesta al FVG M15 -> NO ancla (padre debe ser misma direccion)
        "H4": [_obj(ObjectType.CHOCH, -1, "H4", 20, Role.REFINEMENT, "h4")],
        "H1": [_obj(ObjectType.ORDER_BLOCK, 1, "H1", 30, Role.POI, "h1")],
        "M15": [_obj(ObjectType.FVG, 1, "M15", 100, Role.REFINEMENT, "fvg",
                     zh=1.1052, zl=1.1048)],  # zona EQ (ambigua, no bonifica)
    }
    # sin BOS H4/H1 padre del FVG -> no ancla; zona EQ -> no bonifica
    # score base 4, sin bonus
    attached = attach_alignment(senal, objetos, swing=(1.1100, 1.1000))
    rep = attached["alignment"]
    assert rep["m15_anchored"] is False
    assert rep["score"] == 4.0
