"""Fase E — E2 tests: correlation_engine (sinteticos, sin contexts reales).

Condiciones de Ruben cubiertas:
- #1: solo consume TradeContext v2 (market_context), no crea faceta con pnl.
- #2: NO interpreta/genera hipótesis (solo mide asociaciones).
- #3: cada Association trae feature/outcome/coef/n/strength/can_conclude.
- #4: marca can_conclude=False + warn cuando n < MIN_N o sin contraste.
"""

import pytest

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame
from ict_backtest.diagnostics.correlation_engine import (
    compute, MIN_N, Association, CorrelationReport, _phi, _point_biserial,
)


def _frame(tf, bias="RANGING", **kw):
    return MarketContextFrame(tf=tf, available=True, bias=bias, **kw)


def _ctx(direction, pnl, frames):
    return TradeContext(
        backtest_id="BT-TEST", trade_id="t", signal_id="s",
        symbol="SYN", direction=direction, pnl_r=pnl,
        htf_trend=frames.get("D1", _frame("D1")).bias,
        market_context=frames,
    )


def _bulk(aligned_wins, aligned_losses, mixed_wins, mixed_losses):
    """Construye contexts:
    - aligned (D1/H4/H1 BULLISH) => gana/perdió según params
    - mixed   (D1 BULLISH + H4 BEARISH + H1 BULLISH) => 'not', gana/perdió
    """
    ctxs = []
    for _ in range(aligned_wins):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, 1.0, frames))
    for _ in range(aligned_losses):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, -1.0, frames))
    for _ in range(mixed_wins):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BEARISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, 1.0, frames))
    for _ in range(mixed_losses):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BEARISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, -1.0, frames))
    return ctxs


def test_phi_known_table():
    # tabla [[a=20,b=5],[c=5,d=20]] => asociación fuerte positiva (phi = 0.6)
    a, b, c, d = 20, 5, 5, 20
    r = _phi(a, b, c, d)
    assert r >= 0.6
    assert -1.0 <= r <= 1.0


def test_phi_zero_when_independent():
    r = _phi(10, 10, 10, 10)
    assert abs(r) < 1e-9


def test_point_biserial_known():
    # dummy 1 => y alta, dummy 0 => y baja => correlación ~ +1
    xs = [1, 1, 1, 0, 0, 0]
    ys = [1.0, 1.2, 0.8, -1.0, -1.2, -0.8]
    r = _point_biserial(xs, ys)
    assert r > 0.9


def test_correlation_reports_feature_outcome_coef_n_strength():
    # 80 contexts: aligned (BULLISH triple) => win 30/40; not (mezcla) => win 10/40
    # => phi fuerte y n por lado >= 30 (ambos lados 40)
    ctxs = _bulk(aligned_wins=30, aligned_losses=10, mixed_wins=10, mixed_losses=30)
    rep = compute(ctxs, outcome="win")
    assert isinstance(rep, CorrelationReport)
    aligned = [x for x in rep.associations if x.feature == "htf_alignment" and x.category == "aligned"]
    assert aligned, "debe aparecer la cohorte aligned"
    a = aligned[0]
    assert isinstance(a, Association)
    assert a.outcome == "win"
    # n es la comparación aligned (40) vs resto (40) => 80 total
    assert a.n == 80
    assert "coef" in Association.__annotations__
    assert a.strength in ("negligible", "small", "moderate", "strong")
    assert a.can_conclude is True
    # asociación fuerte: aligned gana mucho más (phi = 0.5 => strong)
    assert a.coef >= 0.5


def test_correlation_excludes_unknown_category():
    # contextos con D1 ausente => htf_alignment 'unknown' no debe aparecer
    ctxs = [_ctx(1, 1.0, {"M15": _frame("M15")}) for _ in range(40)]
    rep = compute(ctxs, outcome="win")
    cats = {x.category for x in rep.associations if x.feature == "htf_alignment"}
    assert "unknown" not in cats


def test_correlation_warns_when_n_low():
    # 10 contexts => cada asociación < MIN_N => can_conclude False
    ctxs = _bulk(aligned_wins=5, aligned_losses=0, mixed_wins=0, mixed_losses=5)
    rep = compute(ctxs, outcome="win")
    assert rep.associations  # hay algo que medir
    for x in rep.associations:
        assert x.can_conclude is False
        assert f"n={x.n} < {MIN_N}" in x.warn


def test_correlation_does_not_use_pnl_to_build_facet():
    """La faceta se construye con cohorts (market_context), no con pnl.

    Ponemos contexts con market_context TODOS iguales (aligned) pero pnl
    mezclado: la cohorte 'aligned' debe aparecer UNA vez, no segmentada por pnl.
    """
    ctxs = []
    for i in range(40):
        frames = {
            "D1": _frame("D1", "BULLISH"), "H4": _frame("H4", "BULLISH"),
            "H1": _frame("H1", "BULLISH"), "M15": _frame("M15"),
            "M5": _frame("M5", confirmation="BULLISH"), "M1": _frame("M1"),
        }
        ctxs.append(_ctx(1, 1.0 if i % 2 == 0 else -1.0, frames))
    rep = compute(ctxs, outcome="win")
    aligned = [x for x in rep.associations if x.feature == "htf_alignment" and x.category == "aligned"]
    assert len(aligned) == 1  # no se partió por pnl


def test_correlation_outcome_pnl_r_uses_point_biserial():
    ctxs = _bulk(aligned_wins=20, aligned_losses=10, mixed_wins=5, mixed_losses=5)
    rep = compute(ctxs, outcome="pnl_r")
    assert all(x.outcome == "pnl_r" for x in rep.associations)
    assert rep.associations  # algo se midió
