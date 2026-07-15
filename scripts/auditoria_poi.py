"""scripts/auditoria_poi.py — Auditoria EMPIRICA del POI HTF (sin tocar el sistema).

NO modifica el sistema. Mide, caso por caso, que el POI que el sistema
marca como "POI HTF" coincida con la definicion de la biblioteca ICT.

Para cada zona LTF que run_sequence intenta validar, registramos el POI
HTF que el filtro hubiera exigido y lo clasificamos:
  - tipo: FVG | OB
  - dir:  bullish | bearish
  - precio (mid del POI)
  - edad_en_velas_H4 (que tan "fresco" esta)
  - tiene_narrativa: ¿hay un BOS/swing en esa direccion en el HTF cerca?
    (proxy de "este POI pertenece a ESTA historia", no es geometria suelta)
  - es_el_ultimo_OB/FVG institucional: ¿es el mas reciente sin invalidar?

Al final: conteo por clase + 20 ejemplos crudos para revision humana.
"""
from __future__ import annotations

import sys, time, json, gc
import numpy as np
import pandas as pd

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig

HTF, LTF = "H4", "M15"
CFG = SequenceConfig(counter_trend=True, tp_mode="fixed2r", require_displacement=True)


def _row_at_time(df, t):
    times = df["time"].to_numpy()
    idx = int(np.searchsorted(times, t, side="right") - 1)
    idx = max(0, min(idx, len(df) - 1))
    return df.iloc[idx]


def _has_htf_narrative(htf_df, idx, target):
    """Proxy ICT: ¿hay un BOS en la direccion del trade en el HTF en las
    ultimas 40 velas H4 (10 dias)? Un POI 'de narrativa' vive despues de un
    desplazamiento estructural, no suelto."""
    lo = max(0, idx - 40)
    chunk = htf_df.iloc[lo:idx + 1]
    if target == 1:
        return bool(chunk.get("bos_bullish", pd.Series([False] * len(chunk))).fillna(False).any())
    return bool(chunk.get("bos_bearish", pd.Series([False] * len(chunk))).fillna(False).any())


def run_audit(symbol):
    print(f"===== AUDITORIA POI HTF — {symbol} ({HTF}->{LTF}) =====", flush=True)
    tfs = tuple(dict.fromkeys([HTF, LTF, "D1"]))
    frames = load_frames(symbol, tfs)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[LTF]
    htf_df = ms.get(HTF, ltf_df)

    # Normalizar zona horaria en 'time' para que searchsorted no falle
    # (load_frames puede devolver LTF tz-aware y HTF tz-naive o viceversa).
    def _tznorm(df):
        col = df["time"]
        if getattr(col.dt, "tz", None) is None:
            col = col.dt.tz_localize("UTC")
        else:
            col = col.dt.tz_convert("UTC")
        df = df.copy()
        df["time"] = col
        return df
    ltf_df = _tznorm(ltf_df)
    htf_df = _tznorm(htf_df)

    htf_times = list(htf_df["time"].to_numpy())
    def _col(name):
        if name in htf_df.columns:
            return htf_df[name].fillna(False).to_numpy()
        return np.zeros(len(htf_df), dtype=bool)
    fvb = _col("fvg_bullish"); fve = _col("fvg_bearish")
    obb = _col("ob_bullish"); obe = _col("ob_bearish")
    fvg_mid = htf_df["fvg_mid"].fillna(0.0).to_numpy() if "fvg_mid" in htf_df.columns else np.zeros(len(htf_df))
    ob_top = htf_df["ob_top"].to_numpy() if "ob_top" in htf_df.columns else np.zeros(len(htf_df))
    ob_bot = htf_df["ob_bottom"].to_numpy() if "ob_bottom" in htf_df.columns else np.zeros(len(htf_df))
    POI_WINDOW = 20

    records = []

    def htf_poi_fn(i, target):
        t = ltf_df.iloc[i]["time"]
        idx = int(np.searchsorted(htf_times, t, side="right") - 1)
        if idx < 0:
            return False
        lo = max(0, idx - POI_WINDOW)
        if target == 1:
            hits = np.where(fvb[lo:idx + 1] | obb[lo:idx + 1])[0]
        else:
            hits = np.where(fve[lo:idx + 1] | obe[lo:idx + 1])[0]
        if len(hits) == 0:
            return False
        j = lo + int(hits[-1])  # el mas reciente en la ventana
        is_fvg = bool(fvb[j] or fve[j])
        ptype = "FVG" if is_fvg else "OB"
        pdir = "bullish" if (fvb[j] or obb[j]) else "bearish"
        price = float(fvg_mid[j]) if is_fvg else float((ob_top[j] + ob_bot[j]) / 2.0)
        age = idx - j
        narr = _has_htf_narrative(htf_df, idx, target)
        records.append({
            "ltf_idx": int(i), "htf_idx": int(j), "tipo": ptype, "dir": pdir,
            "precio": round(price, 5), "edad_h4": int(age),
            "tiene_narrativa": bool(narr),
            "fecha_ltf": str(ltf_df.iloc[i]["time"]),
        })
        return True  # NO bloqueamos: solo registramos

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    raw_sigs, phases = run_sequence(ltf_df, est_htf_fn, CFG,
                                    htf_poi_fn=htf_poi_fn)
    print(f"  zonas LTF evaluadas por el filtro POI: {len(records)}", flush=True)

    df = pd.DataFrame(records)
    total = len(df)
    por_tipo = df["tipo"].value_counts().to_dict() if total else {}
    con_narr = int(df["tiene_narrativa"].sum()) if total else 0
    sin_narr = total - con_narr
    edad_med = float(df["edad_h4"].median()) if total else 0.0
    fresco = int((df["edad_h4"] <= 5).sum()) if total else 0

    summary = {
        "symbol": symbol,
        "total_zonas_poi": total,
        "por_tipo": por_tipo,
        "con_narrativa": con_narr,
        "sin_narrativa": sin_narr,
        "pct_sin_narrativa": round(100.0 * sin_narr / total, 1) if total else 0.0,
        "edad_mediana_h4": round(edad_med, 1),
        "frescos_edad_<=5": fresco,
        "hipotesis_a_auditar": (
            "Si pct_sin_narrativa es ALTO, el sistema marca como POI "
            "geometria suelta (FVG/OB cualquiera) sin narrativa ICT -> "
            "coincide con la sospecha: 'todo FVG H4 = POI'."
        ),
    }
    print(json.dumps(summary, indent=2, default=str), flush=True)

    sample = df.head(20).to_dict(orient="records") if total else []
    print("\n--- 20 EJEMPLOS CRUDOS (revision humana vs biblioteca ICT) ---", flush=True)
    for k, r in enumerate(sample, 1):
        print(f"{k:2d}. {r['fecha_ltf']} | {r['tipo']} {r['dir']} | "
              f"precio={r['precio']} | edad={r['edad_h4']} velas H4 | "
              f"narrativa_HTF={r['tiene_narrativa']}", flush=True)
    return summary, sample


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    s, samp = run_audit(sym)
    out = ROOT / "tests" / "auditoria_poi.json"
    out.write_text(json.dumps({"summary": s, "ejemplos": samp}, indent=2, default=str),
                   encoding="utf-8")
    print(f"\n  -> guardado en {out}", flush=True)
