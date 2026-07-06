from ml.trainer import load_dataset, train_model, save_model, ModelMetadata, FEATURES_ML_V3, TARGET_COLUMN
from datetime import datetime, timezone
from pathlib import Path

X, y, features, schema = load_dataset('data/ml/multi_symbol/v4_dataset.parquet', FEATURES_ML_V3, TARGET_COLUMN)
print(f'Loaded: {len(X)} samples, {len(features)} features')

model, metrics = train_model(X, y, calibrate=True)
print(f'Model: {metrics["model"]}')
print(f'Calibration: {metrics["calibration_used"]} ({metrics["calibration_method"]})')

# Create metadata and save with governance + monitoring
metadata = ModelMetadata(
    feature_names=features,
    schema_version=schema,
    training_date=datetime.now(timezone.utc).isoformat(),
    metrics=metrics,
    model_name="quality_filter",
    n_samples=len(X),
    feature_importance=[],  # will be computed in save_model if needed
)

save_model(model, metadata, Path('ml/models/quality_filter.pkl'), X_train=X)
print("Model saved with governance + monitoring integration")