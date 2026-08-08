"""scripts/measure_motor_veltick.py — BASE de datos vela a vela del motor (tarea D).

Recorre EURUSD M15 de a una vela (reloj del motor) y, en cada cierre H4, calcula
el sesgo HTF con compute_htf_bias(exp012=True) [GATE DURO de hoy] y en la ventana
M15 rodante cuenta CHOCH canonicos vs EXP-012 reales. Registra el sesgo por barra
H4 y el % de barras en NEUTRAL. Sirve de BASE para que el consejo de agentes
decida el camino (medir cuanto empeora el sesgo NEUTRAL en rangos con gate duro).

Uso 1 mes de M15 (regla SMC: backtests >~1 mes mueren por SIGTERM).
Salida: results/motor_veltick_EURUSD_M15.json
"""
from __future__ import annotations

import json
import os
import time as _time

import numpy as np
import pandas as pd

from engine.bias.narrative import NEUTRAL, compute_htf_bias
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.data_feed import load_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
os.makedirs(RESULTS, exist_ok=True)

SYMBOL = "EURUSD"
WINDOW_M15 = 300  # ventana rodante M15 para contar CHOCH
MONTHS = 1


def main() -> None:
    ms = load_frames(SYMBOL, timeframes=("D1", "H4", "H1", "M15"))
    d1, h4, h1, m15 = ms["D1"], ms["H4"], ms["H1"], ms["M15"]
    # 1 mes de M15 aprox
    n_m15 = min(len(m15), int( MONTHS * 30 * 24 * 4))
    m15 = m15.head(n_m15).reset_index(drop=True)
    # Recorta los TF padre al MISMO rango de 1 mes que M15 (evita iterar sobre
    # todo el historico de H4/D1 y disparar el tiempo de ejecucion).
    t_max = m15["time"].iloc[-1]
    d1 = d1[d1["time"] <= t_max].reset_index(drop=True)
    h4 = h4[h4["time"] <= t_max].reset_index(drop=True)
    h1 = h1[h1["time"] <= t_max].reset_index(drop=True)

    t0 = _time.perf_counter()
    rows = []
    # Ordenados por time; uso searchsorted por posicion (O(log n)) en vez de
    # filtro booleano O(n) por barra -> evita el cuello de botella.
    d1_t = d1["time"].to_numpy()
    h4_t = h4["time"].to_numpy()
    h1_t = h1["time"].to_numpy()
    m15_t = m15["time"].to_numpy()
    # Muestreo: 1 barra H4 cada STEP (aprox 1/dia) para acelerar la base.
    STEP = 4
    for k in range(0, len(h4_t), STEP):
        ts = h4_t[k]
        pd1 = int(np.searchsorted(d1_t, ts, side="right"))
        ph4 = int(np.searchsorted(h4_t, ts, side="right"))
        ph1 = int(np.searchsorted(h1_t, ts, side="right"))
        pm15 = int(np.searchsorted(m15_t, ts, side="right"))
        if pd1 < 2 or ph4 < 2 or ph1 < 2 or pm15 < 5:
            continue
        d1_c = d1.iloc[:pd1]
        h4_c = h4.iloc[:ph4]
        h1_c = h1.iloc[:ph1]
        m15_c = m15.iloc[:pm15]
        # CAMINO B: el SESGO es canonico SIEMPRE (inmune al gate). Se mide una
        # sola vez. La estructura LTF (ventana M15) SI aplica el gate.
        bias = compute_htf_bias(d1_c, h4_c, h1_c)
        # CHOCH en ventana M15 rodante: canonico vs gate duro (estructura LTF)
        win = m15_c.tail(WINDOW_M15)
        fr_on = detect_market_structure(win, StructureConfig(exp012_choch=True)).frame
        fr_off = detect_market_structure(win).frame
        n_choch = int((fr_off["choch_dir"] != 0).sum())
        n_exp = int((fr_on["choch_dir"] != 0).sum())
        rows.append({
            "ts": str(pd.Timestamp(ts)),
            "direction": bias.direction,
            "aligned": bool(bias.aligned),
            "neutral": bias.direction == NEUTRAL,
            "choch_canon": n_choch,
            "choch_exp012": n_exp,
        })
    dt = _time.perf_counter() - t0

    n = len(rows)
    def pct(key):
        return round(100.0 * sum(1 for r in rows if r[key]) / n, 2) if n else 0.0
    avg_exp = sum(r["choch_exp012"] for r in rows) / n if n else 0
    avg_can = sum(r["choch_canon"] for r in rows) / n if n else 0

    out = {
        "symbol": SYMBOL,
        "tf": "M15",
        "months": MONTHS,
        "gate": "camino_B: sesgo canonico inmune, gate solo LTF",
        "n_h4_bars": n,
        "pct_neutral": pct("neutral"),
        "pct_aligned": pct("aligned"),
        "avg_choch_canon_per_window": round(avg_can, 3),
        "avg_choch_exp012_per_window": round(avg_exp, 3),
        "elapsed_s": round(dt, 2),
        "rows": rows,
    }
    path = os.path.join(RESULTS, f"motor_veltick_{SYMBOL}_M15.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"[base] barras H4={n}  NEUTRAL={out['pct_neutral']}%  ALIGNED={out['pct_aligned']}%")
    print(f"[base] CHOCH/ventana canonico={avg_can:.2f}  exp012(LTF gate)={avg_exp:.2f}  "
          f"(drop {100*(1-avg_exp/avg_can):.1f}%)")
    print(f"[base] guardado: {path}  ({dt:.1f}s)")


if __name__ == "__main__":
    main()
