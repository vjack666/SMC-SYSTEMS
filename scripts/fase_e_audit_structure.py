"""Fase E — Auditoría ESTRUCTURAL (NO optimización).

Objetivo (Ruben 2026-07-18): verificar que el motor INTERPRETA la tesis ICT
(libros 18 y 21) correctamente trade por trade, antes de correr una muestra
grande. NO ajusta parámetros, RR ni filtros. Solo detecta errores de
cableado / interpretación / simulación en el contexto almacenado.

Validaciones contra la tesis:
- Tesis 18 contrato #3: SL estructural SIEMPRE en exec TF.
- Libro 21 §0: POI bearish debe estar en PREMIUM (short), bullish en DISCOUNT
  (long). Wrong-side = zona opuesta al dealing range.
- Tesis 18 §1: lectura top-down HTF->ITF->LTF; el LTF debe coincidir con el HTF.
- Libro 21 §4: POI anclado a narrativa HTF (has_htf_anchor) debe tener PD Array
  real en H4 (no UNKNOWN).

Cada trade produce un dict de flags; se agregan y se imprime un reporte.
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ict_backtest.diagnostics.trade_context import TradeContext  # noqa: E402


def _mc_from_dict(d: dict) -> dict:
    out = {}
    for tf, v in (d.get("market_context") or {}).items():
        if isinstance(v, str):
            import re
            f = dict(re.findall(r"(\w+)='([^']*)'", v))
            out[tf] = f
        else:
            out[tf] = v
    return out


def audit_trade(c: dict) -> dict:
    """Devuelve {flag: bool/str} por trade. Solo lectura."""
    flags = {}
    direction = c.get("direction", 0)
    mc = _mc_from_dict(c)
    d1 = mc.get("D1", {})
    h4 = mc.get("H4", {})
    h1 = mc.get("H1", {})
    m15 = mc.get("M15", {})
    m5 = mc.get("M5", {})
    m1 = mc.get("M1", {})

    # 1) SL estructural (tesis 18 #3)
    flags["sl_no_estructural"] = (c.get("sl_is_structural") is not True)

    # 2) dist_entry_to_sl_r > 0 (si 0.0 => SL no calculado)
    d = c.get("dist_entry_to_sl_r", 0.0)
    flags["sl_dist_cero"] = (d is None or d == 0.0)

    # 3) Zona wrong-side vs dirección (libro 21 §0)
    pd = (d1.get("premium_discount") or "").upper()
    if direction < 0:  # short => debe estar en PREMIUM
        flags["zona_wrong_side"] = (pd == "DISCOUNT")
    elif direction > 0:  # long => debe estar en DISCOUNT
        flags["zona_wrong_side"] = (pd == "PREMIUM")
    else:
        flags["zona_wrong_side"] = False

    # 4) Setup ICT materializado en M15 (sweep+displacement+fvg => setup != NONE)
    has_sweep = (m15.get("setup_sweep") or "NONE") != "NONE"
    has_fvg = (m15.get("setup_fvg") or "NONE") not in ("NONE", "-", "")
    setup_cls = (m15.get("setup") or "NONE")
    flags["setup_no_clasificado"] = (has_sweep and has_fvg and setup_cls == "NONE")

    # 5) POI anclado debe tener PD Array real en H4 (no UNKNOWN)
    za = c.get("zone_authority") or {}
    anchored = za.get("has_htf_anchor") is True
    h4_poi = (h4.get("poi") or "UNKNOWN").upper()
    flags["ancla_sin_poi_real"] = (anchored and h4_poi in ("UNKNOWN", "MISSING", ""))

    # 6) Confirmación exec TF coherente con dirección
    m5_conf = (m5.get("confirmation") or "MISSING").upper()
    m1_conf = (m1.get("confirmation") or "MISSING").upper()
    if direction < 0:
        flags["conf_no_bearish"] = (m5_conf != "BEARISH" and m1_conf != "BEARISH")
    elif direction > 0:
        flags["conf_no_bullish"] = (m5_conf != "BULLISH" and m1_conf != "BULLISH")
    else:
        flags["conf_no_bearish"] = flags["conf_no_bullish"] = False

    # 7) Bias top-down: H4/H1 no deben estar todos opuestos a direction
    if direction < 0:
        htfs = [(h4.get("bias") or ""), (h1.get("bias") or "")]
        flags["htf_contra_direccion"] = all(b.upper() == "BULLISH" for b in htfs)
    elif direction > 0:
        htfs = [(h4.get("bias") or ""), (h1.get("bias") or "")]
        flags["htf_contra_direccion"] = all(b.upper() == "BEARISH" for b in htfs)
    else:
        flags["htf_contra_direccion"] = False

    return flags


FLAG_LABELS = {
    "sl_no_estructural": "SL no es estructural (tesis 18 #3)",
    "sl_dist_cero": "dist_entry_to_sl_r = 0.0 (SL no calculado)",
    "zona_wrong_side": "Zona wrong-side vs dirección (libro 21 §0)",
    "setup_no_clasificado": "M15 con sweep+FVG pero setup=NONE",
    "ancla_sin_poi_real": "POI anclado pero H4 poi UNKNOWN",
    "conf_no_bearish": "Short sin confirmación BEARISH en M5/M1",
    "conf_no_bullish": "Long sin confirmación BULLISH en M5/M1",
    "htf_contra_direccion": "HTF (H4/H1) opuesto a dirección",
}


def main():
    path = ROOT / "results/backtests/2026-07-18_6m_mtf/EURUSD/contexts.json"
    data = json if False else None  # noqa
    import json
    ctxs = json.load(open(path))
    print(f"=== AUDITORIA ESTRUCTURAL (tesis 18/21) ===")
    print(f"contexts: {len(ctxs)}\n")

    agg = Counter()
    trade_flags = []
    for i, c in enumerate(ctxs):
        fl = audit_trade(c)
        hits = [k for k, v in fl.items() if v]
        for k in hits:
            agg[k] += 1
        trade_flags.append((i, c.get("trade_id"), hits))
        if hits:
            print(f"[trade {i:02d}] {c.get('trade_id')} dir={c.get('direction')} "
                  f"-> {', '.join(hits)}")

    print("\n=== RESUMEN (n trades con flag / 36) ===")
    for k in FLAG_LABELS:
        n = agg.get(k, 0)
        mark = "!!" if n > 0 else "ok"
        print(f"  [{mark}] {FLAG_LABELS[k]}: {n}/36")

    print("\n=== INTERPRETACION (no optimización) ===")
    if agg.get("sl_no_estructural") or agg.get("sl_dist_cero"):
        print("  - SL: el contrato 18 #3 (SL estructural en exec TF) NO se cumple en "
              "todos los trades. Revisar calc_structural_sl / congelado de dist_entry_to_sl_r.")
    if agg.get("zona_wrong_side"):
        print("  - Zona wrong-side: opera en discount para shorts / premium para longs "
              "(libro 21 §0). El filtro de dealing range NO está bloqueando entradas invalidas.")
    if agg.get("setup_no_clasificado"):
        print("  - Setup M15 no clasificado pese a tener sweep+FVG: la deteccion de "
              "estructura ICT no se materializa en el campo 'setup'.")
    if agg.get("ancla_sin_poi_real"):
        print("  - Ancla HTF declarada pero H4 poi UNKNOWN: incoherencia Fase C vs contexto.")
    if agg.get("conf_no_bearish") or agg.get("conf_no_bullish"):
        print("  - Confirmacion exec TF no coincide con direccion: el LTF no valida el HTF.")
    if agg.get("htf_contra_direccion"):
        print("  - HTF opuesto a direccion: lectura NO es top-down coherente (tesis 18 §1).")


if __name__ == "__main__":
    main()
