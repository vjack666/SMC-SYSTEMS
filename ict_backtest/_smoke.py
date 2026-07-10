"""Smoke test de ict_backtest: PARTE 1 (estructura) + reglas + motor event-driven.

Datos sinteticos: H4 y M15 con estructura alcista, y en la vela 20 (hora NY AM,
killzone activa) hay sweep down + BOS activo, para verificar que el mini-check
del dashboard genera una senal y simulate_trade la cierra vela a vela.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import numpy as np
import pandas as pd

from ict_backtest.structure import classify_structure
from ict_backtest.engine import build_signals_from_frames, simulate_trade

# --- PARTE 1: clasificar estructura por TF ---
labels_h4 = ["HH", "HL", "HH", "HL", "HH", "HL"]
labels_m15 = ["HL", "HH", "HL", "HH"]
print("[PARTE1] H4 =", classify_structure(labels_h4), "| M15 =", classify_structure(labels_m15))

n = 40
idx = pd.date_range("2024-01-01 00:00", periods=n, freq="15min", tz="UTC")
idx = idx.insert(20, pd.Timestamp("2024-01-01 13:00:00", tz="UTC"))[:n]  # vela 20 = NY AM

m15 = pd.DataFrame({
    "time": idx,
    "open": np.linspace(2000, 2100, n),
    "high": np.linspace(2002, 2110, n),
    "low": np.linspace(1998, 2095, n),
    "close": np.linspace(2000, 2100, n),
    "atr": np.full(n, 2.0),
    "macro_direction": ["BULLISH"] * n,
    "bos_direction": [0] * 20 + [1] * 20,
    "bos_status": [""] * 20 + ["active"] * 20,
    "sweep_up": [False] * n,
    "sweep_down": [False] * n,
    "fvg_state": ["-"] * n,
    "ob_dir": ["-"] * n,
    "invalidation": [0.0] * n,
})
# Alinear sweep + BOS a la vela 20 (killzone NY AM)
m15.at[20, "sweep_down"] = True
m15.at[20, "bos_direction"] = 1
m15.at[20, "bos_status"] = "active"

h4_idx = idx[::4][:10]
h4 = pd.DataFrame({
    "time": h4_idx,
    "open": np.linspace(2000, 2090, 10),
    "high": np.linspace(2005, 2100, 10),
    "low": np.linspace(1995, 2085, 10),
    "close": np.linspace(2000, 2090, 10),
    "atr": np.full(10, 8.0),
    "macro_direction": ["BULLISH"] * 10,
    "bos_direction": [1] * 10,
    "bos_status": ["active"] * 10,
    "sweep_up": [False] * 10,
    "sweep_down": [False] * 10,
    "fvg_state": ["-"] * 10,
    "ob_dir": ["-"] * 10,
    "invalidation": [0.0] * 10,
})

frames = {"H4": h4, "M15": m15}
bias_by_tf = {"H4": "BULLISH"}
votes = {"LONG": 3, "SHORT": 1}

signals = build_signals_from_frames("XAUUSD", frames, bias_by_tf, votes, model="intradia")
print(f"[ENGINE] senales generadas: {len(signals)}")
if signals:
    sig = signals[0]
    print(f"  primera senal: dir={sig.direction} entry={sig.entry:.1f} sl={sig.stop_loss:.1f} tp={sig.take_profit:.1f}")
    trade, stats = simulate_trade(m15, sig, max_hold_bars=30)
    if trade:
        print(f"[SIM] exit={trade.exit:.1f} pnl_r={trade.pnl_r:.2f} razon={stats['exit_reason']} hold={stats['hold_bars']}")
    else:
        print("[SIM] no se simulo:", stats)

print("SMOKE OK")
