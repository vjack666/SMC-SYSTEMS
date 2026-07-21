"""Forensic audit: trace exactly where signals die in the canonical pipeline.

Runs the SAME path as run_backtest.py -> canonical.py -> sequence.py,
but instruments every decision point to count survivors at each stage.
"""
from __future__ import annotations

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\v_jac\Desktop\SMC-SYSTEMS")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest.rules import killzone_en, KILLZONES_UTC
from ict_backtest.engine import calc_structural_sl, fill_entry_price, _tp_liquidity, STRUCT_SL_MAX_RANGE


def audit_symbol(symbol: str, htf: str, ltf: str, max_hold: int = 16,
                 require_displacement: bool = True, counter_trend: bool = False):
    print(f"\n{'='*80}")
    print(f"  FORENSIC AUDIT: {symbol} {htf}->{ltf}  (max_hold={max_hold})")
    print(f"{'='*80}\n")

    # ── STAGE 0: DATA LOADING ──────────────────────────────────────────
    print("[STAGE 0] Loading frames...")
    tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))
    frames = load_frames(symbol, tfs)
    for tf_name, df in frames.items():
        t0 = pd.to_datetime(df["time"].iloc[0], utc=True)
        t1 = pd.to_datetime(df["time"].iloc[-1], utc=True)
        print(f"  {tf_name}: {len(df)} bars, {t0.date()} -> {t1.date()}")

    # ── STAGE 1: MARKET STRUCTURE DETECTION ────────────────────────────
    print("\n[STAGE 1] Detecting market structure...")
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    for tf_name, df in ms.items():
        bos_active = int((df["bos_status"] == "active").sum())
        bos_total = int((df["bos_dir"] != 0).sum())
        choch_active = int((df["choch_status"] == "active").sum())
        choch_total = int((df["choch_dir"] != 0).sum())
        trend_dist = df["trend"].value_counts().to_dict()
        print(f"  {tf_name}: BOS={bos_total} (active={bos_active}), "
              f"CHOCH={choch_total} (active={choch_active}), trend={trend_dist}")

    # ── STAGE 2: SEQUENCE ENGINE (raw signals) ────────────────────────
    print("\n[STAGE 2] Running sequence engine (sweep→displace→BOS→entry)...")

    def est_htf_fn(i: int):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }

    cfg = SequenceConfig(
        counter_trend=counter_trend,
        tp_mode="fixed2r",
        require_displacement=require_displacement,
        displace_gap=6,
        bos_gap=10,
    )
    raw_sigs, phase_seen = run_sequence(ltf_df, est_htf_fn, cfg, ltf_tf=ltf)
    print(f"  Raw signals from sequence: {len(raw_sigs)}")
    print(f"  Phase counts: {phase_seen}")

    # Count HTF trend distribution during the period
    htf_trends = []
    for i in range(len(ltf_df)):
        est = est_htf_fn(i)
        htf_trends.append(est["trend"])
    trend_counts = pd.Series(htf_trends).value_counts().to_dict()
    print(f"  HTF trend distribution: {trend_counts}")

    # Count sweep events
    sweep_down_count = 0
    sweep_up_count = 0
    for i in range(len(ltf_df)):
        est = est_htf_fn(i)
        if est.get("sweep_down"):
            sweep_down_count += 1
        if est.get("sweep_up"):
            sweep_up_count += 1
    print(f"  HTF sweep events: down={sweep_down_count}, up={sweep_up_count}")

    # ── STAGE 3: POST-SEQUENCE FILTERS (canonical.py logic) ───────────
    print(f"\n[STAGE 3] Applying post-sequence filters to {len(raw_sigs)} raw signals...")

    filter_counts = {
        "raw_signals": len(raw_sigs),
        "fill_next_open_fail": 0,
        "atr_zero_or_nan": 0,
        "killzone_rejected": 0,
        "killzone_details": {},
        "structural_sl_none": 0,
        "structural_sl_sweep_low_missing": 0,
        "structural_sl_swing_low_missing": 0,
        "risk_too_small": 0,
        "risk_too_large": 0,
        "final_signals": 0,
    }

    for idx, s in enumerate(raw_sigs):
        direction = s["direction"]
        entry_at = s["entry_at"]
        sweep_at = s["sweep_at"]

        # Fill mode: next_open
        try:
            entry = fill_entry_price(ltf_df, entry_at, "next_open")
        except ValueError:
            filter_counts["fill_next_open_fail"] += 1
            continue

        # ATR check
        entry_row = ltf_df.iloc[entry_at]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            filter_counts["atr_zero_or_nan"] += 1
            continue

        # Killzone check
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            filter_counts["killzone_rejected"] += 1
            filter_counts["killzone_details"][kz or "NONE"] = filter_counts["killzone_details"].get(kz or "NONE", 0) + 1
            continue

        # Structural SL
        sweep_row = ltf_df.iloc[sweep_at]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            filter_counts["structural_sl_none"] += 1
            # Diagnose why
            has_sweep_low = pd.notna(sweep_row.get("sweep_low", np.nan))
            has_sweep_high = pd.notna(sweep_row.get("sweep_high", np.nan))
            has_swing_low = pd.notna(sweep_row.get("swing_low", np.nan))
            has_swing_high = pd.notna(sweep_row.get("swing_high", np.nan))
            if direction == 1:
                if not has_sweep_low and not has_swing_low:
                    filter_counts["structural_sl_sweep_low_missing"] += 1
            else:
                if not has_sweep_high and not has_swing_high:
                    filter_counts["structural_sl_swing_low_missing"] += 1
            continue

        # Risk check
        risk = abs(entry - sl)
        if risk <= 0:
            filter_counts["risk_too_small"] += 1
            continue
        if risk > STRUCT_SL_MAX_RANGE * atr:
            filter_counts["risk_too_large"] += 1
            continue

        filter_counts["final_signals"] += 1

    print(f"\n  +================================================================+")
    print(f"  |              SIGNAL FUNNEL (EMBUDO DE SENALES)               |")
    print(f"  +================================================================+")
    print(f"  |  Stage 0: Total bars LTF               : {len(ltf_df):>8}         |")
    print(f"  |  Stage 1: BOS detected (ltf)           : {phase_seen.get('SWEEP',0):>8} SWEEPs    |")
    print(f"  |  Stage 2: Raw sequence signals         : {filter_counts['raw_signals']:>8}         |")
    print(f"  |  ----------------------------------------------------------  |")
    print(f"  |  KILLED by fill_next_open_fail          : {filter_counts['fill_next_open_fail']:>8}         |")
    print(f"  |  KILLED by ATR=0/NaN                   : {filter_counts['atr_zero_or_nan']:>8}         |")
    print(f"  |  KILLED by killzone                     : {filter_counts['killzone_rejected']:>8}         |")
    print(f"  |  KILLED by structural SL = None         : {filter_counts['structural_sl_none']:>8}         |")
    print(f"  |    - sweep_low/high missing             : {filter_counts['structural_sl_sweep_low_missing']+filter_counts['structural_sl_swing_low_missing']:>8}         |")
    print(f"  |  KILLED by risk <= 0                    : {filter_counts['risk_too_small']:>8}         |")
    print(f"  |  KILLED by risk > {STRUCT_SL_MAX_RANGE:.0f}*ATR               : {filter_counts['risk_too_large']:>8}         |")
    print(f"  |  ==========================================================  |")
    print(f"  |  FINAL SIGNALS (trades)                : {filter_counts['final_signals']:>8}         |")
    print(f"  +================================================================+")

    if filter_counts["killzone_details"]:
        print(f"\n  Killzone rejection breakdown:")
        for kz_name, count in sorted(filter_counts["killzone_details"].items(), key=lambda x: -x[1]):
            print(f"    {kz_name or 'NONE':20s}: {count}")

    # ── DEEP DIAGNOSTIC: Killzone time distribution ────────────────────
    print(f"\n[DEEP DIAG] Killzone distribution across ALL LTF bars...")
    kz_dist = {}
    for i in range(len(ltf_df)):
        t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True)
        kz = killzone_en(t)
        kz_dist[kz or "NONE"] = kz_dist.get(kz or "NONE", 0) + 1
    for kz_name, count in sorted(kz_dist.items(), key=lambda x: -x[1]):
        pct = 100.0 * count / len(ltf_df)
        print(f"    {kz_name:20s}: {count:>6} bars ({pct:.1f}%)")

    # ── DEEP DIAGNOSTIC: Sequence phase survival ───────────────────────
    print(f"\n[DEEP DIAG] Sequence phase survival (manual trace of first 20 bars)...")
    print(f"  HTF trend at each LTF bar:")
    for i in range(min(20, len(ltf_df))):
        est = est_htf_fn(i)
        t = str(ltf_df.iloc[i]["time"])[:19]
        print(f"    bar {i:4d} {t}: trend={est['trend']:8s} sw_dn={est['sweep_down']} sw_up={est['sweep_up']}")

    # ── DEEP DIAGNOSTIC: Sweep level availability for structural SL ────
    print(f"\n[DEEP DIAG] Sweep level availability in LTF DataFrame...")
    sweep_down_flag = ltf_df["liquidity_sweep_down"].sum() if "liquidity_sweep_down" in ltf_df.columns else 0
    sweep_up_flag = ltf_df["liquidity_sweep_up"].sum() if "liquidity_sweep_up" in ltf_df.columns else 0
    sweep_low_valid = ltf_df["sweep_low"].notna().sum() if "sweep_low" in ltf_df.columns else 0
    sweep_high_valid = ltf_df["sweep_high"].notna().sum() if "sweep_high" in ltf_df.columns else 0
    swing_low_valid = ltf_df["swing_low"].notna().sum() if "swing_low" in ltf_df.columns else 0
    swing_high_valid = ltf_df["swing_high"].notna().sum() if "swing_high" in ltf_df.columns else 0
    print(f"  liquidity_sweep_down=True:  {sweep_down_flag}")
    print(f"  liquidity_sweep_up=True:    {sweep_up_flag}")
    print(f"  sweep_low notna:            {sweep_low_valid}")
    print(f"  sweep_high notna:           {sweep_high_valid}")
    print(f"  swing_low notna:            {swing_low_valid}")
    print(f"  swing_high notna:           {swing_high_valid}")

    # ── DEEP DIAGNOSTIC: displacement availability ─────────────────────
    print(f"\n[DEEP DIAG] Displacement availability...")
    disp_bull = ltf_df["displacement_bullish"].sum() if "displacement_bullish" in ltf_df.columns else 0
    disp_bear = ltf_df["displacement_bearish"].sum() if "displacement_bearish" in ltf_df.columns else 0
    print(f"  displacement_bullish=True:  {int(disp_bull)}")
    print(f"  displacement_bearish=True:  {int(disp_bear)}")

    # ── DEEP DIAGNOSTIC: FVG and OB availability ──────────────────────
    print(f"\n[DEEP DIAG] FVG and OB availability...")
    fvg_bull = ltf_df["fvg_bullish"].sum() if "fvg_bullish" in ltf_df.columns else 0
    fvg_bear = ltf_df["fvg_bearish"].sum() if "fvg_bearish" in ltf_df.columns else 0
    ob_bull = ltf_df["ob_bullish"].sum() if "ob_bullish" in ltf_df.columns else 0
    ob_bear = ltf_df["ob_bearish"].sum() if "ob_bearish" in ltf_df.columns else 0
    print(f"  fvg_bullish=True:  {int(fvg_bull)}")
    print(f"  fvg_bearish=True:  {int(fvg_bear)}")
    print(f"  ob_bullish=True:   {int(ob_bull)}")
    print(f"  ob_bearish=True:   {int(ob_bear)}")

    return filter_counts


if __name__ == "__main__":
    # Run on multiple symbols to get a complete picture
    for sym in ["EURUSD", "GBPUSD", "XAUUSD"]:
        try:
            audit_symbol(sym, htf="D1", ltf="H4", max_hold=16)
        except Exception as e:
            print(f"\n  ERROR auditing {sym}: {e}")
            import traceback
            traceback.print_exc()
