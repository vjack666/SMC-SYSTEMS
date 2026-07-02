from __future__ import annotations

import math
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

    def compute_performance(self) -> dict[str, Any]:
        series = self.get_series()
        n = len(series)
        if n < 2:
            return {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "total_return_pct": 0.0,
                "total_trades": 0,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
            }

        returns = []
        for i in range(1, n):
            prev_eq = series[i - 1]["equity"]
            curr_eq = series[i]["equity"]
            if prev_eq != 0:
                returns.append((curr_eq - prev_eq) / prev_eq)
            else:
                returns.append(0.0)

        total_return_pct = (series[-1]["equity"] - series[0]["equity"]) / series[0]["equity"] * 100.0 if series[0]["equity"] != 0 else 0.0

        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        total_trades = len(returns)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        total_gain = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = total_gain / total_loss if total_loss > 0 else (total_gain if total_gain > 0 else 0.0)

        avg_win_pct = (sum(wins) / len(wins) * 100.0) if wins else 0.0
        avg_loss_pct = (sum(losses) / len(losses) * 100.0) if losses else 0.0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0

        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_var = sum((r - mean_ret) ** 2 for r in downside_returns) / len(returns)
            downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        else:
            downside_std = 0.0
        sortino = (mean_ret / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

        dd_info = self.compute_drawdown()
        max_dd = dd_info["max_drawdown"]
        annualized_return = (1 + mean_ret) ** 252 - 1
        calmar = annualized_return / max_dd if max_dd > 0 else 0.0

        return {
            "win_rate": round(win_rate, 6),
            "profit_factor": round(profit_factor, 6),
            "sharpe_ratio": round(sharpe, 6),
            "sortino_ratio": round(sortino, 6),
            "calmar_ratio": round(calmar, 6),
            "total_return_pct": round(total_return_pct, 6),
            "total_trades": total_trades,
            "avg_win_pct": round(avg_win_pct, 6),
            "avg_loss_pct": round(avg_loss_pct, 6),
        }
