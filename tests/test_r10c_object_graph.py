"""tests/test_r10c_object_graph.py — Fase C (R10.C): grafo causal ObjectGraph.

RED: el grafo expone parent/children/opuesto por PUNTEROS (id), sin tiempo.
TDD estricto: el módulo ict_backtest.object_graph no existe aun.

Incluye INTEGRACION con Invalidators.B2 (bos_opuesto_en_misma_narrativa)
usando el grafo REAL (no el mock de test_r10c_invalidators).
"""
from __future__ import annotations

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    ObjectState,
    Role,
)
from ict_backtest.object_graph import ObjectGraph
from ict_backtest.invalidators import bos_opuesto_en_misma_narrativa


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


def _build_graph() -> ObjectGraph:
    g = ObjectGraph()
    sweep = _obj(ObjectType.SWEEP, 1, "sweep-1")
    bos = _obj(ObjectType.BOS, 1, "bos-1")
    fvg = _obj(ObjectType.FVG, 1, "fvg-1")
    bos_bajista = _obj(ObjectType.BOS, -1, "bos-2")
    g.add(sweep)
    g.add(bos)
    g.add(fvg)
    g.add(bos_bajista)
    # sweep -> bos -> fvg (cadena causal). bos_bajista es opuesto suelto.
    g.link(sweep, bos)
    g.link(bos, fvg)
    return g, sweep, bos, fvg, bos_bajista


def test_parents_children_by_pointer():
    g, sweep, bos, fvg, _ = _build_graph()
    assert g.parents(bos) == [sweep]
    assert g.children(sweep) == [bos]
    assert g.children(bos) == [fvg]
    # Sin tiempo: el grafo no sabe nada de bar_index.
    assert g.parents(fvg) == [bos]


def test_opuesto_en_narrativa_real():
    g, _, bos, _, bos_bajista = _build_graph()
    # B2 (invalidator) consulta el grafo REAL, no un mock.
    assert bos_opuesto_en_misma_narrativa(bos, g) is True
    # Un grafo sin opuesto -> False.
    g2 = ObjectGraph()
    solo = _obj(ObjectType.BOS, 1, "solo-1")
    g2.add(solo)
    assert bos_opuesto_en_misma_narrativa(solo, g2) is False


def test_graph_never_uses_bar_index():
    """El grafo navega por id/punteros, no por nº de vela (anti-timer)."""
    import inspect

    src = inspect.getsource(ObjectGraph)
    body = "\n".join(
        ln for ln in src.splitlines() if not ln.strip().startswith("#")
    )
    assert "bar_index" not in body, "ObjectGraph no debe leer bar_index (anti-timer)"
    assert " - " not in body, "ObjectGraph no debe restar índices"
