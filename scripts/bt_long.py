from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

# Longer test: 30,000 bars (~2 years of M15)
N_BARS = 30000
data_dir = Path("data/mt5")
tmp_dir = Path("data/tmp_long")
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

print(f"Data truncated to last {N_BARS} M15 bars.\n", flush=True)

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
        print(f"[{label}] {elapsed:.0f}s | trades={nt} PF={pf:.4f} WR={float(metrics.get('win_rate',0.0)):.4f} Sharpe={float(metrics.get('sharpe_ratio',0.0)):.4f}", flush=True)
        if trades is not None:
            pd.set_option("display.max_rows", 50)
            print(trades.to_string())
        return {
            "total_trades": nt,
            "win_rate": float(metrics.get("win_rate", 0.0)),
            "profit_factor": pf,
            "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
            "max_daily_drawdown_pct": float(metrics.get("max_daily_drawdown_pct", 0.0)),
            "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
            "expectancy_r": float(metrics.get("expectancy_r", 0.0)),
        }
    except RuntimeError:
        elapsed = time.time() - t0
        print(f"[{label}] {elapsed:.0f}s | 0 trades", flush=True)
        return {k: 0.0 for k in ["total_trades","win_rate","profit_factor","max_drawdown_pct","max_daily_drawdown_pct","sharpe_ratio","expectancy_r"]}


r_on  = run_test("Wyckoff_ON",  use_wyckoff=True)
r_off = run_test("Wyckoff_OFF", use_wyckoff=False)

print("\n" + "=" * 60)
print("LONG BACKTEST COMPARISON (30k bars)")
print("=" * 60)
keys = [("total_trades","Trades","int"),("win_rate","Win Rate",".4f"),
        ("profit_factor","PF",".4f"),("max_drawdown_pct","Max DD%",".4f"),
        ("sharpe_ratio","Sharpe",".4f"),("expectancy_r","Expect",".4f")]
print(f"{'Metric':<15} {'ON':>12} {'OFF':>12} {'Delta':>12}")
print("-" * 51)
for k, l, f in keys:
    av, bv = r_on.get(k, 0), r_off.get(k, 0)
    if f == "int":
        print(f"{l:<15} {int(av):>12d} {int(bv):>12d} {int(av-bv):>+12d}")
    else:
        print(f"{l:<15} {av:>12.4f} {bv:>12.4f} {av-bv:>+12.4f}")

delta = r_on.get("profit_factor", 0) - r_off.get("profit_factor", 0)
print(f"\nPF delta: {delta:+.4f}")
print(f"Recommend: {'ENABLE' if delta >= 0 else 'DISABLE'} Wyckoff")

combined = {"wyckoff_on": r_on, "wyckoff_off": r_off, "pf_delta": delta, "n_bars": N_BARS}
Path("results/bt_long_comparison.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
