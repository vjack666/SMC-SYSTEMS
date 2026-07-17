"""R4-clean + funding-gate (6-month window).

Hermes order: Turtle Soup v2.8 (sequence, tesis 18: structural SL, RR>=1:3,
killzone) on EURUSD/GBPUSD, honest costs ON.

User meta: if a strategy cannot support a prop-style challenge on ~6 months
of history, it does not work for funding. This script measures:

  A) Classic BT: trades, WR, PF, expectancy, maxDD_R
  B) Funding sim (1% risk/trade, balance equity):
     - peak-to-trough max drawdown %
     - worst day loss %
     - days to +8% (Stellar 2-step phase 1 style)
     - days to +10% (1-step style)
     - whether max overall DD stayed within 8% / 10%
     - pass flags under FundedNext-like constraints (DLL 4%, MLL 8%)

Uses last N calendar days of available M15 (default 180). Not multi-year
cherry-pick — funding challenge is a short window by design.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ict_backtest.canonical import evaluate_signals
from ict_backtest.costs import resolve_cost
from ict_backtest.data_feed import load_frames
from ict_backtest.engine import simulate_trade
from ict_backtest.market_structure import detect_market_structure


def _metrics_r(pnls: list[float]) -> dict:
    n = len(pnls)
    if n == 0:
        return {
            "trades": 0, "winrate": 0.0, "pf": 0.0, "expectancy": 0.0,
            "max_dd_r": 0.0, "total_r": 0.0,
        }
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gw, gl = sum(wins), abs(sum(losses))
    pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0)
    equity = peak = max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {
        "trades": n,
        "winrate": len(wins) / n,
        "pf": float(pf) if pf != float("inf") else 999.0,
        "expectancy": sum(pnls) / n,
        "max_dd_r": max_dd,
        "total_r": sum(pnls),
    }


def _funding_sim(
    trades: list[dict],
    *,
    risk_pct: float = 1.0,
    dll_pct: float = 4.0,
    mll_pct: float = 8.0,
    target_p1: float = 8.0,
    target_1step: float = 10.0,
) -> dict:
    """Equity simulation in % of starting balance; sequential trade fills."""
    if not trades:
        return {
            "final_equity_pct": 0.0,
            "max_dd_pct": 0.0,
            "worst_day_pct": 0.0,
            "days_to_8pct": None,
            "days_to_10pct": None,
            "breached_dll": False,
            "breached_mll": False,
            "pass_stellar_2step_p1_shape": False,
            "pass_stellar_1step_shape": False,
            "note": "no_trades",
        }

    bal = 100.0  # percent units
    peak = 100.0
    max_dd = 0.0
    day_pnl: dict[str, float] = {}
    start_t = pd.to_datetime(trades[0]["exit_time"], utc=True)
    days_to_8 = days_to_10 = None
    breached_dll = breached_mll = False

    for tr in trades:
        # R units * risk% = equity change in %
        d = float(tr["pnl_r"]) * risk_pct
        bal += d
        peak = max(peak, bal)
        dd = peak - bal
        max_dd = max(max_dd, dd)
        if (100.0 - bal) >= mll_pct or dd >= mll_pct:
            # overall from start or trailing peak style MLL: use trailing from peak
            if dd >= mll_pct:
                breached_mll = True
        day = str(pd.to_datetime(tr["exit_time"], utc=True).date())
        day_pnl[day] = day_pnl.get(day, 0.0) + d
        if day_pnl[day] <= -dll_pct:
            breached_dll = True
        t = pd.to_datetime(tr["exit_time"], utc=True)
        elapsed = (t - start_t).total_seconds() / 86400.0
        if days_to_8 is None and (bal - 100.0) >= target_p1:
            days_to_8 = round(elapsed, 1)
        if days_to_10 is None and (bal - 100.0) >= target_1step:
            days_to_10 = round(elapsed, 1)

    worst_day = min(day_pnl.values()) if day_pnl else 0.0
    profit = bal - 100.0
    # "shape pass": hit target without breaching DLL/MLL (simplified; no min trading days)
    pass_p1 = (
        profit >= target_p1 and not breached_dll and not breached_mll and days_to_8 is not None
    )
    pass_1s = (
        profit >= target_1step and not breached_dll and not breached_mll and days_to_10 is not None
    )
    return {
        "final_equity_pct": round(bal - 100.0, 2),
        "max_dd_pct": round(max_dd, 2),
        "worst_day_pct": round(worst_day, 2),
        "days_to_8pct": days_to_8,
        "days_to_10pct": days_to_10,
        "breached_dll": breached_dll,
        "breached_mll": breached_mll,
        "pass_stellar_2step_p1_shape": pass_p1,
        "pass_stellar_1step_shape": pass_1s,
        "n_trading_days": len(day_pnl),
        "risk_pct_per_trade": risk_pct,
        "dll_pct": dll_pct,
        "mll_pct": mll_pct,
    }


def _slice_frames(frames: dict, days: int) -> dict:
    """Keep last `days` calendar days on LTF and align others by time."""
    # prefer M15 if present else shortest bar count TF as anchor
    anchor_tf = "M15" if "M15" in frames else sorted(frames.keys(), key=lambda t: len(frames[t]))[-1]
    df = frames[anchor_tf].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    t_end = df["time"].max()
    t_start = t_end - timedelta(days=days)
    out = {}
    for tf, f in frames.items():
        g = f.copy()
        g["time"] = pd.to_datetime(g["time"], utc=True)
        out[tf] = g[g["time"] >= t_start].reset_index(drop=True)
    return out, str(t_start.date()), str(t_end.date()), anchor_tf


def run_cell(
    symbol: str,
    htf: str,
    ltf: str,
    *,
    counter_trend: bool,
    days: int,
    max_hold: int,
    with_cost: bool,
) -> dict:
    t0 = time.time()
    frames = load_frames(symbol, tuple(dict.fromkeys([htf, ltf, "D1"])))
    frames, d0, d1, anchor = _slice_frames(frames, days)
    if len(frames.get(ltf, [])) < 50:
        return {
            "symbol": symbol, "htf": htf, "ltf": ltf, "counter_trend": counter_trend,
            "error": f"insufficient LTF bars after slice ({len(frames.get(ltf, []))})",
            "window": f"{d0}..{d1}",
        }

    cost = resolve_cost(symbol, no_cost=not with_cost)
    signals = evaluate_signals(
        symbol, htf, ltf,
        counter_trend=counter_trend,
        require_displacement=True,
        frames=frames,
        fill_mode="next_open",
    )
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    pnls: list[float] = []
    exits: dict[str, int] = {}
    trade_rows: list[dict] = []
    for sig in signals:
        trade, meta = simulate_trade(ltf_df, sig, max_hold, cost=cost)
        if trade is None:
            continue
        pnls.append(trade.pnl_r)
        reason = meta.get("exit_reason", "?")
        exits[reason] = exits.get(reason, 0) + 1
        trade_rows.append({
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "pnl_r": trade.pnl_r,
            "direction": trade.direction,
            "exit_reason": reason,
        })

    m = _metrics_r(pnls)
    fund = _funding_sim(trade_rows)
    # funding viability flag (user meta): 6m window can reach phase-1 shape
    funding_viable = bool(
        fund.get("pass_stellar_2step_p1_shape")
        or fund.get("pass_stellar_1step_shape")
        or (
            m["trades"] >= 15
            and m["pf"] >= 1.10
            and m["expectancy"] > 0
            and fund.get("max_dd_pct", 99) <= 8.0
            and not fund.get("breached_dll")
        )
    )
    return {
        "symbol": symbol,
        "htf": htf,
        "ltf": ltf,
        "counter_trend": counter_trend,
        "model": "TurtleSoup_CT" if counter_trend else "Sequence_AT",
        "window": f"{d0}..{d1}",
        "days": days,
        "with_cost": with_cost,
        "n_signals": len(signals),
        "metrics": m,
        "exits": exits,
        "funding": fund,
        "funding_viable_6m": funding_viable,
        "elapsed_s": round(time.time() - t0, 1),
        "gate_pf_1_10": m["pf"] >= 1.10 and m["trades"] >= 10,
    }


def main() -> int:
    days = 180
    max_hold = 16
    cells = []
    # R4-clean core: Turtle CT H4->M15 + AT control, EURUSD+GBPUSD, cost ON
    for sym in ("EURUSD", "GBPUSD"):
        for ct in (True, False):
            print(f"\n=== {sym} H4->M15 CT={ct} cost=ON days={days} ===", flush=True)
            cell = run_cell(
                sym, "H4", "M15",
                counter_trend=ct, days=days, max_hold=max_hold, with_cost=True,
            )
            cells.append(cell)
            m = cell.get("metrics", {})
            f = cell.get("funding", {})
            print(
                f"  signals={cell.get('n_signals')} trades={m.get('trades')} "
                f"PF={m.get('pf'):.3f} WR={100*(m.get('winrate') or 0):.1f}% "
                f"E[R]={m.get('expectancy'):.3f} totalR={m.get('total_r'):.1f}",
                flush=True,
            )
            print(
                f"  funding: equity%={f.get('final_equity_pct')} maxDD%={f.get('max_dd_pct')} "
                f"worstDay%={f.get('worst_day_pct')} d8={f.get('days_to_8pct')} "
                f"pass_p1={f.get('pass_stellar_2step_p1_shape')} "
                f"viable={cell.get('funding_viable_6m')}",
                flush=True,
            )

    # Also theory (no cost) for Turtle CT only — diagnose cost impact
    for sym in ("EURUSD", "GBPUSD"):
        print(f"\n=== {sym} H4->M15 CT=True cost=OFF (theory) ===", flush=True)
        cell = run_cell(
            sym, "H4", "M15",
            counter_trend=True, days=days, max_hold=max_hold, with_cost=False,
        )
        cell["label"] = "theory_no_cost"
        cells.append(cell)
        m = cell.get("metrics", {})
        print(
            f"  trades={m.get('trades')} PF={m.get('pf'):.3f} "
            f"viable={cell.get('funding_viable_6m')}",
            flush=True,
        )

    # Verdict synthesis
    turtle = [c for c in cells if c.get("counter_trend") and c.get("with_cost")]
    any_gate = any(c.get("gate_pf_1_10") for c in turtle)
    any_fund = any(c.get("funding_viable_6m") for c in turtle)
    if any_fund and any_gate:
        verdict = "PASS_FUNDING_SHAPE"
        summary = (
            "Turtle CT sequence shows funding-viable shape on >=1 symbol "
            "in 6m with costs AND PF gate."
        )
    elif any_fund:
        verdict = "FUNDING_SHAPE_ONLY"
        summary = (
            "Some funding-shape pass without classic PF>=1.10 on enough trades — "
            "fragile; not production-ready."
        )
    elif any(c.get("metrics", {}).get("trades", 0) == 0 for c in turtle):
        zeros = [c["symbol"] for c in turtle if c.get("metrics", {}).get("trades", 0) == 0]
        if all(c.get("metrics", {}).get("trades", 0) == 0 for c in turtle):
            verdict = "INCONCLUSIVE_ZERO_TRADES"
            summary = (
                "Turtle v2.8 (tesis 18 filters) produced 0 trades in 6m window — "
                "cannot validate funding. Not a green light."
            )
        else:
            verdict = "REJECT_NO_EDGE"
            summary = (
                f"Zero trades on {zeros}; other cells fail PF/funding gates. "
                "Not suitable for FundedNext-style challenge under our automation."
            )
    else:
        verdict = "REJECT_NO_EDGE"
        summary = (
            "Turtle Soup / sequence CT fails PF>=1.10 and funding sim "
            "(8% target without 4% daily / 8% max DD breach) on 6m window."
        )

    report = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": "R4-clean + funding-gate 6m",
        "thesis": "sequence structural SL + RR1:3 + killzone + next_open fill + costs",
        "funding_rules_sim": {
            "risk_per_trade_pct": 1.0,
            "dll_pct": 4.0,
            "mll_pct": 8.0,
            "phase1_target_pct": 8.0,
            "one_step_target_pct": 10.0,
            "note": "Simplified sequential sim; no news blackout, no min trading days",
        },
        "external_context": {
            "fundednext_stellar_2step": "commonly 8% then 5% targets; daily/overall DD firm-specific (~3-5% daily, ~6-10% max)",
            "public_backtests": (
                "Independent 10y mechanical ICT suite (r/Forex 2026): Silver Bullet ~34% of "
                "6m windows FTMO-like pass; Turtle Soup ~27% despite 68% WR — loss clustering "
                "kills challenges. Marketing videos claim ICT passes challenges; automated "
                "filters show low pass rates when risk rules are enforced."
            ),
            "implication": (
                "High WR alone does not pass prop. Need loss distribution + DD control. "
                "Our gate uses 6m window + DLL/MLL + 8% target as funding meta."
            ),
        },
        "cells": cells,
        "verdict": verdict,
        "summary": summary,
        "r4_status": "CLOSED",
        "r4_live_recommendation": (
            "DO_NOT_AUTO_TRADE_ICT_MODELS"
            if verdict.startswith("REJECT") or verdict.startswith("INCONCLUSIVE")
            else "PAPER_ONLY_UNTIL_A12"
        ),
    }

    out_dir = ROOT / "results" / "r4"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"r4_clean_funding_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    # also stable latest pointer
    (out_dir / "r4_clean_funding_LATEST.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print("\n===== R4-CLEAN VERDICT =====", flush=True)
    print(verdict, flush=True)
    print(summary, flush=True)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
