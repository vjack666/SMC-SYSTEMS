"""tests/test_engine_bias.py — Tests de la CAPA 1 del motor (Narrativa HTF).

Deterministas y sintéticos (P4 VISION): datos generados, sin red ni MT5.
Verifica el contrato SPEC §1:
  - sesgo BULLISH en tendencia alcista confirmada
  - sesgo BEARISH en tendencia bajista confirmada
  - NEUTRAL en rango
  - alineación D1→H4→H1 y dirección global
  - SIN look-ahead: una vela abierta (aún sin cerrar) NO cambia el sesgo
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.bias import (
    BEARISH,
    BULLISH,
    NEUTRAL,
    HtfBias,
    compute_htf_bias,
)
from engine.bias.narrative import _bias_for_frame, _swing_points


# --------------------------------------------------------------------------- #
# Helpers: generación de velas sintéticas
# --------------------------------------------------------------------------- #
def _frame_from_closes(closes: list[float], body: float = 0.3) -> pd.DataFrame:
    """Construye velas sintéticas (OHLC) a partir de una serie de cierres.

    Cada vela: open = close anterior, close = valor dado, high = max(open,
    close) + body/2, low = min(open, close) - body/2. Los swings quedan
    deterministas.
    """
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate(([closes[0] - body], closes[:-1]))
    high = np.maximum(opens, closes) + body / 2
    low = np.minimum(opens, closes) - body / 2
    return pd.DataFrame({"open": opens, "high": high, "low": low, "close": closes})


def _zigzag_up(n_legs: int = 6, step: float = 1.0, leg: float = 2.0) -> list[float]:
    """Zigzag alcista: highs más altos (HH) y lows más altos (HL)."""
    closes: list[float] = []
    price = 100.0
    for _ in range(n_legs):
        closes.extend([price + step, price + leg, price + leg + step, price + leg])
        price += leg + 1.0
    return closes


def _zigzag_down(n_legs: int = 6, step: float = 1.0, leg: float = 2.0) -> list[float]:
    """Zigzag bajista: espejo exacto del alcista (lows más bajos LH/LL)."""
    return [300.0 - c for c in _zigzag_up(n_legs, step, leg)]


def _range_frame(
    n_cycles: int = 4, seg: int = 6, center: float = 100.0, amp: float = 2.0
) -> list[float]:
    """Rango lateral SIN drift: oscila entre centro±amp en tramos simétricos.

    Los tramos alcistas y bajistas se alternan en igual proporción → los
    swings HH/HL y LH/LL se balancean → el sesgo debe ser NEUTRAL.
    """
    ext = [center - amp, center + amp] * n_cycles + [center - amp]
    xs = np.arange(len(ext))
    xi = np.linspace(0, len(ext) - 1, (len(ext) - 1) * seg + 1)
    return np.interp(xi, xs, np.asarray(ext, dtype=float)).tolist()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class TestBiasUnTf:
    def test_uptrend_es_bullish(self):
        df = _frame_from_closes(_zigzag_up())
        assert _bias_for_frame(df) == BULLISH

    def test_downtrend_es_bearish(self):
        df = _frame_from_closes(_zigzag_down())
        assert _bias_for_frame(df) == BEARISH

    def test_rango_es_neutral(self):
        df = _frame_from_closes(_range_frame())
        assert _bias_for_frame(df) == NEUTRAL

    def test_swings_sin_lookahead_confirmacion_diferida(self):
        """El swing en la fila i solo se expone desde i+lookback (hallazgo #1)."""
        df = _frame_from_closes(_zigzag_up())
        sh, sl = _swing_points(df, lookback=5)
        first_sh_idx = sh.first_valid_index()
        if first_sh_idx is not None:
            # El swing del alto local debe estar confirmado: el precio NO pudo
            # haberlo superado ANTES de la confirmación (ventana no centrada).
            assert first_sh_idx >= 5


class TestHtfBias:
    def test_alineacion_bullish(self):
        up = _frame_from_closes(_zigzag_up())
        bias = HtfBias(d1=BULLISH, h4=BULLISH, h1=BULLISH)
        assert bias.aligned
        assert bias.direction == BULLISH

    def test_alineacion_bearish(self):
        bias = HtfBias(d1=BEARISH, h4=BEARISH, h1=BEARISH)
        assert bias.aligned
        assert bias.direction == BEARISH

    def test_desalineado_con_neutral_no_alinea(self):
        bias = HtfBias(d1=BULLISH, h4=BULLISH, h1=NEUTRAL)
        assert not bias.aligned
        assert bias.direction == NEUTRAL

    def test_conflicto_no_alinea(self):
        bias = HtfBias(d1=BULLISH, h4=BEARISH, h1=BEARISH)
        assert not bias.aligned
        assert bias.direction == NEUTRAL


class TestComputeHtfBias:
    def test_bias_completo_alineado(self):
        up = _frame_from_closes(_zigzag_up())
        result = compute_htf_bias(d1=up, h4=up, h1=up)
        assert isinstance(result, HtfBias)
        assert result.aligned
        assert result.direction == BULLISH

    def test_bias_mixto_por_tf(self):
        up = _frame_from_closes(_zigzag_up())
        dn = _frame_from_closes(_zigzag_down())
        rng = _frame_from_closes(_range_frame())
        result = compute_htf_bias(d1=up, h4=dn, h1=rng)
        assert result.d1 == BULLISH
        assert result.h4 == BEARISH
        assert result.h1 == NEUTRAL
        assert not result.aligned

    def test_no_lookahead_vela_abierta_no_cambia_sesgo(self):
        """Una vela aún abierta NO debe cambiar el sesgo (PRE SPEC §1).

        El sesgo se computa SOLO con velas cerradas: agregar una vela abierta
        (pendiente) con precios extremos no debe alterar el resultado.
        """
        closes = _zigzag_up()
        frame_cerrado = _frame_from_closes(closes)
        # Vela abierta: close provisional irrelevante (todavía en formación).
        frame_con_abierta = pd.concat(
            [
                frame_cerrado,
                pd.DataFrame(
                    {
                        "open": [closes[-1]],
                        "high": [closes[-1] + 50.0],  # mecha gigante ficticia
                        "low": [closes[-1] - 50.0],
                        "close": [closes[-1]],  # close provisional
                    }
                ),
            ],
            ignore_index=True,
        )
        # El sesgo debe derivarse SOLO de velas cerradas: el resultado
        # "cerrado" es el mismo que si la vela abierta no existiera.
        bias_cerrado = _bias_for_frame(frame_cerrado)
        # IMPORTANTE: el motor debe recibir SOLO velas cerradas. Si alguien le
        # pasa una abierta, la capa la ignora (ultima fila fuera del computo
        # de swings confirmados, porque aun no tiene confirmacion).
        assert bias_cerrado == _bias_for_frame(frame_con_abierta)

    def test_pocos_datos_devuelve_neutral(self):
        """Menos de 2 swings confirmados por lado → NEUTRAL (contexto escaso)."""
        df = _frame_from_closes([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        assert _bias_for_frame(df) == NEUTRAL
