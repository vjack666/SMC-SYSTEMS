"""Demo E2: imprime structs + reporte de CORRELACION de EJEMPLO (sintetico).

NO usa contexts reales. Solo muestra la forma de CorrelationReport.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame
from ict_backtest.diagnostics.correlation_engine import (
    compute, Association, CorrelationReport,
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


ctxs = _bulk(30, 10, 10, 30)
rep = compute(ctxs, outcome="win")

print("=== STRUCTURES ===")
print("Association     :", Association.__annotations__)
print("CorrelationReport:", CorrelationReport.__annotations__)
print()
print("=== DEMO CORRELATION (80 ctx sinteticos, outcome=win) ===")
print(f"outcome={rep.outcome}  (ordenado por |coef| desc)")
print(f"{'feature':<14}{'cat':<10}{'n':>4}{'coef':>8}{'strength':>11}  conclude")
for a in rep.associations:
    flag = "" if a.can_conclude else f"  [{a.warn}]"
    print(f"{a.feature:<14}{a.category:<10}{a.n:>4}{a.coef:>8.2f}{a.strength:>11}  {a.can_conclude}{flag}")
