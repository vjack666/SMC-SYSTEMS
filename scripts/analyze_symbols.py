import sys; sys.path.insert(0, '.')
from pathlib import Path
from strategy.scalping_setup import build_scalping_context, ScalpingConfig
from backtest.combined_backtest import _build_signals_from_context

data_dir = Path('data/tmp_debug')
cfg = ScalpingConfig(use_pac=True, use_wyckoff=True, use_stochastic_exhaustion=True)

for sym in ('EURUSD', 'GBPUSD', 'XAUUSD'):
    ctx = build_scalping_context(symbol=sym, data_dir=data_dir, config=cfg)
    signals = _build_signals_from_context(sym, ctx, 0.52, cfg)
    dirs = [s.direction for s in signals]
    confs = [round(s.confidence, 3) for s in signals]
    pac = int(ctx['pac_entry_ready'].sum())
    print(f'{sym}: {len(signals)} signals, dirs={dirs}, confs={confs}, pac_ready={pac}')
    if 'wyckoff_phase' in ctx.columns:
        phases = ctx['wyckoff_phase'].value_counts().to_dict()
        print(f'  phases={phases}')
    for col in ['wyckoff_accumulation', 'wyckoff_distribution']:
        if col in ctx.columns:
            val = int(ctx[col].sum())
            print(f'  {col}={val}')
