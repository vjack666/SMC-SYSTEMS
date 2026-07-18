"""Fase E — E1 tests: cohorts + statistics_engine (sintéticos, sin contexts reales).

Condiciones de Ruben cubiertas:
- #1/#2: cohorts leen SOLO market_context congelado (la entrada), no pnl ni post-cierre.
- #3: toda estadística muestra n y advierte si n < MIN_N (30).
- #4: statistics NO elige el mejor cohort; reporta todos.
"""

import pytest

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame
from ict_backtest.diagnostics import cohorts as _cohorts
from ict_backtest.diagnostics.statistics_engine import (
    compute, MIN_N, StatisticsReport, CohortStat,
)


def _frame(tf, bias="RANGING", **kw):
    return MarketContextFrame(tf=tf, available=True, bias=bias, **kw)


def _ctx(direction: int, pnl: float, frames: dict) -> TradeContext:
    return TradeContext(
        backtest_id="BT-TEST", trade_id="t", signal_id="s",
        symbol="SYN", direction=direction, pnl_r=pnl,
        htf_trend=frames.get("D1", _frame("D1")).bias,
        market_context=frames,
    )


def test_htf_alignment_aligned():
    frames = {
        "D1": _frame("D1", "BULLISH"),
        "H4": _frame("H4", "BULLISH"),
        "H1": _frame("H1", "BULLISH"),
        "M15": _frame("M15"), "M5": _frame("M5"), "M1": _frame("M1"),
    }
    c = _ctx(1, 1.0, frames)
    assert _cohorts.htf_alignment(c) == "aligned"


def test_htf_alignment_not_when_divergent():
    frames = {
        "D1": _frame("D1", "BULLISH"),
        "H4": _frame("H4", "BEARISH"),
        "H1": _frame("H1", "BULLISH"),
        "M15": _frame("M15"), "M5": _frame("M5"), "M1": _frame("M1"),
    }
    c = _ctx(1, 1.0, frames)
    assert _cohorts.htf_alignment(c) == "not"


def test_htf_alignment_unknown_when_missing_tf():
    frames = {"H4": _frame("H4", "BULLISH"), "M15": _frame("M15")}
    # D1 y H1 ausentes => unknown (no se inventa alineación)
    c = _ctx(1, 1.0, frames)
    assert _cohorts.htf_alignment(c) == "unknown"


def test_has_htf_poi_yes_and_no():
    with_poi = _ctx(1, 1.0, {"D1": _frame("D1"), "H4": _frame("H4", poi="PD"),
                              "M15": _frame("M15")})
    assert _cohorts.has_htf_poi(with_poi) == "yes"
    without = _ctx(1, 1.0, {"D1": _frame("D1"), "H4": _frame("H4", poi="DISCOUNT"),
                            "M15": _frame("M15")})
    assert _cohorts.has_htf_poi(without) == "no"


def test_m5_confirms_uses_direction_not_pnl():
    # dirección +1 y M5 BULLISH => yes. Se prueba que NO mira pnl (ponemos pnl negativo)
    frames = {"M15": _frame("M15"), "M5": _frame("M5", confirmation="BULLISH")}
    c = _ctx(1, -1.0, frames)  # pnl negativo a propósito
    assert _cohorts.m5_confirms(c) == "yes"


def test_statistics_reports_all_cohorts_and_n():
    ctxs = []
    for i in range(40):
        bull = (i % 2 == 0)
        frames = {
            "D1": _frame("D1", "BULLISH" if bull else "BEARISH"),
            "H4": _frame("H4", "BULLISH" if bull else "BEARISH"),
            "H1": _frame("H1", "BULLISH" if bull else "BEARISH"),
            "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH" if bull else "BEARISH"),
            "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1 if bull else -1, 1.0 if bull else -1.0, frames))
    rep = compute(ctxs)
    assert isinstance(rep, StatisticsReport)
    assert rep.overall.n == 40
    # cada cohort tiene sus categorías reportadas (no solo una)
    names = {cs.name for cs in rep.cohorts}
    assert "htf_alignment" in names
    assert "has_htf_poi" in names
    # n total de cohortes == n total de contexts (cada ctx cae en 1 cat por faceta)
    for name in ("htf_alignment", "m5_confirms"):
        total = sum(cs.n for cs in rep.cohorts if cs.name == name)
        assert total == 40


def test_statistics_warns_when_n_low():
    # solo 10 contexts => toda cohorte < MIN_N => can_conclude False
    ctxs = []
    for i in range(10):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"),
            "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, 1.0, frames))
    rep = compute(ctxs)
    assert rep.overall.n == 10
    for cs in rep.cohorts:
        assert cs.can_conclude is False
        assert f"n={cs.n} < {MIN_N}" in cs.warn


def test_statistics_does_not_pick_best_cohort():
    """Condición #4: el reporte NO contiene un campo 'best' ni elige ganador."""
    ctxs = []
    for i in range(40):
        bull = (i % 2 == 0)
        frames = {
            "D1": _frame("D1", "BULLISH" if bull else "BEARISH"),
            "H4": _frame("H4", "BULLISH" if bull else "BEARISH"),
            "H1": _frame("H1", "BULLISH" if bull else "BEARISH"),
            "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH" if bull else "BEARISH"),
            "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1 if bull else -1, 1.0 if bull else -1.0, frames))
    rep = compute(ctxs)
    assert not hasattr(rep, "best")
    assert not hasattr(rep, "winner")
