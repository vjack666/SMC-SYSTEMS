"""scripts/r4_turtle_v28.py — Fase 0 R4: Turtle Soup LIMPIO (look-ahead fix aplicado).

Unica corrida de Fase 0: decide si R4 sigue a Fase 1 o se archiva.
Turtle Soup = --model intradia --counter-trend --tp-mode fixed2r (V4).
Los 2 fixes de look-ahead (row_at_time cutoff + test) ya estan en el codigo
desde commit 6d4b158. Esta corrida es el veredicto DEFINITIVO del candidato.

Gate (de la hoja de ruta IA externa): PF>=1.10 y n>=30 en al menos un simbolo
-> continua a Fase 1. Si no -> "sin edge confirmado en modelos R4 puros",
saltar a Fase 3 (variaciones), no a Optuna.
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
        "--model", "intradia", "--counter-trend", "--tp-mode", "fixed2r",
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
        ("EURUSD Turtle Soup (CT, M15, limpio)", "EURUSD"),
        ("GBPUSD Turtle Soup (CT, M15, limpio)", "GBPUSD"),
    ]
    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 v2.8 TURTLE SOUP LIMPIO {len(experiments)} exps, "
          f"{n_workers} workers ===", flush=True)
    exps: list[dict] = []
    for label, sym in experiments:
        exps.append(_run(label, sym))
    stamp = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4v28_turtle_{stamp}.json"
    out_path.write_text(json.dumps({
        "generated": stamp, "htf": HTF, "ltf": LTF, "max_hold": MAX_HOLD,
        "model": "Turtle Soup (intradia counter_trend fixed2r)",
        "lookahead_fixed": True, "note": "Fase 0: unica corrida, veredicto definitivo del candidato.",
        "workers": n_workers, "experiments": exps,
    }, indent=2))
    print(f"\n=== R4 v2.8 TURTLE guardado en {out_path} ===", flush=True)
    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:38s} PF={pf} WR={wr} trades={e['trades']}", flush=True)
    # Gate de Fase 0
    passed = [e for e in exps if e["pf"] is not None and e["pf"] >= 1.10
              and e["trades"] is not None and e["trades"] >= 30]
    print(f"\nGATE Fase 0 (PF>=1.10 y n>=30 en >=1 simbolo): "
          f"{'PASA' if passed else 'NO PASA'}", flush=True)


if __name__ == "__main__":
    main()
