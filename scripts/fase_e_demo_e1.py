"""Demo E1: imprime structs + un reporte de EJEMPLO (contexts sinteticos).

NO usa contexts reales (condicion #5 de Ruben). Solo muestra la forma de las
salidas antes de integrar con datos de 6m.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.diagnostics.trade_context import TradeContext, MarketContextFrame
from ict_backtest.diagnostics.statistics_engine import (
    compute, OverallStat, CohortStat, Comparison, StatisticsReport,
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


ctxs = []
for i in range(40):
    bull = (i % 2 == 0)
    frames = {
        "D1": _frame("D1", "BULLISH" if bull else "BEARISH"),
        "H4": _frame("H4", "BULLISH" if bull else "BEARISH",
                     poi="PD" if bull else "DISCOUNT"),
        "H1": _frame("H1", "BULLISH" if bull else "BEARISH"),
        "M15": _frame("M15"),
        "M5": _frame("M5", confirmation="BULLISH" if bull else "BEARISH"),
        "M1": _frame("M1"),
    }
    ctxs.append(_ctx(1 if bull else -1, 1.0 if bull else -1.0, frames))

rep = compute(ctxs)

print("=== STRUCTURES (dataclasses) ===")
print("OverallStat:", OverallStat.__annotations__)
print("CohortStat :", CohortStat.__annotations__)
print("Comparison :", Comparison.__annotations__)
print("StatisticsReport:", StatisticsReport.__annotations__)
print()
print("=== DEMO REPORT (40 ctx sinteticos, n>=30 => can_conclude True) ===")
print(f"overall: n={rep.overall.n} wr={rep.overall.win_rate:.2f} "
      f"pf={rep.overall.pf:.2f} avg_r={rep.overall.avg_r:.3f}")
print()
hdr = f"{'cohort':<14}{'cat':<10}{'n':>4}{'wr':>7}{'pf':>7}{'avg_r':>8}{'IC95':>16}  conclude"
print(hdr)
for cs in rep.cohorts:
    ic = f"[{cs.ci95_low:.2f},{cs.ci95_high:.2f}]"
    print(f"{cs.name:<14}{cs.category:<10}{cs.n:>4}{cs.win_rate:>7.2f}"
          f"{cs.pf:>7.2f}{cs.avg_r:>8.3f}{ic:>16}  {cs.can_conclude}")
print()
print("comparisons:")
for cmp in rep.comparisons:
    print(f"  {cmp.cohort}: {cmp.a} vs {cmp.b} delta_wr={cmp.delta_wr:+.2f} "
          f"delta_pf={cmp.delta_pf:+.2f} -> {cmp.verdict} (conclude={cmp.can_conclude})")
