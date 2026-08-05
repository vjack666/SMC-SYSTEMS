import pandas as pd

df_e = pd.read_csv('results/experiment_E.csv', low_memory=False)
df_f = pd.read_csv('results/forensic_trades_dataset.csv', low_memory=False)

keys = ['setup_id', 'symbol', 'side', 'entry_idx', 'sl_atr_mult']
print('df_e rows', len(df_e), 'df_f rows', len(df_f))
for k in keys:
    print('unique', k, 'E', df_e[k].nunique(), 'F', df_f[k].nunique())

merged = df_e.merge(df_f[keys + ['fvg_size_atr', 'hour', 'mitigation_depth_pct']], on=keys, how='left', indicator=True)
print('merged rows', len(merged))
print(merged['_merge'].value_counts().to_dict())
print('na fvg_size_atr count', merged['fvg_size_atr'].isna().sum())
print('na hour count', merged['hour'].isna().sum())
print('na mitigation count', merged['mitigation_depth_pct'].isna().sum())
print('sample unmatched E head')
print(merged[merged['_merge']!='both'][keys].head(10))
