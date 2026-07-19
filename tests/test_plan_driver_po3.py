"""RED — po3 bonus en AlignmentReport (Brecha E, modo OBSERVE).

Si el dia tiene PO3 completo (A/M/D alineado) en la direccion del setup,
score_plan suma +0.5 (bonus, no filtro). Test FALLA hasta agregar po3_complete
a score_plan / plan_attach.
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


def _objs(tf, type=ObjectType.BOS, role=Role.REFINEMENT, direction=1):
    return [MarketObject(type=type, direction=direction, origin_tf=tf, role=role,
                        state=ObjectState.ACTIVE)]


def _sig():
    return {"direction": 1, "phase_log": ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]}


def test_score_con_po3_completo_suma_bonus():
    from ict_backtest.plan_driver import score_plan

    rep = score_plan(
        _sig(),
        d1_objs=_objs("D1", ObjectType.LIQUIDITY, Role.CONTEXT),
        h4_objs=_objs("H4", ObjectType.BOS),
        h1_objs=_objs("H1", ObjectType.ORDER_BLOCK, Role.POI),
        m15_signal=_sig(), m5_confirm={"direction": 1, "confirmed": False},
        m1_trigger={"direction": 1, "confirmed": False}, po3_complete=True,
    )
    # base 4 + 0.5 po3 = 4.5
    assert rep.score == 4.5
    assert rep.po3_complete is True


def test_score_sin_po3_no_suma_bonus():
    from ict_backtest.plan_driver import score_plan

    rep = score_plan(
        _sig(),
        d1_objs=_objs("D1", ObjectType.LIQUIDITY, Role.CONTEXT),
        h4_objs=_objs("H4", ObjectType.BOS),
        h1_objs=_objs("H1", ObjectType.ORDER_BLOCK, Role.POI),
        m15_signal=_sig(), m5_confirm={"direction": 1, "confirmed": False},
        m1_trigger={"direction": 1, "confirmed": False}, po3_complete=False,
    )
    assert rep.score == 4.0
    assert rep.po3_complete is False
