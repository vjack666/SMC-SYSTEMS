from ml.trainer import load_dataset, train_model, FEATURES_ML_V3, TARGET_COLUMN
from pathlib import Path

X, y, features, schema = load_dataset('data/ml/multi_symbol/v4_dataset.parquet', FEATURES_ML_V3, TARGET_COLUMN)
print(f'Loaded: {len(X)} samples, {len(features)} features, schema={schema}')
print(f'Win rate: {y.mean():.3f}')

model, metrics = train_model(X, y, calibrate=True)
print(f'Model: {metrics["model"]}')
print(f'Calibration: {metrics["calibration_used"]} ({metrics["calibration_method"]})')
if 'validation' in metrics:
    print(f'Val ROC-AUC: {metrics["validation"].get("roc_auc", 0):.4f}')
    print(f'Val Precision: {metrics["validation"].get("precision", 0):.4f}')
    print(f'Val Recall: {metrics["validation"].get("recall", 0):.4f}')