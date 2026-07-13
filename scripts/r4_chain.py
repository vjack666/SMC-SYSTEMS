"""scripts/r4_chain.py — R4 v2: medicion aislada CON displacement + multi-simbolo.

Corrige la auditoria: las corridas R4 previas usaron Opcion A SIN
--require-displacement, midiendo el modelo DESNUDO. La doc del backtest
(SDD) define el edge ICT como sweep->displacement->BOS->retorno, asi que
aqui se aplica displacement en TODOS los experimentos.

Paralelismo SIN explotar el equipo:
  - Experimentos independientes -> concurrentes.
  - max_workers = min(n_exps, cpu_count - 2): deja margen para el loop MT5
    vivo y el sistema. Plan de energia Equilibrado intacto; no se toca
    prioridad/affinity/config global.

Modelos (roadmap R4):
  po3      = Solo PO3 completo (E2)
  intradia --counter-trend = Turtle Soup aislado (E3)
  scalping = Silver Bullet aislado (E4)

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

HTF = "H4"
LTF = "M15"
MAX_HOLD = 16
# Costos por simbolo (spread,commission,slippage en pips).
COST = {"EURUSD": "0.8,0.5,0.3", "GBPUSD": "1.0,0.6,0.3"}


def _run(label: str, symbol: str, model: str, counter: bool, cost_key: str | None) -> dict:
    cmd = [
        sys.executable, "ict_backtest/run_backtest.py",
        "--symbol", symbol, "--htf", HTF, "--ltf", LTF,
        "--max-hold", str(MAX_HOLD),
        "--model", model, "--require-displacement",   # <-- clave R4 v2: displacement ON
    ]
    if counter:
        cmd.append("--counter-trend")
    if cost_key:
        cmd += ["--cost", COST[cost_key]]

    print(f"\n##### {label} #####", flush=True)
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    txt = out.stdout + out.stderr
    print(txt[-1200:], flush=True)

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
    # 8 experimentos: 3 modelos x 2 simbolos (sin cost) + 2 con cost (EURUSD).
    experiments: list[tuple[str, str, str, bool, str | None]] = [
        ("EURUSD PO3+disp",       "EURUSD", "po3",      False, None),
        ("EURUSD Turtle+disp",    "EURUSD", "intradia", True,  None),
        ("EURUSD Silver+disp",    "EURUSD", "scalping", False, None),
        ("GBPUSD PO3+disp",       "GBPUSD", "po3",      False, None),
        ("GBPUSD Turtle+disp",    "GBPUSD", "intradia", True,  None),
        ("GBPUSD Silver+disp",    "GBPUSD", "scalping", False, None),
        ("EURUSD PO3+disp+cost",  "EURUSD", "po3",      False, "EURUSD"),
        ("EURUSD Turtle+disp+cost","EURUSD", "intradia", True,  "EURUSD"),
    ]

    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 v2 chain PARALELO (disp ON): {len(experiments)} exps, "
          f"{n_workers} workers (cpu={os.cpu_count()}) ===", flush=True)

    exps: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futs = [ex.submit(_run, *exp) for exp in experiments]
        for f in futs:
            exps.append(f.result())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4v2_chain_{stamp}.json"
    summary = {
        "generated": stamp, "htf": HTF, "ltf": LTF, "max_hold": MAX_HOLD,
        "displacement": "ON (--require-displacement)", "cost_pips": COST,
        "workers": n_workers, "experiments": exps,
        "note": "R4 v2: corrige auditoria — displacement aplicado en todos los exps.",
    }
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\n=== R4 v2 guardado en {out_path} ===", flush=True)
    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:32s} PF={pf}  WR={wr}  trades={e['trades']}", flush=True)


if __name__ == "__main__":
    main()
