"""Lab comparativo: H4->M5 vs H4->H1->M5 (no modifica runner ni motor)."""
from __future__ import annotations

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from collections import defaultdict

import pandas as pd

ROOT = Path(r"C:\Users\v_jac\Desktop\SMC-SYSTEMS")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest.dealing_range import classify_zone
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks

SYMBOL = "EURUSD"
HTF = "H4"
ITF = "H1"
LTF = "M5"
MAX_BARS = 8000

OUT_PATH = ROOT / "backtest/evidence/lab_itf_bridge_EURUSD.jsonl"


def _load(symbol: str, tf: str) -> pd.DataFrame | None:
    p = ROOT / "data/raw" / f"{symbol}_{tf}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    if tf == LTF:
        df = df.tail(MAX_BARS).reset_index(drop=True)
    return df


def _est_htf(ltf_df: pd.DataFrame, htf_df: pd.DataFrame, htf: str):
    def fn(i: int) -> dict:
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }
    return fn


def _attach_fvg_ob(ltf_df: pd.DataFrame) -> pd.DataFrame:
    ob = detect_order_blocks(ltf_df)
    ltf_df["ob_bullish"] = ob["ob_bullish"].values
    ltf_df["ob_bearish"] = ob["ob_bearish"].values
    ltf_df["ob_direction"] = "-"
    ltf_df.loc[ltf_df["ob_bullish"], "ob_direction"] = "bullish"
    ltf_df.loc[ltf_df["ob_bearish"], "ob_direction"] = "bearish"

    fvg = detect_fvg(ltf_df)
    ltf_df["fvg_bullish"] = fvg["fvg_bullish"].values
    ltf_df["fvg_bearish"] = fvg["fvg_bearish"].values
    return ltf_df


def _zone_source_from_signal(sig: dict, itf_present: bool) -> str:
    pd_type = sig.get("zone_pd_type") or "NONE"
    if pd_type != "NONE":
        return "ITF" if itf_present else "LTF"
    # fallback logic after 3cd838a is hidden inside sequence; mark best-effort
    return "DEALING_RANGE_EQ_OR_BOS_FALLBACK"


def run_experiment(name: str, *, itf_df: pd.DataFrame | None, itf_tf: str | None):
    frames = {HTF: ms[HTF], LTF: ms[LTF].copy()}
    if itf_df is not None:
        frames[itf_tf] = ms[itf_tf]

    est_htf_fn = _est_htf(frames[LTF], frames[HTF], HTF)
    cfg = SequenceConfig(
        counter_trend=False,
        tp_mode="fixed2r",
        require_displacement=True,
        displace_gap=6,
        bos_gap=40,
    )

    sigs, phases = run_sequence(
        frames[LTF],
        est_htf_fn,
        cfg,
        ltf_tf=LTF,
        itf_df=itf_df,
        itf_tf=itf_tf,
    )

    rows = []
    for s in sigs:
        rows.append({
            "experiment": name,
            "time": str(s.get("time")),
            "direction": int(s.get("direction", 0)),
            "entry": float(s.get("entry", float("nan"))),
            "bos_level": float(s.get("bos_level", float("nan"))),
            "zone_source": _zone_source_from_signal(s, itf_df is not None),
            "htf_aligned": bool(s.get("htf_aligned", True)),
            "htf_reason": str(s.get("htf_reason", "")),
            "zone_pd_type": str(s.get("zone_pd_type", "NONE")),
            "zone_dealing_side_ok": s.get("zone_dealing_side_ok"),
            "zone_stack_ok": s.get("zone_stack_ok"),
            "tf_level_hint": "ITF" if (itf_df is not None and (s.get("zone_pd_type") or "NONE") != "NONE") else "LTF/EQ",
        })
    return rows, phases, sigs


# Load base frames
print(f"[lab] Loading {SYMBOL} {HTF}/{ITF}/{LTF} ...")
frames_raw = {HTF: _load(SYMBOL, HTF), ITF: _load(SYMBOL, ITF), LTF: _load(SYMBOL, LTF)}
for tf, df in frames_raw.items():
    if df is None or df.empty:
        raise SystemExit(f"Missing {tf} frame")

# Detect structure and attach detectors
ms = {tf: detect_market_structure(df.copy()) for tf, df in frames_raw.items()}
ms[LTF] = _attach_fvg_ob(ms[LTF])

print(f"[lab] Bars: {HTF}={len(ms[HTF])}, {ITF}={len(ms[ITF])}, {LTF}={len(ms[LTF])}")

# Experiment A: H4->M5
print("\n[lab] Experiment A: H4->M5")
rows_a, phases_a, sigs_a = run_experiment("A_H4_M5", itf_df=None, itf_tf=None)

# Experiment B: H4->H1->M5
print("[lab] Experiment B: H4->H1->M5")
rows_b, phases_b, sigs_b = run_experiment("B_H4_H1_M5", itf_df=ms[ITF], itf_tf=ITF)

# Summary
all_rows = rows_a + rows_b
pd.DataFrame(all_rows).to_json(OUT_PATH, orient="records", lines=True, force_ascii=False)

print("\n" + "="*80)
print("  COMPARATIVE SUMMARY")
print("="*80)
print(f"  {'Metric':<40} {'A (H4->M5)':>12} {'B (H4->H1->M5)':>16}")
print(f"  {'-'*69}")
print(f"  {'SWEEP':<40} {phases_a.get('SWEEP',0):>12} {phases_b.get('SWEEP',0):>16}")
print(f"  {'DISPLACE':<40} {phases_a.get('DISPLACE',0):>12} {phases_b.get('DISPLACE',0):>16}")
print(f"  {'BOS':<40} {phases_a.get('BOS',0):>12} {phases_b.get('BOS',0):>16}")
print(f"  {'ENTRY':<40} {len(rows_a):>12} {len(rows_b):>16}")
print(f"  {'delta_entries':<40} {'+0':>12} {'+' + str(len(rows_b)-len(rows_a)):>16}")
print()

# Per-entry source breakdown
from collections import Counter
src_a = Counter(r["zone_source"] for r in rows_a)
src_b = Counter(r["zone_source"] for r in rows_b)

print("  Zone source breakdown")
print(f"  {'Source':<36} {'A':>8} {'B':>10}")
print(f"  {'-'*55}")
for src in sorted(set(list(src_a) + list(src_b))):
    print(f"  {src:<36} {src_a.get(src,0):>8} {src_b.get(src,0):>10}")

# Show recovered entries detail if any
if len(rows_b) > len(rows_a):
    print("\n  Recovered entries (B - A):")
    sig_times_a = {r["time"] for r in rows_a}
    for r in rows_b:
        if r["time"] not in sig_times_a:
            print(f"    {r['time']} dir={r['direction']:+d} entry={r['entry']} zone_source={r['zone_source']} tf_hint={r['tf_level_hint']}")
else:
    print("\n  No recovered entries with current params.")

print(f"\n[lab] Wrote {OUT_PATH}")
