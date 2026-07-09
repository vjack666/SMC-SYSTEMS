"""Inspect the production ML model: schema, sample count, AUC, feature list."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.trainer import load_model

p = Path("ml/models/quality_filter.pkl")
if not p.exists():
    print("MODEL MISSING:", p)
    sys.exit(1)

model, meta = load_model(p)
print("=== METADATA ===")
for k, v in (meta or {}).items():
    if isinstance(v, (list, dict)) and len(v) > 8:
        print(f"  {k}: <{type(v).__name__} len={len(v)}>")
    else:
        print(f"  {k}: {v}")

print("\n=== MODEL TYPE ===")
print(type(model))

# Try to surface training sample count / holdout auc if present
for key in ("train_samples", "n_samples", "holdout_auc", "auc", "roc_auc",
            "test_auc", "n_features", "feature_names", "features"):
    if meta and key in meta:
        print(f"  {key}: {meta[key]}")
