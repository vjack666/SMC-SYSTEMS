"""
Rebuild experiment F with corrected structural stop loss.
Uses ONLY corrected detector logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.rebuild_experiment_f_structural import ExperimentFBuilder


def rebuild_experiment_f_fixed():
    builder = ExperimentFBuilder()
    
    print("=== REBUILDING EXPERIMENT F WITH CORRECTED STRUCTURAL STOP ===\n")
    print("Step 1: Load raw OHLC data...")
    builder.load_all_ohlc()
    print("Step 2: Generate BOS+FVG signals...")
    builder.generate_signals()
    print("Step 3: Simulate trades with CORRECTED structural stop loss...")
    builder.simulate_trades()
    print("Step 4: Save fixed experiment and metrics...")
    
    # Save as fixed version
    output_path = builder.results_dir / "experiment_F_structural_sl_fixed.csv"
    builder.results_dir.mkdir(parents=True, exist_ok=True)
    builder.trades.to_csv(output_path, index=False)
    print(f"\nExperiment saved to {output_path}")
    
    metrics_path = builder.results_dir / "experiment_F_structural_sl_fixed_metrics.json"
    builder.save_metrics("experiment_F_structural_sl_fixed_metrics.json")
    print(f"Metrics saved to {metrics_path}")
    
    return builder


if __name__ == "__main__":
    rebuild_experiment_f_fixed()
