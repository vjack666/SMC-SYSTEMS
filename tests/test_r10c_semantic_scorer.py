"""tests/test_r10c_semantic_scorer.py — Fase F: IA sobre entidades (R11 puro).

RED: un modulo de scoring que recibe MarketObject[] + narrativa y produce
calidad/confianza derivada del ESTADO + NARRATIVA + RELACIONES (entidades),
NO de features de vela aisladas (OHLC).

Criterio verificable: la ENTRADA del scorer son objetos/narrativa, nunca un
DataFrame de OHLC. El score de una estructura se deriva de su estado, su
narrativa causal (sweep -> bos) y sus relaciones en el grafo, no de Precio
aislado.

Requisitos del test:
- SemanticScorer.score(objects, narrative) existe y devuelve un float en [0,1].
- La entrada NO es un DataFrame: si se pasa un DataFrame, debe rechazarse
  (TypeError) o ignorarse; el contrato es entidades, no velas.
- El score de una narrativa completa (sweep->bos valido) es mayor que el de
  una estructura suelta (ruido) con el mismo objeto aislado.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.market_object import MarketObject, ObjectType, ObjectState


def _make_sweep(idx: int) -> MarketObject:
    return MarketObject(
        id=f"sw-{idx}",
        type=ObjectType.SWEEP,
        direction=1,
        origin_tf="H4",
        bar_index=idx,
        zone_high=1900.0,
        zone_low=1890.0,
        state=ObjectState.ACTIVE,
    )


def _make_bos(idx: int, parent_id: str | None = None) -> MarketObject:
    return MarketObject(
        id=f"bos-{idx}",
        type=ObjectType.BOS,
        direction=1,
        origin_tf="H4",
        bar_index=idx,
        zone_high=1910.0,
        zone_low=1905.0,
        state=ObjectState.ACTIVE,
        parent_object=parent_id,
    )


def test_semantic_scorer_receives_entities_not_ohlc():
    """La entrada del scorer son entidades, no un DataFrame OHLC."""
    from ict_backtest.semantic_scorer import SemanticScorer

    sweep = _make_sweep(100)
    bos = _make_bos(110, parent_id=sweep.id)
    narrative = [sweep, bos]

    scorer = SemanticScorer()
    score = scorer.score(narrative, narrative_root=sweep)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0

    # Rechazar DataFrame como entrada de entidades.
    df = pd.DataFrame({"open": [1], "high": [2], "low": [1], "close": [1]})
    with pytest.raises(TypeError):
        scorer.score(df, narrative_root=sweep)  # type: ignore[arg-type]


def test_semantic_scorer_favors_complete_narrative_over_noise():
    """Narrativa completa (sweep->bos) puntua mas que estructura suelta."""
    from ict_backtest.semantic_scorer import SemanticScorer

    sweep = _make_sweep(100)
    bos = _make_bos(110, parent_id=sweep.id)
    complete = [sweep, bos]

    bos_lone = _make_bos(110)  # sin padre -> ruido
    lone = [bos_lone]

    scorer = SemanticScorer()
    s_complete = scorer.score(complete, narrative_root=sweep)
    s_lone = scorer.score(lone, narrative_root=bos_lone)

    assert s_complete > s_lone, (
        f"narrativa completa ({s_complete}) no puntua mas que ruido ({s_lone})"
    )
