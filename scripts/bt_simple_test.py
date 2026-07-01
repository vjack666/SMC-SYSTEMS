from __future__ import annotations

import sys
import time
from pathlib import Path

# Quick test: run backtest on 1 symbol with limited bars
from backtest.combined_backtest import CombinedBacktestConfig, run_combined_backtest
from strategy.scalping_setup import ScalpingConfig

print("Starting backtest (single symbol, 5000 bars)...", flush=True)
t0 = time.time()

cfg = CombinedBacktestConfig(
    symbols=("EURUSD",),
    max_bars=5000,
    scalping_config=ScalpingConfig(use_wyckoff=True, use_structural_sl=True, use_pac=True),
    use_ml_quality_filter=False,
)

try:
    metrics, trades = run_combined_backtest(cfg)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s", flush=True)
    print(f"Trades: {metrics.get('total_trades', 0)}", flush=True)
    print(f"PF: {metrics.get('profit_factor', 0.0):.4f}", flush=True)
    print(f"WR: {metrics.get('win_rate', 0.0):.4f}", flush=True)
except Exception as e:
    print(f"FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
