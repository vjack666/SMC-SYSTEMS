"""tests/test_r10c_state_machine.py — Fase A (R10.C): máquina de estados semántica.

RED: la StateMachine transiciona ObjectState por EVENTO del mercado,
NO por conteo de velas. Ningún assert usa índice - índice.
"""
from __future__ import annotations

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.state_machine import StateMachine, MarketEvent


def _bos() -> MarketObject:
    o = MarketObject(
        type=ObjectType.BOS,
        origin_tf="M15",
        role=Role.REFINEMENT,
        direction=1,
        bar_index=100,
    )
    return o


def _fvg() -> MarketObject:
    o = MarketObject(
        type=ObjectType.FVG,
        origin_tf="M15",
        role=Role.REFINEMENT,
        direction=1,
        zone_high=2000.0,
        zone_low=1990.0,
        bar_index=100,
    )
    return o


def test_swing_broken_invalidates_parent_bos():
    """Evento SwingBroken sobre el padre marca el BOS como INVALIDATED."""
    bos = _bos()
    sm = StateMachine()
    sm.apply(MarketEvent(type="StructureBroken", target=bos))
    assert bos.state == ObjectState.ACTIVE
    sm.apply(MarketEvent(type="SwingBroken", target=bos))
    assert bos.state == ObjectState.INVALIDATED


def test_return_to_zone_mitigates_fvg_not_kills():
    """Retorno a la zona mitiga el FVG (sigue vivo para entry), no lo mata."""
    fvg = _fvg()
    sm = StateMachine()
    sm.apply(MarketEvent(type="StructureBroken", target=fvg))  # confirma
    assert fvg.state == ObjectState.ACTIVE
    sm.apply(MarketEvent(type="ReturnToZone", target=fvg))
    assert fvg.state == ObjectState.MITIGATED


def test_state_machine_ignores_bar_index_for_transition():
    """La máquina decide por evento, no por índice de vela.

    Conductual (no grep frágil): cambiar bar_index del objetivo NO altera
    la transición. Si alguien introdujera `i - target.bar_index > N`,
    este test rompería porque la transición dependería del índice.
    """
    bos_a = _bos()
    bos_a.bar_index = 100
    sm_a = StateMachine()
    sm_a.apply(MarketEvent(type="StructureBroken", target=bos_a))
    sm_a.apply(MarketEvent(type="SwingBroken", target=bos_a))

    bos_b = _bos()
    bos_b.bar_index = 9_999_999  # índice totalmente distinto
    sm_b = StateMachine()
    sm_b.apply(MarketEvent(type="StructureBroken", target=bos_b))
    sm_b.apply(MarketEvent(type="SwingBroken", target=bos_b))

    # Misma secuencia de eventos -> misma transición, sin importar bar_index.
    assert bos_a.state == bos_b.state == ObjectState.INVALIDATED
