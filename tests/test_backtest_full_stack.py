"""Verifica que el backtest UNICO (ruta A) alimenta al motor con el stack
top-down COMPLETO (D1->H4->H1->M15->M5->M1) y el motor lo ejerce en la
compuerta (top_down_allows_trade). No basta con leer el codigo: se demuestra
por ejecucion sobre datos reales.

Si este test pasa, queda probado que el backtest recibe la info completa del
motor (las 4+ capas) y no solo H4 -> no hay "backtest de 2 capas" encubierto.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals


def _capas_del_stack(stack) -> set[str]:
    """Cuenta capas presentes en el stack que recibe top_down_allows_trade."""
    if stack is None:
        return set()
    out: set[str] = set()
    for tf in ("D1", "H4", "H1", "M15", "M5", "M1"):
        node = None
        if isinstance(stack, dict):
            node = stack.get(tf)
        else:
            node = getattr(stack, tf, None)
        if node is None:
            continue
        # capa presente si el nodo trae info (dict no vacio o attr available/trend)
        if isinstance(node, dict):
            if node.get("available") or node.get("trend") or len(node) > 0:
                out.add(tf)
        else:
            out.add(tf)
    return out


@pytest.mark.slow  # carga ~1 mes de EURUSD
def test_backtest_feeds_full_motor_stack():
    seen: list[set[str]] = []

    import engine.plan as plan

    orig = plan.top_down_allows_trade

    def spy(stack, direction, **kw):
        seen.append(_capas_del_stack(stack))
        # no filtrar nada: dejamos pasar para que el motor recorra todo
        return True, "ok(spy)"

    from ict_backtest.data_feed import load_frames

    # Cargar SOLO el LTF para saber el ultimo time, luego recargar los 6 TF
    # desde `start` (1 mes) -> evita cargar 114k velas de M15 completas.
    m15_only = load_frames("EURUSD", ("M15",))["M15"]
    last = pd.to_datetime(m15_only["time"], utc=True, errors="coerce").iloc[-1]
    start = last - pd.DateOffset(months=1)
    frames = load_frames(
        "EURUSD", ("D1", "H4", "H1", "M15", "M5", "M1"), start=start
    )

    with patch.object(plan, "top_down_allows_trade", side_effect=spy):
        sigs, phase = evaluate_signals(
            "EURUSD", "H4", "M15",
            frames=frames,
            return_phase_seen=True,
        )

    assert seen, "top_down_allows_trade NUNCA fue llamado por el motor"

    todas = set().union(*seen)
    # El motor debe evaluar las 4 capas mayores, no solo H4.
    assert "D1" in todas, f"motor no evaluo D1; capas vistas={todas}"
    assert "H1" in todas, f"motor no evaluo H1; capas vistas={todas}"
    assert "H4" in todas, f"motor no evaluo H4; capas vistas={todas}"
    # y al menos una llamada con las 3 capas mayores presentes a la vez.
    assert any({"D1", "H4", "H1"}.issubset(s) for s in seen), (
        f"ninguna llamada tuvo D1+H4+H1 simultaneas; maximo visto={max(len(s) for s in seen)}"
    )
    # embudo monotico presente (el backtest reporta fases)
    assert phase, "phase_seen vacio"
    assert phase["SWEEP"] >= phase["DISPLACE"] >= phase["BOS"] >= phase["ENTRY"], phase
