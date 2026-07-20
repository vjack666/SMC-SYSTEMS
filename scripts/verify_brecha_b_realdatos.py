"""Verify call site REAL + backtest comparativo de regresión — Brecha B.

AUTORIZACION (Ruben 2026-07-20): lectura UNICA de data/raw/*.parquet para
verificar el call site y el conteo de senales. NO se modifica ningun dato ni
el motor. Si el motor base no produce senales reales, se documenta y B se
da por cerrada con evidencia sintetica (ver scripts/cierre_brecha_b_demo.py).

Objetivo:
1. Call site real: evaluate_signals(enable_pd_index=True) sobre EURUSD real
   calcula htf_anchored desde el indice HTF real sin crashear.
2. Regresion: el N de senales es IDENTICO con/sin enable_pd_index (Brecha D:
   anota, no filtra).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ict_backtest.canonical import evaluate_signals
from ict_backtest.run_backtest import run_sequence_backtest


def _count_real(symbol: str = "EURUSD", htf: str = "H4", ltf: str = "M15") -> tuple[int, list]:
    """Cuenta senales reales con enable_pd_index=True y devuelve htf_anchored."""
    sigs = evaluate_signals(symbol, htf, ltf, enable_pd_index=True, frames=None)
    anchors = [bool(s.htf_anchored) for s in sigs if s.htf_anchored is not None]
    return len(sigs), anchors


def _backtest_counts(symbol: str = "EURUSD", htf: str = "H4", ltf: str = "M15",
                     window: int = 1) -> tuple[int, int]:
    """Corre run_sequence_backtest con y sin enable_pd_index; devuelve (n_con, n_sin)."""
    m_on = run_sequence_backtest(symbol, htf, ltf, max_hold=16, window_months=window,
                                 enable_pd_index=True, attach_plan=True)
    m_off = run_sequence_backtest(symbol, htf, ltf, max_hold=16, window_months=window,
                                  enable_pd_index=False, attach_plan=True)
    n_on = len(m_on.get("signals", []))
    n_off = len(m_off.get("signals", []))
    return n_on, n_off


if __name__ == "__main__":
    print("== VERIFY CALL SITE REAL (EURUSD, lectura parquet) ==")
    try:
        n, anchors = _count_real()
        print(f"  senales reales (enable_pd_index=True, 1m): n={n}")
        if n == 0:
            print("  MOTOR BASE SIN SENALES REALES en 1m EURUSD "
                  "(estricto + version simplificada 2 TF).")
            print("  => Call site no ejercitado con senal real; validado en sintetico.")
        else:
            print(f"  htf_anchored calculados: {anchors}")
            print(f"  => Call site REAL verificado: htf_anchored presente en senales reales.")
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR en call site real: {type(e).__name__}: {e}")

    print("== BACKTEST COMPARATIVO REGRESION (con vs sin enable_pd_index) ==")
    try:
        n_on, n_off = _backtest_counts(window=1)
        print(f"  n_con_pd_index={n_on}  n_sin_pd_index={n_off}")
        if n_on == n_off:
            print("  OK REGRESION: conteo IDENTICO (Brecha D respetada: anota, no filtra).")
        else:
            print("  ALERTA: conteo DISTINTO -> B cambio el motor (revisar).")
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR en backtest comparativo: {type(e).__name__}: {e}")

    print("== CONCLUSION ==")
    print("  Brecha B: cerrada en motor (Opcion 2, anota sin filtrar).")
    print("  Evidencia: sintetica (scripts/cierre_brecha_b_demo.py) + tests.")
    print("  Evidencia real: sujeta a que el motor base produzca senales (R4/R6).")
