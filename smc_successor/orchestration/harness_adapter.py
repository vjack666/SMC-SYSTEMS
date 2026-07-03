from __future__ import annotations

from typing import Any

from harness.contracts import HarnessEvent
from smc_successor.orchestration.backtest_validation_graph import build_validation_graph, ValidationState


class LangGraphBacktestAdapter:
    """Harness adapter for the F7 LangGraph validation pipeline."""

    name = "langgraph_validation"

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        symbol = str(parameters.get("symbol", "EURUSD"))
        timeframe = str(parameters.get("timeframe", "M15"))
        data_dir = str(parameters.get("data_dir", "data/raw"))

        try:
            graph = build_validation_graph()
        except Exception as exc:
            return {"module": self.name, "status": "error", "error": f"Graph build failed: {exc}"}

        initial: ValidationState = {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_dir": data_dir,
            "total_bars": 0,
            "_raw_data": [],
            "signals": [],
            "bridge_results": [],
            "ea_results": [],
            "comparison": None,
            "report": "",
            "status": "init",
            "errors": [],
        }

        try:
            result = graph.invoke(initial)
        except Exception as exc:
            return {"module": self.name, "status": "error", "error": f"Graph execution failed: {exc}"}

        signals = result.get("signals", [])
        comparison = result.get("comparison")

        return {
            "module": self.name,
            "status": result.get("status", "unknown"),
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": result.get("total_bars", 0),
            "signals_count": len(signals),
            "ea_results_count": len(result.get("ea_results", [])),
            "matched_trades": comparison.get("matched_trades", 0) if comparison else 0,
            "python_total_net": comparison.get("python_total_net", 0.0) if comparison else 0.0,
            "ea_total_net": comparison.get("ea_total_net", 0.0) if comparison else 0.0,
            "delta_total_net": comparison.get("delta_total_net", 0.0) if comparison else 0.0,
            "report_preview": result.get("report", "")[:300],
            "errors": result.get("errors", []),
        }
