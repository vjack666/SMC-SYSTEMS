from ml.walk_forward import run_walk_forward, print_walk_forward_report
from ml.trainer import FEATURES_ML_V3, TARGET_COLUMN
from pathlib import Path

# Test with purged_kfold cv_strategy
result = run_walk_forward(
    Path('data/ml/multi_symbol/v4_dataset.parquet'),
    feature_list=FEATURES_ML_V3,
    target_column=TARGET_COLUMN,
    n_windows=3,
    calibrate=True,
    cv_strategy="purged_kfold",
    purge=5,
    embargo=5,
)
print_walk_forward_report(result)