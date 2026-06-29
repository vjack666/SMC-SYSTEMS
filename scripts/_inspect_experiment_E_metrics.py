import pandas as pd

path = 'results/experiment_E.csv'
df = pd.read_csv(path)

def metrics(sub):
    r = pd.to_numeric(sub['pnl_r'], errors='coerce').dropna()
    wins = r[r > 0].sum()
    losses = -r[r < 0].sum()
    pf = wins / losses if losses > 0 else float('inf')
    eq = r.cumsum()
    dd = -(eq - eq.cummax()).min() if not eq.empty else 0.0
    sharpe = (r.mean() / r.std(ddof=0) * (len(r) ** 0.5)) if len(r) > 1 and r.std(ddof=0) > 0 else float('nan')
    return {
        'count': len(r),
        'winrate': float((r > 0).mean()) if len(r) > 0 else float('nan'),
        'pf': float(pf),
        'expectancy': float(r.mean()) if len(r) > 0 else float('nan'),
        'max_drawdown': float(dd),
        'net_r': float(r.sum()),
        'sharpe': float(sharpe),
    }

for mult in [None, 1.0, 1.5, 2.0]:
    if mult is None:
        sub = df
        label = 'all'
    else:
        sub = df[df['sl_atr_mult'] == mult]
        label = f'sl_atr_mult={mult}'
    print(label, metrics(sub))
