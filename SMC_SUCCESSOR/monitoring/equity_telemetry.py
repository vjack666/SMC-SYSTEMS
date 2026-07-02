from __future__ import annotations

from pathlib import Path
from typing import Any


class EquityTelemetry:
    def __init__(self, filepath: str = "data/monitoring/equity_telemetry.json") -> None:
        self._filepath = Path(filepath)

    def record(self, equity: float, balance: float, timestamp: str) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        series = self.get_series()
        series.append({"equity": equity, "balance": balance, "timestamp": timestamp})
        self._filepath.write_text(
            __import__("json").dumps(series, indent=2), encoding="utf-8"
        )

    def get_series(self) -> list[dict]:
        if not self._filepath.exists():
            return []
        return __import__("json").loads(self._filepath.read_text(encoding="utf-8"))

    def compute_drawdown(self) -> dict[str, Any]:
        series = self.get_series()
        if not series:
            return {"max_drawdown": 0.0, "current_drawdown": 0.0, "drawdown_duration": 0}

        peak = float("-inf")
        max_dd = 0.0
        dd_start: int | None = None
        max_dd_start: int | None = None
        max_dd_end: int | None = None

        for i, entry in enumerate(series):
            equity = entry["equity"]
            if equity > peak:
                peak = equity
                dd_start = None
            else:
                dd = (peak - equity) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd
                    max_dd_start = dd_start or i
                    max_dd_end = i
                if dd_start is None:
                    dd_start = i

        last_equity = series[-1]["equity"]
        current_peak = max(e["equity"] for e in series)
        current_dd = (current_peak - last_equity) / current_peak if current_peak > 0 else 0.0

        duration = 0
        if max_dd_start is not None and max_dd_end is not None:
            duration = max_dd_end - max_dd_start

        return {
            "max_drawdown": round(max_dd, 6),
            "current_drawdown": round(current_dd, 6),
            "drawdown_duration": duration,
        }
