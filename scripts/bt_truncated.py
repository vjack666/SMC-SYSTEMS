from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

# --- Truncate data ---
N_BARS = 3000
START = "2026-03-01"
END = "2026-05-31"

data_dir = Path("data/mt5")
tmp_dir = Path("data/tmp")
tmp_dir.mkdir(exist_ok=True)

for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    for tf in ("M15",):
        df = pd.read_parquet(data_dir / f"{symbol}_{tf}.parquet")
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df.tail(N_BARS).reset_index(drop=True).to_parquet(tmp_dir / f"{symbol}_{tf}.parquet", compression="zstd")
for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    for tf, n in [("H4", 2000), ("D1", 1000)]:
        df = pd.read_parquet(data_dir / f"{symbol}_{tf}.parquet")
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df.tail(n).reset_index(drop=True).to_parquet(tmp_dir / f"{symbol}_{tf}.parquet", compression="zstd")

print("Data truncated.\n", flush=True)

from backtest.combined_backtest import CombinedBacktestConfig, run_combined_backtest
from strategy.scalping_setup import ScalpingConfig


def run_test(label: str, use_wyckoff: bool, use_pac: bool, use_exhaustion: bool) -> dict[str, Any]:
    cfg = CombinedBacktestConfig(
        symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        data_dir=tmp_dir,
        scalping_config=ScalpingConfig(
            use_wyckoff=use_wyckoff,
            use_stochastic_exhaustion=use_exhaustion,
            use_pac=use_pac,
            use_structural_sl=True,
        ),
        use_ml_quality_filter=False,
        start_time=START,
        end_time=END,
    )
    t0 = time.time()
    print(f"[{label}] ...", flush=True)
    try:
        metrics, trades = run_combined_backtest(cfg)
        elapsed = time.time() - t0
        nt = int(metrics.get("total_trades", 0))
        pf = float(metrics.get("profit_factor", 0.0))
        print(f"[{label}] {elapsed:.0f}s | trades={nt} PF={pf:.4f}", flush=True)
        return {
            "label": label, "use_wyckoff": use_wyckoff, "use_pac": use_pac,
            "total_trades": nt,
            "win_rate": float(metrics.get("win_rate", 0.0)),
            "profit_factor": pf,
            "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
            "max_daily_drawdown_pct": float(metrics.get("max_daily_drawdown_pct", 0.0)),
            "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
            "expectancy_r": float(metrics.get("expectancy_r", 0.0)),
        }
    except RuntimeError as e:
        elapsed = time.time() - t0
        print(f"[{label}] {elapsed:.0f}s | 0 trades (RuntimeError)", flush=True)
        return {"label": label, "use_wyckoff": use_wyckoff, "use_pac": use_pac,
                "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "max_drawdown_pct": 0.0, "max_daily_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0, "expectancy_r": 0.0}


print("=" * 60)
print("TEST 1: Full pipeline (PAC + Exhaustion ON)")
print("=" * 60)
r1a = run_test("1A_Wyckoff_ON",  use_wyckoff=True,  use_pac=True, use_exhaustion=True)
r1b = run_test("1B_Wyckoff_OFF", use_wyckoff=False, use_pac=True, use_exhaustion=True)

print()
print("=" * 60)
print("TEST 2: No PAC (pure Wyckoff filter)")
print("=" * 60)
r2a = run_test("2A_Wyckoff_ON",  use_wyckoff=True,  use_pac=False, use_exhaustion=False)
r2b = run_test("2B_Wyckoff_OFF", use_wyckoff=False, use_pac=False, use_exhaustion=False)


def compare(a: dict, b: dict, title: str) -> None:
    keys = [("total_trades","Trades","int"),("win_rate","Win Rate",".4f"),
            ("profit_factor","PF",".4f"),("max_drawdown_pct","Max DD%",".4f"),
            ("sharpe_ratio","Sharpe",".4f"),("expectancy_r","Expect",".4f")]
    print(f"\n--- {title} ---")
    print(f"{'Metric':<15} {'ON':>10} {'OFF':>10} {'Delta':>10}")
    print("-" * 45)
    for k, l, f in keys:
        av, bv = a.get(k, 0), b.get(k, 0)
        if f == "int":
            print(f"{l:<15} {int(av):>10d} {int(bv):>10d} {int(av-bv):>+10d}")
        else:
            print(f"{l:<15} {av:>10.4f} {bv:>10.4f} {av-bv:>+10.4f}")
    delta = a.get("profit_factor", 0) - b.get("profit_factor", 0)
    print(f"\nPF delta: {delta:+.4f}")
    print(f"Recommend: {'ENABLE' if delta >= 0 else 'DISABLE'} Wyckoff")

compare(r1a, r1b, "TEST 1: Full pipeline")
compare(r2a, r2b, "TEST 2: No PAC (pure filter)")

combined = {
    "test1_full_pipeline": {"wyckoff_on": r1a, "wyckoff_off": r1b},
    "test2_no_pac":        {"wyckoff_on": r2a, "wyckoff_off": r2b},
}
Path("results/bt_wyckoff_comparison.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
