"""Aceptacion del orquestador: evaluate_signals cablea los setups ICT (C2/C3/D1/RR).

Esto NO es test de funcion aislada: corre el PIPELINE REAL de evaluate_signals
(run_sequence mockeado, patron _inject_signal de test_b2_exec_tf) y afirma que
la senal que devuelve YA trae los metadatos anotados por los flags. Cierra la
trampa anti-test-verde-aislado (Ruben): el call-site real del orquestador debe
invocar los flags sobre su propia salida.

Sin datos reales (frames sinteticos).
"""
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from tests.test_b2_exec_tf import _make_frames, _inject_signal


def test_orquestador_anota_setups_en_senal_real(monkeypatch):
    # Frames sinteticos: M15 entry en idx 3 (09:45 UTC = London Open),
    # sweep idx 0 (09:00 UTC = London Open). Ambos en la killzone SB.
    frames, m15, m5, m1 = _make_frames()
    _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)

    signals = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
        use_semantic=False,
    )

    assert len(signals) == 1
    sig = signals[0]
    # Los 4 flags deben haber anotado la senal (knob apagado = no filtran).
    assert hasattr(sig, "sb_confirmed")
    assert hasattr(sig, "turtle_confirmed")
    assert hasattr(sig, "ote_confirmed")
    assert hasattr(sig, "rr_target")
    # En London Open 09:45 -> Silver Bullet confirmado (sb_killzone='L').
    assert sig.sb_confirmed is True, "el orquestador no anoto SB en London Open"
    assert sig.sb_killzone == "L"
    # rr_target resuelto por flag_rr (SB -> 2.0).
    assert sig.rr_target == 2.0, f"rr_target esperado 2.0 (SB), vino {sig.rr_target}"
    # La senal sigue siendo valida (entry/SL/TP intactos, regresion cero).
    assert sig.entry is not None and sig.stop_loss is not None and sig.take_profit is not None
