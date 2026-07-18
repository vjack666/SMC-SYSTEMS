"""Lanza el backtest v2 mtf (costos ON, OOS 0.3) para los 7 simbolos listos.

Excluye XAUUSD: el motor canonico (run_mtf_intraday) SE CUELGA con oro
(escribe live_structure.csv y entra en loop/deadlock; ver ETAPA 4 PASO 2 bug).
Escribe resultados en results/bt_v2/<sym>/mtf_intraday/ y un resumen
consolidado en results/bt_v2_mtf_resumen.txt.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]

from ict_backtest.v2.orchestrator import run_mtf_intraday


def run_one(sym: str) -> dict:
    out = ROOT / "results" / "bt_v2" / sym / "mtf_intraday"
    payload = run_mtf_intraday(
        sym, ltf="M15", max_hold=40, counter_trend=False,
        require_displacement=True, no_cost=False, out_dir=out, oos_frac=0.3,
        live_table=False, live_console=False,
    )
    return payload


def main() -> int:
    lines = []
    t0 = datetime.now(timezone.utc)
    lines.append(f"# Backtest v2 mtf (costos ON, OOS 0.3) — {t0:%Y-%m-%d %H:%M UTC}")
    lines.append(f"# Símbolos: {', '.join(SYMBOLS)} (XAUUSD excluido: motor canonico se cuelga con oro)\n")
    for sym in SYMBOLS:
        try:
            p = run_one(sym)
            m = p["metrics"]
            c = p["coverage"]
            oos = p.get("oos")
            oos_s = ""
            if oos:
                oos_s = (f" | OOS trades={oos['oos']['trades']} PF={oos['oos']['pf']:.3f}")
            line = (f"{sym}: orders={p['n_orders']} trades={m['trades']} "
                    f"WR={m['winrate']*100:.1f}% PF={m['pf']:.3f} R={m['total_r']:.1f} "
                    f"cov={c['coverage_pct']}% [{p['coverage_mode']}]"
                    f"{oos_s}")
            lines.append(line)
            print(line, flush=True)
        except Exception as e:
            err = f"{sym}: ERROR {type(e).__name__}: {e}"
            lines.append(err)
            print(err, flush=True)
    out_path = ROOT / "results" / "bt_v2_mtf_resumen.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[*] Resumen -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
