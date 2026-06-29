from __future__ import annotations

from pathlib import Path
from typing import Any

from smc_successor.signals import ScalpingConfig, build_scalping_context, summarize_filter_diagnosis


class SignalAdapter:
    name = "signal_pipeline"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        symbol = str(parameters.get("symbol", "EURUSD"))
        timeframe = str(parameters.get("timeframe", "M15"))
        data_dir = Path(str(parameters.get("data_dir", "data/mt5")))

        cfg_dict = parameters.get("config", {})
        config = ScalpingConfig(**cfg_dict) if cfg_dict else None

        try:
            context = build_scalping_context(
                symbol=symbol,
                timeframe=timeframe,
                data_dir=data_dir,
                config=config,
            )
        except FileNotFoundError as exc:
            return {"module": self.name, "event_names": [], "status": "error", "error": str(exc), "symbol": symbol}

        diagnosis = summarize_filter_diagnosis(context)
        signal_count = int((context["signal_direction"] != 0).sum())

        return {
            "module": self.name,
            "event_names": [],
            "status": "ok",
            "symbol": symbol,
            "total_bars": int(len(context)),
            "signal_count": signal_count,
            "diagnosis": diagnosis,
        }
