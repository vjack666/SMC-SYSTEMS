"""Deep diagnostic: killzone-timeframe mismatch and displacement bottleneck."""
from __future__ import annotations

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
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


def deep_diagnostic(symbol: str, htf: str, ltf: str):
    print(f"\n{'='*80}")
    print(f"  DEEP DIAGNOSTIC: {symbol} {htf}->{ltf}")
    print(f"{'='*80}")

    tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))
    frames = load_frames(symbol, tfs)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }

    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10)
    raw_sigs, phase_seen = run_sequence(ltf_df, est_htf_fn, cfg, ltf_tf=ltf)

    # ── DIAGNOSTIC 1: Killzone-Timeframe Mismatch ─────────────────────
    print(f"\n[DIAG 1] KILLZONE-TIMEFRAME MISMATCH")
    print(f"  Data timestamps are: {pd.to_datetime(ltf_df.iloc[0]['time'], utc=True)}")
    print(f"  LTF bar hours (first 24):")
    hours = [pd.to_datetime(ltf_df.iloc[i]["time"], utc=True).hour for i in range(min(24, len(ltf_df)))]
    print(f"    {hours}")

    # Check what killzones each H4 bar lands in
    print(f"\n  Killzone per H4 bar hour:")
    kz_per_hour = {}
    for h in range(24):
        fake_ts = pd.Timestamp(f"2024-01-01 {h:02d}:00:00", tz="UTC")
        kz = killzone_en(fake_ts)
        kz_per_hour[h] = kz or "NONE"
        print(f"    {h:02d}:00 UTC -> {kz_per_hour[h]:20s}")

    # Count raw signal timestamps and their killzones
    print(f"\n  Raw signal timestamps and killzones:")
    kz_signal_dist = {}
    for s in raw_sigs:
        t = pd.to_datetime(s["time"], utc=True)
        kz = killzone_en(t) or "NONE"
        kz_signal_dist[kz] = kz_signal_dist.get(kz, 0) + 1
        print(f"    bar {s['entry_at']:5d} {str(t)[:19]} direction={s['direction']:+d} kz={kz}")

    print(f"\n  Signal killzone distribution:")
    for kz, cnt in sorted(kz_signal_dist.items(), key=lambda x: -x[1]):
        allowed = "PASS" if kz in ("London Open", "New York AM", "New York PM") else "KILLED"
        print(f"    {kz:20s}: {cnt:>3} ({allowed})")

    # ── DIAGNOSTIC 2: Displacement bottleneck ──────────────────────────
    print(f"\n[DIAG 2] DISPLACEMENT BOTTLENECK")
    print(f"  Total sweeps: {phase_seen['SWEEP']}")
    print(f"  Survived to displacement: {phase_seen['DISPLACE']} ({100*phase_seen['DISPLACE']/max(1,phase_seen['SWEEP']):.1f}%)")
    print(f"  Survived to BOS: {phase_seen['BOS']}")
    print(f"  Survived to ENTRY: {phase_seen['ENTRY']}")

    # Analyze why displacement fails
    # Count LTF displacement candles
    disp_bull = int(ltf_df["displacement_bullish"].sum()) if "displacement_bullish" in ltf_df.columns else 0
    disp_bear = int(ltf_df["displacement_bearish"].sum()) if "displacement_bearish" in ltf_df.columns else 0
    print(f"\n  LTF displacement candles: bullish={disp_bull}, bearish={disp_bear}")
    print(f"  Total LTF bars: {len(ltf_df)}")
    print(f"  Displacement rate: {(disp_bull+disp_bear)/len(ltf_df)*100:.1f}%")

    # ── DIAGNOSTIC 3: Full pipeline survival ───────────────────────────
    print(f"\n[DIAG 3] FULL PIPELINE SURVIVAL TABLE (EURUSD {htf}->{ltf})")
    print(f"  {'Stage':<45} {'Count':>8} {'Pct':>8}")
    print(f"  {'-'*61}")
    total_bars = len(ltf_df)
    print(f"  {'Total LTF bars':<45} {total_bars:>8} {'100.0%':>8}")

    # HTF RANGING bars (instant kill in sequence engine)
    ranging_count = sum(1 for i in range(len(ltf_df)) if est_htf_fn(i)["trend"] == "RANGING")
    print(f"  {'HTF = RANGING (skipped by sequence)':<45} {ranging_count:>8} {100*ranging_count/total_bars:>7.1f}%")

    non_ranging = total_bars - ranging_count
    print(f"  {'HTF has trend (sequence proceeds)':<45} {non_ranging:>8} {100*non_ranging/total_bars:>7.1f}%")
    print(f"  {'Sweeps detected':<45} {phase_seen['SWEEP']:>8} {100*phase_seen['SWEEP']/total_bars:>7.1f}%")
    print(f"  {'Displacements after sweep (within window)':<45} {phase_seen['DISPLACE']:>8} {100*phase_seen['DISPLACE']/total_bars:>7.1f}%")
    print(f"  {'BOS after displacement':<45} {phase_seen['BOS']:>8} {100*phase_seen['BOS']/total_bars:>7.1f}%")
    print(f"  {'Entry (price returns to zone)':<45} {phase_seen['ENTRY']:>8} {100*phase_seen['ENTRY']/total_bars:>7.1f}%")

    # Post-sequence killzone filter
    kz_killed = 0
    kz_pass = 0
    for s in raw_sigs:
        t = pd.to_datetime(s["time"], utc=True)
        kz = killzone_en(t)
        if kz in ("London Open", "New York AM", "New York PM"):
            kz_pass += 1
        else:
            kz_killed += 1
    print(f"  {'Killed by killzone filter':<45} {kz_killed:>8} {100*kz_killed/max(1,len(raw_sigs)):>7.1f}%")
    print(f"  {'FINAL SIGNALS':<45} {kz_pass:>8} {100*kz_pass/total_bars:>7.4f}%")

    # ── DIAGNOSTIC 4: Missing New York AM ─────────────────────────────
    print(f"\n[DIAG 4] NEW YORK AM GAP (H4 bar at 12:00 vs NY AM at 12.5)")
    print(f"  H4 bar at 12:00 UTC falls in killzone: '{killzone_en(pd.Timestamp('2024-01-01 12:00:00', tz='UTC'))}'")
    print(f"  NY AM starts at: {KILLZONES_UTC['New York AM'][0]} UTC ({KILLZONES_UTC['New York AM'][0]*60:.0f} min)")
    print(f"  H4 bar at 12:00 = {12*60} min UTC")
    print(f"  Gap: {KILLZONES_UTC['New York AM'][0]*60 - 12*60:.0f} minutes = the bar MISSES NY AM by 30 min")
    print(f"  This means 1/6 of H4 bars (16.7%) that COULD be in NY AM are instead 'NONE'")

    # ── DIAGNOSTIC 5: Available vs Required killzone coverage ──────────
    print(f"\n[DIAG 5] KILLZONE COVERAGE FOR H4 TIMEFRAME")
    valid_hours = []
    for h in range(24):
        fake_ts = pd.Timestamp(f"2024-01-01 {h:02d}:00:00", tz="UTC")
        kz = killzone_en(fake_ts)
        if kz in ("London Open", "New York AM", "New York PM"):
            valid_hours.append(h)
    print(f"  Valid H4 bar hours for killzone: {valid_hours}")
    print(f"  H4 bar hours: [0, 4, 8, 12, 16, 20]")
    matching = [h for h in [0, 4, 8, 12, 16, 20] if h in valid_hours]
    print(f"  Matching hours: {matching}")
    print(f"  Coverage: {len(matching)}/6 = {len(matching)/6*100:.0f}% of H4 bars can pass killzone")
    print(f"  *** THEORETICAL MAXIMUM SIGNALS = {len(matching)/6*100:.0f}% of sequence signals ***")


if __name__ == "__main__":
    for sym in ["EURUSD", "GBPUSD", "XAUUSD"]:
        try:
            deep_diagnostic(sym, htf="D1", ltf="H4")
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
