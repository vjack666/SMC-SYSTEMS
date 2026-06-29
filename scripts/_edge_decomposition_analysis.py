from pathlib import Path
import pandas as pd
import numpy as np

E = pd.read_csv(Path('results/experiment_E.csv'))
M = pd.read_csv(Path('results/ml_trade_dataset.csv'))

print('E rows', len(E))
print('E winrate', (E['pnl_r'] > 0).mean())
print('E pf', E[E['pnl_r'] > 0]['pnl_r'].sum() / abs(E[E['pnl_r'] < 0]['pnl_r'].sum()))
print('E expectancy', E['pnl_r'].mean())
print()
print('structure_event counts')
print(E['structure_event'].value_counts())
print('ob_state counts')
print(E['ob_state'].value_counts())
print('session_bucket counts')
print(E['session_bucket'].value_counts())
print('mitigation_depth_pct describe')
print(E['mitigation_depth_pct'].describe())
print('ml_confidence describe')
print(E['ml_confidence'].describe())
print()

print('session performance')
print(E.groupby('session_bucket')['pnl_r'].agg(trades='count', winrate=lambda x: (x > 0).mean(), expectancy='mean'))
print()

bins = [0.0, 0.5, 0.6, 0.7, 0.8, 1.0]
E['ml_bin'] = pd.cut(E['ml_confidence'], bins, right=True, include_lowest=True)
print('ml confidence bins')
print(E.groupby('ml_bin')['pnl_r'].agg(trades='count', winrate=lambda x: (x > 0).mean(), expectancy='mean'))
print('ml confidence quartiles')
E['ml_q'] = pd.qcut(E['ml_confidence'], 4, labels=False)
print(E.groupby('ml_q').agg(trades=('pnl_r', 'count'), winrate=('pnl_r', lambda x: (x > 0).mean()), expectancy=('pnl_r', 'mean'), mean_confidence=('ml_confidence', 'mean')))
print()

print('feature correlations with pnl_r')
for col in ['ml_confidence', 'bars_since_fvg_creation', 'bars_since_mitigation', 'mitigation_depth_pct', 'distance_prev_day_high', 'distance_prev_day_low', 'distance_eqh', 'distance_eql', 'hour_sin', 'hour_cos']:
    if col in E.columns:
        corr = pd.to_numeric(E[col], errors='coerce').corr(E['pnl_r'])
        print(col, corr)
print()

print('M row count', len(M))
for col in ['fvg_detected', 'bos_detected', 'order_block_detected']:
    if col in M.columns:
        sub1 = M[M[col] == 1]
        sub0 = M[M[col] == 0]
        if len(sub1) and len(sub0):
            print(col, '1:', len(sub1), 'wr', (sub1['win'] == 1).mean(), 'exp', sub1['pnl_r'].mean(), '| 0:', len(sub0), 'wr', (sub0['win'] == 1).mean(), 'exp', sub0['pnl_r'].mean())
print()

if 'market_regime' in M.columns:
    print('market_regime performance')
    print(M.groupby('market_regime')['pnl_r'].agg(trades='count', winrate=lambda x: (M.loc[x.index, 'win'] == 1).mean(), expectancy='mean'))
print()
if 'volatility_regime' in M.columns:
    print('volatility_regime performance')
    print(M.groupby('volatility_regime')['pnl_r'].agg(trades='count', winrate=lambda x: (M.loc[x.index, 'win'] == 1).mean(), expectancy='mean'))
print()
print('bars_since_fvg_creation categories')
for th in [1,2,3,4,5,10]:
    sub = E[E['bars_since_fvg_creation'] <= th]
    if len(sub):
        wins = (sub['pnl_r'] > 0).sum(); losses = (sub['pnl_r'] < 0).sum();
        pf = sub[sub['pnl_r'] > 0]['pnl_r'].sum() / abs(sub[sub['pnl_r'] < 0]['pnl_r'].sum()) if losses > 0 else float('inf')
        print(f'<= {th}: n={len(sub)} wr={(wins/len(sub)):.3f} pf={pf:.3f} exp={sub["pnl_r"].mean():.4f}')
print('mitigation_depth_pct bins')
for bins in [(-1.0,0.0),(0.0,0.2),(0.2,0.4),(0.4,1.0)]:
    sub = E[(E['mitigation_depth_pct'] > bins[0]) & (E['mitigation_depth_pct'] <= bins[1])]
    if len(sub):
        wins = (sub['pnl_r'] > 0).sum(); losses = (sub['pnl_r'] < 0).sum();
        pf = sub[sub['pnl_r'] > 0]['pnl_r'].sum() / abs(sub[sub['pnl_r'] < 0]['pnl_r'].sum()) if losses > 0 else float('inf')
        print(f'{bins}: n={len(sub)} wr={(wins/len(sub)):.3f} pf={pf:.3f} exp={sub["pnl_r"].mean():.4f}')
print('ml_confidence linear slope on pnl_r')
coef = np.polyfit(E['ml_confidence'], E['pnl_r'], 1)
print('slope', coef[0], 'intercept', coef[1])
print('hour quadrant mean pnl')
for label, cond in [('Q1', (E['hour_sin'] >= 0) & (E['hour_cos'] >= 0)), ('Q2', (E['hour_sin'] >= 0) & (E['hour_cos'] < 0)), ('Q3', (E['hour_sin'] < 0) & (E['hour_cos'] < 0)), ('Q4', (E['hour_sin'] < 0) & (E['hour_cos'] >= 0))]:
    sub = E[cond]
    if len(sub):
        print(label, len(sub), 'wr', (sub['pnl_r'] > 0).mean(), 'exp', sub['pnl_r'].mean())
