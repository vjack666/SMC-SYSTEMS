from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from monitoring.config import MonitoringConfig


class PerformanceTracker:
    def __init__(self, config: MonitoringConfig | None = None) -> None:
        self._config = config or MonitoringConfig()
        self._trades: list[dict[str, Any]] = []
        self._equity_curve: list[dict[str, Any]] = []
        self._load()

    def record_trade(
        self,
        entry_price: float,
        exit_price: float,
        volume: float,
        direction: str,
        timestamp: str | None = None,
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        pnl = (exit_price - entry_price) * volume if direction.upper() == "BUY" else (entry_price - exit_price) * volume
        return_pct = (exit_price - entry_price) / entry_price * 100.0 if entry_price != 0 else 0.0
        if direction.upper() == "SELL":
            return_pct = -return_pct
        trade = {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "volume": volume,
            "direction": direction.upper(),
            "timestamp": ts,
            "pnl": round(pnl, 6),
            "return_pct": round(return_pct, 6),
        }
        self._trades.append(trade)
        self._update_equity_curve(trade)
        self._persist()

    def get_metrics(self) -> dict[str, Any]:
        if len(self._trades) < 2:
            return {
                "total_trades": len(self._trades),
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "avg_return_pct": 0.0,
                "total_return_pct": 0.0,
            }

        returns = [t["return_pct"] / 100.0 for t in self._trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        total_trades = len(returns)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        total_gain = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = total_gain / total_loss if total_loss > 0 else (total_gain if total_gain > 0 else 0.0)

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

        downside = [r for r in returns if r < 0]
        if downside:
            downside_var = sum((r - mean_ret) ** 2 for r in downside) / len(returns)
            downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        else:
            downside_std = 0.0
        sortino = (mean_ret / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

        max_dd = 0.0
        peak = float("-inf")
        cumulative = 0.0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            else:
                dd = (peak - cumulative) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd
        annualized_return = (1 + mean_ret) ** 252 - 1
        calmar = annualized_return / max_dd if max_dd > 0 else 0.0

        avg_return = mean_ret * 100.0
        total_return = (sum(returns) * 100.0) if returns else 0.0

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 6),
            "profit_factor": round(profit_factor, 6),
            "sharpe_ratio": round(sharpe, 6),
            "sortino_ratio": round(sortino, 6),
            "calmar_ratio": round(calmar, 6),
            "avg_return_pct": round(avg_return, 6),
            "total_return_pct": round(total_return, 6),
        }

    def get_equity_curve(self) -> list[dict[str, Any]]:
        return list(self._equity_curve)

    def _update_equity_curve(self, trade: dict[str, Any]) -> None:
        cumulative = self._equity_curve[-1]["cumulative_pnl"] if self._equity_curve else 0.0
        cumulative += trade["pnl"]
        self._equity_curve.append({
            "timestamp": trade["timestamp"],
            "pnl": trade["pnl"],
            "cumulative_pnl": round(cumulative, 6),
        })

    def _persist(self) -> None:
        path = Path(self._config.performance_metrics_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "trades": self._trades,
            "equity_curve": self._equity_curve,
            "metrics": self.get_metrics(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        path = Path(self._config.performance_metrics_file)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._trades = data.get("trades", [])
                self._equity_curve = data.get("equity_curve", [])
            except (json.JSONDecodeError, Exception):
                self._trades = []
                self._equity_curve = []
