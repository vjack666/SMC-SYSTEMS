from __future__ import annotations

import time
from pathlib import Path

from strategy.scalping_setup import ScalpingConfig, build_scalping_context

print("Building context (5000 bars, EURUSD)...", flush=True)
t0 = time.time()

ctx = build_scalping_context(
    symbol="EURUSD",
    timeframe="M15",
    data_dir=Path("data/mt5"),
    config=ScalpingConfig(use_wyckoff=True, use_structural_sl=True, use_pac=True),
)

elapsed = time.time() - t0
print(f"Context built in {elapsed:.1f}s", flush=True)
print(f"Rows: {len(ctx)}", flush=True)
print(f"Columns: {list(ctx.columns)}", flush=True)
