"""scripts/r4_chain.py — R4 v2.7: re-medicion LIMPIA tras fixes de IA externa.

Fixes aplicados antes de esta corrida (commit local, sin push hasta visto bueno):
- AUDIT_LOOKAHEAD_HTF: row_at_time exige barra HTF ya cerrada (fin look-ahead).
- exec_tf explicito en checklist_scalping (fin silenciamiento Silver).
- choch_status mapeado desde choch_signal (PO3 ve CHOCH).
- displacement en sequence.py acepta HTF (no solo LTF).
- test H1 corregido (confirm_bars real del motor).

Configuracion de esta corrida (hallazgo IA: Silver Bullet es INCOMPATIBLE con
displacement en la vela de entrada M5 -> Silver corre SIN --require-displacement;
PO3 SI lo usa, coherente con su naturaleza de ruptura de estructura).
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
LTF_SB = "M5"    # Silver Bullet opera M5 (FVG M5)
LTF_PO3 = "M15"  # PO3 ejecuta en M15
MAX_HOLD = 16


def _run(label: str, symbol: str, model: str, ltf: str,
         require_displacement: bool = False) -> dict:
    cmd = [
        sys.executable, "ict_backtest/run_backtest.py",
        "--symbol", symbol, "--htf", HTF, "--ltf", ltf,
        "--max-hold", str(MAX_HOLD),
        "--model", model,
    ]
    if require_displacement:
        cmd.append("--require-displacement")
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
    # Silver Bullet SIN displacement (ruptura rapida NY AM, no usa impulse en M5).
    # PO3 CON displacement (ruptura de estructura si lo requiere).
    experiments: list[tuple[str, str, str, str, bool]] = [
        ("EURUSD Silver (M5)",      "EURUSD", "scalping", LTF_SB,  False),
        ("GBPUSD Silver (M5)",      "GBPUSD", "scalping", LTF_SB,  False),
        ("EURUSD PO3+disp (M15)",   "EURUSD", "po3",      LTF_PO3, True),
        ("GBPUSD PO3+disp (M15)",   "GBPUSD", "po3",      LTF_PO3, True),
    ]
    n_workers = min(len(experiments), max(1, (os.cpu_count() or 4) - 2))
    print(f"=== R4 v2.7 (LIMPIO: look-ahead fix + Silver sin disp) "
          f"{len(experiments)} exps, {n_workers} workers ===", flush=True)
    exps: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        for f in [ex.submit(lambda e: _run(*e), e) for e in experiments]:
            exps.append(f.result())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS / f"r4v27_chain_{stamp}.json"
    out_path.write_text(json.dumps({
        "generated": stamp, "htf": HTF, "max_hold": MAX_HOLD,
        "lookahead_fixed": True,
        "displacement": "PO3=ON, Silver=OFF (incompatible con entrada M5)",
        "note": "Corrida LIMPIA tras fixes IA externa (look-ahead HTF, exec_tf, choch, displacement HTF).",
        "workers": n_workers, "experiments": exps,
    }, indent=2))
    print(f"\n=== R4 v2.7 guardado en {out_path} ===", flush=True)
    for e in exps:
        pf = f"{e['pf']:.3f}" if e["pf"] is not None else "n/a"
        wr = f"{e['winrate']*100:.1f}%" if e["winrate"] is not None else "n/a"
        print(f"  {e['label']:30s} PF={pf} WR={wr} trades={e['trades']}", flush=True)


if __name__ == "__main__":
    main()
