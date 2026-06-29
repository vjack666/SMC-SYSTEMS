import pandas as pd
from pathlib import Path
from smc_successor.ml.walk_forward import _build_date_windows, _extract_timestamps

dataset_path = Path("data/ml/multi_symbol/v4_dataset.parquet")
ts = _extract_timestamps(dataset_path)
print(f"Timestamp type: {type(ts)}")
if ts is not None:
    print(f"Length: {len(ts)}")
    print(f"First few: {ts.head()}")
    years = pd.to_datetime(ts, errors="coerce").dt.year
    print(f"Year range: {years.min()} -> {years.max()}")
    print(f"Unique years: {sorted(years.dropna().unique())}")
    print(f"Samples per year:\n{years.value_counts().sort_index()}")

    windows = _build_date_windows(ts, n_windows=5, min_train_frac=0.3)
    for w in windows:
        print(f"Window: {w.name} train={w.train_start}-{w.train_end} test={w.test_start}-{w.test_end}")
else:
    print("No timestamps extracted")
