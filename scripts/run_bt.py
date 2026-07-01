import sys
sys.path.insert(0, '.')
from pathlib import Path
import pandas as pd
from backtest.combined_backtest import run_combined_backtest, CombinedBacktestConfig
from strategy.scalping_setup import ScalpingConfig

# Pre-truncate to 15000 bars for speed
data_dir = Path('data/tmp_15k')
data_dir.mkdir(parents=True, exist_ok=True)
src = Path('data/mt5')
for sym in ('EURUSD', 'GBPUSD', 'XAUUSD'):
    df_m15 = pd.read_parquet(src / f'{sym}_M15.parquet')
    df_m15 = df_m15.tail(15000).reset_index(drop=True)
    start = df_m15['time'].iloc[0]
    end = df_m15['time'].iloc[-1]
    for tf in ('H4', 'D1'):
        df = pd.read_parquet(src / f'{sym}_{tf}.parquet')
        df['time'] = pd.to_datetime(df['time'], utc=True)
        mask = (df['time'] >= pd.to_datetime(start, utc=True)) & (df['time'] <= pd.to_datetime(end, utc=True))
        df[mask].reset_index(drop=True).to_parquet(data_dir / f'{sym}_{tf}.parquet', compression='zstd')
    df_m15.to_parquet(data_dir / f'{sym}_M15.parquet', compression='zstd')

cfg = CombinedBacktestConfig(
    data_dir=data_dir,
    max_bars=0,
    min_confidence=0.52,
    max_hold_bars=48,
    use_ml_quality_filter=False,
    scalping_config=ScalpingConfig(use_pac=True, use_wyckoff=True, use_stochastic_exhaustion=True),
)
metrics, trades_df = run_combined_backtest(cfg)
n = len(trades_df)
print(f'trades={n} wr={metrics["win_rate"]:.3f} pf={metrics["profit_factor"]:.3f} ev={metrics["expectancy_r"]:.3f} dd={metrics["max_drawdown_r"]:.2f}')
if n > 0:
    print(trades_df[['symbol','direction','pnl_r','entry_time']].to_string())
    for sym, grp in trades_df.groupby('symbol'):
        dirs = grp['direction'].value_counts().to_dict()
        print(f'  {sym}: {len(grp)} trades, dirs={dirs}, pnl={grp["pnl_r"].sum():.2f}R')
