"""scripts/r6_ablation.py — R6.4 (M2): ablation de reloj G1/G2/G3.

Mide la Capa 2 REAL (generate_sequence_signals: SL estructural + RR 1:3 +
killzone + HTF closed-only) sobre EURUSD M15 recortado a N_BARS con 3 modos:
  G1      : HTF closed-only, fill=signal_close, cost=None (teoria previa)
  G1+G2   : + fill next_open
  G1+G2+G3: + costos ON (produccion honesta)

Usa el motor canonico COMPLETO (no proxy). Recorta frames a N_BARS antes de
pasarlos para no recalcular market_structure sobre 50000 velas.

Uso: python scripts/r6_ablation.py [SYMBOL] [N_BARS]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import time

import pandas as pd

from ict_backtest.costs import resolve_cost
from ict_backtest.data_feed import load_frames
from ict_backtest.run_backtest import generate_sequence_signals
from ict_backtest.engine import simulate_trade, ICTSignal

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
N_BARS = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
HTF, LTF = "H4", "M15"
MAX_HOLD = 30


def _metrics(signals, ltf_df, cost):
    trades = []
    for sig in signals:
        tr, _ = simulate_trade(ltf_df, sig, MAX_HOLD, cost=cost)
        if tr is not None:
            trades.append(tr)
    if not trades:
        return {"pf": 0.0, "wr": 0.0, "trades": 0, "r": 0.0}
    wins = sum(1 for t in trades if t.pnl_r > 0)
    r = sum(t.pnl_r for t in trades)
    return {"pf": r, "wr": wins / len(trades), "trades": len(trades), "r": r}


def _run(mode: str, fill_mode: str, cost):
    frames = load_frames(SYMBOL, (HTF, LTF, "D1"))
    ltf = frames[LTF]
    if len(ltf) > N_BARS:
        ltf = ltf.iloc[-N_BARS:].reset_index(drop=True)
        frames = {**frames, LTF: ltf}
    signals = generate_sequence_signals(SYMBOL, HTF, LTF,
                                        counter_trend=False, tp_mode="fixed2r",
                                        require_displacement=False, displace_gap=6,
                                        bos_gap=10, frames=frames, fill_mode=fill_mode)
    ltf_df = frames[LTF]
    m = _metrics(signals, ltf_df, cost)
    print(f"[{mode:10s}] PF={m['pf']:+.2f}  WR={m['wr']*100:5.1f}%  trades={m['trades']:4d}  R={m['r']:+.1f}")
    return m


print(f"R6.4 ablation (motor real recortado): {SYMBOL} {LTF}, HTF {HTF}, N_BARS={N_BARS}")
t0 = time.time()
m1 = _run("G1", "signal_close", None)
m2 = _run("G1+G2", "next_open", None)
m3 = _run("G1+G2+G3", "next_open", resolve_cost(SYMBOL))
print(f"--- {time.time()-t0:.1f}s ---")
print(f"EFECTO RELOJ (G1->G1+G2):   PF {m1['pf']:+.2f} -> {m2['pf']:+.2f}")
print(f"EFECTO COSTOS (G1+G2->G3):  PF {m2['pf']:+.2f} -> {m3['pf']:+.2f}")
print(f"TOTAL (G1 teoria -> G3 prod): PF {m1['pf']:+.2f} -> {m3['pf']:+.2f}")
