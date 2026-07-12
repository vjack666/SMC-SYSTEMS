"""Compara el motor VIVO CON vs SIN el filtro choch_bos_confirm (libro 02 §3.1).

No usa optimize.py (ese camino no ejercita pipeline.py). Aqui corremos
build_scalping_context directo, variando el peso del filtro, y medimos:
  - n de senales
  - PF naive (SL/TP = 2xATR, igual que build_scalping_signals)
  - WR%
con barra de progreso por vela + tiempo de carga + ETA de barrido.

Uso: python scripts/compare_choch_bos_confirm.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from signals.pipeline import build_scalping_context, ScalpingConfig


def _naive_pf(signals: list, ctx: pd.DataFrame, max_hold: int = 96) -> dict:
    """PF/WR naive: por cada senal, avanza hasta tocar SL o TP (2xATR)."""
    if not signals:
        return {"trades": 0, "pf": 0.0, "wr": 0.0}
    # indice por tiempo para busqueda rapida
    times = ctx["time"].astype(str).tolist()
    tpos = {t: i for i, t in enumerate(times)}
    wins = 0
    gross = 0.0
    for s in signals:
        i = tpos.get(str(s.time))
        if i is None:
            continue
        entry = s.entry
        sl = s.stop_loss
        tp = s.take_profit
        direction = s.direction
        hit = None
        for j in range(i + 1, min(i + 1 + max_hold, len(ctx))):
            hi = float(ctx["high"].iloc[j])
            lo = float(ctx["low"].iloc[j])
            if direction == 1:
                if lo <= sl:
                    hit = -1.0
                    break
                if hi >= tp:
                    hit = 1.0
                    break
            else:
                if hi >= sl:
                    hit = -1.0
                    break
                if lo <= tp:
                    hit = 1.0
                    break
        if hit is None:
            # vencimiento: cierra al close de la ultima vela de hold
            close_end = float(ctx["close"].iloc[min(i + max_hold, len(ctx) - 1)])
            hit = 1.0 if (close_end - entry) * direction > 0 else -1.0
        gross += hit
        if hit > 0:
            wins += 1
    trades = len(signals)
    pf = gross / max(1, trades - wins) if (trades - wins) > 0 else (gross if gross > 0 else 0.0)
    return {"trades": trades, "pf": round(pf, 3), "wr": round(100.0 * wins / trades, 1)}


def _run(symbol: str, weight: float, gate: bool, max_hold: int = 96) -> dict:
    cfg = ScalpingConfig(mandatory_choch_bos_confirm=gate)
    cfg.confluence_weights["choch_bos_confirm"] = weight  # muta el dict (no reasigna attr)
    t0 = time.time()
    ctx = build_scalping_context(symbol=symbol, timeframe="M15", config=cfg)
    load_s = time.time() - t0

    n = len(ctx)
    sigs = []
    t0 = time.time()
    # barra de progreso por bloques de 5000 velas
    block = 5000
    for start in range(0, n, block):
        end = min(start + block, n)
        chunk = ctx.iloc[start:end]
        valid = chunk[(chunk["signal_direction"] != 0)]
        for _, row in valid.iterrows():
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            direction = int(row["signal_direction"])
            entry = float(row["close"])
            sl = entry - atr if direction == 1 else entry + atr
            tp = entry + 2.0 * atr if direction == 1 else entry - 2.0 * atr
            sigs.append(type("S", (), {
                "time": str(row["time"]),
                "direction": direction,
                "entry": entry,
                "stop_loss": sl,
                "take_profit": tp,
            })())
        done = end
        pct = 100.0 * done / n
        barra = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
        eta = (time.time() - t0) / max(1, done) * (n - done)
        print(f"  [{barra}] {pct:5.1f}% | velas {done}/{n} | ETA {eta:.1f}s", flush=True)

    scan_s = time.time() - t0
    stats = _naive_pf(sigs, ctx, max_hold)
    return {"weight": weight, "load_s": round(load_s, 1), "scan_s": round(scan_s, 1),
            "signals": len(sigs), **stats}


def main() -> None:
    symbol = "EURUSD"
    print(f"== Compara choch_bos_confirm en {symbol} M15 ==", flush=True)
    print("[1/2] SIN filtro (peso 0.0, gate OFF)...", flush=True)
    sin = _run(symbol, 0.0, False)
    print(f"    -> senales={sin['signals']} PF={sin['pf']} WR={sin['wr']}% "
          f"(carga {sin['load_s']}s, barrido {sin['scan_s']}s)", flush=True)
    print("[2/2] CON filtro (peso 2.0, gate ON)...", flush=True)
    con = _run(symbol, 2.0, True)
    print(f"    -> senales={con['signals']} PF={con['pf']} WR={con['wr']}% "
          f"(carga {con['load_s']}s, barrido {con['scan_s']}s)", flush=True)
    print("\n===== Veredicto =====", flush=True)
    print(f"  SIN filtro : {sin['signals']:5d} senales | PF {sin['pf']} | WR {sin['wr']}%")
    print(f"  CON filtro : {con['signals']:5d} senales | PF {con['pf']} | WR {con['wr']}%")
    delta_pf = con["pf"] - sin["pf"]
    delta_wr = con["wr"] - sin["wr"]
    print(f"  Delta PF   : {delta_pf:+.3f}  |  Delta WR: {delta_wr:+.1f} pp")
    print("  (si delta>0 y PF sigue >1.0 -> el filtro ayuda; si empeora, bajar peso a 0)", flush=True)


if __name__ == "__main__":
    main()
