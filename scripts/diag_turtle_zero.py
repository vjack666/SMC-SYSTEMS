"""scripts/diag_turtle_zero.py — Aisla por que Turtle Soup alineado da 0 senales.

No toca run_backtest. Replica el tramo BOS_DONE -> ENTRY del run_sequence
usando las MISMAS funciones de ict_backtest/sequence.py, e instrumenta:
  - cuantas BOS formaron cuadro (FVG / OB / fallback bos+-ATR)
  - de esas, cuantas veces el precio retorno al cuadro en bos_gap velas
  - si el problema es el killzone (lo medimos aparte) o el retorno.

Uso: C:/Python314/python.exe scripts/diag_turtle_zero.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import (run_sequence, SequenceConfig, _row_at_time,
                                   _latest_fvg_zone, _latest_ob_zone, _touches_zone)
from ict_backtest.rules import killzone_en


def main() -> None:
    symbol, htf, ltf = "EURUSD", "H4", "M15"
    tfs = tuple(dict.fromkeys([htf, ltf, "D1"]))
    frames = load_frames(symbol, tfs)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    # 1) Correr run_sequence tal cual (camino alineado ya usa sequence.py).
    raw_sigs, phases = run_sequence(ltf_df, est_htf_fn,
                                    SequenceConfig(counter_trend=True,
                                                   tp_mode="fixed2r",
                                                   require_displacement=True))
    print(f"[run_sequence] fases: {phases}  -> senales ENTRY: {len(raw_sigs)}")

    # 2) Re-walk manual del tramo BOS_DONE -> ENTRY para contar TOQUES al cuadro.
    cfg = SequenceConfig(counter_trend=True, tp_mode="fixed2r",
                         require_displacement=True)
    n_bos = 0
    bos_fvg = bos_ob = bos_fallback = 0
    touched = 0
    touched_in_kz = 0
    for i in range(len(ltf_df)):
        row = ltf_df.iloc[i]
        est = est_htf_fn(i)
        bias = str(est.get("trend", "RANGING"))
        if bias not in ("BULLISH", "BEARISH"):
            continue
        target = -1 if bias == "BULLISH" else 1  # contratendencia
        # Detectar BOS en esta vela (reusa la logica de _has_bos opuesta al HTF)
        from ict_backtest.sequence import _has_bos
        if not _has_bos(row, est, target, True):
            continue
        n_bos += 1
        # Trazar cuadro igual que run_sequence (FVG > OB > fallback bos+-0.5ATR)
        fvg = _latest_fvg_zone(row, target)
        ob = _latest_ob_zone(row, target)
        if fvg is not None:
            zh, zl = fvg
            bos_fvg += 1
        elif ob is not None:
            zh, zl = ob
            bos_ob += 1
        else:
            atr = float(row.get("atr", float("nan")))
            bos_lvl = float(row.get("bos_level", float("nan")))
            if pd.isna(atr) or pd.isna(bos_lvl):
                continue
            zh = bos_lvl + 0.5 * atr
            zl = bos_lvl - 0.5 * atr
            bos_fallback += 1
        # Buscar retorno en las proximas bos_gap velas
        hit = False
        for j in range(i + 1, min(i + 1 + cfg.bos_gap, len(ltf_df))):
            if _touches_zone(ltf_df.iloc[j], zh, zl):
                hit = True
                kz = killzone_en(pd.to_datetime(ltf_df.iloc[j]["time"], utc=True))
                if kz in ("London Open", "New York AM", "New York PM"):
                    touched_in_kz += 1
                break
        if hit:
            touched += 1

    print(f"\n[re-walk BOS->ENTRY]")
    print(f"  BOS totales      : {n_bos}")
    print(f"  cuadro FVG       : {bos_fvg}")
    print(f"  cuadro OB        : {bos_ob}")
    print(f"  cuadro fallback  : {bos_fallback}")
    print(f"  RETORNO al cuadro: {touched}")
    print(f"  de esos, EN KZ   : {touched_in_kz}")
    if n_bos and touched == 0:
        print("\n  >>> DIAGNOSTICO: el precio NUNCA retorna al cuadro en bos_gap velas.")
        print("      Causa = logica de RETORNO (_touches_zone / bos_gap), NO killzone.")
    elif touched and touched_in_kz == 0:
        print("\n  >>> DIAGNOSTICO: hay retornos pero TODOS fuera de killzone.")
        print("      Causa = filtro killzone mata las senales.")


if __name__ == "__main__":
    main()
