"""FASE A LIGERO — runner semantico con telemetria viva (consumidor puro).

Diferencia vs fase_a_cloud.py:
  - USA generate_sequence_signals (thin wrapper -> evaluate_signals -> run_sequence_traced)
    que RETORNA las senales CON event_ids/event_objects (linaje real). NO usa
    run_sequence_backtest (que descarta signals y simula PnL en fase [3/3]).
  - Carga SOLO D1/H4/H1/M15 (monkeypatch TF_CHAIN en runtime, no edita repo).
  - SIN fase de simulacion/trades/PnL (FASE A no los necesita).
  - Telemetria viva: etapas, barra+%, ETA, PID, CPU/RAM, heartbeat 5s,
    log .jsonl historico, estado .json en vivo, funnel, metricas parciales.

NO toca engine/. NO optimiza. NO crea SDD. Linaje preservado intacto.
"""
from __future__ import annotations
import json, sys, time, os, psutil, importlib.util, threading
sys.path.insert(0, ".")

import pandas as pd
import ict_backtest.run_backtest as rb
from engine.data_feed import load_frames
from engine.market_structure import detect_market_structure

# --- monkeypatch TF_CHAIN: solo D1/H4/H1/M15 (M5/M1 sobran para FASE A) ---
LIGHT_CHAIN = ("D1", "H4", "H1", "M15")
rb.TF_CHAIN = LIGHT_CHAIN
import ict_backtest.run_backtest as _rb_mod
_rb_mod.__dict__["TF_CHAIN"] = LIGHT_CHAIN

_spec = importlib.util.spec_from_file_location(
    "phase6_verifier", "research/hypotheses/HYP-002/phase6_verifier.py")
_vmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vmod)
verify_run, verdict = _vmod.verify_run, _vmod.verdict

SYMBOL, HTF, LTF = "EURUSD", "H4", "M15"
WINDOW_MONTHS = int(sys.argv[1]) if len(sys.argv) > 1 else 2

RESULTS = "results"
os.makedirs(RESULTS, exist_ok=True)
STATE_JSON = os.path.join(RESULTS, "fase_a_light_state.json")
HISTORY_JSONL = os.path.join(RESULTS, "fase_a_light_history.jsonl")
PID = os.getpid()


def _stage(etapa, done=None, total=None, extra=None):
    """Escribe estado vivo (.json) y append historico (.jsonl)."""
    now = time.time()
    rec = {"t": now, "etapa": etapa, "pid": PID,
           "done": done, "total": total, "extra": extra or {}}
    with open(STATE_JSON, "w") as fh:
        json.dump(rec, fh, default=str)
    with open(HISTORY_JSONL, "a") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def _cpu_ram():
    p = psutil.Process(PID)
    return round(p.cpu_percent(interval=0.1), 1), round(p.memory_info().rss / 1e6, 1)


def _heartbeat():
    """Cada 5s: log de vida en consola (no bloquea el trabajo)."""
    while not _heartbeat._stop:
        cpu, ram = _cpu_ram()
        print(f"  [HB] vivo pid={PID} cpu={cpu}% ram={ram}MB etapa={_heartbeat._etapa}", flush=True)
        time.sleep(5)
    _heartbeat._etapa = "done"


_heartbeat._stop = False
_heartbeat._etapa = "init"


def main():
    t0 = time.time()
    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()

    # ---------- ETAPA 1: CARGA ----------
    _heartbeat._etapa = "carga"
    print(f"[1/3] Carga {SYMBOL} frames {LIGHT_CHAIN} (window_months={WINDOW_MONTHS}) ...", flush=True)
    load_kwargs = {}
    if WINDOW_MONTHS is not None:
        last = None
        for tf in LIGHT_CHAIN:
            p = os.path.join("data", "raw", f"{SYMBOL}_{tf}.parquet")
            if os.path.exists(p):
                last = pd.read_parquet(p, columns=["time"])["time"].iloc[-1]
                break
        if last is not None:
            load_kwargs["start"] = last - pd.DateOffset(months=WINDOW_MONTHS)
    frames = load_frames(SYMBOL, LIGHT_CHAIN, **load_kwargs)
    _stage("carga", done=1, total=3, extra={"frames": {k: len(v) for k, v in frames.items()}})
    print(f"      frames: { {k: len(v) for k, v in frames.items()} }", flush=True)

    # ---------- ETAPA 2: DETECCION (market_structure = trend REAL) ----------
    _heartbeat._etapa = "deteccion"
    print(f"[2/3] detect_market_structure (trend REAL) ...", flush=True)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    _stage("deteccion", done=2, total=3, extra={"TF_CHAIN": list(LIGHT_CHAIN)})

    # est_htf_ctx_fn: contexto HTF fiel (trend REAL, no RANGING forzado)
    htf_df = ms.get(HTF, ms[LTF])
    from engine._util import closed_row_at_time, tf_duration
    from engine.poi_anchor import build_htf_structure_index
    htf_frames = {tf: df for tf, df in ms.items() if tf != LTF}
    anchored = build_htf_structure_index(htf_frames) if htf_frames else []

    def est_htf_fn(i: int) -> dict:
        t = ms[LTF].iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        ltf_t = pd.to_datetime(t, utc=True, errors="coerce")
        pd_zones = [e for e in anchored if e.time is not None and e.time <= ltf_t]
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False)),
                "pd_zones": pd_zones}

    # ---------- ETAPA 3: GENERACION DE SENALES (run_sequence_traced via wrapper) ----------
    _heartbeat._etapa = "generacion"
    print(f"[3/3] generate_sequence_signals ({HTF}->{LTF}, run_sequence_traced) ...", flush=True)
    signals, phase_seen = rb.generate_sequence_signals(
        SYMBOL, HTF, LTF,
        require_displacement=True, displace_gap=6, bos_gap=10,
        frames=frames, fill_mode="next_open",
        enable_pd_index=True, invalidate_on_opposite_swing=False,
        return_phase_seen=True,
    )
    n_sig = len(signals)
    # trades no se simulan en FASE A ligero; funnel = phase_seen
    funnel = {k: int(phase_seen.get(k, 0)) for k in ("SWEEP", "DISPLACE", "BOS", "ENTRY")}
    print(f"      senales: {n_sig} | funnel: {funnel}", flush=True)
    _stage("generacion", done=3, total=3, extra={"senales": n_sig, "funnel": funnel})

    # ---------- VERIFICACION SEMANTICA (phase6_verifier) ----------
    _heartbeat._etapa = "verificacion"
    with_graph = [s for s in signals if (
        s.get("event_objects") if isinstance(s, dict) else getattr(s, "event_objects", None))]
    agg = verify_run(with_graph)
    v = verdict(agg)
    n = max(1, agg["n_setups"])
    pct = {k: round(100 * agg[f"{k}_ok"] / n, 1)
           for k in ("identity", "link", "causality", "temporal", "graph", "ontology")}
    agg.update(verdict=v, symbol=SYMBOL, htf_ltf=f"{HTF}->{LTF}",
               mode="runner ligero (generate_sequence_signals, sin simulacion PnL)",
               trend_source="detect_market_structure sobre data/raw OHLC (REAL)",
               TF_CHAIN=list(LIGHT_CHAIN), window_months=WINDOW_MONTHS,
               elapsed_s=round(time.time() - t0, 1), funnel=funnel, pct=pct)
    with open(os.path.join(RESULTS, "fase_a_semantic_eurhusd_LIGHT.json"), "w") as fh:
        json.dump(agg, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "fase_a_semantic_eurhusd_LIGHT.md"), "w") as fh:
        fh.write(f"# FASE A LIGERO — Verificacion Semantica (EURUSD)\n\n")
        fh.write(f"- Symbol: {SYMBOL} ({HTF}->{LTF})\n- Modo: runner ligero, sin PnL\n")
        fh.write(f"- TF: {LIGHT_CHAIN}, window_months={WINDOW_MONTHS}\n")
        fh.write(f"- Trend HTF: {agg['trend_source']}\n- Setups con linaje: {agg['n_setups']}\n")
        fh.write(f"- POI anclado HTF: {agg['poi_anchored']} | Ciclos: {agg['cycles_total']}\n")
        fh.write(f"- Funnel: {funnel}\n- Elapsed: {agg['elapsed_s']}s\n\n")
        fh.write("## % por dimension (SDD_GOVERNANCE §4)\n\n")
        for k, val in pct.items():
            fh.write(f"- {k}: {val}%\n")
        fh.write(f"\n## Veredicto\n\n**{v}**\n")
    _stage("verificacion", done=3, total=3,
           extra={"veredicto": v, "setups": agg["n_setups"], "funnel": funnel, "pct": pct})
    print(f"[FASE A LIGERO] Veredicto: {v} | setups={agg['n_setups']} | funnel={funnel}", flush=True)
    print(f"[FASE A LIGERO] -> {RESULTS}/fase_a_semantic_eurhusd_LIGHT.md", flush=True)

    _heartbeat._stop = True
    hb.join(timeout=1)
    _heartbeat._etapa = "done"


if __name__ == "__main__":
    main()
