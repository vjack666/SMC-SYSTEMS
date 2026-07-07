"""
Direct runner for the ML-isolation experiment (Ítem A).

Loads CombinedBacktestConfig from a harness fixture YAML and runs
run_combined_backtest, dumping metrics + trade count to JSON.

Usage (repo root, probe venv):
    python scripts/_run_ml_iso.py harness/fixtures/backtest_ml_off_raw_fixture.yaml
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import CombinedBacktestConfig, run_combined_backtest  # noqa: E402


def _clean(v):
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (int, float)):
        return float(v)
    return str(v)


def main() -> int:
    fixture = Path(sys.argv[1])
    raw = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    cfg_dict = raw["parameters"]["config"]
    # Coerce Path-like fields
    for k in ("data_dir", "ml_model_path", "quality_dataset_path", "dataset_quality_log_path"):
        if k in cfg_dict and cfg_dict[k] is not None:
            cfg_dict[k] = Path(cfg_dict[k])
    config = CombinedBacktestConfig(**cfg_dict)

    print(f"[run] {fixture.name}  symbols={config.symbols} tf={config.timeframe} "
          f"ml={config.use_ml_quality_filter} max_bars={config.max_bars}")
    metrics, trades = run_combined_backtest(config)

    out = {
        "fixture": fixture.name,
        "use_ml_quality_filter": config.use_ml_quality_filter,
        "metrics": _clean(metrics),
        "total_trades": len(trades),
    }
    print(json.dumps(out, indent=2))

    result_path = Path("scripts") / f"_ml_iso_{fixture.stem}.json"
    result_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[written] {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
