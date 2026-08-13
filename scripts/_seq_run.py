import pandas as pd, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.canonical import evaluate_signals

print("START (ventana reciente, lectura eficiente)", flush=True)
DATA = ROOT / "data" / "raw"
COLS = ["time", "open", "high", "low", "close"]
# Ventana reciente por TF: leemos TODO pero nos quedamos el tail (M1 es grande).
# Para M1 usamos solo las ultimas 5000 para no tragar 1.66M filas.
WIN = {"D1": 80, "H4": 160, "H1": 320, "M15": 600, "M5": 1200, "M1": 5000}
frames = {}
for tf, n in WIN.items():
    df = pd.read_parquet(DATA / f"EURUSD_{tf}.parquet")
    df = df[COLS].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.sort_values("time").reset_index(drop=True)
    frames[tf] = df.iloc[-n:].reset_index(drop=True)
print({tf: len(df) for tf, df in frames.items()}, flush=True)

sigs = evaluate_signals("EURUSD", "H4", "M15", counter_trend=False,
                        enable_pd_index=True, exec_tf=None, frames=frames)
print("TOTAL_SEÑALES", len(sigs), flush=True)
for s in sigs[-5:]:
    rr = round(abs(s.take_profit - s.entry) / abs(s.entry - s.stop_loss), 2)
    print(json.dumps({
        "time": str(s.time),
        "side": "LONG" if s.direction == 1 else "SHORT",
        "entry": round(float(s.entry), 5),
        "sl": round(float(s.stop_loss), 5),
        "tp": round(float(s.take_profit), 5),
        "rr": rr,
        "anchored": bool(s.htf_anchored),
        "zone": s.zone_class,
    }), flush=True)
print("DONE", flush=True)
