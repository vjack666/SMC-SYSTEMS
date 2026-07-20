"""Fase RR-aplicacion: canonical usa rr_target para calcular el TP (no 3.0 fijo).

TDD RED->GREEN. Call-site real: evaluate_signals resuelve el setup de la
senal cruda (via los detectores is_*) y aplica rr_target al TP:
  tp = entry +/- rr_target * risk   (cuando no hay liquidez internal)

Aislamos cada setup mockeando los 3 detectores (el bajo test -> True, los
otros -> False) para que la precedencia SB>Turtle>OTE no contamine. Sin datos
reales (frames sinteticos + run_sequence mockeado).
"""
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from tests.test_b2_exec_tf import _make_frames, _inject_signal


def _force_setup(monkeypatch, setup):
    import ict_backtest.setups.silver_bullet as sb
    import ict_backtest.setups.turtle_soup as ts
    import ict_backtest.setups.ote as ote

    # Por defecto todos False; solo el setup bajo test devuelve True.
    # Se mockea a nivel de modulo del detector (donde _rr_for_raw_signal los llama).
    monkeypatch.setattr(sb, "is_silver_bullet", lambda *a, **k: (setup == "silver_bullet", {}))
    monkeypatch.setattr(ts, "is_turtle_soup", lambda *a, **k: (setup == "turtle_soup", {}))
    monkeypatch.setattr(ote, "is_ote_entry", lambda *a, **k: (setup == "ote", {}))


def _rr_of(monkeypatch, setup):
    frames, m15, m5, m1 = _make_frames()
    # Para OTE, el row de entry debe traer swing_high/swing_low no-NaN.
    if setup == "ote":
        frames["M15"]["swing_high"] = 1.1050
        frames["M15"]["swing_low"] = 1.0950
    _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)
    _force_setup(monkeypatch, setup)
    sigs = evaluate_signals("SYN", "D1", "M15", frames=frames, enable_pd_index=False)
    assert sigs, "no se produjo senal"
    sig = sigs[0]
    risk = abs(sig.entry - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry)
    return reward / risk if risk > 0 else 0.0


def test_rr_sb_aplica_2_0_en_tp(monkeypatch):
    rr = _rr_of(monkeypatch, "silver_bullet")
    assert abs(rr - 2.0) < 1e-6, f"SB debe dar RR 2.0, vino {rr}"


def test_rr_turtle_aplica_1_5_en_tp(monkeypatch):
    rr = _rr_of(monkeypatch, "turtle_soup")
    assert abs(rr - 1.5) < 1e-6, f"Turtle debe dar RR 1.5, vino {rr}"


def test_rr_ote_aplica_3_0_en_tp(monkeypatch):
    rr = _rr_of(monkeypatch, "ote")
    assert abs(rr - 3.0) < 1e-6, f"OTE debe dar RR 3.0, vino {rr}"


def test_rr_default_3_0_sin_setup(monkeypatch):
    frames, m15, m5, m1 = _make_frames()
    _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)
    # Todos los detectores en False -> default 3.0.
    _force_setup(monkeypatch, setup="__none__")
    sigs = evaluate_signals("SYN", "D1", "M15", frames=frames, enable_pd_index=False)
    sig = sigs[0]
    risk = abs(sig.entry - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry)
    rr = reward / risk if risk > 0 else 0.0
    assert abs(rr - 3.0) < 1e-6, f"sin setup debe dar RR 3.0, vino {rr}"
