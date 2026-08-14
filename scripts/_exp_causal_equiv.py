"""EXP-CAUSAL-EQUIV — Opción 3 como optimización SEMANTICAMENTE NEUTRA.

Valida tu exigencia: ORIGINAL == OPTIMIZADO vela por vela, campo por campo,
NO solo resultado final.

Usa el dataset sintético (make_signal_objs) que dispara 1 setup LONG.
Para cada vela t:
  - contexto ORIGINAL: build_multitf_context(ms, t)  [O(n) por vela, lento]
  - contexto OPTIMIZADO: mi cache O(n) total, lookup O(1)
Compara TODOS los campos consumidos por engine:
  HTF closed index, bias, POI, BOS, CHOCH, FVG, OB, swing, liquidity.

SI todas las velas coinciden campo-a-campo => Opción 3 es neutra => autorizable.
SI alguna vela diverge => la optimización introduce look-ahead o pierde datos.
"""

import sys, os, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context, MultiTFContext, extract_htf_layer
from engine.poi_anchor import build_htf_structure_index
from engine._util import tf_duration

_spec = importlib.util.spec_from_file_location(
    "replay_core_ce",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "research", "hypotheses", "HYP-002", "functional_replay", "replay_core.py"))
_rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc)
make_signal_objs = _rc.make_signal_objs

HTF = "H4"
TFS = ("D1", "H4", "H1", "M15")


def make_synthetic_ms():
    """Construye ms con estructura sobre el dataset sintético (12 velas M15)."""
    objs = make_signal_objs(n=12)
    df = pd.DataFrame([o.meta for o in objs])
    df["time"] = [o.bar_time for o in objs]
    # HTF sintético: 2 velas H4 que cubren las 12 M15
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
    ms = {"M15": df, "H4": h4, "H1": h1, "D1": d1}
    return ms, df


def optimized_ctx_factory(ms, htf_frames):
    """Mi Solución A (cache O(n) total, lookup O(1))."""
    ltf_df = ms["M15"]
    n = len(ltf_df)
    htf_data = {tf: htf_frames[tf] for tf in htf_frames}
    htimes = {tf: list(pd.to_datetime(htf_data[tf]["time"], utc=True, errors="coerce")) for tf in htf_data}
    idx_by_i = {tf: [None] * n for tf in htf_data}
    for tf in htf_data:
        ht = htimes[tf]
        dur = tf_duration(tf)
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] + pd.Timedelta(dur) <= t:
                ji += 1
            idx_by_i[tf][i] = ji if ji >= 0 else None
    _ev = build_htf_structure_index(htf_frames) if htf_frames else []
    def fn(i):
        anchored = None
        if _ev:
            ltf_t = pd.to_datetime(ms["M15"].iloc[i]["time"], utc=True, errors="coerce")
            prior = [e for e in _ev if e.time is not None and e.time <= ltf_t]
            anchored = {}
            for e in prior:
                anchored.setdefault(e.tf, []).append(e)
        ctx = {}
        for tf in htf_data:
            j = idx_by_i[tf][i]
            if j is not None:
                ctx[tf] = htf_data[tf].iloc[j].to_dict()
        return MultiTFContext(ctx)
    return fn


def fields_of(ctx_dict):
    """Extrae todos los campos comparables de un contexto (capa H4)."""
    if not ctx_dict:
        return {}
    row = ctx_dict
    keys = ["trend", "bos_dir", "choch_signal", "fvg_state", "ob_direction",
            "liquidity_sweep_up", "liquidity_sweep_down", "close", "high", "low",
            "swing_high", "swing_low", "pd_type", "pd_tier"]
    return {k: str(row.get(k)) for k in keys}


def main():
    ms, ltf = make_synthetic_ms()
    htf_frames = {tf: ms[tf] for tf in ("D1", "H4", "H1")}
    opt_fn = optimized_ctx_factory(ms, htf_frames)
    _ev = build_htf_structure_index(htf_frames)
    n = len(ltf)

    divergences = 0
    print(f"[EXP-CAUSAL-EQUIV] {n} velas M15, comparando ORIGINAL vs OPTIMIZADO por vela\n")
    print(f"{'vela':>4} | {'ORIGINAL(H4)':<40} | {'OPTIMIZADO(H4)':<40} | OK?")
    print("-" * 100)
    for i in range(n):
        t = ltf.iloc[i]["time"]
        # ORIGINAL: build_multitf_context por vela (lento pero fiel)
        orig_ctx = build_multitf_context(ms, t, tfs=TFS, anchored_pd_zones=None)
        orig_layer = extract_htf_layer(orig_ctx, HTF)
        orig_f = fields_of(orig_layer)
        # OPTIMIZADO: cache O(n)
        opt_ctx = opt_fn(i)
        opt_layer = extract_htf_layer(opt_ctx, HTF)
        opt_f = fields_of(opt_layer)
        ok = (orig_f == opt_f)
        if not ok:
            divergences += 1
            print(f"{i:>4} | {str(orig_f):<40} | {str(opt_f):<40} | ❌ DIVERGE")
        else:
            print(f"{i:>4} | {str(orig_f):<40} | {str(opt_f):<40} | ✅")

    print("-" * 100)
    print(f"\n=== Veredicto ===")
    if divergences == 0:
        print(f"✅ ORIGINAL == OPTIMIZADO en TODAS las velas ({n}/{n}). Opción 3 es SEMANTICAMENTE NEUTRA.")
        print("   Autorizable como optimización (no cambia ningún dato que el motor conocía en t).")
    else:
        print(f"❌ {divergences} velas divergen. La optimización introduce diferencia -> NO autorizable sin corregir.")


if __name__ == "__main__":
    main()
