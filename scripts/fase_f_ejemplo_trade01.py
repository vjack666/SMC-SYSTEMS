"""Fase F - Ejemplo concreto del trade_01: lo que el motor DETECTO vs la tesis.

No concluye nada. Solo vuelca las filas reales del M15 alrededor de la
entrada del trade_01, con los campos de cada detector, para que se vea
la evidencia fila por fila.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ict_backtest.data_feed import load_tf

CTX_PATH = ROOT / "results" / "backtests" / "2026-07-18_6m_mtf" / "EURUSD" / "contexts.json"


def main() -> None:
    ctxs = json.loads(CTX_PATH.read_text())
    ctx = ctxs[0]  # trade_01
    etime = pd.Timestamp(ctx["entry_time"])
    start = etime - pd.Timedelta(minutes=15 * 45)
    end = etime + pd.Timedelta(minutes=15 * 30)
    m15 = load_tf("EURUSD", "M15", start=start, end=end)
    m15["time"] = pd.to_datetime(m15["time"])

    # encontrar entry
    ej = m15.index[m15["time"] == etime]
    ei = int(ej[0]) if len(ej) else int((m15["time"] - etime).abs().idxmin())
    lo, hi = max(0, ei - 12), min(len(m15), ei + 6)

    cols = ["time", "open", "high", "low", "close",
            "fvg_bullish", "fvg_bearish", "ob_bullish", "ob_bearish",
            "bos_dir", "choch_dir", "liquidity_sweep_up", "liquidity_sweep_down"]
    cols = [c for c in cols if c in m15.columns]
    sub = m15.iloc[lo:hi][cols].copy()
    sub["time"] = sub["time"].dt.strftime("%m-%d %H:%M")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)

    print(f"=== TRADE 01 ===")
    print(f"entry_time={etime}  direction={ctx['direction']}  phase_log={ctx['phase_log']}")
    print(f"htf_bias={ctx['htf_bias']}  htf_trend={ctx['htf_trend']}")
    print(f"zone_authority={ctx['zone_authority']}")
    print()
    print(sub.to_string(index=False))
    print()
    print("Interpretacion de la tesis (libros 03/04/02):")
    print("- FVG bull/bear: low[i]>high[i-2] / high[i]<low[i-2]  (tesis 03 §0/#1)")
    print("- OB bull/bear: vela opuesta + cuerpo>0.7 + close[i+1] cruza  (tesis 04 §0/#1-3)")
    print("- BOS: close rompe swing previo a favor  (tesis 02 §1/#1)")
    print("- CHOCH: rompe nivel del ultimo BOS opuesto  (tesis 02 §1/#2)")
    print("- Sweep: barrido de liquidez (max/min)  (tesis 06/07)")


if __name__ == "__main__":
    main()
