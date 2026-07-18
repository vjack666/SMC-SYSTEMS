"""Fase D — Validación multi-TF + AUDIT REPORT (reglas #4/#6/#7).

Corre run_sequence_backtest con la cadena completa D1/H4/H1/M15/M5/M1 sobre
la ventana pedida y emite:
  - contexts.json (TradeContext v2 congelados, con market_context)
  - audit_report.json (disponibilidad por TF + contexts incompletos)

Nada de estadísticas todavia (Fase E). Solo fidelidad del expediente.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.run_backtest import run_sequence_backtest
from ict_backtest.diagnostics.context_builder import build_trade_context
from ict_backtest.diagnostics.trade_context import TradeContext

TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")


def run(symbol: str, window_months: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    backtest_id = f"BT-VAL-{symbol}-{window_months}M"
    m = run_sequence_backtest(
        symbol, "H4", "M15", max_hold=96,
        require_displacement=False, enable_pd_index=True,
        backtest_id=backtest_id, window_months=window_months,
    )
    # congelar contexts v2
    contexts = [build_trade_context(raw, signal_id=raw.signal.time)
                for raw in m["contexts"]]
    # serializar (frozen dataclass -> dict)
    ctx_json = [c.__dict__ for c in contexts]
    (out_dir / "contexts.json").write_text(
        json.dumps(ctx_json, default=str, indent=2), encoding="utf-8")

    # AUDIT REPORT (regla #6)
    avail: dict[str, int] = {tf: 0 for tf in TF_CHAIN}
    incomplete = 0
    for c in contexts:
        mc = c.market_context or {}
        ok = True
        for tf in TF_CHAIN:
            frame = mc.get(tf)
            if frame is not None and getattr(frame, "available", False):
                avail[tf] += 1
            else:
                ok = False
        if not ok:
            incomplete += 1
    n = len(contexts)
    audit = {
        "backtest_id": backtest_id,
        "symbol": symbol,
        "window_months": window_months,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trades": n,
        "tf_availability": {
            tf: {"available": avail[tf], "pct": round(100 * avail[tf] / n, 1) if n else 0.0}
            for tf in TF_CHAIN
        },
        "incomplete_contexts": incomplete,
        "incomplete_pct": round(100 * incomplete / n, 1) if n else 0.0,
    }
    (out_dir / "audit_report.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8")
    # imprimir resumen
    print("\n===== AUDIT REPORT =====")
    print(f"  backtest_id : {backtest_id}")
    print(f"  trades      : {n}")
    for tf in TF_CHAIN:
        a = audit["tf_availability"][tf]
        print(f"  {tf:<4} disponible: {a['pct']:>5.1f}%  ({a['available']}/{n})")
    print(f"  incompletos : {incomplete} ({audit['incomplete_pct']}%)")
    return audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--window-months", type=int, default=6)
    ap.add_argument("--out", default="results/backtests/2026-07-18_6m_mtf")
    args = ap.parse_args()
    run(args.symbol, args.window_months, Path(args.out) / args.symbol)


if __name__ == "__main__":
    main()
