"""scripts/b2_opposite_swing.py — Driver para medir OPPOSITE_SWING_BREAK.

Corre run_sequence_backtest (motor canonico sequence) con 1 mes de EURUSD
(D1->H4->H1->M15), con el flag invalidate_on_opposite_swing OFF u ON, y
escribe results/bt_v2/EURUSD/opposite_swing/<MODE>/run_summary.json.

Uso:
  python scripts/b2_opposite_swing.py OFF
  python scripts/b2_opposite_swing.py ON

El backtest NO pasaba antes el flag; este driver lo cablea aditivamente
(OFF => regresion cero, identico al historico).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.run_backtest import run_sequence_backtest  # noqa: E402

SYMBOL = "EURUSD"
HTF = "H4"
LTF = "M15"
WINDOW_MONTHS = 1
MAX_HOLD = 40


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["OFF", "ON"])
    ap.add_argument("--htf", default=HTF)
    ap.add_argument("--ltf", default=LTF)
    ap.add_argument("--months", type=int, default=WINDOW_MONTHS)
    args = ap.parse_args()
    htf = args.htf
    ltf = args.ltf
    on = args.mode == "ON"

    out = ROOT / "results" / "bt_v2" / "EURUSD" / "opposite_swing" / args.mode
    out.mkdir(parents=True, exist_ok=True)

    m = run_sequence_backtest(
        SYMBOL, htf, ltf, MAX_HOLD,
        counter_trend=False,
        tp_mode="fixed2r",
        require_displacement=True,
        displace_gap=6,
        bos_gap=None,
        cost=None,  # resolve_cost por defecto (costos ON)
        fill_mode="next_open",
        enable_pd_index=True,
        backtest_id=f"BT-OPS-{args.mode}",
        window_months=args.months,
        invalidate_on_opposite_swing=on,
    )

    # Extracto compacto para el reporte del trader.
    summary = {
        "mode": args.mode,
        "invalidate_on_opposite_swing": on,
        "symbol": SYMBOL,
        "htf": htf,
        "ltf": ltf,
        "window_months": args.months,
        "n_orders": m["trades"],
        "funnel": m.get("funnel"),
        "metrics": {k: m[k] for k in ("trades", "winrate", "pf", "expectancy",
                                       "max_dd_r", "total_r")},
    }
    (out / "run_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    # Tambien volcar el full metrics (contexts/etc.) por si se quiere auditar.
    (out / "full_metrics.json").write_text(
        json.dumps(m, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n[driver] {args.mode}: n_orders={m['trades']} PF={m['pf']:.3f} "
          f"funnel={m.get('funnel')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
