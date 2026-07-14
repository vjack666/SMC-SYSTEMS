"""scripts/r4_turtle_v29_structsl.py — R4 Fase 0 RE-RUN con SL estructural.

No pisa r4_turtle_v28.py (veredicto definitivo con ATR). Este corre Turtle
Soup (H4->M15, contratendencia) CON:
  - SL estructural (calc_structural_sl): mecha del sweep +- buffer, nunca ATR.
  - TP en liquidez opuesta (--tp-mode liquidity): BSL/SSL del HTF, no 1:2 fijo.
  - Filtro de tamaño: si el SL estructural > STRUCT_SL_MAX_ATR, salta el trade.

Objetivo: medir si el edge contratendencia respira sin el stop a 1 ATR.
Veredicto honesto lo da el re-run; no se afirma PF mejorado antes de medir.

Libro de referencia: docs/ict/14_STOP_LOSS_ESTRUCTURAL.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "r4"
RESULTS.mkdir(parents=True, exist_ok=True)

HTF = "H4"
LTF = "M15"
MAX_HOLD = 16


def _run(label: str, symbol: str) -> dict:
    cmd = [
        sys.executable, "ict_backtest/run_backtest.py",
        "--symbol", symbol, "--htf", HTF, "--ltf", LTF,
        "--max-hold", str(MAX_HOLD),
        "--model", "intradia", "--counter-trend",
        "--tp-mode", "liquidity", "--require-displacement",
    ]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    txt = out.stdout + out.stderr
    print(txt[-1200:], flush=True)
    m: dict = {"label": label, "cmd": " ".join(cmd), "ok": out.returncode == 0,
               "pf": None, "winrate": None, "trades": None, "total_r": None,
               "max_dd_r": None, "exits": None, "raw_tail": txt[-800:]}
    for line in txt.splitlines():
        if "profit factor:" in line:
            m["pf"] = float(line.split(":")[1].strip())
        elif "winrate" in line:
            m["winrate"] = float(line.split(":")[1].replace("%", "").strip()) / 100
        elif "trades       :" in line:
            m["trades"] = int(line.split(":")[1].strip())
        elif "total        :" in line:
            m["total_r"] = float(line.split(":")[1].split()[0])
        elif "max drawdown" in line:
            m["max_dd_r"] = float(line.split(":")[1].split()[0])
        elif "salidas" in line:
            try:
                m["exits"] = line.split(":", 1)[1].strip()
            except Exception:
                pass
    return m


def main() -> None:
    experiments = [
        ("EURUSD Turtle Soup (CT, SL estructural, liquidity TP)", "EURUSD"),
        ("GBPUSD Turtle Soup (CT, SL estructural, liquidity TP)", "GBPUSD"),
    ]
    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 v2.9 TURTLE SL-ESTRUCTURAL {len(experiments)} exps, "
          f"{n_workers} workers ===", flush=True)
    exps: list[dict] = []
    for label, sym in experiments:
        exps.append(_run(label, sym))
    stamp = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4v29_turtle_structsl_{stamp}.json"
    out_path.write_text(json.dumps({
        "generated": stamp, "htf": HTF, "ltf": LTF, "max_hold": MAX_HOLD,
        "model": "Turtle Soup (intradia counter_trend, SL estructural, tp-mode liquidity)",
        "sl_mode": "structural (sweep mecha + buffer, no ATR fallback)",
        "lookahead_fixed": True,
        "note": "Re-run de Fase 0 con SL estructural. No pisa v28 (que usaba ATR).",
        "workers": n_workers, "experiments": exps,
    }, indent=2))
    print(f"\n=== R4 v2.9 TURTLE guardado en {out_path} ===", flush=True)
    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:44s} PF={pf} WR={wr} trades={e['trades']}", flush=True)
    passed = [e for e in exps if e["pf"] is not None and e["pf"] >= 1.10
              and e["trades"] is not None and e["trades"] >= 30]
    print(f"\nGATE Fase 0 (PF>=1.10 y n>=30 en >=1 simbolo): "
          f"{'PASA' if passed else 'NO PASA'}", flush=True)


if __name__ == "__main__":
    main()
