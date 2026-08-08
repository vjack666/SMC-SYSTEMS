"""scripts/measure_ote_c.py — BASE (C): OTE mini-swing M5 vs rango HTF M15.

Reusa las 25 entries de (A) (results/funnel_authority_filter.json) y, para cada
una, calcula dos OTE en el momento de la entry:
  (1) OTE RANGO HTF: retroceso 0.62-0.79 sobre dealing range M15 (lookback=10).
  (2) OTE MINI-SWING M5: retroceso 0.62-0.79 sobre el ultimo swing M5 previo a
      la entry (rango del mini-swing interno).
Mide: ancho de cada zona y si la entry cae dentro de ambas. La base para decidir
si (C) mejora la precision de entrada.
Salida: results/ote_c_EURUSD.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from engine.dealing_range import DealingRangeConfig, compute_dealing_range
from engine.data_feed import load_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
OTE_LO, OTE_HI = 0.62, 0.79


def last_m5_swing_range(m5: pd.DataFrame, t_entry, bars=60) -> tuple[float, float] | None:
    """Rango del ultimo mini-swing M5 antes de t_entry (ventana 'bars' velas)."""
    win = m5[m5["time"] <= t_entry].tail(bars)
    if len(win) < 5:
        return None
    # Swing = max/min del tramo previo al cierre (geometria pura).
    return float(win["low"].min()), float(win["high"].max())


def ote_zone(lo: float, hi: float, direction: int) -> tuple[float, float]:
    """Retroceso OTE 0.62-0.79 sobre [lo,hi]. direction +1 alcista (descuento),
    -1 bajista (premium)."""
    span = hi - lo
    if direction > 0:  # OTE_LONG en descuento: desde lo hacia hi
        return lo + OTE_LO * span, lo + OTE_HI * span
    else:  # OTE_SHORT en premium: desde hi hacia lo
        return hi - OTE_HI * span, hi - OTE_LO * span


def main() -> None:
    with open(os.path.join(RESULTS, "funnel_authority_filter.json")) as f:
        data = json.load(f)
    entries = data.get("detalle", [])
    ms = load_frames("EURUSD", timeframes=("M15", "M5"))
    m15, m5 = ms["M15"], ms["M5"]

    rows = []
    for ts_str, lvl, *_ in entries:
        t = pd.Timestamp(ts_str)
        direction = 1 if lvl in ("Alta", "Media") else -1  # autoridad ~ direccion sesgo
        # (1) OTE rango HTF M15 (lookback=10 antes de la entry)
        win15 = m15[m15["time"] <= t].tail(10)
        if len(win15) < 3:
            continue
        dr = compute_dealing_range(win15, config=DealingRangeConfig(lookback=10))
        rh, rl = float(dr["range_high"].iloc[-1]), float(dr["range_low"].iloc[-1])
        z_htf = ote_zone(rl, rh, direction)
        # (2) OTE mini-swing M5
        sw = last_m5_swing_range(m5, t, bars=60)
        if sw is None:
            continue
        sl, sh = sw
        z_m5 = ote_zone(sl, sh, direction)
        # nivel de entry aproximado: close de la vela M15 en t
        row_m15 = m15[m15["time"] == t]
        entry_px = float(row_m15["close"].iloc[-1]) if len(row_m15) else float(win15["close"].iloc[-1])
        in_htf = z_htf[0] <= entry_px <= z_htf[1]
        in_m5 = z_m5[0] <= entry_px <= z_m5[1]
        width_htf = z_htf[1] - z_htf[0]
        width_m5 = z_m5[1] - z_m5[0]
        rows.append({
            "ts": ts_str, "direction": direction,
            "entry_px": round(entry_px, 5),
            "ote_htf": [round(z_htf[0], 5), round(z_htf[1], 5)],
            "ote_m5": [round(z_m5[0], 5), round(z_m5[1], 5)],
            "width_htf": round(width_htf, 5),
            "width_m5": round(width_m5, 5),
            "in_htf": bool(in_htf), "in_m5": bool(in_m5),
        })

    n = len(rows)
    avg_w_htf = sum(r["width_htf"] for r in rows) / n if n else 0
    avg_w_m5 = sum(r["width_m5"] for r in rows) / n if n else 0
    pct_in_htf = round(100.0 * sum(1 for r in rows if r["in_htf"]) / n, 1) if n else 0
    pct_in_m5 = round(100.0 * sum(1 for r in rows if r["in_m5"]) / n, 1) if n else 0
    pct_in_both = round(100.0 * sum(1 for r in rows if r["in_htf"] and r["in_m5"]) / n, 1) if n else 0

    out = {
        "symbol": "EURUSD", "m5_within_m15": True,
        "ote_retrace": [OTE_LO, OTE_HI],
        "n_entries": n,
        "avg_width_htf": round(avg_w_htf, 5),
        "avg_width_m5": round(avg_w_m5, 5),
        "width_ratio_htf_over_m5": round(avg_w_htf / avg_w_m5, 2) if avg_w_m5 else 0,
        "pct_entry_in_htf": pct_in_htf,
        "pct_entry_in_m5": pct_in_m5,
        "pct_entry_in_both": pct_in_both,
        "rows": rows,
    }
    path = os.path.join(RESULTS, "ote_c_EURUSD.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[C] entries={n}  ancho HTF={avg_w_htf:.5f}  M5={avg_w_m5:.5f}  "
          f"ratio={out['width_ratio_htf_over_m5']}x")
    print(f"[C] entry en HTF={pct_in_htf}%  en M5={pct_in_m5}%  en ambos={pct_in_both}%")
    print(f"[C] guardado: {path}")


if __name__ == "__main__":
    main()
