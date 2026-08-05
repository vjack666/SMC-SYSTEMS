"""Integración SLOW: confirma dinámicamente que ``--model po3`` FILTRA de verdad.

Este test es la pieza que faltaba cerrar en la Auditoría PO3 (fork a,
2026-07-23, ver ``docs/plan/CRONOGRAMA_Y_ROADMAP.md`` fila "Auditoría PO3").

Los 4 tests unitarios de ``filter_signals_by_model`` + 8 de regresión del
runner ya prueban el *cableado* y el filtro en aislamiento, pero NO ejercitan
el camino real sobre datos reales. Aquí corremos el motor canónico completo
(``evaluate_signals``) dos veces -- ``model="intradia"`` y ``model="po3"`` --
sobre datos REALES de EURUSD y verificamos empíricamente que:

  1) hay señales base (intradia = regresión cero, sin filtro de modelo);
  2) po3 es un subconjunto ESTRICTO de intradia -> el flag NO es muerto;
  3) po3 deja pasar AL MENOS una señal (el motor detecta ciclos PO3/AMD
     completos de verdad, no solo descarta todo);
  4) toda señal que queda en po3 tiene ``po3_complete is True``
     (calculado por ``compute_po3_complete`` de ``po3_motor.py``).

Para no pagar el cómputo de 40k+ barras (motor legacy lento en este HW) se
monkeypatchea ``load_frames`` y se recorta el parquet REAL de EURUSD a una
ventana temporal corta (~4000 velas M15 ≈ 1.5 meses). Los datos siguen siendo
REALES (del disco), solo más acotados: confirma comportamiento real sin I/O
pesada.

Marcado ``@pytest.mark.slow``: se salta por defecto. Correr con
``pytest -m slow`` o vía Runner Monitor. Los tests normales lo excluyen con
``-m "not slow"``.
"""
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.data_feed import load_frames as _real_load_frames

# Ventana real acotada: últimas ~4000 velas M15 (~1.5 meses). Reduce el
# cómputo del motor (lo que lo hace lento) sin dejar de usar datos reales.
M15_WINDOW = 4000


def _real_windowed_frames(symbol, timeframes, data_dir=None, start=None, end=None):
    """Carga los parquet REALES y los recorta a una ventana temporal común.

    Toma el inicio temporal de las últimas ``M15_WINDOW`` velas M15 y filtra
    TODOS los TF a esa misma ventana -> coherencia multitemporal preservada.
    """
    full = _real_load_frames(symbol, timeframes)
    m15 = full.get("M15")
    cutoff = m15["time"].iloc[-M15_WINDOW] if m15 is not None else None
    out = {}
    for tf, df in full.items():
        if cutoff is not None:
            df = df[df["time"] >= cutoff]
        out[tf] = df.reset_index(drop=True)
    return out


@pytest.mark.slow
def test_po3_integration_filters_real_eurusd(monkeypatch):
    # Redirige load_frames -> ventana real acotada (evita I/O/cómputo pesado).
    monkeypatch.setattr("ict_backtest.data_feed.load_frames", _real_windowed_frames)

    # Camino de producción (R10.C, use_semantic=True): es lo que usa el runner.
    intradia = evaluate_signals(
        symbol="EURUSD", htf="H4", ltf="M15",
        counter_trend=True, tp_mode="fixed2r",
        require_displacement=True, enable_pd_index=True,
        use_semantic=True, model="intradia",
    )
    po3 = evaluate_signals(
        symbol="EURUSD", htf="H4", ltf="M15",
        counter_trend=True, tp_mode="fixed2r",
        require_displacement=True, enable_pd_index=True,
        use_semantic=True, model="po3",
    )

    # (1) Hay señales base: intradia no aplica filtro de modelo (regresión cero).
    assert len(intradia) > 0, (
        "intradia no produjo señales sobre datos reales EURUSD "
        "(¿ventana muy corta o datos ausentes?)"
    )

    # (2) El filtro po3 es subconjunto estricto: descarta lo incompleto.
    assert len(po3) < len(intradia), (
        "El flag --model po3 NO filtró nada: produce el mismo nº que intradia "
        f"({len(po3)}). Revisar filter_signals_by_model / compute_po3_complete "
        "en po3_motor.py -- el flag sería ENGAÑOSO."
    )

    # (3) El motor detecta ciclos PO3/AMD completos de verdad (no descarta todo).
    assert len(po3) > 0, (
        "po3 descartó TODAS las señales (0 completas). El flag técnicamente "
        "filtra, pero no confirma detección real de ciclo PO3/AMD en EURUSD "
        "real. Revisar compute_po3_complete / signals/po3.build_po3_state."
    )

    # (4) Todo lo que queda en po3 tiene el ciclo PO3/AMD COMPLETO.
    incompletas = [s for s in po3
                   if getattr(s, "po3_complete", None) is not True]
    assert not incompletas, (
        f"Hay {len(incompletas)} señales en po3 sin po3_complete=True "
        "(el filtro dejó pasar señales incompletas)"
    )
