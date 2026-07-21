"""Top-down multi-TF strategy (D1 → H4 → H1 → M15 setup).

Clock = LTF only. Higher TFs are closed-only snapshots at each signal time.
Does NOT invert to bottom-up (M1→D1).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest.engine import ICTSignal
from ict_backtest.run_backtest import generate_sequence_signals
from ict_backtest.v2.context_mtf import build_context_stack, top_down_allows_trade
from ict_backtest.v2.contracts import (
    CoverageMode,
    Order,
    PlanState,
    TradeExplanation,
    TradingPlan,
)
from ict_backtest.v2.event_log import EventLog
from ict_backtest.v2.nearest_tp import apply_nearest_tp_to_signals


def generate_mtf_signals(
    symbol: str,
    ms: dict[str, pd.DataFrame],
    *,
    ltf: str = "M15",
    counter_trend: bool = False,
    require_displacement: bool = True,
    displace_gap: int = 6,
    bos_gap: int | None = None,
    fill_mode: str = "next_open",
    require_d1: bool = True,
    require_h1: bool = True,
    require_pd: bool = True,
    use_nearest_tp: bool = True,
    min_rr: float = 3.0,
    event_log: EventLog | None = None,
    enable_pd_index: bool = False,
) -> tuple[list[ICTSignal], dict[str, Any]]:
    """Sequence on M15 with H4 bias, then filter each signal top-down D1/H4/H1/PD."""
    log = event_log if event_log is not None else EventLog()
    frames = {tf: df for tf, df in ms.items()}
    # Ensure required keys for generate_sequence_signals
    if "H4" not in frames and "D1" in frames:
        # fallback: use D1 as htf if no H4
        htf = "D1"
    else:
        htf = "H4" if "H4" in frames else list(frames.keys())[0]

    raw = generate_sequence_signals(
        symbol,
        htf,
        ltf,
        counter_trend=counter_trend,
        require_displacement=require_displacement,
        displace_gap=displace_gap,
        bos_gap=bos_gap,
        frames=frames,
        fill_mode=fill_mode,
        enable_pd_index=enable_pd_index,
    )
    ltf_df = ms[ltf]
    if use_nearest_tp:
        raw = apply_nearest_tp_to_signals(raw, ltf_df, min_rr=min_rr)

    kept: list[ICTSignal] = []
    filter_stats: dict[str, int] = {"raw": len(raw), "kept": 0}
    for s in raw:
        t = s.time
        stack = build_context_stack(
            ms, t, tfs=("D1", "H4", "H1", ltf) if "H1" in ms else ("D1", "H4", ltf)
        )
        ok, reason = top_down_allows_trade(
            stack,
            int(s.direction),
            require_d1=require_d1,
            require_h1=require_h1 and "H1" in ms,
            require_pd=require_pd,
            counter_trend=counter_trend,
        )
        log.append(
            "TopDownGate",
            ts=str(t),
            tf=ltf,
            payload={
                "ok": ok,
                "reason": reason,
                "direction": s.direction,
                "d1": stack.get("D1", {}).get("trend"),
                "h4": stack.get("H4", {}).get("trend"),
                "h1": stack.get("H1", {}).get("trend"),
                "pd": stack.get("dealing", {}).get("pd_side"),
            },
        )
        filter_stats[reason] = filter_stats.get(reason, 0) + 1
        if not ok:
            continue
        # attach context for explanations
        s.meta = getattr(s, "meta", None) or {}
        if not hasattr(s, "meta") or s.meta is None:
            pass
        kept.append(s)
        # store stack on signal via dynamic attribute for later explanation
        setattr(s, "_mtf_stack", stack)

    filter_stats["kept"] = len(kept)
    log.append(
        "PlanFormed",
        tf=ltf,
        payload={"mode": "mtf_intraday", "filter_stats": filter_stats},
    )
    return kept, filter_stats


def mtf_signals_to_plan(
    signals: list[ICTSignal],
    *,
    symbol: str,
    max_hold_bars: int = 40,
    ltf: str = "M15",
    event_log: EventLog | None = None,
    filter_stats: dict[str, Any] | None = None,
) -> TradingPlan:
    plan_id = f"plan-mtf-{symbol}"
    log = event_log if event_log is not None else EventLog()
    orders: list[Order] = []
    for i, sig in enumerate(signals):
        oid = f"ord-mtf-{symbol}-{i:05d}"
        stack = getattr(sig, "_mtf_stack", {})
        log.append(
            "OrderIntentEmitted",
            ts=str(sig.time),
            plan_id=plan_id,
            order_id=oid,
            tf=ltf,
            payload={
                "direction": sig.direction,
                "d1": (stack.get("D1") or {}).get("trend"),
                "h4": (stack.get("H4") or {}).get("trend"),
                "pd": (stack.get("dealing") or {}).get("pd_side"),
            },
        )
        orders.append(
            Order(
                order_id=oid,
                plan_id=plan_id,
                symbol=symbol,
                model_id="mtf_intraday",
                direction=int(sig.direction),
                signal_time=str(sig.time),
                stop_loss=float(sig.stop_loss),
                take_profit=float(sig.take_profit),
                max_hold_bars=max_hold_bars,
                entry_price_ref=float(sig.entry),
                entry_at=sig.entry_at,
                meta={
                    "sweep_at": sig.sweep_at,
                    "bos_at": sig.bos_at,
                    "mtf_stack": {
                        "d1": (stack.get("D1") or {}).get("trend"),
                        "h4": (stack.get("H4") or {}).get("trend"),
                        "h1": (stack.get("H1") or {}).get("trend"),
                        "pd": (stack.get("dealing") or {}).get("pd_side"),
                    },
                },
            )
        )
    state = PlanState.ENTRY_READY if orders else PlanState.NO_TRADE
    return TradingPlan(
        plan_id=plan_id,
        symbol=symbol,
        model_id="mtf_intraday",
        state=state,
        coverage_mode=CoverageMode.V2_PARTIAL,
        orders=orders,
        context={"filter_stats": filter_stats or {}, "cascade": "D1→H4→H1→M15"},
        narrative={"htf_bias": "H4", "context": "D1", "zone": "H1"},
        zone={"tf": "H1"},
        setup={"tf": ltf, "engine": "run_sequence+top_down_gate"},
        explanation_template={"cascade": "D1→H4→H1→M15"},
    )


def explanation_mtf(plan: TradingPlan, order: Order, exit_reason: str) -> TradeExplanation:
    m = order.meta.get("mtf_stack") or {}
    layers = {
        "D1": m.get("d1", "?"),
        "H4": m.get("h4", "?"),
        "H1": m.get("h1", "?"),
        "PD": m.get("pd", "?"),
        "M15": plan.setup,
        "exec": {
            "tf": "M15",
            "direction": order.direction,
            "entry": order.entry_price_ref,
            "sl": order.stop_loss,
            "tp": order.take_profit,
        },
    }
    return TradeExplanation(
        trade_id=f"tr-{order.order_id}",
        plan_id=plan.plan_id,
        order_id=order.order_id,
        result=exit_reason,
        layers=layers,
    )
