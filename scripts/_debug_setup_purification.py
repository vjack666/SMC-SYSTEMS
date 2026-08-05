import pandas as pd

df_e = pd.read_csv('results/experiment_E.csv', low_memory=False)
df_f = pd.read_csv('results/forensic_trades_dataset.csv', low_memory=False)
for col in ['setup_id', 'symbol', 'side', 'entry_idx', 'sl_atr_mult', 'fvg_size_atr', 'hour']:
    print('E has', col, col in df_e.columns)
    print('F has', col, col in df_f.columns)
keys = ['setup_id','symbol','side','entry_idx','sl_atr_mult']
print('merge keys exist in E', all(k in df_e.columns for k in keys))
print('merge keys exist in F', all(k in df_f.columns for k in keys))
df_e2 = df_e.merge(df_f[keys + ['fvg_size_atr','hour']], on=keys, how='left', validate='many_to_one')
print('merged columns', df_e2.columns.tolist()[:20])
print('hour present after merge', 'hour' in df_e2.columns)
print('na hour', df_e2['hour'].isna().sum())
print('na fvg_size_atr', df_e2['fvg_size_atr'].isna().sum())
