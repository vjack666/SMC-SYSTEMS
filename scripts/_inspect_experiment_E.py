import pandas as pd

path = 'results/forensic_trades_dataset.csv'
df = pd.read_csv(path, low_memory=False)
print('rows', len(df))
print('experiments', df['experiment'].value_counts().to_dict())
print('has fvg_size_atr', 'fvg_size_atr' in df.columns)
print('has hour', 'hour' in df.columns)
print('has mitigation_depth_pct', 'mitigation_depth_pct' in df.columns)
