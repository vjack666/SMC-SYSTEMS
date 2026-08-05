from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backtest.fvg_mitigation_backtest import run_fvg_mitigation_comparison
from backtest.fvg_pac_experiments import run_pac_experiments


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FVG backtests (legacy A/B or PAC experiments A-E).")
    parser.add_argument(
        "--experiment",
        choices=["A", "B", "C", "D", "E", "ALL"],
        default=None,
        help="Run PAC experimental matrix for selected experiment. If omitted, runs legacy A/B mitigation backtest.",
    )
    args = parser.parse_args()

    if args.experiment is None:
        summary = run_fvg_mitigation_comparison()
    else:
        summary = run_pac_experiments(experiment=args.experiment)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
