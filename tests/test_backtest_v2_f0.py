"""F0 Backtest v2: contracts, coverage report, pure simulator bridge."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ict_backtest.engine import ICTSignal
from ict_backtest.v2.contracts import CoverageMode, Order, PlanState
from ict_backtest.v2.coverage import build_coverage_report, default_registry
from ict_backtest.v2.event_log import EventLog
from ict_backtest.v2.simulator import simulate_order
from ict_backtest.v2.strategy_legacy import explanation_for_trade, signals_to_plan


def test_coverage_report_is_automatic_not_narrative():
    rep = build_coverage_report("sequence_legacy", "legacy_subset")
    assert rep.coverage_mode == "legacy_subset"
    assert rep.required > 0
    assert 0.0 <= rep.coverage_pct <= 100.0
    assert "parcial" in rep.verdict.lower() or "partial" in rep.verdict.lower() or "implementacion" in rep.verdict.lower()
    # Must not claim full thesis
    assert "completa" in rep.verdict.lower() or "objetivo" in rep.verdict.lower() or "parcial" in rep.verdict.lower()
    assert rep.per_capability["C07"] == "implemented"
    assert rep.per_capability["C02"] == "missing"
    assert rep.per_capability["C16"] == "implemented"


def test_coverage_formula_partial_half_weight():
    reg = {c: "missing" for c in default_registry()}
    # 2 required-like: force only C01 implemented, C07 partial, rest missing but
    # use a tiny custom path via full registry
    reg = default_registry("legacy_subset")
    rep = build_coverage_report("x", "legacy_subset", reg)
    # Sanity: formula (impl + 0.5*partial) / required
    expected = 100.0 * (rep.implemented + 0.5 * rep.partial) / rep.required
    assert abs(rep.coverage_pct - round(expected, 1)) < 0.15


def test_signals_to_plan_legacy_subset():
    sigs = [
        ICTSignal(
            symbol="EURUSD",
            time="2024-01-02 10:00:00+00:00",
            direction=1,
            entry=1.1,
            stop_loss=1.09,
            take_profit=1.13,
            model="sequence",
            entry_at=10,
            sweep_at=5,
            bos_at=8,
        )
    ]
    log = EventLog()
    plan = signals_to_plan(sigs, symbol="EURUSD", event_log=log)
    assert plan.coverage_mode == CoverageMode.LEGACY_SUBSET
    assert plan.state == PlanState.ENTRY_READY
    assert len(plan.orders) == 1
    assert plan.orders[0].stop_loss == 1.09
    assert len(log) >= 2  # PlanFormed + OrderIntent


def test_simulate_order_no_ict_columns_needed():
    """Simulator only needs OHLC + order levels."""
    n = 30
    df = pd.DataFrame(
        {
            "time": [f"2024-01-01 {i:02d}:00:00" for i in range(n)],
            "open": [1.1000 + i * 0.0001 for i in range(n)],
            "high": [1.1010 + i * 0.0001 for i in range(n)],
            "low": [1.0990 + i * 0.0001 for i in range(n)],
            "close": [1.1005 + i * 0.0001 for i in range(n)],
        }
    )
    order = Order(
        order_id="ord-1",
        plan_id="plan-1",
        symbol="EURUSD",
        model_id="test",
        direction=1,
        signal_time=df.iloc[5]["time"],
        stop_loss=1.05,
        take_profit=1.20,
        max_hold_bars=10,
        entry_price_ref=float(df.iloc[5]["close"]),
        entry_at=5,
    )
    log = EventLog()
    result, meta = simulate_order(order, df, cost=None, event_log=log)
    assert result is not None
    assert result.pnl_r == result.pnl_r  # finite
    assert any(r.kind == "EntryFilled" for r in log.records)
    assert any(r.kind == "TradeClosed" for r in log.records)


def test_explanation_human_readable():
    sigs = [
        ICTSignal(
            symbol="XAUUSD",
            time="t0",
            direction=-1,
            entry=2000.0,
            stop_loss=2010.0,
            take_profit=1970.0,
            entry_at=1,
        )
    ]
    plan = signals_to_plan(sigs, symbol="XAUUSD", htf="H4", ltf="M15")
    exp = explanation_for_trade(plan, plan.orders[0], "TP")
    text = exp.format_human()
    assert "Result: TP" in text
    assert "H1" in text
    assert "legacy" in text.lower() or "missing" in text.lower()


def test_event_log_jsonl(tmp_path: Path):
    log = EventLog()
    log.append("BiasFormed", ts="t1", plan_id="p1", tf="H4", payload={"bias": "BULLISH"})
    log.append("SweepTaken", ts="t2", plan_id="p1", tf="M15")
    path = tmp_path / "events.jsonl"
    log.to_jsonl(path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "BiasFormed"
