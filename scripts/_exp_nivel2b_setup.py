"""NIVEL 2b — Equivalencia BATCH vs STEP(i) CON setups (dataset sintético).

Valida que step(i) produce los MISMOS setups (con lineage/indices) que batch
cuando hay eventos. Usa make_signal_objs (dispara 1 setup LONG en vela ~9).

Compara por senal: direction, sweep_at, displace_at, bos_at, entry_at, event_ids.
"""

import sys, os, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig, run_sequence_traced, SequenceRunner, _candle_objects
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context

_spec = importlib.util.spec_from_file_location(
    "replay_core_n2",
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


def ctx_fn_factory(ms, htf_frames):
    ltf_df = ms["M15"]
    n = len(ltf_df)
    idx_by_i = {}
    for tf in htf_frames:
        ht = list(pd.to_datetime(htf_frames[tf]["time"], utc=True, errors="coerce"))
        arr = [None] * n
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] <= t:
                ji += 1
            arr[i] = ji if ji >= 0 else None
        idx_by_i[tf] = arr
    def fn(i):
        t = ms["M15"].iloc[i]["time"]
        ci = {tf: idx_by_i[tf][i] for tf in htf_frames if idx_by_i[tf][i] is not None}
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1"),
                                      anchored_pd_zones=None, closed_index=ci)
    return fn


def main():
    ms, ltf = make_synthetic_ms()
    htf_frames = {tf: ms[tf] for tf in ("D1", "H4", "H1")}
    ctx_fn = ctx_fn_factory(ms, htf_frames)
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)

    # BATCH
    sigs_batch, phase_batch, _, _ = run_sequence_traced(
        ltf, None, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    print(f"[BATCH] setups={len(sigs_batch)} funnel={dict(phase_batch)}")

    # STREAM
    objs = _candle_objects(ltf, "M15")
    runner = SequenceRunner(objs, ctx_fn, cfg, ltf_tf="M15", htf="H4")
    for i in range(1, len(ltf)):
        runner.step(i)
    sigs_stream = runner.signals
    print(f"[STREAM] setups={len(sigs_stream)} funnel={dict(runner.phase_seen)}")

    print("\n=== Veredicto Nivel 2b (CON setups) ===")
    if len(sigs_batch) != len(sigs_stream):
        print(f"❌ DIVERGEN: BATCH={len(sigs_batch)} STREAM={len(sigs_stream)}")
        return
    ok = True
    for k, (b, s) in enumerate(zip(sigs_batch, sigs_stream)):
        for fld in ("direction", "sweep_at", "displace_at", "bos_at", "entry_at"):
            if b.get(fld) != s.get(fld):
                print(f"❌ senal {k} {fld}: BATCH={b.get(fld)} STREAM={s.get(fld)}")
                ok = False
        # event_ids: los UUID son efimeros (trazabilidad), no semantica. Solo
        # validamos que las CLAVES del lineage existan y la ESTRUCTURA coincida.
        b_ids = b.get("event_ids") or {}
        s_ids = s.get("event_ids") or {}
        if set(b_ids.keys()) != set(s_ids.keys()):
            print(f"❌ senal {k} event_ids keys divergen: {set(b_ids)} vs {set(s_ids)}")
            ok = False
    if ok:
        print(f"✅ BATCH == STREAM en {len(sigs_batch)} setups. Mismos indices "
              f"(sweep_at/displace_at/bos_at/entry_at/direction).")
        print("   Los event_ids UUID difieren (efimeros por corrida) pero la")
        print("   SEMANTICA CAUSAL es identica: misma vela, misma secuencia.")
        print("   Opción B cumple: step(i) == batch en comportamiento observable.")


if __name__ == "__main__":
    main()
