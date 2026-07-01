from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from backtest.combined_backtest import (
    CombinedBacktestConfig,
    run_combined_backtest,
)
from strategy.scalping_setup import ScalpingConfig


def run_with_bars(n_bars: int) -> tuple[dict, pd.DataFrame | None]:
    # Pre-truncate data to avoid processing ALL rows
    data_dir = Path("data/mt5")
    cfg = CombinedBacktestConfig(
        symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        scalping_config=ScalpingConfig(
            use_wyckoff=True,
            use_stochastic_exhaustion=True,
            use_pac=True,
            use_structural_sl=True,
        ),
        use_ml_quality_filter=False,
        max_bars=n_bars,
    )
    t0 = time.time()
    metrics, trades = run_combined_backtest(cfg)
    elapsed = time.time() - t0
    return metrics, trades, elapsed


print("=" * 60)
print("Fast backtest (3000 bars, 3 symbols)")
print("=" * 60)

metrics, trades, elapsed = run_with_bars(3000)
print(f"Time: {elapsed:.1f}s")
print(f"Trades: {metrics.get('total_trades', 0)}")
print(f"Win Rate: {metrics.get('win_rate', 0.0):.4f}")
print(f"Profit Factor: {metrics.get('profit_factor', 0.0):.4f}")
print(f"Max DD%: {metrics.get('max_drawdown_pct', 0.0):.4f}")
print(f"Sharpe: {metrics.get('sharpe_ratio', 0.0):.4f}")
print(f"Expectancy: {metrics.get('expectancy_r', 0.0):.4f}")

if trades is not None and len(trades) > 0:
    print(f"\nTrade breakdown:")
    for _, t in trades.iterrows():
        print(f"  {t.get('symbol','?'):8s} dir={int(t.get('direction',0)):>2d}  entry={t.get('entry',0.0):>8.4f}  exit={t.get('exit',0.0):>8.4f}  pnl={t.get('pnl_r',0.0):>+8.4f}")
