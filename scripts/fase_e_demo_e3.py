"""Demo E3: imprime structs + HypothesisReport de EJEMPLO (sintetico).

NO usa contexts reales. Recibe StatisticsReport + CorrelationReport ya
construidos (separacion limpia: HypothesisEngine no ve TradeContext crudo).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.diagnostics.statistics_engine import (
    StatisticsReport, OverallStat, CohortStat,
)
from ict_backtest.diagnostics.correlation_engine import (
    CorrelationReport, Association,
)
from ict_backtest.diagnostics.hypothesis_engine import compute, HypothesisReport, Hypothesis

stats = StatisticsReport(
    overall=OverallStat(n=80, win_rate=0.5, pf=1.0, avg_r=0.0, expectancy_r=0.0),
    cohorts=[
        CohortStat("htf_alignment", "aligned", n=40, win_rate=0.75, pf=1.6,
                   avg_r=0.3, ci95_low=0.60, ci95_high=0.87, can_conclude=True, warn=""),
        CohortStat("htf_alignment", "not", n=40, win_rate=0.35, pf=0.9,
                   avg_r=-0.1, ci95_low=0.21, ci95_high=0.50, can_conclude=True, warn=""),
        CohortStat("m5_confirms", "yes", n=40, win_rate=0.60, pf=1.2,
                   avg_r=0.1, ci95_low=0.45, ci95_high=0.73, can_conclude=True, warn=""),
        CohortStat("m5_confirms", "no", n=40, win_rate=0.40, pf=0.8,
                   avg_r=-0.05, ci95_low=0.26, ci95_high=0.55, can_conclude=True, warn=""),
    ],
    comparisons=[],
)
corr = CorrelationReport(outcome="win", associations=[
    Association("htf_alignment", "aligned", "win", coef=0.5, n=80,
                strength="strong", can_conclude=True, warn=""),
    Association("m5_confirms", "yes", "win", coef=0.2, n=80,
                strength="small", can_conclude=True, warn=""),
])

rep = compute(stats, corr)

print("=== STRUCTURES ===")
print("Hypothesis     :", Hypothesis.__annotations__)
print("HypothesisReport:", HypothesisReport.__annotations__)
print()
print("=== DEMO HYPOTHESIS (80 ctx sinteticos) ===")
print(f"Total hipotesis: {len(rep.hypotheses)} | No concluyentes: {len(rep.inconclusive)}")
print()
for i, h in enumerate(rep.hypotheses, 1):
    print(f"{i}. [{h.confidence}] {h.statement}")
    print(f"   evidencia a favor : {h.evidence_for}")
    print(f"   evidencia en contra: {h.evidence_against}")
    print(f"   n={h.n} | {h.metrics} | conclude={h.can_conclude}")
    print()
if rep.inconclusive:
    print("NO CONCLUIDO:")
    for s in rep.inconclusive:
        print(f"  - {s}")
