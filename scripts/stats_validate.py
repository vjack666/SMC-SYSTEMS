from ml.stats_validator import compute_full_validation
from ml.trainer import load_dataset, FEATURES_ML_V3, TARGET_COLUMN, train_model
from ml.walk_forward import run_walk_forward
from pathlib import Path
import numpy as np

# Load data and get predictions
X, y, features, schema = load_dataset('data/ml/multi_symbol/v4_dataset.parquet', FEATURES_ML_V3, TARGET_COLUMN)
model, _ = train_model(X, y, calibrate=True)

proba = model.predict_proba(X)[:, 1]
pred = (proba >= 0.5).astype(int)

# Load pnl_r for trade metrics
import pandas as pd
df = pd.read_parquet('data/ml/multi_symbol/v4_dataset.parquet')
pnl_r = df['pnl_r'].values

# Compute trade returns for accepted trades
accepted_mask = pred == 1
accepted_pnl = pnl_r[accepted_mask] if accepted_mask.sum() > 0 else np.array([0.0])

print(f"Total trades: {len(pnl_r)}")
print(f"Accepted: {accepted_mask.sum()} ({accepted_mask.sum()/len(pnl_r):.1%})")
print(f"Win rate all: {(pnl_r > 0).mean():.3f}")
print(f"Win rate accepted: {(accepted_pnl > 0).mean():.3f}" if len(accepted_pnl) > 0 else "No accepted")

# Full statistical validation
print("\n=== FULL STATISTICAL VALIDATION ===")
result = compute_full_validation(
    trade_returns=accepted_pnl,
    num_trials=1,
    n_bootstrap=1000,
    n_pbo_simulations=500,
)
print(f"Sharpe: {result.sharpe_ratio:.4f}")
print(f"Sortino: {result.sortino_ratio:.4f}")
print(f"Calmar: {result.calmar_ratio:.4f}")
print(f"CVaR 95%: {result.cvar_95:.4f}")
print(f"CVaR 99%: {result.cvar_99:.4f}")
print(f"Deflated Sharpe: {result.deflated_sharpe:.4f}")
print(f"PBO: {result.pbo:.4f}")
print(f"Max DD: {result.max_drawdown:.4f}")
print(f"Profit Factor: {result.profit_factor:.4f}")
print(f"Bootstrap CI Sharpe: [{result.bootstrap_ci_sharpe['lower']:.4f}, {result.bootstrap_ci_sharpe['upper']:.4f}]")
print(f"Bootstrap CI Win Rate: [{result.bootstrap_ci_win_rate['lower']:.4f}, {result.bootstrap_ci_win_rate['upper']:.4f}]")