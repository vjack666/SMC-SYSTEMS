"""R4 E2 — Medicion aislada de PO3: el gating solo toma el ciclo COMPLETO.

Test liviano (sin datos historicos) que verifica que build_signals_from_frames
con model="po3" no crashea y no genera senales espurias cuando la estructura
no cumple PO3 completo. La medicion PF/WR real corre via
`python ict_backtest/run_backtest.py --symbol EURUSD --htf H4 --ltf M15 --model po3`
y se reporta en METRICS_CANON §"Modelos aislados".
"""

import numpy as np
import pandas as pd

from ict_backtest.engine import build_signals_from_frames


def _empty_frames():
    """Frames minimos (columnas del contrato) sin estructura PO3 -> 0 senales."""
    idx = pd.date_range("2026-01-01", periods=50, freq="15min", tz="UTC")
    def mk():
        return pd.DataFrame(
            {
                "time": idx,
                "open": np.full(50, 1.10),
                "high": np.full(50, 1.101),
                "low": np.full(50, 1.099),
                "close": np.full(50, 1.10),
                "atr": np.full(50, 0.0005),
                "trend": ["RANGING"] * 50,
                "macro_direction": ["RANGING"] * 50,
                "bos_direction": [0] * 50,
                "bos_status": ["-"] * 50,
                "liquidity_sweep_up": [False] * 50,
                "liquidity_sweep_down": [False] * 50,
                "fvg_state": ["-"] * 50,
                "ob_direction": ["-"] * 50,
                "choch_signal": [None] * 50,
                "displacement_bullish": [False] * 50,
                "displacement_bearish": [False] * 50,
                "displacement_magnitude": [0.0] * 50,
                "bsl_price": [np.nan] * 50,
                "ssl_price": [np.nan] * 50,
            }
        )
    return {"D1": mk(), "H4": mk(), "M15": mk()}


def test_model_po3_no_genera_senales_sin_estructura():
    """Con frames planos (sin PO3 completo), model='po3' devuelve 0 senales."""
    frames = _empty_frames()
    sigs = build_signals_from_frames(
        "EURUSD", frames, bias_by_tf={}, model="po3", htf="H4", ltf="M15"
    )
    assert isinstance(sigs, list)
    assert len(sigs) == 0


def test_model_po3_acepta_flag():
    """El motor acepta model='po3' sin error de tipo/shadow."""
    frames = _empty_frames()
    # No debe lanzar; con estructura plana simplemente no hay senal.
    sigs = build_signals_from_frames(
        "EURUSD", frames, bias_by_tf={}, model="po3", htf="H4", ltf="M15",
        counter_trend=False, tp_mode="fixed2r", require_displacement=False,
    )
    assert sigs == []
