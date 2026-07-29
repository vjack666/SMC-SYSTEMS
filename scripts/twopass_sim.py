"""Script: two-pass simulación sobre parquet EURUSD M15+M5.

Modo_NO-BLOCKING: imprime tabla comparativa y nada más. No rompe imports.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ict_backtest.data_feed import build_features, build_objects
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.canonical import evaluate_signals

# ---------------------------------------------------------------------------
# 1. Load last 90 days for speed
# ---------------------------------------------------------------------------
RAW = Path("data/raw")
SYMBOL = "EURUSD"
m15 = pd.read_parquet(RAW / f"{SYMBOL}_M15.parquet")
m5 = pd.read_parquet(RAW / f"{SYMBOL}_M5.parquet")
m15["time"] = pd.to_datetime(m15["time"], utc=True)
m5["time"] = pd.to_datetime(m5["time"], utc=True)
cut = m15["time"].max() - pd.Timedelta(days=90)
m15 = m15[m15["time"] >= cut].reset_index(drop=True)
m5 = m5[m5["time"] >= cut].reset_index(drop=True)

# 2. Features + structure
m15_f = build_features(m15)
m15_ms = detect_market_structure(m15_f)
h4 = build_features(m5)
h4_ms = detect_market_structure(h4)

frames = {"D1": m15_f, "H4": h4, "H1": m15_f, "M15": m15_f}

# 3. Warm-up build_objects for M5 once (heavy)
from ict_backtest.data_feed import build_objects as _build_objects
_exec_objs_fast = _build_objects({"M5": m5})
print(f"Loaded {len(m15)} M15 / {len(m5)} M5 bars, exec objects {len(_exec_objs_fast)}")

# ---------------------------------------------------------------------------
# 4. Run canonical with two-pass variants
# ---------------------------------------------------------------------------
results = {}
for preset in ("fallback", "strict", "medium", "loose"):
    t0 = time.time()
    sigs = evaluate_signals(
        SYMBOL,
        htf="H4",
        ltf="M15",
        frames=frames,
        enable_pd_index=True,
        exec_tf="M5" if preset != "fallback" else None,
        use_semantic=True,
    )
    dt = time.time() - t0
    c = {k: 0 for k in (0, 1, 2, 3)}
    for s in sigs: c[getattr(s, "exec_m5_score", 0)] += 1
    results[preset] = {
        "signals_total": len(sigs),
        "score_0": c[0], "score_1": c[1], "score_2": c[2], "score_3": c[3],
        "elapsed_s": round(dt, 3),
    }

# ---------------------------------------------------------------------------
# 5. Print compact table for human interpretation
# ---------------------------------------------------------------------------
rows = []
for preset in ("fallback", "strict", "medium", "loose"):
    r = results[preset]
    rows.append(
        f"{preset:9} | signals={r['signals_total']:4} | "
        f"0:{r['score_0']} 1:{r['score_1']} 2:{r['score_2']} 3:{r['score_3']} | {r['elapsed_s']}s"
    )
print("\nTwo-pass EURUSD M15->M5 preset scan (last 90d):")
print("\n".join(rows))
print("\nfallback = M15 only")
print("strict   = score == 3")
print("medium   = score >= 1")
print("loose    = no score filter")
