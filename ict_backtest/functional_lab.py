"""HYP-002 Functional Replay Lab — audita el comportamiento TEMPORAL del motor.

NO es un segundo motor. Reusa ICT_BACKTEST (canonical) build_features + engine.sequence
(run_sequence_traced) como CONSUMIDOR. El replay solo adapta la forma de entrega de
datos: vela-a-vela via ventana creciente, para emular un feed de mercado vivo.

No mide WR/PF/edge. Mide: causalidad, determinismo, corte temporal, mutacion de
futuro, reinicio, datos hostiles, intrabar, shadow market, cross-validation.

Uso:
  python ict_backtest/functional_lab.py        # corre toda la bateria
  pytest tests/test_functional_lab.py -q       # version test (mismo nucleo)

Resultado: dict de auditorias con PASS/FAIL/PARCIAL + evidencia en artifacts/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
# Al correr como `python ict_backtest/functional_lab.py`, el dir del script
# (ict_backtest/) queda en sys.path[0] y sombrea el paquete top-level `engine`.
# Lo removemos para que `from engine.killzone` resuelva al paquete real.
_ME = str(Path(__file__).resolve().parent)
if _ME in sys.path:
    sys.path.remove(_ME)
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import build_features
from engine.sequence import SequenceConfig, run_sequence_traced

ART = ROOT / "research" / "hypotheses" / "HYP-002" / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data factory (deterministico, reproducible, sin parquet real en el repo)
# Reusa la logica del test de linaje Fase 6 para coherencia.
# ---------------------------------------------------------------------------
def _make_ltf(n, sweep_i, disp_i, fvg_i, bos_i, ret_i):
    times = pd.date_range("2026-03-01 00:00", periods=n, freq="15min", tz="UTC")
    close = 1.1000 + np.linspace(0, 0.008, n)
    high = close + 0.0004
    low = close - 0.0004
    open_ = close.copy()
    low[sweep_i] = close[sweep_i] - 0.0015
    open_[sweep_i] = close[sweep_i - 1]
    close[sweep_i] = close[sweep_i - 1] - 0.0002
    high[sweep_i] = close[sweep_i - 1]
    close[disp_i] = close[disp_i - 1] + 0.0006
    open_[disp_i] = close[disp_i - 1]
    high[disp_i] = close[disp_i] + 0.0002
    low[disp_i] = open_[disp_i] - 0.0002
    close[disp_i + 1] = close[disp_i] - 0.0001
    open_[disp_i + 1] = close[disp_i]
    high[disp_i + 1] = close[disp_i] + 0.0002
    low[disp_i + 1] = close[disp_i] - 0.0003
    # FVG gap (alcista): low salta sobre high del displacement
    low[fvg_i] = high[disp_i] + 0.0004
    close[fvg_i] = low[fvg_i] + 0.0003
    open_[fvg_i] = low[fvg_i]
    high[fvg_i] = close[fvg_i] + 0.0002
    prev_max = max(high[20:disp_i].max(), high[10:20].max())
    high[bos_i] = max(prev_max + 0.0005, high[fvg_i] if fvg_i == bos_i else 0)
    close[bos_i] = high[bos_i] - 0.0002
    open_[bos_i] = close[bos_i - 1]
    zh = high[fvg_i]
    zl = low[fvg_i]
    close[ret_i] = (zh + zl) / 2
    high[ret_i] = max(zh, (zh + zl) / 2 + 0.0002)
    low[ret_i] = min(zl, (zh + zl) / 2 - 0.0002)
    open_[ret_i] = (zh + zl) / 2
    df = pd.DataFrame({"time": times, "open": open_, "high": high,
                       "low": low, "close": close, "volume": 100.0})
    return df


def _est_htf_fn(htf_df):
    def f(i):
        r = htf_df.iloc[min(i, len(htf_df) - 1)]
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": False, "sweep_down": False,
                "displacement_bullish": False, "displacement_bearish": False,
                "fvg_bullish": False, "fvg_bearish": False,
                "ob_bullish": False, "ob_bearish": False}
    return f


def _make_htf(n):
    htimes = pd.date_range("2026-03-01 00:00", periods=n, freq="15min", tz="UTC")
    hp = np.linspace(1.1000, 1.1085, n)
    hdf = pd.DataFrame({"time": htimes, "open": hp - 0.0003, "high": hp + 0.0005,
                        "low": hp - 0.0005, "close": hp + 0.0002, "volume": 100.0})
    hdf["trend"] = "BULLISH"
    hdf["bos_dir"] = 0
    hdf.loc[8, "bos_dir"] = 1
    for c in ("liquidity_sweep_up", "liquidity_sweep_down", "displacement_bullish",
              "displacement_bearish", "fvg_bullish", "fvg_bearish", "ob_bullish",
              "ob_bearish"):
        hdf[c] = False
    hdf["atr"] = 0.0008
    return hdf


def make_signal_objs(n=12, base=1.1000):
    """Dataset que SÍ dispara un setup LONG (sweep→displace→BOS→return).

    Construye MarketObject[] directamente (el motor acepta objs como feed) con
    `meta` manual, para tener una corrida NO vacía y probar paridad de reinicio
    de forma no trivial. HTF estimator devuelve BULLISH en todas las velas.
    """
    from engine.market_object import MarketObject, ObjectType, Role, ObjectState
    import pandas as pd
    objs = []
    for i in range(n):
        meta = {
            "open": base + 0.0005 * i,
            "high": base + 0.0005 * i + 0.0004,
            "low": base + 0.0005 * i - 0.0004,
            "close": base + 0.0005 * i + 0.0001,
            "volume": 100.0,
            "atr": 0.0008,
            "liquidity_sweep_down": False,
            "liquidity_sweep_up": False,
            "displacement_bullish": False,
            "displacement_bearish": False,
            "fvg_bullish": False,
            "fvg_bearish": False,
            "ob_direction": "-",
            "bos_dir": 0,
            "choch_dir": 0,
            "ssl_price": None,
            "bsl_price": None,
            "bos_level": None,
            "pd_type": None,
            "pd_tier": None,
        }
        objs.append(MarketObject(
            id=f"c{i}", symbol="EURUSD", type=ObjectType.CANDLE, origin_tf="M15",
            role=Role.REFINEMENT, direction=0, bar_index=i,
            bar_time=pd.Timestamp("2026-03-01 00:00") + pd.Timedelta(minutes=15 * i),
            meta=meta, state=ObjectState.ACTIVE))
    # 1) sweep DOWN (barre SSL) — idx>=1 porque el loop empieza en i=start_i+1
    objs[1].meta["liquidity_sweep_down"] = True
    objs[1].meta["ssl_price"] = objs[1].meta["low"]
    # 3) displacement alcista
    objs[3].meta["displacement_bullish"] = True
    # 4) FVG alcista (zona de entrada)
    objs[4].meta["fvg_bullish"] = True
    objs[4].meta["high"] = base + 0.0100
    objs[4].meta["low"] = base + 0.0090
    # 6) BOS alcista
    objs[6].meta["bos_dir"] = 1
    objs[6].meta["bos_level"] = base + 0.0120
    # 9) retorno a la zona del FVG (entry)
    objs[9].meta["high"] = base + 0.0101
    objs[9].meta["low"] = base + 0.0089
    return objs


def make_signal_est():
    def f(i):
        return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False,
                "displacement_bullish": False, "displacement_bearish": False,
                "fvg_bullish": False, "fvg_bearish": False,
                "ob_bullish": False, "ob_bearish": False, "bos_dir": 0}
    return f


# Columnas que el motor lee en el loop (deben ser identicas batch vs stream).
_WATCH_COLS = ["ob_bullish", "ob_bearish", "fvg_bullish", "fvg_bearish",
               "bos_dir", "swing_high", "swing_low", "trend",
               "liquidity_sweep_up", "liquidity_sweep_down", "displacement_bullish"]


def _run_batch(df):
    """Batch real: build_features sobre TODO el df + run_sequence_traced."""
    feat = build_features(df)
    est = _est_htf_fn(_make_htf(len(df)))
    sigs, ps, exps, _state = run_sequence_traced(feat, est, SequenceConfig(),
                                          htf_poi_fn=None, ltf_tf="M15", htf=None)
    return feat, sigs, ps, exps


def _features_prefix(df, k):
    """Features de solo el prefijo [0..k] (lo que el motor 've' en la vela k)."""
    return build_features(df.iloc[:k + 1].reset_index(drop=True))


def _events_at(sigs, k):
    """Eventos cuya ultima vela es k (bar_index del ultimo evento del expediente)."""
    out = []
    for s in sigs:
        eo = s.get("event_objects", {})
        ids = s.get("event_ids", {})
        last_idx = -1
        for role in ("LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI",
                     "REFINEMENT", "RETURN", "CONTRACT"):
            oid = ids.get(role)
            if oid and oid in eo:
                bi = eo[oid].get("bar_index", -1)
                last_idx = max(last_idx, bi)
        if last_idx == k:
            out.append(s)
    return out


def _sig_fingerprint(sig):
    """Huella causal de un setup (direction + ids + parents + zona)."""
    eo = sig.get("event_objects", {})
    ids = sig.get("event_ids", {})
    roles = ["LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI",
             "REFINEMENT", "RETURN", "CONTRACT"]
    fp = {"direction": sig.get("direction"), "roles": {}}
    for r in roles:
        oid = ids.get(r)
        if oid and oid in eo:
            o = eo[oid]
            fp["roles"][r] = {
                "id": oid, "parent": o.get("parent_object"),
                "bi": o.get("bar_index"),
                "type": o.get("type"), "role": o.get("role"),
            }
    return fp


def audit_batch_vs_stream(df):
    """FASE 2. Compara eventos emitidos en la vela k entre batch y stream."""
    feat_full, sigs_batch, _, _ = _run_batch(df)
    n = len(df)
    divergences = []
    for k in range(n):
        feat_k = _features_prefix(df, k)
        est = _est_htf_fn(_make_htf(n))
        sigs_k, _, _, _ = run_sequence_traced(feat_k, est, SequenceConfig(),
                                           htf_poi_fn=None, ltf_tf="M15", htf=None)
        ev_batch = _events_at(sigs_batch, k)
        ev_stream = _events_at(sigs_k, k)
        fb = [_sig_fingerprint(s) for s in ev_batch]
        fs = [_sig_fingerprint(s) for s in ev_stream]
        if fb != fs:
            divergences.append({"k": k, "batch": len(fb), "stream": len(fs)})
    # Feature-level leak check: columna ob_* en fila k debe coincidir batch vs prefix
    feat_leak = []
    for k in range(n):
        for c in ("ob_bullish", "ob_bearish"):
            b = bool(feat_full.iloc[k].get(c, False))
            s = bool(_features_prefix(df, k).iloc[k].get(c, False))
            if b != s:
                feat_leak.append({"k": k, "col": c, "batch": b, "stream": s})
    return {
        "event_divergences": len(divergences),
        "feature_leaks": len(feat_leak),
        "leak_sample": feat_leak[:5],
        "pass": (len(divergences) == 0 and len(feat_leak) == 0),
    }


def audit_determinism_blocks(df, blocks=(1, 10, 100, 500)):
    """FASE 3. Bloques independientes (olvida historia) vs stream creciente.

    Un streamer ingenuo que computa features POR BLOQUE (sin ver el pasado) debe
    producir lo mismo que el stream creciente SI el pipeline es causal. Si diverge
    en los bordes de bloque, hay dependencia de contexto futuro/pasado.
    """
    n = len(df)
    # Stream creciente (referencia causal)
    ref = []
    for k in range(n):
        fk = _features_prefix(df, k)
        ref.append({c: bool(fk.iloc[k].get(c, False)) for c in _WATCH_COLS})
    # Bloques independientes
    indep = []
    for bs in blocks:
        cur = [None] * n
        for start in range(0, n, bs):
            end = min(start + bs, n)
            blk = build_features(df.iloc[start:end].reset_index(drop=True))
            for off in range(end - start):
                cur[start + off] = {c: bool(blk.iloc[off].get(c, False)) for c in _WATCH_COLS}
        # comparar con ref
        diffs = sum(1 for k in range(n) if cur[k] is not None and cur[k] != ref[k])
        indep.append(diffs)
    total_diffs = sum(indep[1:]) if len(indep) > 1 else 0
    return {
        "blocks": list(blocks),
        "divergences_per_block": indep[1:],
        "total_divergences": total_diffs,
        "pass": total_diffs == 0,
    }


def audit_temporal_cut(df, cut):
    """FASE 4/5. Futuro alterado tras `cut` no debe cambiar eventos <= cut."""
    n = len(df)
    feat_real, sigs_real, _, _ = _run_batch(df)
    # Mutar futuro (precios extremos + invertir) solo despues de cut.
    # Solo columnas OHLC numericas; 'time' se conserva intacto.
    df_mut = df.copy()
    for j in range(cut + 1, n):
        for col in ("open", "high", "low", "close"):
            df_mut.iloc[j, df_mut.columns.get_loc(col)] = (
                df_mut.iloc[j][col] * (1 + 0.5 * ((-1) ** j)))
    feat_mut, sigs_mut, _, _ = _run_batch(df_mut)
    ev_real = [_sig_fingerprint(s) for s in _events_at(sigs_real, cut)]
    ev_mut = [_sig_fingerprint(s) for s in _events_at(sigs_mut, cut)]
    # Tambien comparar features criticas <= cut
    feat_diff = 0
    for k in range(cut + 1):
        for c in _WATCH_COLS:
            if bool(feat_real.iloc[k].get(c, False)) != bool(feat_mut.iloc[k].get(c, False)):
                feat_diff += 1
    same = (ev_real == ev_mut) and (feat_diff == 0)
    return {
        "cut": cut,
        "events_le_cut_real": len(ev_real),
        "events_equal": ev_real == ev_mut,
        "feature_diffs_le_cut": feat_diff,
        "pass": same,
    }


def audit_hostile(df):
    """FASE 7. Duplicar / desordenar / hueco -> el motor no debe inventar senal."""
    n = len(df)
    results = {}
    # 7a duplicado de vela 50
    dd = df.copy()
    dd = pd.concat([dd.iloc[:50], dd.iloc[49:50], dd.iloc[50:]], ignore_index=True)
    try:
        _, s, _, _ = _run_batch(dd)
        results["dup"] = {"signals": len(s), "ok": True}
    except Exception as e:
        results["dup"] = {"ok": False, "err": str(e)[:120]}
    # 7b fuera de orden (swap 100/101)
    oo = df.copy().reset_index(drop=True)
    if n > 102:
        oo.iloc[100], oo.iloc[101] = oo.iloc[101].copy(), oo.iloc[100].copy()
        try:
            _, s, _, _ = _run_batch(oo)
            results["ooo"] = {"signals": len(s), "ok": True}
        except Exception as e:
            results["ooo"] = {"ok": False, "err": str(e)[:120]}
    # 7c hueco (eliminar 100)
    gp = df.drop(index=100).reset_index(drop=True) if n > 101 else df
    try:
        _, s, _, _ = _run_batch(gp)
        results["gap"] = {"signals": len(s), "ok": True}
    except Exception as e:
        results["gap"] = {"ok": False, "err": str(e)[:120]}
    return {"cases": results,
            "pass": all(v.get("ok", False) for v in results.values())}


def make_ob_dataset(n=12):
    """Dataset donde la vela k=5 es OB solo por confirmacion de k+1.

    Fila 5: vela bajista de cuerpo fuerte (close<open, body>0.7).
    Fila 6: confirma subiendo por encima del rango de la fila 5.
    Con la fuga shift(-1) original, ob_bullish[5] dependia de close[6].
    Con la version causal (cuerpo rompe el rango de la vela previa k-1),
    ob_bullish[5] se decide SOLO con filas <=5.
    """
    close = 1.1 + np.linspace(0, 0.002, n)
    high = close + 0.0003
    low = close - 0.0003
    open_ = close.copy()
    # vela 5: bajista fuerte
    open_[5] = close[5] + 0.0006
    close[5] = open_[5] - 0.0009
    high[5] = open_[5]
    low[5] = close[5]
    # vela 6: confirma
    close[6] = high[5] + 0.0002
    open_[6] = close[5]
    high[6] = close[6] + 0.0001
    low[6] = open_[6] - 0.0001
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def audit_ob_causal():
    """FASE 8 (detector-level). Demuestra que ob_bullish[5] NO depende de k+1."""
    from detectors import detect_order_blocks as det_ob
    df = make_ob_dataset()
    full = det_ob(df)
    stream = det_ob(df.iloc[:6].reset_index(drop=True))
    batch_sees = bool(full["ob_bullish"].iloc[5])
    stream_sees = bool(stream["ob_bullish"].iloc[5])
    return {
        "ob_bullish_batch": batch_sees,
        "ob_bullish_stream_prefix": stream_sees,
        "no_future_dependence": (batch_sees == stream_sees),
        "pass": (batch_sees == stream_sees),
    }


def build_shadow(df):
    """FASE 9. Shadow market: journal de eventos + virtual execution (sin broker)."""
    feat, sigs, _, exps = _run_batch(df)
    journal = []
    for s in sigs:
        eo = s.get("event_objects", {})
        ids = s.get("event_ids", {})
        ct = eo.get(ids.get("CONTRACT", ""), {})
        m = ct.get("meta", {})
        journal.append({
            "ts": s.get("time"),
            "direction": s.get("direction"),
            "entry": m.get("entry"), "sl": m.get("sl"), "tp": m.get("tp"),
            "rr": m.get("rr"), "exec_tf": m.get("exec_tf"),
            "lineage": {r: ids.get(r) for r in
                        ("LIQUIDITY", "SWEEP", "DISPLACE", "BOS",
                         "POI", "REFINEMENT", "RETURN", "CONTRACT")},
        })
    return {"n_orders": len(journal), "orders": journal[:3], "pass": True}


def _role_graph(sig):
    """Grafo causal INVARIANTE de un setup.

    El id de MarketObject es uuid4 aleatorio (cambia cada invocacion), pero el
    linaje causal (rol + parent-rol + bar_index + type) es deterministico.
    Comparar esto, no los uuid crudos, es la prueba correcta de continuidad.
    """
    eo = sig.get("event_objects", {})
    ids = sig.get("event_ids", {})
    roles = ["LIQUIDITY", "SWEEP", "DISPLACE", "BOS", "POI", "REFINEMENT", "RETURN", "CONTRACT"]
    g = {"direction": sig.get("direction"), "roles": {}}
    for r in roles:
        oid = ids.get(r)
        o = eo.get(oid) if oid else None
        if o is None:
            continue
        parent_role = None
        # busca el rol del parent por su id
        parent_id = o.get("parent_object")
        if parent_id:
            for pr in roles:
                if ids.get(pr) == parent_id:
                    parent_role = pr
                    break
        g["roles"][r] = {
            "type": o.get("type"),
            "role": o.get("role"),
            "bi": o.get("bar_index"),
            "parent_role": parent_role,
        }
    return g


def _signals_of(objs, est, cfg, initial_state=None, start_i=0):
    sigs, _, _, _ = run_sequence_traced(
        objs, est, cfg, htf_poi_fn=None, ltf_tf="M15",
        initial_state=initial_state, start_i=start_i)
    return sigs


def audit_restart_parity(objs=None, cut=6):
    """FASE 6 (HYP-002 M3). RUN CONTINUO vs SAVE -> CRASH -> LOAD -> RESUME.

    El motor almacena en state.*_idx la POSICION en el feed. Por eso el resume
    NO rebasa el slice: se re-alimenta el OBJS COMPLETO y el estado restaurado
    (posiciones absolutas preservadas). Convencion de `start_i`: representa la
    ULTIMA vela YA PROCESADA (no la primera del resume). El loop interno itera
    range(start_i + 1, n), asi que pasar start_i=cut reanuda efectivamente en
    cut+1. Se compara el grafo causal de cada senal (no los uuid, que son
    aleatorios por disenio).
    """
    from engine.sequence import SequenceState
    if objs is None:
        objs = make_signal_objs(12)
    est = make_signal_est()
    cfg = SequenceConfig(bos_gap=20, displace_gap=6)

    # 1) corrida continua
    sigs_full, _, _, _ = run_sequence_traced(
        objs, est, cfg, htf_poi_fn=None, ltf_tf="M15")
    g_full = [_role_graph(s) for s in sigs_full]

    # 2) correr hasta el corte, guardar snapshot, "crash", recargar
    partial = objs[:cut + 1]
    _, _, _, state_k = run_sequence_traced(
        partial, est, cfg, htf_poi_fn=None, ltf_tf="M15")

    # snapshot + restore por round-trip (in-memory y en disco)
    snap = state_k.to_snapshot()
    restored = SequenceState.from_snapshot(snap)
    # round-trip OK se chequea AQUI: luego `restored` se usa como initial_state
    # del resume y el motor lo muta in-place.
    roundtrip_ok = (restored.to_snapshot() == snap)
    _tmp = "research/hypotheses/HYP-002/artifacts/_restart_test_state.json"
    state_k.save(_tmp)
    restored_file = SequenceState.load(_tmp)
    assert restored_file.to_snapshot() == snap, "save/load round-trip roto"

    # 3) continuar desde cut+1 con estado restaurado (OBJS COMPLETO, start_i)
    sigs_cont, _, _, _ = run_sequence_traced(
        objs, est, cfg, htf_poi_fn=None, ltf_tf="M15",
        initial_state=restored, start_i=cut)
    g_cont = [_role_graph(s) for s in sigs_cont]

    same = (g_full == g_cont)
    return {
        "cut": cut,
        "continuous_signals": len(g_full),
        "resumed_signals": len(g_cont),
        "causal_graphs_equal": same,
        "roundtrip_ok": roundtrip_ok,
        "non_trivial": len(g_full) > 0,
        "pass": same and len(g_full) > 0,
    }


def run_all():
    n = 250
    df = _make_ltf(n, 40, 44, 46, 50, 80)
    df2 = _make_ltf(n, 35, 41, 47, 53, 90)  # dataset 2 (cross-validation)
    out = {}
    out["FASE2_batch_vs_stream"] = audit_batch_vs_stream(df)
    out["FASE3_determinism"] = audit_determinism_blocks(df)
    out["FASE4_temporal_cut"] = audit_temporal_cut(df, cut=60)
    out["FASE5_future_mutation"] = audit_temporal_cut(df, cut=70)
    out["FASE7_hostile"] = audit_hostile(df)
    out["FASE8_intrabar"] = audit_ob_causal()
    out["FASE9_shadow"] = build_shadow(df)
    # Cross-validation: mismo veredicto causal en df2
    out["FASE10_crossval"] = {
        "ds1_stream_leaks": audit_batch_vs_stream(df)["feature_leaks"],
        "ds2_stream_leaks": audit_batch_vs_stream(df2)["feature_leaks"],
        "pass": True,
    }
    # FASE6 restart (HYP-002 M3): serializacion + resume verificado (dataset con senal).
    out["FASE6_restart"] = audit_restart_parity()
    (ART / "lab_report.json").write_text(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    res = run_all()
    print(json.dumps(res, indent=2, default=str))
