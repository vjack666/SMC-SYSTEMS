"""tests/test_engine_plan.py — T9.3: el stack lee el sesgo por ESTRUCTURA
(BOS/CHOCH activo), no la etiqueta de swing que deja RANGING.

Determinista y sintetico (sin red ni MT5). Verifica que snapshot_tf y
top_down_allows_trade usen el sesgo por estructura vigente, igual que
compute_htf_bias (una sola fuente de verdad del sesgo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.plan import build_context_stack, snapshot_tf, top_down_allows_trade


def _annotated_frame(n: int = 60, choch_active: bool = True) -> pd.DataFrame:
    """Frame anotado sintetico: tendencia por etiqueta RANGING pero con un
    CHOCH alcista activo (y sin BOS activo). Esto es exactamente el caso que
    T9.3 corrige: la etiqueta de swing dice RANGING pero el sesgo humano es
    BULLISH por el CHOCH vigente.

    Construye bos_dir/choch_dir/bos_status/choch_status manualmente para no
    depender de detect_market_structure (aislamiento del test de plan).
    """
    idx = pd.date_range("2026-01-01", periods=n, freq="4h")
    # trend por etiqueta: RANGING en todas las velas (lo que _derive_trend daria)
    trend = ["RANGING"] * n
    bos_dir = [0] * n
    bos_status = ["none"] * n
    # CHOCH alcista activo en la ultima vela (evento de giro alcista vigente)
    choch_dir = [0] * (n - 1) + [1]
    last_status = "active" if choch_active else "invalidated"
    choch_status = ["none"] * (n - 1) + [last_status]
    return pd.DataFrame(
        {
            "time": idx,
            "open": np.arange(n, dtype=float),
            "high": np.arange(n, dtype=float) + 1,
            "low": np.arange(n, dtype=float) - 1,
            "close": np.arange(n, dtype=float) + 0.5,
            "trend": trend,
            "bos_dir": bos_dir,
            "bos_status": bos_status,
            "choch_dir": choch_dir,
            "choch_status": choch_status,
        }
    )


class TestSnapshotStructuralBias:
    def test_choch_activo_manda_aunque_trend_ranging(self):
        """snapshot_tf debe leer BULLISH por CHOCH activo, no RANGING por etiqueta."""
        df = _annotated_frame(choch_active=True)
        t = df["time"].iloc[-1]
        snap = snapshot_tf({"D1": df}, "D1", t)
        assert snap["trend"] == "BULLISH"

    def test_choch_invalidado_cae_a_ranging(self):
        """Si el CHOCH fue invalidado (precio lo cruzo), no pesa: RANGING."""
        df = _annotated_frame(choch_active=False)
        t = df["time"].iloc[-1]
        snap = snapshot_tf({"D1": df}, "D1", t)
        assert snap["trend"] == "RANGING"

    def test_gate_no_bloquea_por_ranging_si_choch_activo(self):
        """El gate no debe bloquear por d1_ranging cuando el sesgo por
        estructura es BULLISH (T9.3 cierra la coherencia end-to-end)."""
        df = _annotated_frame(choch_active=True)
        t = df["time"].iloc[-1]
        ms = {"D1": df, "H4": df, "H1": df}
        stack = build_context_stack(ms, t, tfs=("D1", "H4", "H1"))
        allow, reason = top_down_allows_trade(stack, direction=1, require_pd=False)
        assert allow, f"espero PERMITIDO por sesgo estructural, got {reason}"
        assert reason == "ok"
