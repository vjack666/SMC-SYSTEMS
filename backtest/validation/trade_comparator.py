from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backtest.validation.mt5_backtest_runner import SimulatedTradeResult


@dataclass
class ComparisonResult:
    """Aggregated comparison between Python backtest and simulated EA execution."""

    # --- Trade matching ---
    total_python_trades: int = 0
    total_ea_trades: int = 0
    matched_trades: int = 0
    unmatched_python_trades: int = 0
    unmatched_ea_trades: int = 0

    # --- Entry quality ---
    entry_price_mean_diff: float = 0.0
    entry_price_max_diff: float = 0.0
    entry_price_mae: float = 0.0  # Mean Absolute Error

    # --- Performance metrics (Python engine) ---
    python_win_rate: float = 0.0
    python_profit_factor: float = 0.0
    python_total_gross: float = 0.0
    python_total_net: float = 0.0
    python_total_pips: float = 0.0
    python_total_commission: float = 0.0
    python_max_drawdown: float = 0.0
    python_sharpe: float = 0.0

    # --- Performance metrics (MT5 EA simulation) ---
    ea_win_rate: float = 0.0
    ea_profit_factor: float = 0.0
    ea_total_gross: float = 0.0
    ea_total_net: float = 0.0
    ea_total_pips: float = 0.0
    ea_total_commission: float = 0.0
    ea_max_drawdown: float = 0.0
    ea_sharpe: float = 0.0

    # --- Delta (EA - Python) ---
    delta_win_rate: float = 0.0
    delta_profit_factor: float = 0.0
    delta_total_net: float = 0.0
    delta_total_pips: float = 0.0

    # --- Slippage impact ---
    avg_slippage_pips: float = 0.0
    slippage_cost_total: float = 0.0
    slippage_cost_per_trade: float = 0.0

    # --- Per-trade details ---
    details: list[dict[str, Any]] = field(default_factory=list)


class TradeComparator:
    """Compares trades from the Python backtest engine against
    simulated EA execution results."""

    def compare(
        self,
        python_trades: list[dict[str, Any]],
        ea_results: list[SimulatedTradeResult],
    ) -> ComparisonResult:
        """Compare two sets of trade results.

        Parameters
        ----------
        python_trades : list[dict]
            Trades from Python backtest engine. Each dict needs at minimum:
            signal_id, entry_price, exit_price, volume, gross_profit, net_profit,
            commission, pips, win (bool).
        ea_results : list[SimulatedTradeResult]
            Results from MT5BacktestRunner.run().

        Returns
        -------
        ComparisonResult
        """
        cmp = ComparisonResult()
        cmp.total_python_trades = len(python_trades)
        cmp.total_ea_trades = len(ea_results)

        # --- Match by signal_id ---
        ea_by_id = {r.signal_id: r for r in ea_results if r.signal_id}

        py_entries: list[float] = []
        ea_entries: list[float] = []

        for pt in python_trades:
            sid = pt.get("signal_id", "")
            if sid in ea_by_id:
                ea = ea_by_id[sid]
                cmp.matched_trades += 1
                py_entries.append(float(pt.get("entry_price", 0)))
                ea_entries.append(ea.entry_price)
                self._record_detail(cmp, pt, ea)
            else:
                cmp.unmatched_python_trades += 1

        cmp.unmatched_ea_trades = cmp.total_ea_trades - cmp.matched_trades

        # --- Entry price differences (matched trades only) ---
        if py_entries and ea_entries:
            diffs = [abs(p - e) for p, e in zip(py_entries, ea_entries)]
            cmp.entry_price_mean_diff = round(sum(diffs) / len(diffs), 5)
            cmp.entry_price_max_diff = round(max(diffs), 5)
            cmp.entry_price_mae = round(sum(diffs) / len(diffs), 5)

        # --- Python metrics ---
        cmp.python_win_rate = self._win_rate(python_trades)
        cmp.python_profit_factor = self._profit_factor(python_trades)
        cmp.python_total_gross = sum(float(t.get("gross_profit", 0)) for t in python_trades)
        cmp.python_total_net = sum(float(t.get("net_profit", 0)) for t in python_trades)
        cmp.python_total_pips = sum(float(t.get("pips", 0)) for t in python_trades)
        cmp.python_total_commission = sum(float(t.get("commission", 0)) for t in python_trades)
        cmp.python_max_drawdown = self._max_drawdown(python_trades)
        cmp.python_sharpe = self._sharpe(python_trades)

        # --- EA metrics ---
        cmp.ea_win_rate = self._win_rate_ea(ea_results)
        cmp.ea_profit_factor = self._profit_factor_ea(ea_results)
        cmp.ea_total_gross = sum(r.gross_profit for r in ea_results)
        cmp.ea_total_net = sum(r.net_profit for r in ea_results)
        cmp.ea_total_pips = sum(r.pips for r in ea_results)
        cmp.ea_total_commission = sum(r.commission for r in ea_results)
        cmp.ea_max_drawdown = self._max_drawdown_ea(ea_results)
        cmp.ea_sharpe = self._sharpe_ea(ea_results)

        # --- Deltas ---
        cmp.delta_win_rate = round(cmp.ea_win_rate - cmp.python_win_rate, 4)
        cmp.delta_profit_factor = round(cmp.ea_profit_factor - cmp.python_profit_factor, 4)
        cmp.delta_total_net = round(cmp.ea_total_net - cmp.python_total_net, 2)
        cmp.delta_total_pips = round(cmp.ea_total_pips - cmp.python_total_pips, 1)

        # --- Slippage ---
        slippages = [r.slippage for r in ea_results]
        cmp.avg_slippage_pips = round((sum(slippages) / len(slippages)) * 10_000, 2) if slippages else 0.0
        cmp.slippage_cost_total = round(
            sum(abs(r.net_profit - r.gross_profit) for r in ea_results), 2
        )
        cmp.slippage_cost_per_trade = round(
            cmp.slippage_cost_total / max(len(ea_results), 1), 2
        )

        return cmp

    # ------------------------------------------------------------------
    # Internal helpers — Python trades
    # ------------------------------------------------------------------

    def _win_rate(self, trades: list[dict]) -> float:
        wins = sum(1 for t in trades if t.get("win", False))
        return round(wins / max(len(trades), 1), 4)

    def _profit_factor(self, trades: list[dict]) -> float:
        gross = sum(float(t.get("gross_profit", 0)) for t in trades if float(t.get("gross_profit", 0)) > 0)
        loss = abs(sum(float(t.get("gross_profit", 0)) for t in trades if float(t.get("gross_profit", 0)) < 0))
        return round(gross / max(loss, 1e-9), 4)

    def _max_drawdown(self, trades: list[dict]) -> float:
        peak = -1e9
        dd = 0.0
        cum = 0.0
        for t in trades:
            cum += float(t.get("net_profit", 0))
            if cum > peak:
                peak = cum
            dd_val = peak - cum
            if dd_val > dd:
                dd = dd_val
        return round(dd, 2)

    def _sharpe(self, trades: list[dict]) -> float:
        returns = [float(t.get("net_profit", 0)) for t in trades]
        return self._compute_sharpe(returns)

    # ------------------------------------------------------------------
    # Internal helpers — EA results
    # ------------------------------------------------------------------

    def _win_rate_ea(self, results: list[SimulatedTradeResult]) -> float:
        wins = sum(1 for r in results if r.net_profit > 0)
        return round(wins / max(len(results), 1), 4)

    def _profit_factor_ea(self, results: list[SimulatedTradeResult]) -> float:
        gross = sum(r.gross_profit for r in results if r.gross_profit > 0)
        loss = abs(sum(r.gross_profit for r in results if r.gross_profit < 0))
        return round(gross / max(loss, 1e-9), 4)

    def _max_drawdown_ea(self, results: list[SimulatedTradeResult]) -> float:
        peak = -1e9
        dd = 0.0
        cum = 0.0
        for r in results:
            cum += r.net_profit
            if cum > peak:
                peak = cum
            dd_val = peak - cum
            if dd_val > dd:
                dd = dd_val
        return round(dd, 2)

    def _sharpe_ea(self, results: list[SimulatedTradeResult]) -> float:
        returns = [r.net_profit for r in results]
        return self._compute_sharpe(returns)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    def _compute_sharpe(self, returns: list[float], rfr: float = 0.0) -> float:
        if len(returns) < 2:
            return 0.0
        import numpy as np
        arr = np.array(returns, dtype=float)
        excess = arr - rfr
        std = float(np.std(excess, ddof=1))
        return round(float(np.mean(excess)) / max(std, 1e-9), 4)

    def _record_detail(self, cmp: ComparisonResult, pt: dict, ea: SimulatedTradeResult) -> None:
        cmp.details.append({
            "signal_id": pt.get("signal_id", ""),
            "symbol": pt.get("symbol", ea.symbol),
            "python_entry": float(pt.get("entry_price", 0)),
            "ea_entry": ea.entry_price,
            "entry_diff": round(float(pt.get("entry_price", 0)) - ea.entry_price, 5),
            "python_net": float(pt.get("net_profit", 0)),
            "ea_net": ea.net_profit,
            "net_diff": round(float(pt.get("net_profit", 0)) - ea.net_profit, 2),
            "python_pips": float(pt.get("pips", 0)),
            "ea_pips": ea.pips,
            "pips_diff": round(float(pt.get("pips", 0)) - ea.pips, 1),
        })
