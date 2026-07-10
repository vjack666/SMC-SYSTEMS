from __future__ import annotations

from pathlib import Path
from typing import Any

from legacy.harness.contracts import HarnessEvent

ADAPTER_NAME = "paper_trading"


class PaperTradingHarnessAdapter:
    name = ADAPTER_NAME

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        symbols = parameters.get("symbols", ["EURUSD"])
        timeframe = parameters.get("timeframe", "M15")

        return {
            "module": self.name,
            "symbols": symbols,
            "timeframe": timeframe,
            "status": "configured",
            "note": "PaperTradingRunner requires MT5 connection — run via scripts/run_paper_trading.py",
            "errors": [],
        }
