from pathlib import Path
import pandas as pd
root = Path(__file__).resolve().parent.parent
for name in ['results/experiment_A.csv','results/experiment_B.csv','results/experiment_C.csv','results/experiment_D.csv','results/experiment_E.csv']:
    p = root / name
    if p.exists():
        df = pd.read_csv(p)
        pf = df[df['pnl_r'] > 0]['pnl_r'].sum() / abs(df[df['pnl_r'] < 0]['pnl_r'].sum()) if (df['pnl_r'] < 0).any() else float('inf')
        print(f'{name}: rows={len(df)} pf={pf:.4f} exp={df["pnl_r"].mean():.4f} wr={(df["pnl_r"]>0).mean():.4f}')
        if 'structure_event' in df.columns:
            print('  structure_event', df['structure_event'].value_counts().to_dict())
            for v, sub in df.groupby('structure_event'):
                pf_sub = sub[sub['pnl_r'] > 0]['pnl_r'].sum() / abs(sub[sub['pnl_r'] < 0]['pnl_r'].sum()) if (sub['pnl_r'] < 0).any() else float('inf')
                print(f'    {v}: n={len(sub)} pf={pf_sub:.4f} exp={sub["pnl_r"].mean():.4f} wr={(sub["pnl_r"]>0).mean():.4f}')
        if 'ob_state' in df.columns:
            print('  ob_state', df['ob_state'].value_counts().to_dict())
        print('---')

M = pd.read_csv(root / 'results' / 'ml_trade_dataset.csv')
for col in ['fvg_detected','bos_detected']:
    if col in M.columns:
        sub1 = M[M[col] == 1]
        sub0 = M[M[col] == 0]
        if len(sub1) and len(sub0):
            pf1 = sub1[sub1['pnl_r'] > 0]['pnl_r'].sum() / abs(sub1[sub1['pnl_r'] < 0]['pnl_r'].sum()) if (sub1['pnl_r'] < 0).any() else float('inf')
            pf0 = sub0[sub0['pnl_r'] > 0]['pnl_r'].sum() / abs(sub0[sub0['pnl_r'] < 0]['pnl_r'].sum()) if (sub0['pnl_r'] < 0).any() else float('inf')
            print(f'{col}=1: n={len(sub1)} pf={pf1:.4f} exp={sub1["pnl_r"].mean():.4f}')
            print(f'{col}=0: n={len(sub0)} pf={pf0:.4f} exp={sub0["pnl_r"].mean():.4f}')
            print('---')

for col in ['market_regime','volatility_regime','regime','trend_regime','volatility']:
    if col in M.columns:
        print('Column', col, 'unique', M[col].nunique())
        print(M[col].value_counts(dropna=False).head(20).to_string())
        print('---')
