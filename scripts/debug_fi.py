from ml.trainer import load_dataset, train_model, compute_feature_importance, FEATURES_ML_V3, TARGET_COLUMN
from pathlib import Path

X, y, features, schema = load_dataset('data/ml/multi_symbol/v4_dataset.parquet', FEATURES_ML_V3, TARGET_COLUMN)
model, metrics = train_model(X, y, calibrate=True)

print(f"Model type: {type(model)}")
print(f"Has base_estimator: {hasattr(model, 'base_estimator')}")

if hasattr(model, 'base_estimator'):
    inner = model.base_estimator
    print(f"Inner type: {type(inner)}")
    print(f"Inner has named_steps: {hasattr(inner, 'named_steps')}")
    if hasattr(inner, 'named_steps'):
        for name, step in inner.named_steps.items():
            print(f"  Step '{name}': {type(step)}")
            if hasattr(step, 'feature_importances_'):
                print(f"    -> HAS feature_importances_! len={len(step.feature_importances_)}")
            if hasattr(step, 'named_steps'):
                for n2, s2 in step.named_steps.items():
                    print(f"    Sub-step '{n2}': {type(s2)}")
                    if hasattr(s2, 'feature_importances_'):
                        print(f"      -> HAS feature_importances_! len={len(s2.feature_importances_)}")

# Test compute_feature_importance
fi = compute_feature_importance(model, features, X, y)
print("\nTop 10 feature importance:")
for f in fi[:10]:
    print(f"  {f['feature']:45s} {f['importance']:.4f}")