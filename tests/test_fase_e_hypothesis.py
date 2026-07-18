"""Fase E — E3 tests: hypothesis_engine (consume reportes, no contexts reales).

Condiciones de Ruben cubiertas:
- #1: NO integra contexts reales (se construyen reportes sinteticos a mano).
- #2: NO genera reglas de trading ni toca lógica de entrada.
- #3: HypothesisEngine solo consume StatisticsReport + CorrelationReport.
- #4: cada Hypothesis trae statement/evidence_for/evidence_against/n/metrics/confidence.
- #5: NO elige "la mejor"; reporta TODAS rankeadas; no-concluyente => inconclusive.
"""

import pytest

from ict_backtest.diagnostics.statistics_engine import (
    StatisticsReport, OverallStat, CohortStat, Comparison,
)
from ict_backtest.diagnostics.correlation_engine import (
    CorrelationReport, Association,
)
from ict_backtest.diagnostics.hypothesis_engine import (
    compute, HypothesisReport, Hypothesis,
)


def _stats(cohorts):
    return StatisticsReport(
        overall=OverallStat(n=80, win_rate=0.5, pf=1.0, avg_r=0.0, expectancy_r=0.0),
        cohorts=cohorts,
        comparisons=[],
    )


def _corr(assocs):
    return CorrelationReport(outcome="win", associations=assocs)


def test_hypothesis_consumes_reports_not_contexts():
    # solo pasamos reportes; el motor no recibe lista de TradeContext
    s = _stats([])
    c = _corr([])
    rep = compute(s, c)
    assert isinstance(rep, HypothesisReport)
    assert isinstance(rep.hypotheses, list)
    assert isinstance(rep.inconclusive, list)


def test_hypothesis_reports_all_with_required_fields():
    cohorts = [
        CohortStat("htf_alignment", "aligned", n=40, win_rate=0.75, pf=1.6,
                   avg_r=0.3, ci95_low=0.60, ci95_high=0.87, can_conclude=True, warn=""),
        CohortStat("htf_alignment", "not", n=40, win_rate=0.35, pf=0.9,
                   avg_r=-0.1, ci95_low=0.21, ci95_high=0.50, can_conclude=True, warn=""),
    ]
    assocs = [
        Association("htf_alignment", "aligned", "win", coef=0.5, n=80,
                    strength="strong", can_conclude=True, warn=""),
    ]
    rep = compute(_stats(cohorts), _corr(assocs))
    assert rep.hypotheses, "debe generar al menos una hipótesis"
    h = rep.hypotheses[0]
    assert isinstance(h, Hypothesis)
    # campos obligatorios presentes y no vacíos
    assert h.statement
    assert h.evidence_for
    assert h.evidence_against
    assert h.n > 0
    assert h.metrics
    assert h.confidence in ("low", "medium", "high")
    # una hipótesis de cohorte + una de asociación => 2 reportadas
    assert len(rep.hypotheses) == 2


def test_hypothesis_does_not_pick_best():
    cohorts = [
        CohortStat("htf_alignment", "aligned", n=40, win_rate=0.75, pf=1.6,
                   avg_r=0.3, ci95_low=0.60, ci95_high=0.87, can_conclude=True, warn=""),
        CohortStat("htf_alignment", "not", n=40, win_rate=0.35, pf=0.9,
                   avg_r=-0.1, ci95_low=0.21, ci95_high=0.50, can_conclude=True, warn=""),
        CohortStat("m5_confirms", "yes", n=40, win_rate=0.60, pf=1.2,
                   avg_r=0.1, ci95_low=0.45, ci95_high=0.73, can_conclude=True, warn=""),
        CohortStat("m5_confirms", "no", n=40, win_rate=0.40, pf=0.8,
                   avg_r=-0.05, ci95_low=0.26, ci95_high=0.55, can_conclude=True, warn=""),
    ]
    assocs = [
        Association("htf_alignment", "aligned", "win", coef=0.5, n=80,
                    strength="strong", can_conclude=True, warn=""),
        Association("m5_confirms", "yes", "win", coef=0.2, n=80,
                    strength="small", can_conclude=True, warn=""),
    ]
    rep = compute(_stats(cohorts), _corr(assocs))
    # NO hay campo 'best' ni 'winner'
    assert not hasattr(rep, "best")
    assert not hasattr(rep, "winner")
    # reporta TODAS las cohortes (2 pares) + TODAS las asociaciones (2)
    assert len(rep.hypotheses) == 4


def test_hypothesis_moves_inconclusive():
    # n bajo => can_conclude False en ambos motores => va a inconclusive
    cohorts = [
        CohortStat("htf_alignment", "aligned", n=10, win_rate=0.7, pf=1.5,
                   avg_r=0.2, ci95_low=0.4, ci95_high=0.9, can_conclude=False,
                   warn="n=10 < 30: muestra insuficiente"),
        CohortStat("htf_alignment", "not", n=10, win_rate=0.3, pf=0.8,
                   avg_r=-0.1, ci95_low=0.1, ci95_high=0.6, can_conclude=False,
                   warn="n=10 < 30: muestra insuficiente"),
    ]
    assocs = [
        Association("htf_alignment", "aligned", "win", coef=0.4, n=20,
                    strength="moderate", can_conclude=False,
                    warn="n=20 < 30: no concluyente"),
    ]
    rep = compute(_stats(cohorts), _corr(assocs))
    assert rep.hypotheses == []  # nada concluyente
    assert len(rep.inconclusive) >= 2  # cohorte + asociación


def test_hypothesis_confidence_levels_present():
    cohorts = [
        CohortStat("htf_alignment", "aligned", n=40, win_rate=0.9, pf=2.0,
                   avg_r=0.5, ci95_low=0.78, ci95_high=0.96, can_conclude=True, warn=""),
        CohortStat("htf_alignment", "not", n=40, win_rate=0.3, pf=0.7,
                   avg_r=-0.2, ci95_low=0.18, ci95_high=0.45, can_conclude=True, warn=""),
    ]
    # asociación fuerte => high; cohorte con delta grande => high
    assocs = [
        Association("htf_alignment", "aligned", "win", coef=0.6, n=80,
                    strength="strong", can_conclude=True, warn=""),
    ]
    rep = compute(_stats(cohorts), _corr(assocs))
    confs = {h.confidence for h in rep.hypotheses}
    assert "high" in confs
    # rankeado: high primero
    assert rep.hypotheses[0].confidence == "high"
