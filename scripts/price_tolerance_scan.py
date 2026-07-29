from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ict_backtest.data_feed import build_features, build_objects
from ict_backtest.event_engine import run_semantic, EventEngine, LAST_META
from ict_backtest.market_object import ObjectState, ObjectType
from ict_backtest.market_narrative import MarketNarrative
from ict_backtest.object_graph import ObjectGraph
from ict_backtest.state_machine import StateMachine, MarketEvent


def _find_return_bar(ltf_df: pd.DataFrame, zone_high: float, zone_low: float, after_bar: int) -> int | None:
    if ltf_df is None or not len(ltf_df):
        return None
    if zone_high <= zone_low or zone_high <= 0:
        return None
    n = len(ltf_df)
    start = int(after_bar) + 1
    if start >= n:
        return None
    for i in range(start, n):
        row = ltf_df.iloc[i]
        low = float(row.get("low", 0))
        high = float(row.get("high", 0))
        if low <= zone_high and high >= zone_low:
            return i
    return None


def _near_level(price: float, level: float, tol: float) -> bool:
    if level <= 0 or price <= 0:
        return False
    return abs(price - level) <= tol


def _score_exec(exec_objs, ltf_zh: float, ltf_zl: float, sig_dir: int, ltf_bos_bar: int, price_tolerance_pips: int):
    tol = price_tolerance_pips * 0.0001
    ltf_zone_mid = (ltf_zh + ltf_zl) / 2.0 if (ltf_zh and ltf_zl) else 0
    if ltf_zh <= 0 or ltf_zl <= 0:
        return 0, []

    def _zone_near_ltf(eo_zh: float, eo_zl: float) -> bool:
        if eo_zh <= 0 and eo_zl <= 0:
            return False
        return (
            _near_level(eo_zh, ltf_zh, tol)
            or _near_level(eo_zh, ltf_zl, tol)
            or _near_level(eo_zl, ltf_zh, tol)
            or _near_level(eo_zl, ltf_zl, tol)
            or _near_level((eo_zh + eo_zl) / 2.0, ltf_zone_mid, tol)
        )

    _after = [
        eo
        for eo in exec_objs
        if (int(eo.bar_index) if eo.bar_index is not None else 0) > ltf_bos_bar
        and (int(eo.bar_index) if eo.bar_index is not None else 0) <= ltf_bos_bar + 50
    ]
    score = 0
    matched_types: list[str] = []
    for eo in _after:
        t = eo.type.value if hasattr(eo.type, "value") else str(eo.type)
        if eo.direction != sig_dir:
            continue
        if eo.zone_high <= 0 and eo.zone_low <= 0:
            continue
        if _zone_near_ltf(eo.zone_high, eo.zone_low):
            if t == "SWEEP":
                score += 1
                matched_types.append("sweep")
            elif t == "FVG":
                score += 1
                matched_types.append("fvg")
            elif t == "BOS":
                score += 1
                matched_types.append("bos")
    return score, matched_types


def run_price_tolerance_scan(
    price_tolerance_pips: int = 20,
):
    from ict_backtest.sequence import SequenceConfig
    root = Path(__file__).resolve().parent.parent
    raw = root / "data" / "raw"
    m15_path = raw / "EURUSD_M15.parquet"
    m5_path = raw / "EURUSD_M5.parquet"

    m15_raw = pd.read_parquet(m15_path)
    m5_raw = pd.read_parquet(m5_path)
    m15_raw["time"] = pd.to_datetime(m15_raw["time"], utc=True)
    m5_raw["time"] = pd.to_datetime(m5_raw["time"], utc=True)

    cut = m15_raw["time"].max() - pd.Timedelta(days=30)
    m15 = m15_raw[m15_raw["time"] >= cut].reset_index(drop=True)
    m5 = m5_raw[m5_raw["time"] >= cut].reset_index(drop=True)

    m15_f = build_features(m15)
    m5_f = build_features(m5)
    exec_objs = build_objects({"M5": m5_f})
    exec_by_type_dir = {}
    for eo in exec_objs:
        t = eo.type.value if hasattr(eo.type, "value") else str(eo.type)
        exec_by_type_dir.setdefault((t, int(eo.direction) or 0), []).append(eo)

    def htf_fn(i):
        return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False}

    sigs = run_semantic(
        m15_f,
        htf_fn,
        SequenceConfig(),
        ltf_tf="M15",
        max_hold=200,
        ltf_df=m15_f,
        est_htf_ctx_fn=None,
        exec_df=m5_f,
        exec_tf="M5",
        price_tolerance_pips=price_tolerance_pips,
    )
    signals = [s for s in sigs if s.get("exec_m5_score", 0) > 0]
    trades = _simulate_trades(m5_f, signals, max_hold_bars=192)
    metrics = _compute_metrics(signals, trades)
    return metrics


def _simulate_trades(ltf_df: pd.DataFrame, signals: list[dict], max_hold_bars: int = 192) -> list[dict]:
    pip = 0.0001
    trades: list[dict] = []
    for sig in signals:
        entry_bar = int(sig.get("entry_at", sig.get("bar_index", 0)))
        if entry_bar + 1 >= len(ltf_df):
            continue
        entry = float(ltf_df.iloc[entry_bar + 1]["open"])
        sl = float(sig.get("zone_low", 0)) if sig.get("direction", 1) == 1 else float(sig.get("zone_high", 0))
        if sl <= 0:
            continue
        risk = abs(entry - sl)
        if risk <= pip:
            continue
        tp = entry + 3.0 * risk if sig.get("direction", 1) == 1 else entry - 3.0 * risk
        exit_price, exit_reason, hold_bars = entry, "hold_limit", 0
        for step in range(1, max_hold_bars + 1):
            j = entry_bar + 1 + step
            if j >= len(ltf_df):
                break
            row = ltf_df.iloc[j]
            high = float(row["high"])
            low = float(row["low"])
            if sig.get("direction", 1) == 1:
                if low <= sl:
                    exit_price, exit_reason, hold_bars = sl, "SL", step
                    break
                if high >= tp:
                    exit_price, exit_reason, hold_bars = tp, "TP", step
                    break
            else:
                if high >= sl:
                    exit_price, exit_reason, hold_bars = sl, "SL", step
                    break
                if low <= tp:
                    exit_price, exit_reason, hold_bars = tp, "TP", step
                    break
            exit_price, hold_bars = float(row["close"]), step
        trades.append(
            {
                "entry": entry,
                "exit": exit_price,
                "direction": sig.get("direction", 1),
                "risk": risk,
                "pnl_r": (exit_price - entry) / risk if (sig.get("direction", 1) == 1 and risk > 0) else (entry - exit_price) / risk,
                "exit_reason": exit_reason,
                "hold_bars": hold_bars,
            }
        )
    return trades


def _compute_metrics(signals: list[dict], trades: list[dict]) -> dict:
    pnls = [t["pnl_r"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_trades = len(trades)
    winrate = len(wins) / total_trades * 100 if total_trades else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = min(gross_win / gross_loss, 10.0) if gross_loss > 0 else (10.0 if gross_win > 0 else 0.0)
    equity = peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    expectancy_r = sum(pnls) / total_trades if total_trades else 0.0
    return {
        "signals_generated": len(signals),
        "total_trades": total_trades,
        "winrate": winrate,
        "pf": pf,
        "max_dd_r": max_dd,
        "expectancy_r": expectancy_r,
    }


def _scan_tolerance(tol: int) -> dict:
    return run_price_tolerance_scan(price_tolerance_pips=tol)


def main() -> None:
    tolerances = [10, 15, 20, 30]
    results = []
    for tol in tolerances:
        try:
            m = _scan_tolerance(tol)
        except Exception as e:  # pragma: no cover - exploratory helper
            print(f"FAILED tol={tol}: {e}")
            continue
        results.append(
            {
                "tol": tol,
                "signals_generated": m["signals_generated"],
                "total_trades": m["total_trades"],
                "winrate": m["winrate"],
                "pf": m["pf"],
                "max_dd_r": m["max_dd_r"],
                "expectancy_r": m["expectancy_r"],
            }
        )

    if not results:
        print("No results")
        return

    print("tol= pips | sigs=X | trades=Y | winrate=Z% | PF=W | DD=D | exp=E")
    for r in results:
        print(
            f"tol={r['tol']:>2} | sigs={r['signals_generated']:>4} | trades={r['total_trades']:>3} | "
            f"winrate={r['winrate']:6.2f}% | PF={r['pf']:.3f} | DD={r['max_dd_r']:.3f} | exp={r['expectancy_r']:.3f}"
        )

    best = sorted(results, key=lambda r: (r["pf"], r["winrate"]), reverse=True)[0]
    print(
        f"\nRECOMMENDATION: price_tolerance_pips={best['tol']} "
        f"(PF={best['pf']:.3f}, winrate={best['winrate']:.2f}%)"
    )


if __name__ == "__main__":
    main()
