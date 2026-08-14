"""NIVEL 1 — Contexto ORIGINAL vs OPTIMIZADO (Opción 3, Change Gate).

Valida el invariante del Director: ORIGINAL(t) == OPTIMIZADO(t) para CADA vela.

- ORIGINAL: build_multitf_context(ms, t)  [sin closed_index, camino actual]
- OPTIMIZADO: build_multitf_context(ms, t, closed_index=idx_en_i)  [con índice
  precomputado O(n) total por el llamador, lookup O(1) por vela]

El llamador precompute idx_by_i[tf][i] con dos punteros (O(n) total) y pasa
closed_index={tf: idx_by_i[tf][i]} por vela. snapshot_tf usa df.iloc[idx].

Compara TODOS los campos de la capa H4 (trend, bos_dir, choch, fvg, ob, swing,
liquidity, pd) vela por vela. Si alguna diverge => INVALIDADO.
"""

import sys, os, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context, extract_htf_layer
from engine.poi_anchor import build_htf_structure_index
from engine._util import tf_duration

_spec = importlib.util.spec_from_file_location(
    "replay_core_n1",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "research", "hypotheses", "HYP-002", "functional_replay", "replay_core.py"))
_rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc)
make_signal_objs = _rc.make_signal_objs

HTF = "H4"
TFS = ("D1", "H4", "H1", "M15")


def make_synthetic_ms():
    objs = make_signal_objs(n=12)
    df = pd.DataFrame([o.meta for o in objs])
    df["time"] = [o.bar_time for o in objs]
    h4 = pd.DataFrame([
        {"time": objs[0].bar_time, "trend": "BULLISH", "bos_dir": 0, "choch_signal": "",
         "fvg_state": "NONE", "ob_direction": "-", "liquidity_sweep_up": False,
         "liquidity_sweep_down": False, "close": 1.10, "high": 1.11, "low": 1.09,
         "swing_high": 1.11, "swing_low": 1.09, "pd_type": None, "pd_tier": None},
        {"time": objs[6].bar_time, "trend": "BULLISH", "bos_dir": 0, "choch_signal": "",
         "fvg_state": "NONE", "ob_direction": "-", "liquidity_sweep_up": False,
         "liquidity_sweep_down": False, "close": 1.12, "high": 1.13, "low": 1.11,
         "swing_high": 1.13, "swing_low": 1.11, "pd_type": None, "pd_tier": None},
    ])
    d1 = h4.copy(); d1["time"] = objs[0].bar_time
    h1 = h4.copy()
    return {"M15": df, "H4": h4, "H1": h1, "D1": d1}, df


def precompute_closed_index(ms, htf_frames):
    """O(n) total: dos punteros por TF. Devuelve idx_by_i[tf][i]."""
    ltf_df = ms["M15"]
    n = len(ltf_df)
    idx_by_i = {}
    for tf in htf_frames:
        ht = list(pd.to_datetime(htf_frames[tf]["time"], utc=True, errors="coerce"))
        dur = tf_duration(tf)
        arr = [None] * n
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] + pd.Timedelta(dur) <= t:
                ji += 1
            arr[i] = ji if ji >= 0 else None
        idx_by_i[tf] = arr
    return idx_by_i


def fields_of(layer):
    if not layer:
        return {}
    keys = ["trend", "bos_dir", "choch_signal", "fvg_state", "ob_direction",
            "liquidity_sweep_up", "liquidity_sweep_down", "close", "high", "low",
            "swing_high", "swing_low", "pd_type", "pd_tier"]
    return {k: str(layer.get(k)) for k in keys}


def main():
    ms, ltf = make_synthetic_ms()
    htf_frames = {tf: ms[tf] for tf in ("D1", "H4", "H1")}
    idx_by_i = precompute_closed_index(ms, htf_frames)
    _ev = build_htf_structure_index(htf_frames)
    n = len(ltf)

    divergences = 0
    print(f"[NIVEL 1] {n} velas M15, ORIGINAL vs OPTIMIZADO(closed_index) por vela\n")
    print(f"{'vela':>4} | {'ORIGINAL(H4)':<34} | {'OPTIMIZADO(H4)':<34} | OK?")
    print("-" * 90)
    for i in range(n):
        t = ltf.iloc[i]["time"]
        # ORIGINAL (sin índice)
        orig = build_multitf_context(ms, t, tfs=TFS, anchored_pd_zones=None)
        orig_layer = extract_htf_layer(orig, HTF)
        # OPTIMIZADO (con índice precomputado)
        closed_index = {tf: idx_by_i[tf][i] for tf in htf_frames if idx_by_i[tf][i] is not None}
        opt = build_multitf_context(ms, t, tfs=TFS, anchored_pd_zones=None, closed_index=closed_index)
        opt_layer = extract_htf_layer(opt, HTF)
        of = fields_of(orig_layer)
        qf = fields_of(opt_layer)
        ok = (of == qf)
        if not ok:
            divergences += 1
            print(f"{i:>4} | {str(of):<34} | {str(qf):<34} | ❌")
        else:
            print(f"{i:>4} | {str(of):<34} | {str(qf):<34} | ✅")

    print("-" * 90)
    print("\n=== Veredicto Nivel 1 ===")
    if divergences == 0:
        print(f"✅ ORIGINAL == OPTIMIZADO en TODAS las velas ({n}/{n}). Opción 3 es SEMANTICAMENTE NEUTRA.")
        print("   Cumple invariante: mismo procesamiento de fila, solo lookup O(1) de índice.")
    else:
        print(f"❌ {divergences} velas divergen. INVALIDADO (no promote, investigar).")


if __name__ == "__main__":
    main()
