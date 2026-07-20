"""INTEGRACION — Fase 5: el CALL SITE real produce alignments con score > 0.

Audita que el cableado NO quede muerto (la trampa de 'funcion aislada verde
pero call site muerto'). Mockea el I/O pesado (load_frames, estructura,
simulacion) pero USA build_objects REAL sobre un mini-DataFrame con una
senal, y confirma que run_sequence_backtest(attach_plan=True) devuelve
m['alignments'] con AlignmentReport de score > 0 para esa senal.

No usa data/raw real (ventana chica da 0 senales por diseno del motor);
inyecta 1 senal con entry_at para forzar el camino del medidor.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from unittest import mock


def _mini_frames():
    """Mini-DataFrames crudos con forma ICT (sweep + displacement + BOS).

    build_features produce las columnas de detectores que df_to_objects lee.
    El H4 tiene un BOS temprano (antes de la senal M15 en t=10h) para que
    el emisor H4 marque con anti-look-ahead valido.
    """
    import pandas as pd

    from ict_backtest.data_feed import build_features

    base = pd.Timestamp("2024-01-01 00:00:00")

    def _h4(i):
        # forma: baja (sweep) en i=1, rebota y rompe (BOS up) en i=2, luego range
        if i == 0:
            return (1.1000, 1.1010, 1.0990, 1.1000)
        if i == 1:  # sweep down (toma SSL)
            return (1.1000, 1.1005, 1.0950, 1.0960)
        if i == 2:  # displacement up + cierre alto (BOS bullish)
            return (1.0960, 1.1030, 1.0955, 1.1025)
        return (1.1025, 1.1030, 1.1015, 1.1020)

    rows = []
    for i in range(30):
        o, h, l, c = _h4(i)
        rows.append({"time": base + timedelta(hours=4 * i),
                     "open": o, "high": h, "low": l, "close": c})
    df = pd.DataFrame(rows)

    # M15: senal alrededor de base+10h (iloc 40). BOS M15 previo en i=25.
    m15_rows = []
    for i in range(120):
        if i < 10:
            o, h, l, c = (1.10, 1.101, 1.099, 1.10)
        elif i == 10:  # sweep down M15
            o, h, l, c = (1.10, 1.1005, 1.095, 1.096)
        elif i == 25:  # BOS M15 up
            o, h, l, c = (1.096, 1.103, 1.0955, 1.1025)
        elif i == 30:  # FVG M15
            o, h, l, c = (1.1025, 1.104, 1.102, 1.1035)
        else:
            o, h, l, c = (1.1025, 1.103, 1.1015, 1.102)
        m15_rows.append({"time": base + timedelta(minutes=15 * i),
                         "open": o, "high": h, "low": l, "close": c})
    m15 = pd.DataFrame(m15_rows)

    # H1 / D1 / M5 / M1: BOS temprano (t=2h) para contexto HTF valido
    side = pd.DataFrame([{
        "time": base + timedelta(hours=2),
        "open": 1.096, "high": 1.103, "low": 1.0955, "close": 1.1025,
    }])
    raw = {"H4": df, "M15": m15, "D1": side, "H1": side, "M5": side, "M1": side}
    return {tf: build_features(d.copy()) for tf, d in raw.items()}


def test_run_sequence_attach_plan_produce_score_real():
    from ict_backtest.run_backtest import run_sequence_backtest

    frames = _mini_frames()
    # senal unica con entry_at para que emit_m15 => STRUCTURE_OK
    fake_sig = mock.MagicMock()
    fake_sig.direction = 1
    fake_sig.time = frames["M15"]["time"].iloc[40]
    fake_sig.entry_at = 40
    fake_sig.bos_at = 25
    fake_sig.sweep_at = 10

    fake_trade = mock.MagicMock()
    fake_trade.pnl_r = 1.0
    fake_meta = {"exit_reason": "tp"}

    def _fake_seq(*a, **k):
        return [fake_sig]

    with mock.patch("ict_backtest.run_backtest.load_frames", return_value=frames), \
         mock.patch("ict_backtest.run_backtest.detect_market_structure",
                    side_effect=lambda df: df), \
         mock.patch("ict_backtest.run_backtest.generate_sequence_signals",
                    side_effect=_fake_seq), \
         mock.patch("ict_backtest.run_backtest.simulate_trade_with_context",
                    return_value=(fake_trade, fake_meta, None)), \
         mock.patch("ict_backtest.v2.context_mtf.build_context_stack",
                    return_value={}):
        m = run_sequence_backtest(
            "EURUSD", "H4", "M15", max_hold=16,
            attach_plan=True, backtest_id="TEST-CABLE", window_months=None,
        )

    assert "alignments" in m, "attach_plan debe poblar alignments"
    assert len(m["alignments"]) == 1, f"debe haber 1 alignment, hubo {len(m['alignments'])}"
    rep = m["alignments"][0]
    # El cableado REAL (lo que estaba muerto antes del fix):
    #  - m['alignments'] se puebla en el loop (antes: nunca, porque el stack
    #    muerto no daba objetos y solo se adjuntaba si stack is not None).
    #  - emit_m15 infiere STRUCTURE_OK desde ICTSignal real (entry_at), no de
    #    phase_log imaginario. Antes del fix m15 era SIEMPRE False.
    #  - score > 0 (antes del fix era SIEMPRE 0: objs_by_tf vacio).
    assert rep["score"] > 0, f"score debe ser > 0 con cableado real, fue {rep['score']}"
    assert rep["m15"] is True, f"emit_m15 debe marcar desde ICTSignal, rep={rep}"
    # Nota: d1/h4/h1 dependen de que build_features detecte BOS/CHOCH HTF en el
    # mini-dato (no siempre con 30 velas). El demo sintetico (fase5_demo_*.py)
    # cubre el caso totalmente alineado con objetos forzados.
