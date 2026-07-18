"""E4 — corrida real sobre contexts de EURUSD 6m (punta a punta Fase E).

Protocolo Ruben: muestra reporte BRUTO, n por cohorte, advertencias de
muestra pequeña. NO saca conclusiones del asistente: solo los flags de los
motores (can_conclude / warn / inconclusive).
"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.diagnostics.trade_context import TradeContext
from ict_backtest.diagnostics.diagnosis_report import run

CTX_PATH = ROOT / "results" / "backtests" / "2026-07-18_6m_mtf" / "EURUSD" / "contexts.json"


def _mc_from_dict(d: dict) -> dict:
    out = {}
    for tf, v in (d.get("market_context") or {}).items():
        if isinstance(v, dict):
            from ict_backtest.diagnostics.trade_context import MarketContextFrame
            out[tf] = MarketContextFrame(
                tf=v.get("tf", tf),
                available=bool(v.get("available", True)),
                bias=v.get("bias", ""),
                structure=v.get("structure", ""),
                premium_discount=v.get("premium_discount", ""),
                poi=v.get("poi", ""),
                liquidity=v.get("liquidity", ""),
                setup=v.get("setup", ""),
                setup_sweep=v.get("setup_sweep", ""),
                setup_displacement=v.get("setup_displacement", ""),
                setup_bos=v.get("setup_bos", ""),
                setup_fvg=v.get("setup_fvg", ""),
                setup_ob=v.get("setup_ob", ""),
                confirmation=v.get("confirmation", ""),
                micro_structure=v.get("micro_structure", ""),
                execution=v.get("execution", ""),
            )
        elif isinstance(v, str):
            # run2/run3 dumped MarketContextFrame via default=str -> repr string.
            # Parsearlo campo por campo (clave='valor', comillas simples).
            import re
            fields = dict(re.findall(r"(\w+)='([^']*)'", v))
            from ict_backtest.diagnostics.trade_context import MarketContextFrame
            out[tf] = MarketContextFrame(
                tf=fields.get("tf", tf),
                available=(fields.get("available", "True") == "True"),
                bias=fields.get("bias", ""),
                structure=fields.get("structure", ""),
                premium_discount=fields.get("premium_discount", ""),
                poi=fields.get("poi", ""),
                liquidity=fields.get("liquidity", ""),
                setup=fields.get("setup", ""),
                setup_sweep=fields.get("setup_sweep", ""),
                setup_displacement=fields.get("setup_displacement", ""),
                setup_bos=fields.get("setup_bos", ""),
                setup_fvg=fields.get("setup_fvg", ""),
                setup_ob=fields.get("setup_ob", ""),
                confirmation=fields.get("confirmation", ""),
                micro_structure=fields.get("micro_structure", ""),
                execution=fields.get("execution", ""),
            )
        else:
            out[tf] = v
    return out


def main() -> None:
    raw = json.load(open(CTX_PATH))
    contexts: list[TradeContext] = []
    for d in raw:
        d2 = dict(d)
        d2["market_context"] = _mc_from_dict(d)
        contexts.append(TradeContext(**d2))

    rep = run(contexts)

    print("=" * 70)
    print(f"DIAGNOSIS REPORT — EURUSD 6m | n total = {rep.statistics.overall.n}")
    print("=" * 70)

    print("\n--- STATISTICS: overall ---")
    o = rep.statistics.overall
    print(f"n={o.n} wr={o.win_rate:.2f} pf={o.pf:.2f} avg_r={o.avg_r:.3f}")

    print("\n--- STATISTICS: cohorts (n por cohorte) ---")
    print(f"{'cohort':<14}{'cat':<10}{'n':>4}{'wr':>7}{'pf':>7}{'avg_r':>8}  conclude  warn")
    for cs in rep.statistics.cohorts:
        print(f"{cs.name:<14}{cs.category:<10}{cs.n:>4}{cs.win_rate:>7.2f}"
              f"{cs.pf:>7.2f}{cs.avg_r:>8.3f}  {cs.can_conclude}  {cs.warn}")

    print("\n--- CORRELATION: associations ---")
    print(f"{'feature':<14}{'cat':<10}{'n':>4}{'coef':>8}{'strength':>11}  conclude  warn")
    for a in rep.correlation.associations:
        print(f"{a.feature:<14}{a.category:<10}{a.n:>4}{a.coef:>8.2f}"
              f"{a.strength:>11}  {a.can_conclude}  {a.warn}")

    print("\n--- HYPOTHESIS: reportadas ---")
    for i, h in enumerate(rep.hypothesis.hypotheses, 1):
        print(f"{i}. [{h.confidence}] {h.statement}")
        print(f"     evidencia a favor : {h.evidence_for}")
        print(f"     n={h.n} | {h.metrics} | conclude={h.can_conclude}")

    print("\n--- NO CONCLUIDO (advertencias de muestra) ---")
    if rep.hypothesis.inconclusive:
        for s in rep.hypothesis.inconclusive:
            print(f"  - {s}")
    else:
        print("  (ninguna)")


if __name__ == "__main__":
    main()
