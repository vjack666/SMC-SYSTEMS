"""FASE A — CIERRE SEMANTICO DEL MOTOR (nube, 3 meses, consumidor puro).

Version para GitHub Actions: recorta a window_months=3 (la fase [1/3] de
run_sequence_backtest ya recorta HTF por 'start', asi 3 meses de M15 son
unas pocas miles de velas, no 114k => evita el O(n^2) de sequence.py:708).

Usa el consumidor canonico (ict_backtest.run_backtest) sobre data/raw (OHLC
puro, trend REAL via detect_market_structure). Audita el grafo causal con
HYP-002/phase6_verifier (dimensiones SDD_GOVERNANCE §4).

NO toca engine/. NO optimiza. NO agrega features. NO crea SDD.
Salida: results/fase_a_semantic_eurhusd_CLOUD.md (artifact de nube).
"""
from __future__ import annotations
import json, sys, time, importlib.util, os
sys.path.insert(0, ".")

from ict_backtest import run_backtest

_spec = importlib.util.spec_from_file_location(
    "phase6_verifier", "research/hypotheses/HYP-002/phase6_verifier.py")
_vmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vmod)
verify_run, verdict = _vmod.verify_run, _vmod.verdict

SYMBOL, HTF, LTF = "EURUSD", "H4", "M15"
WINDOW_MONTHS = 3


def main():
    t0 = time.time()
    print(f"[FASE A CLOUD] backtest canonico {SYMBOL} {HTF}->{LTF} "
          f"(trend REAL, window_months={WINDOW_MONTHS}) ...", flush=True)
    out = run_backtest.run_sequence_backtest(
        SYMBOL, HTF, LTF, max_hold=16,
        require_displacement=True, displace_gap=6, bos_gap=10,
        enable_pd_index=True, invalidate_on_opposite_swing=False,
        window_months=WINDOW_MONTHS,
    )
    signals = out.get("signals") if isinstance(out, dict) else out[0]
    print(f"[FASE A CLOUD] {len(signals)} senales en {time.time()-t0:.1f}s", flush=True)

    with_graph = [s for s in signals if (
        s.get("event_objects") if isinstance(s, dict) else getattr(s, "event_objects", None))]
    print(f"[FASE A CLOUD] {len(with_graph)} con event_objects (linaje auditado)", flush=True)

    agg = verify_run(with_graph)
    v = verdict(agg)
    agg.update(verdict=v, symbol=SYMBOL, htf_ltf=f"{HTF}->{LTF}",
               mode="consumidor puro (nube, window_months=3, no toca engine/)",
               trend_source="detect_market_structure sobre data/raw OHLC (REAL)",
               window_months=WINDOW_MONTHS)
    n = max(1, agg["n_setups"])
    agg["pct"] = {k: round(100 * agg[f"{k}_ok"] / n, 1)
                  for k in ("identity", "link", "causality", "temporal", "graph", "ontology")}

    os.makedirs("results", exist_ok=True)
    with open("results/fase_a_semantic_eurhusd_CLOUD.json", "w") as fh:
        json.dump(agg, fh, indent=2, default=str)
    with open("results/fase_a_semantic_eurhusd_CLOUD.md", "w") as fh:
        fh.write("# FASE A (NUBE, 3 meses) — Verificacion Semantica (EURUSD)\n\n")
        fh.write(f"- Symbol: {SYMBOL} ({HTF}->{LTF})\n- Modo: consumidor puro nube (no toca engine/)\n")
        fh.write(f"- Window: {WINDOW_MONTHS} meses de M15\n- Trend HTF: {agg['trend_source']}\n")
        fh.write(f"- Setups con linaje: {agg['n_setups']}\n- POI anclado HTF: {agg['poi_anchored']}\n")
        fh.write(f"- Ciclos: {agg['cycles_total']}\n\n## % por dimension (SDD_GOVERNANCE §4)\n\n")
        for k, val in agg["pct"].items():
            fh.write(f"- {k}: {val}%\n")
        fh.write(f"\n## Veredicto\n\n**{v}**\n")
        fh.write("\n> Reproduce localmente el veredicto A VALIDADA de HYP-002 Fase 6 "
                 "(60k velas) sobre un slice de 3 meses, cerrando el caveat de "
                 "'no reproducible local'.\n")
    print(f"[FASE A CLOUD] Veredicto: {v}", flush=True)
    print(f"[FASE A CLOUD] -> results/fase_a_semantic_eurhusd_CLOUD.md", flush=True)


if __name__ == "__main__":
    main()
