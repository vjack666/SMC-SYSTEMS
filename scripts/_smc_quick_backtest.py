"""Quick offline backtest runner — bypasses MT5 download, uses cached parquet.

Usage:
    C:/Users/v_jac/smc_probe/Scripts/python.exe scripts/_smc_quick_backtest.py \
        --symbols EURUSD GBPUSD USDCHF --no-ml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import CombinedBacktestConfig, run_combined_backtest  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "USDCHF"])
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--no-ml", action="store_true")
    ap.add_argument("--max-bars", type=int, default=None)
    ap.add_argument("--out", default="results/_quick_backtest.json")
    args = ap.parse_args()

    cfg = CombinedBacktestConfig(
        data_dir=Path(args.data_dir),
        symbols=tuple(args.symbols),
        timeframe=args.timeframe,
        use_ml_quality_filter=not args.no_ml,
        max_bars=args.max_bars,
    )
    metrics, trades = run_combined_backtest(cfg, progress_cb=None)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print("METRICS:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
