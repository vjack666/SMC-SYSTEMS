"""Diagnóstico mínimo: entradas perdidas al activar ITF H1."""
from __future__ import annotations

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Users\v_jac\Desktop\SMC-SYSTEMS")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.sequence import (
    run_sequence,
    SequenceConfig,
    _candle_objects,
    _latest_fvg_zone,
    _latest_ob_zone,
)
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks

SYMBOL = "EURUSD"
HTF = "H4"
ITF = "H1"
LTF = "M5"
MAX_BARS = 8000


def load(tf: str) -> pd.DataFrame:
    p = ROOT / "data/raw" / f"{SYMBOL}_{tf}.parquet"
    df = pd.read_parquet(p)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    if tf == LTF:
        df = df.tail(MAX_BARS).reset_index(drop=True)
    return df


print("[diag] loading frames...")
frames = {tf: load(tf) for tf in [HTF, ITF, LTF]}
ms = {tf: detect_market_structure(df.copy()) for tf, df in frames.items()}

ltf = frames[LTF]
ob = detect_order_blocks(ltf)
ltf["ob_bullish"] = ob["ob_bullish"].values
ltf["ob_bearish"] = ob["ob_bearish"].values
ltf["ob_direction"] = "-"
ltf.loc[ltf["ob_bullish"], "ob_direction"] = "bullish"
ltf.loc[ltf["ob_bearish"], "ob_direction"] = "bearish"
fvg = detect_fvg(ltf)
ltf["fvg_bullish"] = fvg["fvg_bullish"].values
ltf["fvg_bearish"] = fvg["fvg_bearish"].values
ms[LTF] = detect_market_structure(ltf)


def est(i: int) -> dict:
    t = ltf.iloc[i]["time"]
    r = closed_row_at_time(frames[HTF], t, tf_duration(HTF))
    return {
        "trend": str(r.get("trend", "RANGING")),
        "sweep_up": bool(r.get("liquidity_sweep_up", False)),
        "sweep_down": bool(r.get("liquidity_sweep_down", False)),
    }


cfg = SequenceConfig(
    counter_trend=False,
    tp_mode="fixed2r",
    require_displacement=True,
    displace_gap=6,
    bos_gap=40,
)

print("[diag] running A/B...")
a, _ = run_sequence(ltf, est, cfg, ltf_tf=LTF, itf_df=None, itf_tf=None)
b, _ = run_sequence(ltf, est, cfg, ltf_tf=LTF, itf_df=frames[ITF], itf_tf=ITF)

lost = [s for s in a if s["time"] not in {x["time"] for x in b}]
print(f"A={len(a)} B={len(b)} lost={len(lost)}")

if not lost:
    raise SystemExit(0)

itf_objs = _candle_objects(frames[ITF], ITF)
itf_dur = tf_duration(ITF)
itf_times = pd.to_datetime(frames[ITF]["time"], utc=True, errors="coerce")

# O(1) mapping: closest ITF closed bar at or before LTF time - ITF duration
ltf_to_itf = {}
ltf_times = pd.to_datetime(ltf["time"], utc=True, errors="coerce")
for i in range(len(ltf)):
    t = ltf_times.iloc[i]
    cutoff = t - pd.Timedelta(itf_dur)
    matches = itf_times[itf_times <= cutoff]
    ltf_to_itf[i] = int(matches.index[-1]) if len(matches) > 0 else 0

eq = (float(frames[ITF]["high"].max()) + float(frames[ITF]["low"].min())) / 2.0
rng = float(frames[ITF]["high"].max() - frames[ITF]["low"].min())
lo, hi = eq - 0.3 * rng, eq + 0.3 * rng


def _check_zone(objs, idx, direction):
    if idx < 0 or idx >= len(objs):
        return None, None
    return _latest_fvg_zone(objs[idx], direction), _latest_ob_zone(objs[idx], direction)


for s in lost:
    idx = s["entry_at"]
    direction = s["direction"]
    entry = s["entry"]
    i0 = ltf_to_itf.get(idx, 0)
    i1 = max(0, i0 - 1)
    i2 = min(len(frames[ITF]) - 1, i0 + 1)

    fvg0, ob0 = _check_zone(itf_objs, i0, direction)
    fvg1, ob1 = _check_zone(itf_objs, i1, direction)
    fvg2, ob2 = _check_zone(itf_objs, i2, direction)

    def _has(zone):
        return zone is not None and not (isinstance(zone[0], float) and zone[0] != zone[0])

    itf_has = _has(fvg0) or _has(ob0) or _has(fvg1) or _has(ob1) or _has(fvg2) or _has(ob2)
    in_eq = lo <= entry <= hi

    t0 = frames[ITF].iloc[i0]["time"] if i0 < len(frames[ITF]) else "OOB"
    t1 = frames[ITF].iloc[i1]["time"] if i1 < len(frames[ITF]) else "OOB"
    t2 = frames[ITF].iloc[i2]["time"] if i2 < len(frames[ITF]) else "OOB"

    print(f"\nENTRY {s['time']} dir={direction} entry={entry}")
    print(f"  ITF idx0={i0} time={t0} FVG={fvg0} OB={ob0}")
    print(f"  ITF idx-1={i1} time={t1} FVG={fvg1} OB={ob1}")
    print(f"  ITF idx+1={i2} time={t2} FVG={fvg2} OB={ob2}")
    print(f"  ITF EQ±0.3rng {round(lo,5)}-{round(hi,5)} in_eq={in_eq}")

    if itf_has:
        verdict = "MAPEO"
    elif in_eq:
        verdict = "ZONA_EQ"
    else:
        verdict = "DETECCION"
    print(f"  VERDICT: {verdict}")

from collections import Counter
c = Counter(
    (
        "MAPEO"
        if _has(_check_zone(itf_objs, ltf_to_itf.get(s["entry_at"], 0), s["direction"])[0])
        or _has(_check_zone(itf_objs, ltf_to_itj := max(0, ltf_to_itf.get(s["entry_at"], 0) - 1), s["direction"])[0])
        or _has(_check_zone(itf_objs, min(len(frames[ITF]) - 1, ltf_to_itf.get(s["entry_at"], 0) + 1), s["direction"])[0])
        else "ZONA_EQ"
        if lo <= s["entry"] <= hi
        else "DETECCION"
    )
    for s in lost
)
print("\n=== SUMMARY ===")
for k, n in c.items():
    print(f"{n}/{len(lost)} {k}")
