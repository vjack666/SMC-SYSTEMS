"""tests/test_r10c_invalidators.py — Fase B1 (R10.C): predicados de invalidación semántica.

RED: los Invalidators deciden por RELACIÓN DE PRECIO / CONTEXTO,
NUNCA por nº de velas ni conteo temporal.
"""
from __future__ import annotations

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    ObjectState,
    Role,
)
from ict_backtest.invalidators import (
    rompio_swing_que_defendia,
    liquidez_tomada_sin_continuacion,
    bos_opuesto_en_misma_narrativa,
)


class _FakeGraph:
    """Grafo mock (duck-typed) para testar B2 sin acoplar a Fase C.

    Implementa solo lo que B2 necesita: 'opuesto_en' devuelve el
    BOS de dirección contraria en la misma narrativa, o None.
    """

    def __init__(self, opuesto: MarketObject | None = None):
        self._opuesto = opuesto

    def opuesto_en(self, obj: MarketObject) -> MarketObject | None:
        return self._opuesto


def _bos(direction: int, swing: float) -> MarketObject:
    o = MarketObject(
        type=ObjectType.BOS,
        origin_tf="M15",
        role=Role.REFINEMENT,
        direction=direction,
        zone_high=swing + 2.0,
        zone_low=swing - 2.0,
        meta={"swing_defended": swing},
        bar_index=100,
    )
    o.state = ObjectState.ACTIVE
    return o


def _ctx(*closes: float) -> list[MarketObject]:
    out = []
    for i, c in enumerate(closes):
        v = MarketObject(
            type=ObjectType.CANDLE,
            origin_tf="M15",
            direction=0,
            bar_index=i,
        )
        v.meta["close"] = c
        out.append(v)
    return out


def test_rompio_swing_por_precio_no_por_velas():
    bos = _bos(direction=1, swing=2000.0)
    ctx_down = _ctx(1995.0, 1992.0, 1988.0)
    assert rompio_swing_que_defendia(bos, ctx_down) is True
    ctx_up = _ctx(2005.0, 2010.0, 2015.0)
    assert rompio_swing_que_defendia(bos, ctx_up) is False


def test_liquidez_tomada_sin_continuacion():
    bos = _bos(direction=1, swing=2000.0)
    ctx_taken_no_follow = _ctx(1999.0, 1996.0, 1994.0)
    assert liquidez_tomada_sin_continuacion(bos, ctx_taken_no_follow) is True
    ctx_taken_follow = _ctx(1999.0, 2003.0, 2008.0)
    assert liquidez_tomada_sin_continuacion(bos, ctx_taken_follow) is False


def test_bos_opuesto_en_misma_narrativa():
    """True si hay un BOS de dirección opuesta en la misma narrativa.

    B2 usa el grafo (duck-typed): pregunta `graph.opuesto_en(obj)`.
    NO mira índices ni nº de velas. El grafo mock devuelve el opuesto.
    """
    bos_alcista = _bos(direction=1, swing=2000.0)

    bos_bajista = _bos(direction=-1, swing=2000.0)
    g_con_opuesto = _FakeGraph(opuesto=bos_bajista)
    assert bos_opuesto_en_misma_narrativa(bos_alcista, g_con_opuesto) is True

    g_sin_opuesto = _FakeGraph(opuesto=None)
    assert bos_opuesto_en_misma_narrativa(bos_alcista, g_sin_opuesto) is False
