from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from strategy.scalping_setup import ScalpingConfig, build_scalping_context

print("Loading last 1000 bars...", flush=True)
full = pd.read_parquet("data/mt5/EURUSD_M15.parquet")
full["time"] = pd.to_datetime(full["time"], utc=True)
small = full.tail(1000).reset_index(drop=True)
small.to_parquet("data/mt5/_temp_EURUSD_M15.parquet", compression="zstd")
print(f"Wrote {len(small)} rows", flush=True)

t0 = time.time()
print("Building context...", flush=True)
ctx = build_scalping_context(
    symbol="_temp",
    timeframe="M15",
    data_dir=Path("data/mt5"),
    config=ScalpingConfig(use_wyckoff=True, use_pac=False, use_structural_sl=False),
)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s, rows={len(ctx)}, cols={len(ctx.columns)}", flush=True)
