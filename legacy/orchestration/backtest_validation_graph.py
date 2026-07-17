from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Literal, TypedDict

import numpy as np
from langgraph.graph import END, StateGraph

from backtest.validation.mt5_backtest_runner import (
    MT5BacktestRunner,
    SlippageConfig,
    SimulatedTradeResult,
    SignalAction,
    SignalMessage,
    OrderType,
)
from backtest.validation.trade_comparator import ComparisonResult, TradeComparator
from backtest.validation.report_generator import ReportGenerator
from _data_legacy import load_frame

logger = logging.getLogger(__name__)


class ValidationState(TypedDict):
    symbol: str
    timeframe: str
    data_dir: str
    total_bars: int
    _raw_data: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    bridge_results: list[dict[str, Any]]
    ea_results: list[dict[str, Any]]
    comparison: dict[str, Any] | None
    report: str
    status: str
    errors: list[str]


# ---------------------------------------------------------------------------
# OHLC helpers
# ---------------------------------------------------------------------------


def _compute_atr(records: list[dict[str, Any]], period: int = 14) -> float:
    if len(records) < period + 1:
        return 0.001
    tr_values: list[float] = []
    for i in range(1, len(records)):
        high = records[i].get("high", 0)
        low = records[i].get("low", 0)
        prev_close = records[i - 1].get("close", 0)
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    if len(tr_values) < period:
        return 0.001
    return float(np.mean(tr_values[-period:]))


def _compute_ema(values: list[float], period: int) -> list[float]:
    if not values or period < 1:
        return []
    multiplier = 2.0 / (period + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append((v - ema[-1]) * multiplier + ema[-1])
    return ema


def _simulate_trade_outcome(
    entry: float,
    sl: float,
    tp: float,
    records: list[dict[str, Any]],
    bar_idx: int,
    direction: str,
    volume: float = 0.01,
) -> tuple[float, float, float, str]:
    for i in range(bar_idx, len(records)):
        high = records[i].get("high", entry)
        low = records[i].get("low", entry)
        if direction == "BUY":
            if sl is not None and low <= sl:
                return sl, (sl - entry) * volume * 100_000, (sl - entry) * 10_000, "stop_loss"
            if tp is not None and high >= tp:
                return tp, (tp - entry) * volume * 100_000, (tp - entry) * 10_000, "take_profit"
        else:
            if sl is not None and high >= sl:
                return sl, (entry - sl) * volume * 100_000, (entry - sl) * 10_000, "stop_loss"
            if tp is not None and low <= tp:
                return tp, (entry - tp) * volume * 100_000, (entry - tp) * 10_000, "take_profit"
    last_close = records[-1].get("close", entry)
    if direction == "BUY":
        pnl = (last_close - entry) * volume * 100_000
        pips = (last_close - entry) * 10_000
    else:
        pnl = (entry - last_close) * volume * 100_000
        pips = (entry - last_close) * 10_000
    return last_close, pnl, pips, "expired"


# ---------------------------------------------------------------------------
# Node: load_data
# ---------------------------------------------------------------------------


def load_data(state: ValidationState) -> dict[str, Any]:
    try:
        from pathlib import Path

        data_dir = Path(state.get("data_dir", "data/raw"))
        frame = load_frame(data_dir, state["symbol"], state["timeframe"])
        total_bars = int(len(frame))
        records = frame.tail(5000).to_dict("records")

        return {
            "total_bars": total_bars,
            "_raw_data": records,
            "status": "data_loaded",
            "errors": [],
        }
    except Exception as exc:
        return {
            "status": "error",
            "errors": [f"load_data: {exc}"],
        }


# ---------------------------------------------------------------------------
# Node: generate_signals — EMA crossover + ATR-based SL/TP
# ---------------------------------------------------------------------------


def generate_signals(state: ValidationState) -> dict[str, Any]:
    records = state.get("_raw_data", [])
    if not records:
        return {"status": "error", "errors": ["generate_signals: no data available"]}

    closes = [r.get("close", 0.0) for r in records]
    if len(closes) < 60:
        return {"status": "error", "errors": ["generate_signals: need >= 60 bars"]}

    ema20 = _compute_ema(closes, 20)
    ema50 = _compute_ema(closes, 50)
    atr = _compute_atr(records)

    atr_mult = 2.0
    min_bars_between = 10
    last_sig_idx = -min_bars_between

    signals: list[dict[str, Any]] = []
    for i in range(1, len(ema20)):
        if i >= len(ema50) or i < 1:
            continue

        if i - last_sig_idx < min_bars_between:
            continue

        prev_20 = ema20[i - 1]
        prev_50 = ema50[i - 1]
        curr_20 = ema20[i]
        curr_50 = ema50[i]

        action: str | None = None
        if prev_20 <= prev_50 and curr_20 > curr_50:
            action = "BUY"
        elif prev_20 >= prev_50 and curr_20 < curr_50:
            action = "SELL"

        if action is None:
            continue

        close = closes[i]
        sl_dist = max(atr * atr_mult, 0.0005)
        tp_dist = sl_dist * 1.5

        if action == "BUY":
            sl = round(close - sl_dist, 5)
            tp = round(close + tp_dist, 5)
        else:
            sl = round(close + sl_dist, 5)
            tp = round(close - tp_dist, 5)

        signals.append({
            "signal_id": f"sig_{i:06d}",
            "symbol": state["symbol"],
            "action": action,
            "order_type": "MARKET",
            "volume": 0.01,
            "price": close,
            "stop_loss": sl,
            "take_profit": tp,
            "comment": "ema_crossover_lg",
            "magic_number": 20260701,
            "_entry_bar_idx": i,
        })
        last_sig_idx = i

    return {"signals": signals, "status": "signals_generated"}


# ---------------------------------------------------------------------------
# Node: simulate_bridge — canal de envío a MT5 eliminado (empezar de 0).
# Devuelve lista vacía: la simulación de envío real ya no existe.
# ---------------------------------------------------------------------------


def simulate_bridge(state: ValidationState) -> dict[str, Any]:
    signals = state.get("signals", [])
    if not signals:
        return {"status": "error", "errors": ["simulate_bridge: no signals"]}
    logger.info("simulate_bridge: canal MT5 eliminado, sin simulacion de envio")
    return {"bridge_results": [], "status": "bridge_disabled"}


# ---------------------------------------------------------------------------
# Node: simulate_ea — usa el runner local (sin canal MT5) para simular la
# ejecución del EA. Los tipos SignalAction/SignalMessage son locales ahora.
# ---------------------------------------------------------------------------


def simulate_ea(state: ValidationState) -> dict[str, Any]:
    bridge_results = state.get("bridge_results", [])
    if not bridge_results:
        return {"status": "error", "errors": ["simulate_ea: no bridge results"]}

    signals: list[SignalMessage] = []
    for item in bridge_results:
        signals.append(SignalMessage(
            signal_id=item["signal_id"],
            symbol=item["symbol"],
            action=SignalAction(item["action"]),
            order_type=OrderType.MARKET,
            volume=item.get("volume"),
            price=item.get("price"),
            stop_loss=item.get("stop_loss"),
            take_profit=item.get("take_profit"),
            comment="langgraph_validation",
        ))

    runner = MT5BacktestRunner(SlippageConfig(mode="fixed", fixed_pips=0.5))
    results = runner.run(signals)

    ea_results: list[dict[str, Any]] = []
    for r in results:
        ea_results.append({
            "signal_id": r.signal_id,
            "symbol": r.symbol,
            "action": r.action.value,
            "volume": r.volume,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "stop_loss": r.stop_loss,
            "take_profit": r.take_profit,
            "gross_profit": r.gross_profit,
            "net_profit": r.net_profit,
            "pips": r.pips,
            "exit_reason": r.exit_reason,
            "slippage": r.slippage,
        })

    return {"ea_results": ea_results, "status": "ea_simulated"}


# ---------------------------------------------------------------------------
# Node: compare_results — realistic Python P&L using OHLC walk
# ---------------------------------------------------------------------------


def compare_results(state: ValidationState) -> dict[str, Any]:
    signals = state.get("signals", [])
    ea_results = state.get("ea_results", [])
    records = state.get("_raw_data", [])

    if not signals or not ea_results:
        return {"status": "error", "errors": ["compare_results: missing data"]}

    # Build Python trades with realistic P&L by walking OHLC
    python_trades: list[dict[str, Any]] = []
    for sig in signals:
        entry = sig.get("price", 0.0)
        sl = sig.get("stop_loss")
        tp = sig.get("take_profit")
        direction = sig["action"]
        volume = sig.get("volume", 0.01)
        bar_idx = sig.get("_entry_bar_idx", 0)

        exit_price, gross, pips, exit_reason = _simulate_trade_outcome(
            entry=entry,
            sl=sl,
            tp=tp,
            records=records,
            bar_idx=min(bar_idx + 1, len(records) - 1),
            direction=direction,
            volume=volume,
        )

        commission = volume * 3.5
        net = gross - commission

        python_trades.append({
            "signal_id": sig["signal_id"],
            "symbol": sig["symbol"],
            "entry_price": entry,
            "exit_price": exit_price,
            "volume": volume,
            "gross_profit": round(gross, 2),
            "net_profit": round(net, 2),
            "commission": round(commission, 2),
            "pips": round(pips, 1),
            "exit_reason": exit_reason,
            "win": gross > 0,
        })

    ea_objs = [
        SimulatedTradeResult(
            signal_id=r["signal_id"],
            symbol=r["symbol"],
            action=SignalAction(r["action"]),
            volume=r["volume"],
            entry_price=r["entry_price"],
            exit_price=r["exit_price"] or 0.0,
            stop_loss=r["stop_loss"],
            take_profit=r["take_profit"],
            gross_profit=r["gross_profit"],
            net_profit=r["net_profit"],
            pips=r["pips"],
            exit_reason=r["exit_reason"],
            slippage=r["slippage"],
        )
        for r in ea_results
    ]

    comparator = TradeComparator()
    cmp = comparator.compare(python_trades, ea_objs)

    return {
        "comparison": {
            "total_python_trades": cmp.total_python_trades,
            "total_ea_trades": cmp.total_ea_trades,
            "matched_trades": cmp.matched_trades,
            "unmatched_python_trades": cmp.unmatched_python_trades,
            "unmatched_ea_trades": cmp.unmatched_ea_trades,
            "entry_price_mae": cmp.entry_price_mae,
            "entry_price_max_diff": cmp.entry_price_max_diff,
            "entry_price_mean_diff": cmp.entry_price_mean_diff,
            "python_win_rate": cmp.python_win_rate,
            "python_profit_factor": cmp.python_profit_factor,
            "python_total_gross": cmp.python_total_gross,
            "python_total_net": cmp.python_total_net,
            "python_total_pips": cmp.python_total_pips,
            "python_total_commission": cmp.python_total_commission,
            "python_max_drawdown": cmp.python_max_drawdown,
            "python_sharpe": cmp.python_sharpe,
            "ea_win_rate": cmp.ea_win_rate,
            "ea_profit_factor": cmp.ea_profit_factor,
            "ea_total_gross": cmp.ea_total_gross,
            "ea_total_net": cmp.ea_total_net,
            "ea_total_pips": cmp.ea_total_pips,
            "ea_total_commission": cmp.ea_total_commission,
            "ea_max_drawdown": cmp.ea_max_drawdown,
            "ea_sharpe": cmp.ea_sharpe,
            "delta_win_rate": cmp.delta_win_rate,
            "delta_profit_factor": cmp.delta_profit_factor,
            "delta_total_net": cmp.delta_total_net,
            "delta_total_pips": cmp.delta_total_pips,
            "avg_slippage_pips": cmp.avg_slippage_pips,
            "slippage_cost_total": cmp.slippage_cost_total,
            "slippage_cost_per_trade": cmp.slippage_cost_per_trade,
            "details": cmp.details[:50],
        },
        "status": "compared",
    }


# ---------------------------------------------------------------------------
# Node: generate_report
# ---------------------------------------------------------------------------


def generate_report(state: ValidationState) -> dict[str, Any]:
    cmp_raw = state.get("comparison")
    if not cmp_raw:
        return {"status": "error", "errors": ["generate_report: no comparison data"]}

    cmp = ComparisonResult(**{k: v for k, v in cmp_raw.items() if k != "details"})
    for detail in cmp_raw.get("details", []):
        cmp.details.append(detail)

    gen = ReportGenerator()
    report = gen.generate_text(cmp, title=f"F7 Backtest Validation — {state['symbol']} {state['timeframe']}")

    return {
        "report": report,
        "status": "report_generated",
        "_raw_data": [],  # Strip raw data from final state
    }


# ---------------------------------------------------------------------------
# Node: error_handler
# ---------------------------------------------------------------------------


def error_handler(state: ValidationState) -> dict[str, Any]:
    errors = state.get("errors", [])
    return {
        "status": "failed",
        "report": f"Validation failed with {len(errors)} error(s):\n" + "\n".join(f"  - {e}" for e in errors),
        "comparison": None,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def route_after_load(state: ValidationState) -> str:
    return "generate_signals" if not state.get("errors") else "error_handler"


def route_after_generate(state: ValidationState) -> str:
    return "simulate_bridge" if not state.get("errors") else "error_handler"


def route_after_bridge(state: ValidationState) -> str:
    return "simulate_ea" if not state.get("errors") else "error_handler"


def route_after_ea(state: ValidationState) -> str:
    return "compare_results" if not state.get("errors") else "error_handler"


def route_after_compare(state: ValidationState) -> str:
    return "generate_report" if not state.get("errors") else "error_handler"


def route_after_report(state: ValidationState) -> str:
    return END if not state.get("errors") else END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_validation_graph() -> StateGraph:
    builder = StateGraph(ValidationState)

    builder.add_node("load_data", load_data)
    builder.add_node("generate_signals", generate_signals)
    builder.add_node("simulate_bridge", simulate_bridge)
    builder.add_node("simulate_ea", simulate_ea)
    builder.add_node("compare_results", compare_results)
    builder.add_node("generate_report", generate_report)
    builder.add_node("error_handler", error_handler)

    builder.set_entry_point("load_data")

    builder.add_conditional_edges("load_data", route_after_load, {
        "generate_signals": "generate_signals",
        "error_handler": "error_handler",
    })

    builder.add_conditional_edges("generate_signals", route_after_generate, {
        "simulate_bridge": "simulate_bridge",
        "error_handler": "error_handler",
    })

    builder.add_conditional_edges("simulate_bridge", route_after_bridge, {
        "simulate_ea": "simulate_ea",
        "error_handler": "error_handler",
    })

    builder.add_conditional_edges("simulate_ea", route_after_ea, {
        "compare_results": "compare_results",
        "error_handler": "error_handler",
    })

    builder.add_conditional_edges("compare_results", route_after_compare, {
        "generate_report": "generate_report",
        "error_handler": "error_handler",
    })

    builder.add_conditional_edges("generate_report", route_after_report, {
        END: END,
    })

    builder.add_edge("error_handler", END)

    return builder.compile()


def run_validation(
    symbol: str = "EURUSD",
    timeframe: str = "M15",
    data_dir: str = "data/raw",
) -> dict[str, Any]:
    graph = build_validation_graph()
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
    return graph.invoke(initial)
