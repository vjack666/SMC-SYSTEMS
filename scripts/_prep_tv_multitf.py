"""scripts/_prep_tv_multitf.py — prepara datos MULTI-TF para los 10 escenarios.

Por cada setup: ventanas D1/H4/H1/M15/M5 alrededor del timestamp + marcas del
motor en cada TF (sesgo en HTF, estructura BOS/CHOCH en M15/M5, POI/entry en M15).
Guarda results/tv_scenarios_multitf.json para que los agentes dibujen estilo
TradingView multi-panel (como cambiar de TF).

Optimizado: estructura M15/M5 precalc UNA vez; sesgo HTF cacheado por indice.
"""
import json, os
import pandas as pd
from engine.data_feed import load_frames
from engine.bias.narrative import compute_htf_bias
from engine.bos.structure import StructureConfig, detect_market_structure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
TF_CHAIN = ("D1", "H4", "H1", "M15", "M5")

# Usar los 10 primeros setups de WM=3 (25 disponibles)
d = json.load(open(os.path.join(RESULTS, "funnel_authority_filter.json")))
det = d["detalle"][:10]
ms = load_frames("EURUSD", timeframes=TF_CHAIN)
frames = {tf: ms[tf].copy() for tf in TF_CHAIN}
times = {tf: pd.to_datetime(frames[tf]["time"], utc=True, errors="coerce") for tf in TF_CHAIN}


def window(tf, t, before, after):
    idx = int((times[tf] <= t).sum() - 1)
    lo = max(0, idx - before)
    hi = min(len(frames[tf]), idx + after)
    win = frames[tf].iloc[lo:hi]
    candles = [[str(pd.Timestamp(r["time"])), round(float(r["open"]), 5),
               round(float(r["high"]), 5), round(float(r["low"]), 5),
               round(float(r["close"]), 5)] for _, r in win.iterrows()]
    return candles, idx - lo


# Precalcular estructura M15 y M5 UNA vez (gate duro)
fr15_full = detect_market_structure(frames["M15"], StructureConfig(exp012_choch=True)).frame
fr5_full = detect_market_structure(frames["M5"], StructureConfig(exp012_choch=True)).frame
t15, t5 = times["M15"], times["M5"]
bias_cache = {}


def get_bias(d1_i, h4_i, h1_i):
    key = (d1_i, h4_i, h1_i)
    if key not in bias_cache:
        bias_cache[key] = compute_htf_bias(frames["D1"].iloc[:d1_i],
                                           frames["H4"].iloc[:h4_i],
                                           frames["H1"].iloc[:h1_i])
    return bias_cache[key]


scenarios = []
for i, entry in enumerate(det, 1):
    ts_str = entry[0]
    lvl = entry[1]
    px_entry, sl, tp = entry[5], entry[6], entry[7]
    t = pd.Timestamp(ts_str)

    d1_i = int((times["D1"] <= t).sum())
    h4_i = int((times["H4"] <= t).sum())
    h1_i = int((times["H1"] <= t).sum())
    bias = get_bias(d1_i, h4_i, h1_i)

    i15 = int((t15 <= t).sum())
    i5 = int((t5 <= t).sum())
    m15_choch = int((fr15_full["choch_dir"].iloc[:i15] != 0).sum())
    m5_choch = int((fr5_full["choch_dir"].iloc[:i5] != 0).sum())

    c1, i1 = window("D1", t, 30, 5)
    c4, i4 = window("H4", t, 40, 8)
    c_h1, i_h1 = window("H1", t, 50, 10)
    c15, i15w = window("M15", t, 40, 15)
    c5, i5w = window("M5", t, 120, 40)
    panels = {
        "D1":  {"candles": c1,  "entry_idx": i1,   "role": "SESGO (direccion general)"},
        "H4":  {"candles": c4,  "entry_idx": i4,   "role": "SESGO (contexto)"},
        "H1":  {"candles": c_h1,"entry_idx": i_h1, "role": "SESGO (contexto)"},
        "M15": {"candles": c15, "entry_idx": i15w, "role": "ESTRUCTURA + POI (donde rompio)"},
        "M5":  {"candles": c5,  "entry_idx": i5w,  "role": "EJECUCION (donde entro)"},
    }
    scenarios.append({
        "n": i, "ts": ts_str, "lvl": lvl,
        "entry": px_entry, "sl": sl, "tp": tp,
        "bias_dir": bias.direction if bias else "n/a",
        "bias_aligned": bool(bias.aligned) if bias else False,
        "m15_choch_censurado": m15_choch,
        "m5_choch_censurado": m5_choch,
        "panels": panels,
    })

out = os.path.join(RESULTS, "tv_scenarios_multitf.json")
with open(out, "w") as f:
    json.dump(scenarios, f, indent=2)
print(f"[prep-multitf] {len(scenarios)} escenarios multi-TF -> {out}")
