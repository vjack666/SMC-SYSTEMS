"""Fase E — E4 tests: diagnosis_report orquestador (integracion con sinteticos).

Confirma que diagnosis_report.py es SOLO orquestador:
- Ejecuta la cadena completa sobre contexts sinteticos.
- No altera la cadena, no filtra, no elige "mejor".
- Devuelve los 3 reportes con sus datos intactos.
"""

import pytest

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame
from ict_backtest.diagnostics.diagnosis_report import run, DiagnosisReport
from ict_backtest.diagnostics.statistics_engine import StatisticsReport
from ict_backtest.diagnostics.correlation_engine import CorrelationReport
from ict_backtest.diagnostics.hypothesis_engine import HypothesisReport


def _frame(tf, bias="RANGING", **kw):
    return MarketContextFrame(tf=tf, available=True, bias=bias, **kw)


def _ctx(direction, pnl, frames):
    return TradeContext(
        backtest_id="BT-TEST", trade_id="t", signal_id="s",
        symbol="SYN", direction=direction, pnl_r=pnl,
        htf_trend=frames.get("D1", _frame("D1")).bias,
        market_context=frames,
    )


def _bulk(aw, al, mw, ml):
    ctxs = []
    for _ in range(aw):
        f = {"D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
             "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
             "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1")}
        ctxs.append(_ctx(1, 1.0, f))
    for _ in range(al):
        f = {"D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
             "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
             "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1")}
        ctxs.append(_ctx(1, -1.0, f))
    for _ in range(mw):
        f = {"D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BEARISH"),
             "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
             "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1")}
        ctxs.append(_ctx(1, 1.0, f))
    for _ in range(ml):
        f = {"D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BEARISH"),
             "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
             "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1")}
        ctxs.append(_ctx(1, -1.0, f))
    return ctxs


def test_orchestrator_returns_all_three_reports():
    ctxs = _bulk(30, 10, 10, 30)
    rep = run(ctxs)
    assert isinstance(rep, DiagnosisReport)
    assert isinstance(rep.statistics, StatisticsReport)
    assert isinstance(rep.correlation, CorrelationReport)
    assert isinstance(rep.hypothesis, HypothesisReport)
    # cadena coherente: n del overall == n total de contexts
    assert rep.statistics.overall.n == 80


def test_orchestrator_is_pure_pass_through():
    # los datos de correlation/hypothesis deben ser los que producen los motores
    ctxs = _bulk(30, 10, 10, 30)
    rep = run(ctxs)
    # hypothesis reporta todas las asociaciones concluyentes + cohortes
    assert len(rep.hypothesis.hypotheses) >= 1
    # correlation trae asociaciones ordenadas por |coef|
    assert rep.correlation.associations
    # NO hay campo 'best'/'winner' en ningún reporte
    assert not hasattr(rep, "best")
    assert not hasattr(rep.hypothesis, "best")
