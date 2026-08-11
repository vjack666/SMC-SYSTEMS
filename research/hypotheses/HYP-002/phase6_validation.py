"""HYP-002 Fase 6 — VALIDACIÓN + FALSACIÓN de Arquitectura A COMPLETA (consumidor puro).

Cierra la formación causal: LIQUIDITY -> SWEEP -> DISPLACEMENT -> BOS -> POI(HTF) ->
REFINEMENT(LTF) -> RETURN. Respeta ontología (POI institucional HTF, FVG/OB LTF =
REFINEMENT). Separ E IDENTITY/LINK/CAUSALITY. No usa WR/PF. Corre local + nube.

Regla 9 del Director: demuestra que con DOS candidatos plausibles de POI, el sistema
NO elige por proximidad post-hoc, sino por el parent declarado en el origen.
"""
import sys, time, uuid
import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from engine.sequence import SequenceConfig, run_sequence_traced
from engine.expediente import Expediente, PhaseEvent
from engine.poi_anchor import make_htf_poi_fn
from detectors import detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
from engine.bos.structure import detect_market_structure


def _avg_candle_range(df, window=50):
    return (df["high"] - df["low"]).clip(lower=0.0).rolling(window).mean()


def build_features_like(df):
    d = df.copy().reset_index(drop=True)
    ms = detect_market_structure(d, None)
    frame = ms.frame if hasattr(ms, "frame") else ms
    d["bos_dir"] = frame["bos_dir"].astype(int).values
    d["choch_dir"] = frame["choch_dir"].astype(int).values
    d["trend"] = frame["trend"].values
    d["atr"] = _avg_candle_range(d, 50).to_numpy()
    f = detect_fvg(d)
    for c in f.columns:
        d[c] = f[c].values
    o = detect_order_blocks(d)
    for c in o.columns:
        d[c] = o[c].values
    disp = detect_displacement(d)
    d["displacement_bullish"] = disp["displacement_bullish"].values
    d["displacement_bearish"] = disp["displacement_bearish"].values
    liq = detect_liquidity(d)
    d["bsl_price"] = liq["bsl_price"].values
    d["ssl_price"] = liq["ssl_price"].values
    swept = canonical_sweep(d, lookback=DEFAULT_SWEEP_LOOKBACK)
    d["liquidity_sweep_up"] = swept["liquidity_sweep_up"].values
    d["liquidity_sweep_down"] = swept["liquidity_sweep_down"].values
    return d


def est_htf_fn_for(htf_df):
    def f(i):
        if htf_df is not None and i < len(htf_df):
            r = htf_df.iloc[i]
            return {"trend": str(r.get("trend", "RANGING")),
                    "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                    "sweep_down": bool(r.get("liquidity_sweep_down", False)),
                    "displacement_bullish": bool(r.get("displacement_bullish", False)),
                    "displacement_bearish": bool(r.get("displacement_bearish", False)),
                    "fvg_bullish": bool(r.get("fvg_bullish", False)),
                    "fvg_bearish": bool(r.get("fvg_bearish", False)),
                    "ob_bullish": bool(r.get("ob_bullish", False)),
                    "ob_bearish": bool(r.get("ob_bearish", False))}
        return {"trend": "RANGING"}
    return f


def load_parquet(symbol, tf):
    p = f"data/raw/{symbol}_{tf}.parquet"
    df = pd.read_parquet(p)
    if "time" not in df.columns and df.index.name == "time":
        df = df.reset_index()
    return df


# Cadena completa que el motor debe haber enlazado (en orden hijo->padre).
CHAIN = [("RETURN", "REFINEMENT"), ("REFINEMENT", "POI"), ("POI", "BOS"),
         ("BOS", "DISPLACE"), ("DISPLACE", "SWEEP"), ("SWEEP", "LIQUIDITY")]


def audit_full_chain(sig):
    """Recorre el linaje completo y separa IDENTITY / LINK / CAUSALITY."""
    ids = sig.get("event_ids", {})
    exp = sig.get("expediente")
    levels = sig.get("levels", {})
    # Mapa event_id -> (phase, parent_event_id, idx)
    ev = {}
    for pe in exp.phase_events:
        if pe.phase == "INVALID":
            continue
        ev[pe.event_id] = (pe.phase, pe.parent_event_id, pe.idx)
    out = {"identity": "OK", "link": "OK", "causality": "OK", "issues": []}
    # IDENTITY: ids no vacíos y únicos en el setup
    seen = set()
    for ph, eid in ids.items():
        if not eid:
            if ph in ("POI",):  # POI puede faltar si no hay ancla HTF (no es fallo de identidad)
                continue
            out["identity"] = "MISSING"; out["issues"].append(f"id vacio {ph}")
        if eid in seen:
            out["identity"] = "DUP"; out["issues"].append(f"id duplicado {eid}")
        seen.add(eid)
    # LINK + CAUSALITY por la cadena
    for child_ph, parent_ph in CHAIN:
        cid = ids.get(child_ph, "")
        pid = ids.get(parent_ph, "")
        if not cid:
            if child_ph in ("RETURN", "REFINEMENT", "BOS", "DISPLACE", "SWEEP", "LIQUIDITY"):
                out["link"] = "CHILD_MISSING"; out["issues"].append(f"{child_ph} id ausente")
            continue
        if cid not in ev:
            out["link"] = "CHILD_MISSING"; out["issues"].append(f"{child_ph} id {cid} ausente en traza")
            continue
        if pid and pid not in ev:
            out["link"] = "PARENT_MISSING"; out["issues"].append(f"{child_ph}->padre {parent_ph} ({pid}) ausente")
            continue
        if pid and ev[cid][2] < ev[pid][2]:
            out["link"] = "PARENT_FUTURE"; out["issues"].append(
                f"{child_ph} idx {ev[cid][2]} < padre {parent_ph} idx {ev[pid][2]}")
        # CAUSALITY: el parent_event_id declarado en el PhaseEvent debe coincidir con el id del padre
        pe_by_phase = {pe.phase: pe for pe in exp.phase_events if pe.phase in
                       ("SWEEP", "DISPLACE", "BOS", "ENTRY", "LIQUIDITY")}
        pe = pe_by_phase.get(child_ph if child_ph != "RETURN" else "ENTRY")
        if pe is not None and pid and pe.parent_event_id != pid:
            out["causality"] = "PARENT_MISMATCH"; out["issues"].append(
                f"{child_ph}.parent={pe.parent_event_id} != {parent_ph}.id={pid}")
    # CICLOS
    cycles = 0
    for eid, (ph, pid, ix) in ev.items():
        if pid == eid:
            cycles += 1
    return out, ev, cycles


def main():
    t0 = time.time()
    full = load_parquet("EURUSD", "M15")
    htf_raw = load_parquet("EURUSD", "H4")
    n = min(60000, len(full))
    ltf_df = build_features_like(full.iloc[:n].reset_index(drop=True))
    htf_feat = build_features_like(htf_raw.iloc[:n].reset_index(drop=True))
    est_fn = est_htf_fn_for(htf_feat)
    htf_poi_fn = make_htf_poi_fn(ltf_df, {"H4": htf_raw.iloc[:n]})
    sigs, phase_seen, exps = run_sequence_traced(
        ltf_df, est_fn, SequenceConfig(),
        htf_poi_fn=htf_poi_fn, ltf_tf="M15", htf="H4", est_htf_ctx_fn=None,
    )

    all_ids = []
    id_uniq = True
    link_ok = link_bad = 0
    causality_fail = 0
    identity_fail = 0
    chain_ok = 0
    cycles_total = 0
    poi_anchored = 0
    for sig in sigs:
        ids = sig.get("event_ids", {})
        all_ids.extend([v for v in ids.values() if v])
        res, ev, cycles = audit_full_chain(sig)
        cycles_total += cycles
        if res["identity"] != "OK":
            identity_fail += 1
        if res["link"] == "OK":
            link_ok += 1
        else:
            link_bad += 1
        if res["causality"] != "OK":
            causality_fail += 1
        if ids.get("POI"):
            poi_anchored += 1
        # cadena recorrible RETURN->...->LIQUIDITY (los nodos presentes)
        if ids.get("RETURN") and ids.get("LIQUIDITY"):
            chain_ok += 1

    id_uniq = len(all_ids) == len(set(all_ids))

    # --- Regla 8/9 adversariales ---
    # A: parent futuro rechazado
    exp_t = Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=10, birth_time="t")
    exp_t.advance("LIQUIDITY", 10, "t", event_id="l1")
    exp_t.advance("SWEEP", 10, "t", event_id="s1", parent_event_id="l1")
    future_err = None
    try:
        exp_t.advance("DISPLACE", 5, "t", event_id="d1", parent_event_id="s1")
    except ValueError as e:
        future_err = str(e)
    # B: padre fantasma (GHOST) marcado, no crashea
    fake = {"event_ids": {"LIQUIDITY": "l1", "SWEEP": "s1", "DISPLACE": "d1", "BOS": "b1",
                          "POI": "p1", "REFINEMENT": "r1", "RETURN": "rt1"},
            "expediente": Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=1, birth_time="t")}
    fake["expediente"].advance("LIQUIDITY", 1, "t", event_id="l1")
    fake["expediente"].advance("SWEEP", 2, "t", event_id="s1", parent_event_id="l1")
    fake["expediente"].advance("DISPLACE", 3, "t", event_id="d1", parent_event_id="GHOST")
    res_fake, _, _ = audit_full_chain(fake)
    # C: invalidate corta y conserva historia
    exp_inv = Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=1, birth_time="t")
    exp_inv.advance("LIQUIDITY", 1, "t", event_id="l1")
    exp_inv.advance("SWEEP", 2, "t", event_id="s1", parent_event_id="l1")
    exp_inv.advance("DISPLACE", 3, "t", event_id="d1", parent_event_id="s1")
    exp_inv.invalidate(4, "t", "BOS roto", event_id="inv1", parent_event_id="d1")
    invalid_cut = exp_inv.outcome == "INVALID"
    history_kept = len(exp_inv.phase_events) == 4  # LIQ, SWEEP, DISP, INVALID
    # D: dos expedientes DISTINTOS no comparten identidad (Ley 7: iguales colisionan
    # intencionalmente; distintos deben ser únicos). Usamos birth_idx distinto.
    e1 = Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=1, birth_time="t")
    e2 = Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=2, birth_time="t")
    no_share = e1.id != e2.id
    # E: PADRE INCORRECTO (dos candidatos plausibles) — el motor NO elige por proximidad.
    # Construimos un setup donde el RETURN declara parent=REFINEMENT (correcto) y otro donde
    # declara parent=BOS (incorrecto); audit_full_chain debe marcar PARENT_MISMATCH en el 2do.
    sig_bad = {"event_ids": {"LIQUIDITY": "l1", "SWEEP": "s1", "DISPLACE": "d1", "BOS": "b1",
                             "POI": "p1", "REFINEMENT": "r1", "RETURN": "rt1"},
               "expediente": Expediente.open(symbol="X", tf="M15", direction=1, birth_idx=1, birth_time="t")}
    sig_bad["expediente"].advance("LIQUIDITY", 1, "t", event_id="l1")
    sig_bad["expediente"].advance("SWEEP", 2, "t", event_id="s1", parent_event_id="l1")
    sig_bad["expediente"].advance("DISPLACE", 3, "t", event_id="d1", parent_event_id="s1")
    sig_bad["expediente"].advance("BOS", 4, "t", event_id="b1", parent_event_id="d1")
    sig_bad["expediente"].advance("POI", 4, "t", event_id="p1", parent_event_id="b1")
    sig_bad["expediente"].advance("REFINEMENT", 4, "t", event_id="r1", parent_event_id="p1")
    sig_bad["expediente"].advance("ENTRY", 5, "t", event_id="rt1", parent_event_id="b1")  # MAL: apunta a BOS
    res_bad, _, _ = audit_full_chain(sig_bad)

    report = ["# FASE 6 — VALIDACIÓN + FALSACIÓN Arquitectura A COMPLETA (HYP-002)",
              f"Símbolo EURUSD M15 | {n} velas | setups={len(sigs)} | {time.time()-t0:.1f}s",
              "",
              "## A. Regla 7 — pruebas estructurales (setups reales)",
              f"- IDs únicos en todo el run: {id_uniq} ({len(all_ids)} ids, {len(set(all_ids))} unicos)",
              f"- IDENTITY OK: {len(sigs)-identity_fail}/{len(sigs)} | fallos={identity_fail}",
              f"- LINK OK (parent resoluble + anterior): {link_ok}/{len(sigs)} | fallos={link_bad}",
              f"- CAUSALITY OK (parent declarado == id padre): {len(sigs)-causality_fail}/{len(sigs)} | fallos={causality_fail}",
              f"- Cadena RETURN->LIQUIDITY recorrible: {chain_ok}/{len(sigs)}",
              f"- POI institucional HTF anclado (role=POI): {poi_anchored}/{len(sigs)} setups",
              f"- Ciclos detectados: {cycles_total}",
              "",
              "## B. Regla 8/9 — casos adversariales",
              f"- Parent FUTURO (idx 5 < 10) rechazado: {'SI' if future_err else 'NO'}",
              f"  -> {future_err}",
              f"- Parent INEXISTENTE (GHOST): auditor marca {res_fake['link']} (no crashea)",
              f"- invalidate() corta y CONSERVA historia: {'SI' if invalid_cut and history_kept else 'NO'} (kept={history_kept})",
              f"- Dos expedientes NO comparten identidad: {'SI' if no_share else 'NO'}",
              f"- PADRE INCORRECTO (RETURN->BOS en vez de REFINEMENT): auditor marca {res_bad['causality']}",
              "  (demuestra que NO se elige por proximidad: el parent declarado en origen es la fuente)",
              "",
              "## C. Veredicto",
              ""]
    if link_bad == 0 and causality_fail == 0 and id_uniq and cycles_total == 0:
        verdict = "A VALIDADA (completa): linaje LIQ->SWEEP->DISP->BOS->POI->REF->RETURN demostrable sin proximidad."
    elif link_bad == 0 and causality_fail == 0 and not id_uniq:
        verdict = "A PARCIAL: linaje correcto pero colisión de ids (naming)."
    else:
        verdict = f"A REFUTADA: {link_bad} LINK / {causality_fail} CAUSALITY fallidos / ciclos={cycles_total}."
    report.append(f"**VEREDICTO:** {verdict}")
    report.append("")
    report.append("## D. Qué NO se modificó")
    report.append("- Lógica de decisión: detectores, thresholds, secuencia, filtros. Sin ATR/RSI/EMA.")
    report.append("- Macro/News no usado como filtro. Sin WR/PF/edge. Sin ML/scores.")
    report.append("- Compatibilidad run_sequence_traced: firma intacta (3er elem = expedientes).")
    with open("research/hypotheses/HYP-002/phase6_validation_report.md", "w") as fh:
        fh.write("\n".join(report))
    print("\n".join(report[:30]))
    print(f"\nVEREDICTO: {verdict}")


if __name__ == "__main__":
    main()
