"""scripts/r4_chain.py — R4 v2.5: re-medicion Silver Bullet (M5) y PO3.

Corrige la auditoria AUDIT_R4_V2_SENALES_PO3_SILVER:
- Silver Bullet antes daba 0 porque no habia datos M5/M1 (solo 1000 velas
  viejas). Ahora update_mt5_data.py bajo 50000 velas M5/M1. Se re-mide con
  --ltf M5 (el checklist_scalping usa FVG M5, regla del libro).
- PO3 se re-mide TAL CUAL (el motor tiene bug choch_status; se reporta el
  numero honesto del sistema y se deja el parche propuesto en la auditoria).
- displacement ON en todos (correccion de la auditoria de displacement).

Paralelismo: 4 workers (16 libres para MT5, plan Equilibrado intacto).
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
LTF_SB = "M5"   # Silver Bullet opera M5 (FVG M5)
LTF_PO3 = "M15"  # PO3 ejecuta en M15
MAX_HOLD = 16


def _run(label: str, symbol: str, model: str, ltf: str, cost_key: str | None = None) -> dict:
    cmd = [
        sys.executable, "ict_backtest/run_backtest.py",
        "--symbol", symbol, "--htf", HTF, "--ltf", ltf,
        "--max-hold", str(MAX_HOLD),
        "--model", model, "--require-displacement",
    ]
    if cost_key is None:
        pass
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    txt = out.stdout + out.stderr
    print(txt[-1000:], flush=True)
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
    # 4 experimentos: Silver Bullet M5 (EUR/GBP) + PO3 M15 (EUR/GBP)
    experiments: list[tuple[str, str, str, str]] = [
        ("EURUSD Silver+disp (M5)", "EURUSD", "scalping", LTF_SB),
        ("GBPUSD Silver+disp (M5)", "GBPUSD", "scalping", LTF_SB),
        ("EURUSD PO3+disp (M15)",   "EURUSD", "po3",      LTF_PO3),
        ("GBPUSD PO3+disp (M15)",   "GBPUSD", "po3",      LTF_PO3),
    ]
    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 v2.5 (Silver M5 + PO3 remedir, disp ON) {len(experiments)} exps, "
          f"{n_workers} workers ===", flush=True)
    exps: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        for f in [ex.submit(_run, *e) for e in experiments]:
            exps.append(f.result())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4v25_chain_{stamp}.json"
    out_path.write_text(json.dumps({
        "generated": stamp, "htf": HTF, "max_hold": MAX_HOLD,
        "displacement": "ON", "note": "Silver Bullet M5 (datos 50k recien bajados); PO3 M15 tal cual (bug choch_status documentado).",
        "workers": n_workers, "experiments": exps,
    }, indent=2))
    print(f"\n=== R4 v2.5 guardado en {out_path} ===", flush=True)
    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:30s} PF={pf} WR={wr} trades={e['trades']}", flush=True)


if __name__ == "__main__":
    main()
