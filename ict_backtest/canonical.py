"""R7 — Single source of truth for ICT decision.

Only public decision API for the in-scope R7 surface:

    evaluate_signals(...)  -> list[ICTSignal]
    latest_plan(...)       -> dict | None   (for observador / live)

Canonical engine: ``sequence.run_sequence`` (+ structural SL / RR 1:3 / killzone).

Out of R7 implementation scope (documented debt — not invisible):
  - legacy/backtest/engine.py  — accepted as DEBT; not rewired here
  - ml/dataset_builder.py      — accepted as DEBT; still uses legacy

Those must not be treated as a second "official" ICT motor for new work.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.engine import (
    STRUCT_SL_MAX_ATR,
    ICTSignal,
    calc_structural_sl,
    fill_entry_price,
    _tp_liquidity,
)
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.rules import killzone_en
from ict_backtest.sequence import SequenceConfig, run_sequence

CANONICAL_ENGINE = "sequence"

# Explicit R7 debt (DoD H2/H3) — not migrated in this change.
R7_DOCUMENTED_DEBT = (
    "legacy/backtest/engine.py",
    "ml/dataset_builder.py",
)


def load_bos_table() -> dict | None:
    """Load empirical bos_table if present (R10); else None -> sequence fallback."""
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parent / "bos_table.json"
    if not path.exists():
        return None
    try:
        return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (ValueError, OSError):
        return None


def evaluate_signals(
    symbol: str,
    htf: str,
    ltf: str,
    *,
    counter_trend: bool = False,
    tp_mode: str = "fixed2r",
    require_displacement: bool = True,
    displace_gap: int = 6,
    bos_gap: int | None = 10,
    bos_table: dict | None = None,
    frames: dict | None = None,
    fill_mode: str = "next_open",
) -> list[ICTSignal]:
    """Canonical ICT signal generator (R7).

    Event-sequence sweep→displace→BOS→return, structural SL, RR≥1:3, killzone.
    """
    if bos_table is None:
        bos_table = load_bos_table()
    if frames is None:
        from ict_backtest.data_feed import load_frames

        tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))
        frames = load_frames(symbol, tfs)

    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    def est_htf_fn(i: int) -> dict[str, Any]:
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }

    raw_sigs, _ = run_sequence(
        ltf_df,
        est_htf_fn,
        SequenceConfig(
            counter_trend=counter_trend,
            tp_mode=tp_mode,
            require_displacement=require_displacement,
            displace_gap=displace_gap,
            bos_gap=bos_gap,
        ),
        ltf_tf=ltf,
        bos_table=bos_table,
    )

    signals: list[ICTSignal] = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        try:
            entry = fill_entry_price(ltf_df, entry_at, fill_mode)
        except ValueError:
            continue
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_ATR * atr:
            continue
        liq = _tp_liquidity(entry_row, direction)
        if liq is not None:
            tp = liq
        else:
            tp = entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        signals.append(
            ICTSignal(
                symbol=symbol,
                time=s["time"],
                direction=direction,
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
                model="sequence",
                sweep_at=s["sweep_at"],
                bos_at=s["bos_at"],
                entry_at=s["entry_at"],
            )
        )
    return signals


def latest_plan(
    symbol: str,
    htf: str = "H4",
    ltf: str = "M15",
    *,
    frames: dict | None = None,
    max_age_bars: int = 48,
) -> dict[str, Any] | None:
    """Last canonical signal as a live plan dict, or None.

    Used by the observador so Lab/LIMIT share the same brain as sequence.
    ``max_age_bars``: ignore signals whose entry_at is older than this many
    bars from the end of the LTF series (stale setups).
    """
    signals = evaluate_signals(symbol, htf, ltf, frames=frames)
    if not signals:
        return None
    sig = signals[-1]
    # Optional freshness when frames available
    if frames is not None and ltf in frames and sig.entry_at is not None:
        n = len(frames[ltf])
        if n - 1 - int(sig.entry_at) > max_age_bars:
            return None
    side = "LONG" if sig.direction == 1 else "SHORT"
    risk = abs(sig.entry - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry)
    rr = (reward / risk) if risk > 0 else 0.0
    return {
        "engine": CANONICAL_ENGINE,
        "symbol": sig.symbol,
        "side": side,
        "direction": sig.direction,
        "entry": float(sig.entry),
        "sl": float(sig.stop_loss),
        "tp": float(sig.take_profit),
        "rr": float(rr),
        "time": str(sig.time),
        "model": sig.model,
        "sweep_at": sig.sweep_at,
        "bos_at": sig.bos_at,
        "entry_at": sig.entry_at,
    }
