"""RED — Fase 1: emisores por TF (D1/H4/H1) como funciones puras.

El emisor recibe SOLO sus MarketObjects y devuelve un PlanEvent.
NO consulta frames de otro TF. Test FALLA hasta implementar emisores.
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
from ict_backtest.plan_fsm import PlanEvent, PlanVerdict


def _obj(obj_type: ObjectType, direction: int, tf: str, role: Role = Role.REFINEMENT) -> MarketObject:
    return MarketObject(
        type=obj_type,
        direction=direction,
        origin_tf=tf,
        role=role,
        state=ObjectState.ACTIVE,
    )


def test_emit_h4_context_ok_cuando_hay_bos():
    from ict_backtest.plan_emitters import emit_h4

    objs = [_obj(ObjectType.BOS, 1, "H4")]
    ev = emit_h4(objs)
    assert isinstance(ev, PlanEvent)
    assert ev.layer == "H4"
    assert ev.verdict is PlanVerdict.CONTEXT_OK


def test_emit_h4_context_invalid_cuando_vacio():
    from ict_backtest.plan_emitters import emit_h4

    ev = emit_h4([])
    assert ev.verdict is PlanVerdict.CONTEXT_INVALID


def test_emit_h1_zone_armed_cuando_hay_poi():
    from ict_backtest.plan_emitters import emit_h1

    objs = [_obj(ObjectType.ORDER_BLOCK, 1, "H1", role=Role.POI)]
    ev = emit_h1(objs)
    assert ev.layer == "H1"
    assert ev.verdict is PlanVerdict.ZONE_ARMED


def test_emit_h1_zone_invalid_cuando_vacio():
    from ict_backtest.plan_emitters import emit_h1

    ev = emit_h1([])
    assert ev.verdict is PlanVerdict.ZONE_INVALID


def test_emit_d1_context_ok_cuando_hay_objetos():
    from ict_backtest.plan_emitters import emit_d1

    objs = [_obj(ObjectType.LIQUIDITY, 1, "D1", role=Role.CONTEXT)]
    ev = emit_d1(objs)
    assert ev.layer == "D1"
    assert ev.verdict is PlanVerdict.CONTEXT_OK
