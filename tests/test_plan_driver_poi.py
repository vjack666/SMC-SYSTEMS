"""RED — score_plan bonus por POI anclado (Brecha B como bonus en el score).

Si el POI del M15 esta anclado a narrativa HTF padre, score_plan suma +0.5
(bonus, no condicion). Test FALLA hasta agregar m15_anchored a score_plan.
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


def _objs(tf, type=None):
    # objetos que los emisores aceptan (igual que test_plan_driver base)
    if tf == "D1":
        return [MarketObject(type=ObjectType.LIQUIDITY, direction=1, origin_tf="D1",
                             role=Role.CONTEXT, state=ObjectState.ACTIVE)]
    if tf == "H4":
        return [MarketObject(type=ObjectType.BOS, direction=1, origin_tf="H4",
                             role=Role.REFINEMENT, state=ObjectState.ACTIVE)]
    if tf == "H1":
        return [MarketObject(type=ObjectType.ORDER_BLOCK, direction=1, origin_tf="H1",
                             role=Role.POI, state=ObjectState.ACTIVE)]
    return []


def _sig():
    return {"direction": 1, "phase_log": ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]}


def test_score_con_poi_anclado_suma_bonus():
    from ict_backtest.plan_driver import score_plan

    rep = score_plan(
        _sig(),
        d1_objs=_objs("D1"), h4_objs=_objs("H4"), h1_objs=_objs("H1"),
        m15_signal=_sig(), m5_confirm={"direction": 1, "confirmed": False},
        m1_trigger={"direction": 1, "confirmed": False}, m15_anchored=True,
    )
    # base 4 (D1+H4+H1+M15) + 0.5 ancla = 4.5
    assert rep.score == 4.5
    assert rep.m15_anchored is True


def test_score_sin_poi_anclado_no_suma_bonus():
    from ict_backtest.plan_driver import score_plan

    rep = score_plan(
        _sig(),
        d1_objs=_objs("D1"), h4_objs=_objs("H4"), h1_objs=_objs("H1"),
        m15_signal=_sig(), m5_confirm={"direction": 1, "confirmed": False},
        m1_trigger={"direction": 1, "confirmed": False}, m15_anchored=False,
    )
    # base 4, sin bonus de ancla
    assert rep.score == 4.0
    assert rep.m15_anchored is False
