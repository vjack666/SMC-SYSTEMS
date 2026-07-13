"""scripts/r4_chain.py — R4: medicion aislada EN PARALELO (E2 // E3 // E5).

Corre los experimentos R4 de forma headless y vuelca PF/WR/expectancy a
results/r4/<exp>.json. No imprime solo; deja artefactos para METRICS_CANON.

Paralelismo SIN explotar el equipo:
  - Los experimentos son independientes -> se lanzan concurrentes.
  - max_workers = min(n_experimentos, cpu_count - 2): deja margen para el
    loop MT5 en vivo y el sistema (NO se toca prioridad/affinity/plan de
    energia; el equipo queda en Equilibrado).
  - Cada `run_backtest.py` es vela-a-vela single-thread (1 nucleo), asi que
    N workers => N nucleos usados en paralelo, no 20.

Modelos (ver roadmap R4):
  E2  = Solo PO3 completo (model="po3", gating en engine.py)
  E3  = Turtle Soup aislado (model="intradia" + counter_trend; proxy del libro 02)
  E5  = E2 y E3 CON costos de mercado reales (EURUSD ~0.8/0.5/0.3 pips)

Uso:
  python scripts/r4_chain.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "r4"
RESULTS.mkdir(parents=True, exist_ok=True)

SYMBOL = "EURUSD"
HTF = "H4"
LTF = "M15"
MAX_HOLD = 16
COST = "0.8,0.5,0.3"  # spread,commission,slippage (pips) EURUSD


def _run(label: str, extra: list[str]) -> dict:
    cmd = [
        sys.executable, "ict_backtest/run_backtest.py",
        "--symbol", SYMBOL, "--htf", HTF, "--ltf", LTF,
        "--max-hold", str(MAX_HOLD),
    ] + extra
    print(f"\n##### {label} #####", flush=True)
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    txt = out.stdout + out.stderr
    print(txt[-1500:], flush=True)

    m: dict = {"label": label, "cmd": " ".join(cmd), "ok": out.returncode == 0,
               "pf": None, "winrate": None, "trades": None,
               "expectancy": None, "total_r": None, "max_dd_r": None,
               "exits": None, "raw_tail": txt[-800:]}
    for line in txt.splitlines():
        if "profit factor:" in line:
            m["pf"] = float(line.split(":")[1].strip())
        elif "winrate" in line:
            m["winrate"] = float(line.split(":")[1].replace("%", "").strip()) / 100
        elif "trades       :" in line:
            m["trades"] = int(line.split(":")[1].strip())
        elif "expectancy" in line:
            m["expectancy"] = float(line.split(":")[1].strip().split()[0])
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
        ("E2 PO3 aislado (sin cost)", ["--model", "po3"]),
        ("E3 Turtle Soup aislado (sin cost)", ["--model", "intradia", "--counter-trend"]),
        ("E5 PO3 aislado (CON cost)", ["--model", "po3", "--cost", COST]),
        ("E5 Turtle Soup aislado (CON cost)", ["--model", "intradia", "--counter-trend", "--cost", COST]),
    ]

    # Paralelismo acotado: no usar todos los nucleos (dejar margen a MT5 vivo).
    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 chain PARALLELO: {len(experiments)} exps, {n_workers} workers "
          f"(cpu_count={os.cpu_count()}) ===", flush=True)

    exps: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futs = [ex.submit(_run, label, extra) for label, extra in experiments]
        for f in futs:
            exps.append(f.result())  # en orden de finalizacion; ok para reporte

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4_chain_{stamp}.json"
    summary = {
        "generated": stamp,
        "symbol": SYMBOL, "htf": HTF, "ltf": LTF, "max_hold": MAX_HOLD,
        "cost_eurusd_pips": COST, "workers": n_workers,
        "experiments": exps,
    }
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\n=== R4 chain guardado en {out_path} ===", flush=True)

    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:42s} PF={pf}  WR={wr}  trades={e['trades']}", flush=True)


if __name__ == "__main__":
    main()
