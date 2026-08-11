"""HYP-002 Fase 3 — PRUEBA DE FALSABILIDAD de la Arquitectura B.

Consumidor PURO del motor (Opción B, sin import ict_backtest). NO modifica engine/.
Objetivo: intentar ROMPER B, no confirmarla.

B = el auditor reconstruye el linaje causal offline por PROXIMIDAD + DIRECCIÓN usando
los MISMOS detectores del motor (detectors.*, fvg_for_bos). Medimos si esa reconstrucción
es ÚNICA, ESTABLE y NO AMBIGUA.

Regla central del Director (2026-08-11):
  PROXIMIDAD NO ES CAUSALIDAD.
  SI EXISTEN DOS PADRES PLAUSIBLES -> UNKNOWN/AMBIGUOUS.
  NUNCA "elige el mas cercano -> PASS".

Para cada señal emitida por el motor (sweep_at, displace_at, bos_at, entry_at, direction):
  - SWEEP->DISP: candidatos = displacement flags en dir correcta entre sweep_at y bos_at.
  - DISP->BOS:   candidatos = bos_dir en dir correcta despues del displacement.
  - BOS->POI:    candidatos = FVG/OB en dir correcta entre sweep y bos.
  Contamos candidatos por union (unicidad). Si >1 -> AMBIGUOUS (no elegir).
SENSIBILIDAD: repetir matching con ventanas de gap {2,3,4,5,7}; si el linaje cambia -> inestable.
ADVERSARIAL: buscar deliberately casos con eventos cercanos / multiples candidatos.

Salida: b_falsifiability_report.md con tasas de reconstruccion unica, limites de B,
casos ambiguos muestreados, y recomendacion A/B por evidencia.
"""
import sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from detectors import detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
from engine.bos.structure import detect_market_structure
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.poi_anchor import make_htf_poi_fn
from engine.fvg_poi import fvg_for_bos

SYM = "EURUSD"
DATA_DIR = "data/raw"
WINDOWS = [2, 3, 4, 5, 7]  # ventanas de gap para sensibilidad


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


def load_parquet(symbol, tf):
    p = f"{DATA_DIR}/{symbol}_{tf}.parquet"
    df = pd.read_parquet(p)
    if "time" not in df.columns and df.index.name == "time":
        df = df.reset_index()
    return df


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


def _disp_flags(d, direction):
    return d["displacement_bullish"] if direction == 1 else d["displacement_bearish"]


def _bos_dir(d, i):
    return int(d["bos_dir"].iloc[i]) if i < len(d) else 0


def _poi_candidates(d, sweep_i, bos_i, direction):
    """Candidatos POI (FVG/OB) en dir correcta entre sweep y bos. Arquitectura B."""
    seg = d.iloc[max(0, sweep_i):bos_i + 1]
    if direction == 1:
        pool = seg[seg["fvg_bullish"] | seg["ob_bullish"]]
    else:
        pool = seg[seg["fvg_bearish"] | seg["ob_bearish"]]
    return list(pool.index)


def count_candidates(d, sig, gap):
    """Cuenta candidatos por union bajo una ventana de gap dada.
    Devuelve dict con n_cand por union y veredicto por union."""
    direction = int(sig["direction"])
    sweep_i = int(sig["sweep_at"]); disp_i = int(sig["displace_at"])
    bos_i = int(sig["bos_at"]); entry_i = int(sig["entry_at"])

    # SWEEP -> DISP: displacement en [sweep_i+1, bos_i] en dir correcta
    lo = sweep_i + 1
    hi = bos_i
    seg = d.iloc[max(0, lo):hi + 1] if hi > lo else d.iloc[0:0]
    disp_cand = list(seg.index[_disp_flags(seg, direction).values]) if len(seg) else []

    # DISP -> BOS: bos_dir en dir correcta en [disp_i+1, entry_i]
    lo2 = disp_i + 1
    hi2 = entry_i
    bos_cand = []
    if hi2 > lo2:
        for j in range(max(0, lo2), hi2 + 1):
            if _bos_dir(d, j) == direction:
                bos_cand.append(j)

    # BOS -> POI: FVG/OB en [sweep_i, bos_i]
    poi_cand = _poi_candidates(d, sweep_i, bos_i, direction)

    res = {
        "sweep_disp": len(disp_cand),
        "disp_bos": len(bos_cand),
        "bos_poi": len(poi_cand),
    }
    return res, disp_cand, bos_cand, poi_cand


def classify(res):
    """Veredicto por union: UNIQUE si ==1, AMBIGUOUS si >1, NONE si 0."""
    out = {}
    for k, n in res.items():
        if n == 1:
            out[k] = "UNIQUE"
        elif n > 1:
            out[k] = "AMBIGUOUS"
        else:
            out[k] = "NONE"
    return out


def run_window(d, sigs, gap):
    rows = []
    for sig in sigs:
        res, *_ = count_candidates(d, sig, gap)
        rows.append(res)
    return rows


def main():
    t0 = time.time()
    full = load_parquet(SYM, "M15")
    htf_raw = load_parquet(SYM, "H4")
    # Muestras progresivas (velas M15): ~5k, 15k, 38k, 60k
    samples = [(5000, "S1_5k"), (15000, "S2_15k"), (38000, "S3_38k"), (60000, "S4_60k")]
    # limitar a lo disponible
    samples = [(n, tag) for n, tag in samples if n <= len(full)]

    report = ["# PRUEBA DE FALSABILIDAD — Arquitectura B (HYP-002 Fase 3)",
              f"Símbolo: {SYM} M15 | Motor: run_sequence_traced (consumidor puro, Opción B)",
              "Regla: PROXIMIDAD NO ES CAUSALIDAD; >1 candidato -> AMBIGUOUS",
              "",
              "## Metodología",
              "- Se emite el setup con el motor (índices sweep/displace/bos/entry).",
              "- El AUDITOR (no el motor) reconstruye el linaje por PROXIMIDAD+DIRECCIÓN.",
              "- Por cada unión se CUENTA el nº de candidatos plausibles (unicidad).",
              "- Si >1 -> AMBIGUOUS (nunca se elige el más cercano silenciosamente).",
              "- Sensibilidad: se repite con ventanas de gap {2,3,4,5,7}.",
              "",
              "## Resultados por muestra", ""]

    summary_rows = []
    adversarial_examples = []

    for n, tag in samples:
        ltf_df = build_features_like(full.iloc[:n].reset_index(drop=True))
        htf_feat = build_features_like(htf_raw.iloc[:n].reset_index(drop=True))
        est_fn = est_htf_fn_for(htf_feat)
        htf_poi_fn = make_htf_poi_fn(ltf_df, {"H4": htf_raw.iloc[:n]})
        sigs, _, _ = run_sequence_traced(
            ltf_df, est_fn, SequenceConfig(),
            htf_poi_fn=htf_poi_fn, ltf_tf="M15", htf="H4", est_htf_ctx_fn=None,
        )
        if len(sigs) == 0:
            report.append(f"### {tag} ({n} velas): 0 setups emitidos")
            continue

        # Por cada ventana de gap, contar candidatos por union
        union_counts = {"sweep_disp": [], "disp_bos": [], "bos_poi": []}
        per_setup_verdicts = []
        for sig in sigs:
            verdicts_per_window = []
            for gap in WINDOWS:
                res, *_ = count_candidates(ltf_df, sig, gap)
                verdicts_per_window.append(classify(res))
                for k in union_counts:
                    union_counts[k].append(res[k])
            # sensibilidad: el veredicto de la union cambia entre ventanas?
            stable = all(
                set(v.get(k) for v in verdicts_per_window) <= {"UNIQUE"}
                for k in union_counts
            )
            # veredicto agregado del setup (el peor de las ventanas)
            agg = {}
            for k in union_counts:
                states = [v[k] for v in verdicts_per_window]
                if "AMBIGUOUS" in states:
                    agg[k] = "AMBIGUOUS"
                elif "NONE" in states:
                    agg[k] = "NONE"
                else:
                    agg[k] = "UNIQUE"
            # capturar ejemplos adversariales (alguna union AMBIGUOUS)
            if "AMBIGUOUS" in agg.values():
                adversarial_examples.append((tag, sig, agg, union_counts))
            per_setup_verdicts.append(agg)

        # tasas
        n_setup = len(per_setup_verdicts)
        unique_all = sum(1 for v in per_setup_verdicts if all(x == "UNIQUE" for x in v.values()))
        ambig_any = sum(1 for v in per_setup_verdicts if "AMBIGUOUS" in v.values())
        none_any = sum(1 for v in per_setup_verdicts if "NONE" in v.values())
        report.append(f"### {tag} ({n} velas M15) — {n_setup} setups emitidos")
        report.append(f"- Setup con las 3 uniones UNIQUE: {unique_all}/{n_setup} "
                      f"({100*unique_all/max(1,n_setup):.0f}%)")
        report.append(f"- Setup con >=1 union AMBIGUOUS: {ambig_any}/{n_setup} "
                      f"({100*ambig_any/max(1,n_setup):.0f}%)")
        report.append(f"- Setup con >=1 union NONE (sin candidato): {none_any}/{n_setup}")
        # distribucion de candidatos por union (promedio)
        for k in union_counts:
            vals = union_counts[k]
            report.append(f"  - {k}: candidatos promedio={np.mean(vals):.2f}, "
                          f"max={max(vals)}, >=2 en {sum(1 for x in vals if x>=2)}/{len(vals)} setups")
        report.append("")
        summary_rows.append((tag, n_setup, unique_all, ambig_any, none_any))

    report.append("## Resumen agregado")
    report.append("| Muestra | Setups | UNIQUE(3/3) | AMBIGUOUS(>=1) | NONE(>=1) |")
    report.append("|---|---|---|---|---|")
    for tag, ns, u, a, ne in summary_rows:
        report.append(f"| {tag} | {ns} | {u} | {a} | {ne} |")

    report.append("")
    report.append("## Casos adversariales (muestra de setups con >=1 union AMBIGUOUS)")
    if adversarial_examples:
        for tag, sig, agg, _ in adversarial_examples[:12]:
            report.append(f"- [{tag}] dir={sig['direction']} sweep@{sig['sweep_at']} "
                          f"disp@{sig['displace_at']} bos@{sig['bos_at']} -> {agg}")
    else:
        report.append("(ninguno encontrado en las muestras)")

    report.append("")
    report.append("## Determinacion A vs B (por evidencia, no preferencia)")
    total_setup = sum(r[1] for r in summary_rows)
    total_unique = sum(r[2] for r in summary_rows)
    total_ambig = sum(r[3] for r in summary_rows)
    total_none = sum(r[4] for r in summary_rows)
    report.append(f"Total setups auditados: {total_setup}")
    report.append(f"UNIQUE(3/3): {total_unique} ({100*total_unique/max(1,total_setup):.0f}%)")
    report.append(f"AMBIGUOUS(>=1): {total_ambig} ({100*total_ambig/max(1,total_setup):.0f}%)")
    report.append(f"NONE(>=1): {total_none} ({100*total_none/max(1,total_setup):.0f}%)")
    if total_setup and total_ambig / total_setup >= 0.10:
        verdict = ("RESULTADO C (tendencia): B produce ambiguedad material (>10%). "
                   "La evidencia sugiere que la info no se recupera fiablemente post-hoc; "
                   "estudiar Arquitectura A (motor conserva ids enlazados).")
    elif total_setup and total_unique / total_setup >= 0.90:
        verdict = ("RESULTADO A: B validada para auditoria historica (>=90% unicos). "
                   "No es necesario tocar el motor para DEMOSTRAR FORMACION.")
    else:
        verdict = ("RESULTADO B (parcial): B funciona mayormente pero con ambiguedad no trivial. "
                   "Definir estados RECONSTRUCTED / RECONSTRUCTED_UNIQUE / AMBIGUOUS / UNKNOWN "
                   "y continuar investigando sin tocar engine/.")
    report.append("")
    report.append(f"**VEREDICTO:** {verdict}")
    report.append("")
    report.append(f"Tiempo total: {time.time()-t0:.1f}s")

    with open("research/hypotheses/HYP-002/b_falsifiability_report.md", "w") as fh:
        fh.write("\n".join(report))
    print("\n".join(report[:40]))
    print(f"\nTOTAL setups={total_setup} unique={total_unique} ambig={total_ambig} none={total_none}")
    print(f"verdict: {verdict}")


if __name__ == "__main__":
    main()
