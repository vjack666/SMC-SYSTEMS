from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent.parent
out_dir = root / 'results' / 'quant_audit' / 'charts'
out_dir.mkdir(parents=True, exist_ok=True)

E = pd.read_csv(root / 'results' / 'experiment_E.csv')
M = pd.read_csv(root / 'results' / 'ml_trade_dataset.csv')

# Session performance
session = E.groupby('session_bucket').agg(
    trades=('pnl_r', 'count'),
    winrate=('pnl_r', lambda x: (x > 0).mean()),
    expectancy=('pnl_r', 'mean')
).reset_index()

plt.figure(figsize=(8, 5))
plt.bar(session['session_bucket'], session['expectancy'], color=['#3b82f6', '#10b981', '#f59e0b'])
plt.title('Expectativa por sesión')
plt.ylabel('Expectativa R')
plt.xlabel('Session Bucket')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'session_expectancy.png', dpi=150)
plt.close()

# ML quartiles
E['ml_q'] = pd.qcut(E['ml_confidence'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
mlq = E.groupby('ml_q').agg(
    trades=('pnl_r', 'count'),
    winrate=('pnl_r', lambda x: (x > 0).mean()),
    expectancy=('pnl_r', 'mean'),
    mean_confidence=('ml_confidence', 'mean')
).reset_index()

plt.figure(figsize=(8, 5))
plt.plot(mlq['ml_q'], mlq['expectancy'], marker='o', linestyle='-', color='#6366f1')
plt.title('Expectativa por cuartil de ML confidence')
plt.ylabel('Expectativa R')
plt.xlabel('ML Confidence Quartil')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'ml_quartiles_expectancy.png', dpi=150)
plt.close()

# FVG age thresholds
thresh = [1, 2, 3, 4, 5, 10]
rows = []
for th in thresh:
    sub = E[E['bars_since_fvg_creation'] <= th]
    if len(sub):
        rows.append((th, len(sub), sub['pnl_r'].mean(), (sub['pnl_r'] > 0).mean()))

fvg_df = pd.DataFrame(rows, columns=['threshold', 'trades', 'expectancy', 'winrate'])
plt.figure(figsize=(8, 5))
plt.plot(fvg_df['threshold'], fvg_df['expectancy'], marker='o', color='#ef4444')
plt.title('Expectativa según edad de FVG (bars_since_fvg_creation)')
plt.xlabel('Threshold de barras')
plt.ylabel('Expectativa R')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'fvg_age_expectancy.png', dpi=150)
plt.close()

# Mitigation bins
bins = [(-1.0, 0.0), (0.0, 0.2), (0.2, 0.4), (0.4, 1.0)]
rows = []
for low, high in bins:
    sub = E[(E['mitigation_depth_pct'] > low) & (E['mitigation_depth_pct'] <= high)]
    if len(sub):
        rows.append((f'{low:.1f},{high:.1f}', len(sub), sub['pnl_r'].mean(), (sub['pnl_r'] > 0).mean()))
mit_df = pd.DataFrame(rows, columns=['bin', 'trades', 'expectancy', 'winrate'])
plt.figure(figsize=(8, 5))
plt.bar(mit_df['bin'], mit_df['expectancy'], color=['#8b5cf6', '#ec4899', '#22c55e', '#fb923c'])
plt.title('Expectativa por rango de mitigación')
plt.ylabel('Expectativa R')
plt.xlabel('Mitigation Depth Bin')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'mitigation_bins_expectancy.png', dpi=150)
plt.close()

# Hour quadrants
conds = [
    ('Q1', (E['hour_sin'] >= 0) & (E['hour_cos'] >= 0)),
    ('Q2', (E['hour_sin'] >= 0) & (E['hour_cos'] < 0)),
    ('Q3', (E['hour_sin'] < 0) & (E['hour_cos'] < 0)),
    ('Q4', (E['hour_sin'] < 0) & (E['hour_cos'] >= 0)),
]
rows = []
for label, cond in conds:
    sub = E[cond]
    if len(sub):
        rows.append((label, len(sub), sub['pnl_r'].mean(), (sub['pnl_r'] > 0).mean()))
hour_df = pd.DataFrame(rows, columns=['quadrant', 'trades', 'expectancy', 'winrate'])
plt.figure(figsize=(8, 5))
plt.bar(hour_df['quadrant'], hour_df['expectancy'], color=['#0ea5e9', '#14b8a6', '#22c55e', '#f97316'])
plt.title('Expectativa por cuadrante horario')
plt.ylabel('Expectativa R')
plt.xlabel('Cuadrante horario')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'hour_quadrant_expectancy.png', dpi=150)
plt.close()

# Feature correlations
features = [
    'ml_confidence', 'bars_since_fvg_creation', 'bars_since_mitigation',
    'mitigation_depth_pct', 'distance_prev_day_high', 'distance_prev_day_low',
    'distance_eqh', 'distance_eql', 'hour_sin', 'hour_cos'
]
corrs = []
for col in features:
    if col in E.columns:
        corr = pd.to_numeric(E[col], errors='coerce').corr(E['pnl_r'])
        corrs.append((col, corr))
feat_df = pd.DataFrame(corrs, columns=['feature', 'correlation']).sort_values('correlation')
plt.figure(figsize=(10, 5))
colors = ['#ef4444' if x < 0 else '#22c55e' for x in feat_df['correlation']]
plt.bar(feat_df['feature'], feat_df['correlation'], color=colors)
plt.title('Correlación de features con pnl_r')
plt.ylabel('Correlación')
plt.xlabel('Feature')
plt.xticks(rotation=45, ha='right')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'feature_correlations.png', dpi=150)
plt.close()

# Experiment comparison
experiment_names = ['results/experiment_A.csv','results/experiment_B.csv','results/experiment_C.csv','results/experiment_D.csv','results/experiment_E.csv']
rows = []
for name in experiment_names:
    df = pd.read_csv(root / name)
    pf = df[df['pnl_r'] > 0]['pnl_r'].sum() / abs(df[df['pnl_r'] < 0]['pnl_r'].sum()) if (df['pnl_r'] < 0).any() else float('inf')
    rows.append((Path(name).stem, len(df), pf, df['pnl_r'].mean(), (df['pnl_r'] > 0).mean()))
exp_df = pd.DataFrame(rows, columns=['experiment', 'trades', 'pf', 'expectancy', 'winrate'])
plt.figure(figsize=(10, 5))
plt.plot(exp_df['experiment'], exp_df['pf'], marker='o', linestyle='-', color='#2563eb')
plt.title('Profit Factor por experimento')
plt.ylabel('Profit Factor')
plt.xlabel('Experimento')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'experiment_pf_comparison.png', dpi=150)
plt.close()

plt.figure(figsize=(10, 5))
plt.plot(exp_df['experiment'], exp_df['expectancy'], marker='o', linestyle='-', color='#16a34a')
plt.title('Expectativa por experimento')
plt.ylabel('Expectativa R')
plt.xlabel('Experimento')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out_dir / 'experiment_expectancy_comparison.png', dpi=150)
plt.close()

print('Charts saved to', out_dir)
print('Report images generated:')
for path in sorted(out_dir.glob('*.png')):
    print('-', path.name)
