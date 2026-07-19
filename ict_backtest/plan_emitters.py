"""ict_backtest/plan_emitters.py — Fase 1: emisores por TF (D1/H4/H1).

Funciones PURAS que reciben SOLO los MarketObjects de su propio TF y
devuelven un PlanEvent. NUNCA consultan frames de otro TF (regla de
desacoplamiento de ARQUITECTURA_TEMPORALIDADES.md).

El loop driver (run_backtest) orquesta: pasa a cada emisor los objetos
de su TF y alimenta los eventos a PlanFSM en orden causal. Los emisores
no saben de la existencia de los otros TF.
"""

from __future__ import annotations

from typing import Sequence

from ict_backtest.market_object import MarketObject, ObjectState, ObjectType, Role
from ict_backtest.plan_fsm import PlanEvent, PlanVerdict


def _bar_index_of(objs: Sequence[MarketObject]) -> int:
    idxs = [o.bar_index for o in objs if o.bar_index is not None]
    return max(idxs) if idxs else 0


def emit_d1(objs: Sequence[MarketObject]) -> PlanEvent:
    """Contexto macro (D1). CONTEXT_OK si hay estructura de contexto."""
    if not objs:
        return PlanEvent("D1", PlanVerdict.CONTEXT_INVALID, bar_index=0)
    return PlanEvent("D1", PlanVerdict.CONTEXT_OK, bar_index=_bar_index_of(objs))


def emit_h4(objs: Sequence[MarketObject]) -> PlanEvent:
    """Bias intradia (H4). CONTEXT_OK si hay BOS/CHOCH activo."""
    if not objs:
        return PlanEvent("H4", PlanVerdict.CONTEXT_INVALID, bar_index=0)
    hay_bias = any(
        o.type in (ObjectType.BOS, ObjectType.CHOCH)
        and o.state in (ObjectState.ACTIVE, ObjectState.CREATED)
        for o in objs
    )
    if not hay_bias:
        return PlanEvent("H4", PlanVerdict.CONTEXT_INVALID, bar_index=_bar_index_of(objs))
    return PlanEvent("H4", PlanVerdict.CONTEXT_OK, bar_index=_bar_index_of(objs))


def emit_h1(objs: Sequence[MarketObject]) -> PlanEvent:
    """Validacion POI (H1). ZONE_ARMED si hay POI (OB/FVG) en H1."""
    if not objs:
        return PlanEvent("H1", PlanVerdict.ZONE_INVALID, bar_index=0)
    hay_poi = any(
        o.role is Role.POI
        and o.type in (ObjectType.ORDER_BLOCK, ObjectType.FVG)
        and o.state in (ObjectState.ACTIVE, ObjectState.CREATED)
        for o in objs
    )
    if not hay_poi:
        return PlanEvent("H1", PlanVerdict.ZONE_INVALID, bar_index=_bar_index_of(objs))
    return PlanEvent("H1", PlanVerdict.ZONE_ARMED, bar_index=_bar_index_of(objs))
