from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backtest.mt5_validation.mt5_backtest_runner import MT5BacktestRunner, SlippageConfig
from backtest.mt5_validation.trade_comparator import ComparisonResult, TradeComparator
from backtest.mt5_validation.report_generator import ReportGenerator
from smc_successor._data_legacy import load_frame


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


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
# Node: load_data
# ---------------------------------------------------------------------------


def load_data(state: ValidationState) -> dict[str, Any]:
    """Load historical price data from disk."""
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
# Node: generate_signals
# ---------------------------------------------------------------------------


def generate_signals(state: ValidationState) -> dict[str, Any]:
    """Generate placeholder signals from the loaded data."""
    records = state.get("_raw_data", [])
    if not records:
        return {"status": "error", "errors": ["generate_signals: no data available"]}

    signals: list[dict[str, Any]] = []
    for i, row in enumerate(records):
        if i % 100 != 0:
            continue
        close = row.get("close", 0.0)
        if close == 0.0:
            continue
        action = "BUY" if row.get("close", 0) > row.get("open", 0) else "SELL"
        sl = close * 0.995
        tp = close * 1.005
        signals.append({
            "signal_id": f"sig_{i:06d}",
            "symbol": state["symbol"],
            "action": action,
            "order_type": "MARKET",
            "volume": 0.01,
            "price": close,
            "stop_loss": round(sl, 5),
            "take_profit": round(tp, 5),
            "comment": "langgraph_validation",
            "magic_number": 20260701,
        })

    return {"signals": signals, "status": "signals_generated"}


# ---------------------------------------------------------------------------
# Node: simulate_bridge
# ---------------------------------------------------------------------------


def simulate_bridge(state: ValidationState) -> dict[str, Any]:
    """Simulate sending signals through the Bridge Module (F5)."""
    signals = state.get("signals", [])
    if not signals:
        return {"status": "error", "errors": ["simulate_bridge: no signals"]}

    bridge_results: list[dict[str, Any]] = []
    for sig in signals:
        bridge_results.append({
            "signal_id": sig["signal_id"],
            "symbol": sig["symbol"],
            "action": sig["action"],
            "volume": sig["volume"],
            "price": sig["price"],
            "stop_loss": sig["stop_loss"],
            "take_profit": sig["take_profit"],
            "bridge_status": "sent",
            "bridge_timestamp": "",
        })

    return {"bridge_results": bridge_results, "status": "bridge_simulated"}


# ---------------------------------------------------------------------------
# Node: simulate_ea
# ---------------------------------------------------------------------------


def simulate_ea(state: ValidationState) -> dict[str, Any]:
    """Simulate EA execution using the MT5BacktestRunner (F6/F7)."""
    bridge_results = state.get("bridge_results", [])
    if not bridge_results:
        return {"status": "error", "errors": ["simulate_ea: no bridge results"]}

    from integration.mt5_bridge.schema import SignalAction, SignalMessage, OrderType

    signals: list[SignalMessage] = []
    for item in bridge_results:
        signals.append(SignalMessage(
            signal_id=item["signal_id"],
            symbol=item["symbol"],
            action=SignalAction(item["action"]),
            order_type=OrderType(item.get("order_type", "MARKET")),
            volume=item.get("volume"),
            price=item.get("price"),
            stop_loss=item.get("stop_loss"),
            take_profit=item.get("take_profit"),
            comment=item.get("comment", ""),
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
# Node: compare_results
# ---------------------------------------------------------------------------


def compare_results(state: ValidationState) -> dict[str, Any]:
    """Compare signals vs EA results using TradeComparator."""
    signals = state.get("signals", [])
    ea_results = state.get("ea_results", [])

    if not signals or not ea_results:
        return {"status": "error", "errors": ["compare_results: missing data"]}

    from backtest.mt5_validation.mt5_backtest_runner import SimulatedTradeResult

    python_trades = [
        {
            "signal_id": sig["signal_id"],
            "symbol": sig["symbol"],
            "entry_price": sig.get("price", 0),
            "gross_profit": 0.0,
            "net_profit": 0.0,
            "commission": 0.0,
            "pips": 0.0,
            "win": False,
        }
        for sig in signals
    ]

    ea_objs = [
        SimulatedTradeResult(
            signal_id=r["signal_id"],
            symbol=r["symbol"],
            action=r["action"],
            volume=r["volume"],
            entry_price=r["entry_price"],
            exit_price=r["exit_price"],
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
            "python_win_rate": cmp.python_win_rate,
            "python_profit_factor": cmp.python_profit_factor,
            "python_total_net": cmp.python_total_net,
            "python_total_pips": cmp.python_total_pips,
            "ea_win_rate": cmp.ea_win_rate,
            "ea_profit_factor": cmp.ea_profit_factor,
            "ea_total_net": cmp.ea_total_net,
            "ea_total_pips": cmp.ea_total_pips,
            "delta_win_rate": cmp.delta_win_rate,
            "delta_profit_factor": cmp.delta_profit_factor,
            "delta_total_net": cmp.delta_total_net,
            "delta_total_pips": cmp.delta_total_pips,
            "avg_slippage_pips": cmp.avg_slippage_pips,
            "slippage_cost_total": cmp.slippage_cost_total,
            "details": cmp.details[:50],
        },
        "status": "compared",
    }


# ---------------------------------------------------------------------------
# Node: generate_report
# ---------------------------------------------------------------------------


def generate_report(state: ValidationState) -> dict[str, Any]:
    """Generate a text report from the comparison."""
    cmp_raw = state.get("comparison")
    if not cmp_raw:
        return {"status": "error", "errors": ["generate_report: no comparison data"]}

    cmp = ComparisonResult(**{k: v for k, v in cmp_raw.items() if k != "details"})
    for detail in cmp_raw.get("details", []):
        cmp.details.append(detail)

    gen = ReportGenerator()
    report = gen.generate_text(cmp, title=f"F7 Backtest Validation — {state['symbol']} {state['timeframe']}")

    return {"report": report, "status": "report_generated"}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_validation_graph() -> StateGraph:
    """Build and compile the F7 backtest validation LangGraph."""
    builder = StateGraph(ValidationState)

    builder.add_node("load_data", load_data)
    builder.add_node("generate_signals", generate_signals)
    builder.add_node("simulate_bridge", simulate_bridge)
    builder.add_node("simulate_ea", simulate_ea)
    builder.add_node("compare_results", compare_results)
    builder.add_node("generate_report", generate_report)

    builder.set_entry_point("load_data")
    builder.add_edge("load_data", "generate_signals")
    builder.add_edge("generate_signals", "simulate_bridge")
    builder.add_edge("simulate_bridge", "simulate_ea")
    builder.add_edge("simulate_ea", "compare_results")
    builder.add_edge("compare_results", "generate_report")
    builder.add_edge("generate_report", END)

    return builder.compile()


def run_validation(
    symbol: str = "EURUSD",
    timeframe: str = "M15",
    data_dir: str = "data/raw",
) -> dict[str, Any]:
    """Run the full F7 validation pipeline end-to-end."""
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
