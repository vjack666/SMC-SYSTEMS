from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import numpy as np

# --- Step 1: Monkey-patch to make Wyckoff-OFF produce trades ---
# The issue: PAC exhaustion series depends on Wyckoff accumulation.
# For a fair comparison, add a volume-spread fallback when Wyckoff is OFF.

import strategy.scalping_setup as ss

_original_build_exhaustion = ss._build_exhaustion_series

def _patched_build_exhaustion(data: pd.DataFrame, config: ss.ScalpingConfig) -> pd.Series:
    series = _original_build_exhaustion(data, config)
    # If Wyckoff is OFF, add a volume-spread fallback exhaustion
    if not config.use_wyckoff:
        atr = data["atr"] if "atr" in data.columns else data["close"] * 0.001
        fallback = (data["high"] - data["low"]) > atr * 1.2
        series = series | fallback
    return series

ss._build_exhaustion_series = _patched_build_exhaustion

# --- Step 2: Prepare truncated data ---
N_BARS = 30000
data_dir = Path("data/mt5")
tmp_dir = Path("data/tmp_bt")
tmp_dir.mkdir(exist_ok=True, parents=True)

for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    for tf in ("M15",):
        df = pd.read_parquet(data_dir / f"{symbol}_{tf}.parquet")
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df.tail(N_BARS).reset_index(drop=True).to_parquet(tmp_dir / f"{symbol}_{tf}.parquet", compression="zstd")
for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    for tf, n in [("H4", 5000), ("D1", 2000)]:
        df = pd.read_parquet(data_dir / f"{symbol}_{tf}.parquet")
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df.tail(n).reset_index(drop=True).to_parquet(tmp_dir / f"{symbol}_{tf}.parquet", compression="zstd")

print("Data ready.\n", flush=True)

from backtest.combined_backtest import CombinedBacktestConfig, run_combined_backtest
from strategy.scalping_setup import ScalpingConfig


def run_test(label: str, use_wyckoff: bool) -> dict:
    cfg = CombinedBacktestConfig(
        symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        data_dir=tmp_dir,
        scalping_config=ScalpingConfig(
            use_wyckoff=use_wyckoff,
            use_stochastic_exhaustion=True,
            use_pac=True,
            use_structural_sl=True,
        ),
        use_ml_quality_filter=False,
    )
    t0 = time.time()
    print(f"[{label}] ...", flush=True)
    try:
        metrics, trades = run_combined_backtest(cfg)
        elapsed = time.time() - t0
        nt = int(metrics.get("total_trades", 0))
        pf = float(metrics.get("profit_factor", 0.0))
        wr = float(metrics.get("win_rate", 0.0))
        sh = float(metrics.get("sharpe_ratio", 0.0))
        ex = float(metrics.get("expectancy_r", 0.0))
        print(f"[{label}] {elapsed:.0f}s | trades={nt} PF={pf:.4f} WR={wr:.4f} Sharpe={sh:.4f} Expect={ex:.4f}", flush=True)
        if trades is not None and len(trades) > 0:
            print(f"  Symbols: {trades['symbol'].value_counts().to_dict()}")
            print(f"  Directions: {trades['direction'].value_counts().to_dict()}")
        return {
            "total_trades": nt, "win_rate": wr, "profit_factor": pf,
            "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
            "max_daily_drawdown_pct": float(metrics.get("max_daily_drawdown_pct", 0.0)),
            "sharpe_ratio": sh, "expectancy_r": ex,
        }
    except RuntimeError as e:
        elapsed = time.time() - t0
        print(f"[{label}] {elapsed:.0f}s | 0 trades: {e}", flush=True)
        return {k: 0.0 for k in ["total_trades","win_rate","profit_factor",
                                   "max_drawdown_pct","max_daily_drawdown_pct",
                                   "sharpe_ratio","expectancy_r"]}


print("=" * 60)
print("Test: Full pipeline (PAC + Exhaustion + fallback for OFF)")
print("=" * 60)
r_on  = run_test("Wyckoff ON",  use_wyckoff=True)
r_off = run_test("Wyckoff OFF (fallback)", use_wyckoff=False)

print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
keys = [("total_trades","Trades","int"),("win_rate","Win Rate",".4f"),
        ("profit_factor","PF",".4f"),("max_drawdown_pct","Max DD%",".4f"),
        ("sharpe_ratio","Sharpe",".4f"),("expectancy_r","Expect",".4f")]
print(f"{'Metric':<20} {'WyckOFF':>10} {'WyckOFF':>10} {'Delta':>10}")
print("-" * 50)
for k, l, f in keys:
    av, bv = r_on.get(k, 0), r_off.get(k, 0)
    if f == "int":
        print(f"{l:<20} {int(av):>10d} {int(bv):>10d} {int(av-bv):>+10d}")
    else:
        print(f"{l:<20} {av:>10.4f} {bv:>10.4f} {av-bv:>+10.4f}")

delta = r_on.get("profit_factor", 0) - r_off.get("profit_factor", 0)
print(f"\nPF delta: {delta:+.4f}")
print(f"Wyckoff filter effect: {'IMPROVES' if delta > 0.05 else 'NEUTRAL' if delta >= -0.05 else 'HARMS'} PF")

combined = {
    "wyckoff_on": r_on,
    "wyckoff_off_fallback": r_off,
    "pf_delta": delta,
    "note": "OFF uses volume-spread fallback for PAC exhaustion (otherwise 0 trades)",
}
Path("results/bt_fair_comparison.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")

# --- Step 3: Cleanup ---
import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)
print(f"\nResults saved to results/bt_fair_comparison.json")
