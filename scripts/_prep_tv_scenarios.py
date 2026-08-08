"""scripts/_prep_tv_scenarios.py — extrae ventanas M15 para los 10 setups y las
guarda en results/tv_scenarios.json para que los agentes dibujen estilo TradingView.
Solo prepara datos (no dibuja)."""
import json, os
import pandas as pd
from engine.data_feed import load_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")

# Cargar setups del JSON de auditoria (WM=1, 10 setups con precios)
d = json.load(open(os.path.join(RESULTS, "funnel_authority_filter.json")))
det = d["detalle"]
ms = load_frames("EURUSD", timeframes=("M15",))
m15 = ms["M15"].copy()
m15_t = pd.to_datetime(m15["time"], utc=True, errors="coerce")

scenarios = []
for i, entry in enumerate(det, 1):
    ts_str = entry[0]
    lvl = entry[1]
    conf = entry[2]
    tier = entry[3]
    px_entry = entry[5]
    sl = entry[6]
    tp = entry[7]
    t = pd.Timestamp(ts_str)
    # Indice de la vela M15 del setup
    idx = int((m15_t <= t).sum() - 1)
    lo = max(0, idx - 40)
    hi = min(len(m15), idx + 15)
    win = m15.iloc[lo:hi]
    # Serializar velas como lista de [time, open, high, low, close]
    candles = []
    for _, r in win.iterrows():
        candles.append([
            str(pd.Timestamp(r["time"])),
            round(float(r["open"]), 5),
            round(float(r["high"]), 5),
            round(float(r["low"]), 5),
            round(float(r["close"]), 5),
        ])
    scenarios.append({
        "n": i,
        "ts": ts_str,
        "lvl": lvl,
        "conf": conf,
        "tier": tier,
        "entry": px_entry,
        "sl": sl,
        "tp": tp,
        "entry_idx_in_candles": int(idx - lo),
        "candles": candles,
    })

out = os.path.join(RESULTS, "tv_scenarios.json")
with open(out, "w") as f:
    json.dump(scenarios, f, indent=2)
print(f"[prep] {len(scenarios)} escenarios -> {out}")
print(f"[prep] velas por escenario: ~{len(scenarios[0]['candles'])}")
