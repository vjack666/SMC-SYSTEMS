"""hermes-verify-funnel-authority-filter.py — filtro Alta sobre funnel (1m rapido).

CONSUME el motor: por cada ENTRY del funnel llama a engine.htf_narrative.
build_htf_narrative (MISMA fuente que el observador) y lee poi["authority"].
NO reconstruye autoridad a mano (Ley: consumir el motor, no reimplementar).
"""
import sys, time as _t, json
sys.path.insert(0, r"C:\Users\v_jac\Desktop\SMC-SYSTEMS")
import pandas as pd
from engine.data_feed import load_frames
from ict_backtest.canonical import evaluate_signals
from engine.htf_narrative import build_htf_narrative

SYMBOL, HTF, LTF = "EURUSD", "D1", "M15"
TF_CHAIN = ("D1", "H4", "H1", "M15")
WM = int(sys.argv[1]) if len(sys.argv) > 1 else 1

t0 = _t.time()
frames = load_frames(SYMBOL, TF_CHAIN)
last = pd.to_datetime(frames[LTF]["time"].iloc[-1], utc=True, errors="coerce")
start = last - pd.DateOffset(months=WM)
frames = {tf: df.loc[pd.to_datetime(df["time"], utc=True, errors="coerce") >= start].reset_index(drop=True)
          for tf, df in frames.items()}
print(f"[filt] frames {WM}m cargados ({len(frames[LTF])} M15). detectando...", flush=True)

res, phase_seen = evaluate_signals(SYMBOL, HTF, LTF, frames=frames,
                                   enable_pd_index=True, require_displacement=True,
                                   counter_trend=False, return_phase_seen=True)
signals = res if isinstance(res, list) else res.get("signals", []) or []
print(f"[filt] funnel: {phase_seen}  | setups ENTRY: {len(signals)}", flush=True)

htf_frames = {tf: frames[tf] for tf in ("D1", "H4", "H1")}
alta = media = baja = sin = 0
detalle = []
for n, s in enumerate(signals, 1):
    t = getattr(s, "time", None) or getattr(s, "entry_time", None) or getattr(s, "birth_time", None)
    direction = getattr(s, "direction", None) or getattr(s, "bias", None)
    dir_num = 1 if str(direction).upper().startswith("BULL") else (-1 if str(direction).upper().startswith("BEAR") else 0)
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    mask = pd.to_datetime(frames[LTF]["time"], utc=True, errors="coerce") <= tt
    if not mask.any():
        sin += 1
        detalle.append((str(tt), "sin-ventana"))
        continue
    i = int(mask.sum() - 1)
    ltf_win = frames[LTF].iloc[:i+1].reset_index(drop=True)
    narr = build_htf_narrative(ltf_win, htf_frames=htf_frames)
    auth = (narr.get("poi") or {}).get("authority")
    if auth is None:
        sin += 1
        detalle.append((str(tt), "sin-authority", narr.get("poi", {}).get("kind")))
    else:
        lvl = auth.get("level")
        if lvl == "Alta":
            alta += 1
        elif lvl == "Media":
            media += 1
        else:
            baja += 1
        # Precio de referencia: nivel POI/ENTRY del setup (ICTSignal).
        entry = getattr(s, "entry", None)
        sl = getattr(s, "stop_loss", None)
        tp = getattr(s, "take_profit", None)
        detalle.append((
            str(tt), lvl, round(auth.get("confidence_weight", 0), 3), auth.get("tier"), auth.get("stacking_level"),
            round(float(entry), 5) if entry is not None else None,
            round(float(sl), 5) if sl is not None else None,
            round(float(tp), 5) if tp is not None else None,
        ))

print(f"\n[filt] ---- SETUPS COMPLETOS POR NIVEL DE AUTORIDAD HTF ({WM}m) ----", flush=True)
print(f"  Alta : {alta}", flush=True)
print(f"  Media: {media}", flush=True)
print(f"  Baja : {baja}", flush=True)
print(f"  sin_authority: {sin}", flush=True)
tot = len(signals)
print(f"[filt] TOTAL: {tot}  |  Alta = {100*alta/max(tot,1):.1f}%  |  Alta+Media = {100*(alta+media)/max(tot,1):.1f}%", flush=True)
print("[filt] detalle:", flush=True)
for d in detalle:
    print("   ", d, flush=True)
print(f"[filt] listo en {_t.time()-t0:.1f}s", flush=True)

# Volcado a JSON para lectura robusta (no depender del buffer del wrapper).
import json as _json
with open("results/funnel_authority_filter.json", "w") as _fh:
    _json.dump({
        "window_months": WM, "funnel": phase_seen, "total": tot,
        "alta": alta, "media": media, "baja": baja, "sin_authority": sin,
        "pct_alta": round(100*alta/max(tot,1), 1),
        "pct_alta_media": round(100*(alta+media)/max(tot,1), 1),
        "detalle": [list(d) for d in detalle],
    }, _fh, indent=2)
print("[filt] JSON escrito en results/funnel_authority_filter.json", flush=True)
