from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    # cuando se importa desde la raiz del repo (legacy.backtest)
    from legacy.backtest import CombinedBacktestConfig, run_filter_diagnosis
    _backtest_mod = "legacy.backtest"
except ModuleNotFoundError:
    # cuando el harness corre desde dentro de legacy/ (backtest)
    from backtest import CombinedBacktestConfig, run_filter_diagnosis
    _backtest_mod = "backtest"


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
                run_combined_backtest = __import__(
                    _backtest_mod, fromlist=["run_combined_backtest"]
                ).run_combined_backtest
                metrics, trades = run_combined_backtest(config)
                return {
                    "module": self.name,
                    "event_names": [],
                    "status": "ok",
                    "mode": "backtest",
                    "metrics": {k: float(v) if isinstance(v, (int, float)) else v for k, v in metrics.items()},
                    "metrics_by_symbol": metrics.get("by_symbol", {}),
                    "metrics_by_symbol_oos": metrics.get("by_symbol_oos", {}),
                    "total_trades": int(len(trades)),
                }
        except (FileNotFoundError, RuntimeError) as exc:
            return {"module": self.name, "event_names": [], "status": "error", "mode": mode, "error": str(exc)}
