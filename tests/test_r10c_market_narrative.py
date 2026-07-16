"""tests/test_r10c_market_narrative.py — Fase D (R10.C): narrativa viva.

RED: agrupa la cadena causal sweep -> BOS -> FVG del grafo y marca como
RUIDO lo que queda suelto (sin narrativa vigente).

Criterio verificable del diseno (Fase D):
- FVG suelto (sin narrativa) => no produce senal (is_noise True).
- El mismo FVG dentro de narrativa VIGENTE => produce senal (is_noise False).
"""
from __future__ import annotations

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    ObjectState,
    Role,
)
from ict_backtest.object_graph import ObjectGraph
from ict_backtest.market_narrative import MarketNarrative


def _obj(type_: ObjectType, direction: int, oid: str) -> MarketObject:
    o = MarketObject(
        id=oid,
        type=type_,
        origin_tf="M15",
        role=Role.REFINEMENT,
        direction=direction,
        bar_index=100,
    )
    o.state = ObjectState.ACTIVE
    return o


def _chain_graph() -> tuple[ObjectGraph, MarketObject, MarketObject, MarketObject]:
    g = ObjectGraph()
    sweep = _obj(ObjectType.SWEEP, 1, "sweep-1")
    bos = _obj(ObjectType.BOS, 1, "bos-1")
    fvg = _obj(ObjectType.FVG, 1, "fvg-1")
    g.add(sweep)
    g.add(bos)
    g.add(fvg)
    g.link(sweep, bos)
    g.link(bos, fvg)
    return g, sweep, bos, fvg


def test_fvg_suelto_es_ruido_sin_narrativa():
    g, _, _, fvg = _chain_graph()
    # Sin narrativa: el FVG suelto es ruido (no produce senal).
    assert MarketNarrative.is_noise(fvg, []) is True


def test_fvg_en_narrativa_vigente_no_es_ruido():
    g, sweep, bos, fvg = _chain_graph()
    # Narrativa construida desde el sweep (raiz de la cadena causal).
    narr = MarketNarrative.from_root(g, sweep)
    assert narr.is_active() is True
    assert narr.contains(fvg) is True
    # El mismo FVG ahora es parte de narrativa vigente => no ruido.
    assert MarketNarrative.is_noise(fvg, [narr]) is False


def test_narrativa_agrupa_cadena_y_excluye_sueltos():
    g, sweep, bos, fvg = _chain_graph()
    suelto = _obj(ObjectType.FVG, -1, "fvg-suelto")
    g.add(suelto)
    narr = MarketNarrative.from_root(g, sweep)
    # La narrativa contiene la cadena, no el suelto.
    assert narr.contains(sweep) and narr.contains(bos) and narr.contains(fvg)
    assert narr.contains(suelto) is False
    # Solo los objetos en narrativa vigente son candidatos a senal.
    candidatos = narr.signal_objects()
    ids = {o.id for o in candidatos}
    assert "fvg-1" in ids
    assert "fvg-suelto" not in ids
