from __future__ import annotations

from pathlib import Path
from typing import Any

from smc_successor.backtest import CombinedBacktestConfig, run_filter_diagnosis


class BacktestAdapter:
    name = "backtest"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        cfg_dict = parameters.get("config", {})
        config = CombinedBacktestConfig(**cfg_dict) if cfg_dict else None

        mode = str(parameters.get("mode", "diagnosis"))

        try:
            if mode == "diagnosis":
                diagnosis = run_filter_diagnosis(config)
                return {"module": self.name, "event_names": [], "status": "ok", "mode": "diagnosis", "diagnosis": diagnosis}
            else:
                from smc_successor.backtest import run_combined_backtest
                metrics, trades = run_combined_backtest(config)
                return {
                    "module": self.name,
                    "event_names": [],
                    "status": "ok",
                    "mode": "backtest",
                    "metrics": {k: float(v) if isinstance(v, (int, float)) else v for k, v in metrics.items()},
                    "total_trades": int(len(trades)),
                }
        except (FileNotFoundError, RuntimeError) as exc:
            return {"module": self.name, "event_names": [], "status": "error", "mode": mode, "error": str(exc)}
