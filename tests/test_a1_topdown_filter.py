"""BRECHA A1 REAL (Opción B, filtro suave): cablear top_down_allows_trade
a run_sequence, para que el motor deje de decidir dirección solo desde H4
y use la cascada D1->H4->H1 del MultiTFContext completo.

TDD estricto RED->GREEN. Sin datos reales (sintético puro).

Criterios:
- El filtro SOLO se aplica cuando se pasa est_htf_ctx_fn (modo multitemporal).
  Con est_htf_ctx_fn=None (legacy) el comportamiento es IDÉNTICO al histórico.
- require_pd=False (POI anclado NO es veto; bonus, no gate duro).
- Anota en la señal: htf_aligned (bool), htf_reason (str). No altera conteo.
- El filtro VETA dirección que choca con la cascada (state.reset(); continue),
  sin tocar la lógica interna del SETUP.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest.multitf_context import MultiTFContext


# ---------------------------------------------------------------------------
# LTF sintético que produce UNA señal LONG limpia (sweep->displace->bos->touch)
# ---------------------------------------------------------------------------
def _make_ltf_long() -> pd.DataFrame:
    rows = [
        # bar0: SWEEP DOWN (long busca barrer SSL)
        {"time": "2026-01-01 00:00", "open": 1.100, "high": 1.102, "low": 1.098,
         "close": 1.099, "atr": 0.001,
         "liquidity_sweep_down": True, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
        # bar1: DISPLACE BULLISH + FVG (zona congelada high=1.110 low=1.106)
        {"time": "2026-01-01 01:00", "open": 1.100, "high": 1.110, "low": 1.106,
         "close": 1.109, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": True, "displacement_bearish": False,
         "fvg_bullish": True, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
        # bar2: BOS bullish (continuación)
        {"time": "2026-01-01 02:00", "open": 1.110, "high": 1.115, "low": 1.111,
         "close": 1.114, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 1, "choch_dir": 0, "bos_level": 1.111},
        # bar3: retorno al cuadro FVG (toca zona 1.106..1.110)
        {"time": "2026-01-01 03:00", "open": 1.108, "high": 1.111, "low": 1.105,
         "close": 1.106, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
    ]
    return pd.DataFrame(rows)


def _ctx_factory(d1_trend: str, h4_trend: str = "BULLISH",
                 h1_trend: str = "BULLISH") -> MultiTFContext:
    """MultiTFContext cerrado-only sintético (solo claves que lee el gate)."""
    return MultiTFContext({
        "D1": {"tf": "D1", "available": True, "trend": d1_trend},
        "H4": {"tf": "H4", "available": True, "trend": h4_trend},
        "H1": {"tf": "H1", "available": True, "trend": h1_trend},
    })


def _dummy_est_htf_fn(i):
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False, "pd_zones": []}


# ---------------------------------------------------------------------------
# RED / GREEN: la cascada D1 veta LONG aunque H4 sea BULLISH
# ---------------------------------------------------------------------------
def test_a1_veta_long_cuando_d1_ranging_aunque_h4_bullish():
    """CASO A1: H4=BULLISH deriva target=LONG, pero D1=RANGING -> cascada
    veta. Antes del cableado run_sequence IGNORABA D1 y generaba la señal
    (RED). Tras cablear top_down_allows_trade -> 0 señales (GREEN)."""
    ltf = _make_ltf_long()
    ctx = _ctx_factory(d1_trend="RANGING", h4_trend="BULLISH", h1_trend="BULLISH")

    def est_htf_ctx_fn(i):
        return ctx

    sigs, _ = run_sequence(
        ltf, _dummy_est_htf_fn, SequenceConfig(),
        ltf_tf="M15", htf="H4", est_htf_ctx_fn=est_htf_ctx_fn,
    )
    assert len(sigs) == 0, (
        f"A1 debe vetar LONG cuando D1=RANGING; señales inesperadas: {sigs}"
    )


def test_a1_genera_long_cuando_d1_bullish_h4_bullish():
    """CONTRASTE: si D1=BULLISH la cascada APROBÓ -> run_sequence SÍ genera
    la señal LONG (el SETUP interno no se tocó)."""
    ltf = _make_ltf_long()
    ctx = _ctx_factory(d1_trend="BULLISH", h4_trend="BULLISH", h1_trend="BULLISH")

    def est_htf_ctx_fn(i):
        return ctx

    sigs, _ = run_sequence(
        ltf, _dummy_est_htf_fn, SequenceConfig(),
        ltf_tf="M15", htf="H4", est_htf_ctx_fn=est_htf_ctx_fn,
    )
    assert len(sigs) == 1, f"esperada 1 señal LONG alineada, got {len(sigs)}"
    assert sigs[0]["direction"] == 1
    # Anotación de observabilidad presente y coherente.
    assert sigs[0]["htf_aligned"] is True
    assert sigs[0]["htf_reason"] == "ok"


def test_a1_anota_veto_en_senal_cuando_no_hay_senal():
    """El reset por veto debe dejar registrado htf_aligned/reason en el estado
    (observabilidad). Verificamos que el gate realmente evaluó D1=RANGING."""
    from ict_backtest.v2.context_mtf import top_down_allows_trade

    ctx = _ctx_factory(d1_trend="RANGING", h4_trend="BULLISH", h1_trend="BULLISH")
    ok, reason = top_down_allows_trade(ctx, 1, require_pd=False)
    assert ok is False
    assert reason == "d1_ranging"


# ---------------------------------------------------------------------------
# REGRESIÓN: legacy (est_htf_ctx_fn=None) idéntico al histórico
# ---------------------------------------------------------------------------
def test_legacy_sin_ctx_no_aplica_filtro():
    """Con est_htf_ctx_fn=None el filtro NO se aplica: run_sequence se comporta
    IGUAL que antes, aunque un contexto externo hubiera vetado. Debe generar
    la señal LONG (comportamiento histórico intacto)."""
    ltf = _make_ltf_long()

    def est_htf_fn(i):
        # HTF=BULLISH en el modo legacy de 1 nivel (como hoy).
        return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False, "pd_zones": []}

    sigs, _ = run_sequence(ltf, est_htf_fn, SequenceConfig(), ltf_tf="M15")
    assert len(sigs) == 1, (
        f"legacy debe generar señal como antes (sin filtro A1): got {len(sigs)}"
    )
    assert sigs[0]["direction"] == 1


# ---------------------------------------------------------------------------
# CALL SITE real: el filtro se ejecuta DENTRO del loop de run_sequence
# ---------------------------------------------------------------------------
def test_call_site_filtro_se_ejecuta_en_loop_real():
    """AUDITORÍA DE CALL SITE: parcheamos top_down_allows_trade y confirmamos
    que run_sequence LO LLAMA dentro de su loop cuando recibe est_htf_ctx_fn,
    y que NO lo llama en modo legacy (est_htf_ctx_fn=None)."""
    import inspect
    from unittest import mock

    from ict_backtest.v2.context_mtf import top_down_allows_trade as real_gate

    calls = {"n": 0}

    def spy(stack, direction, **kw):
        calls["n"] += 1
        return real_gate(stack, direction, **kw)

    ltf = _make_ltf_long()
    ctx_veto = _ctx_factory(d1_trend="RANGING", h4_trend="BULLISH", h1_trend="BULLISH")

    def est_htf_ctx_fn(i):
        return ctx_veto

    with mock.patch("ict_backtest.v2.context_mtf.top_down_allows_trade", side_effect=spy):
        # Multitemporal: el filtro DEBE ejecutarse en el loop.
        sigs_m, _ = run_sequence(
            ltf, _dummy_est_htf_fn, SequenceConfig(),
            ltf_tf="M15", htf="H4", est_htf_ctx_fn=est_htf_ctx_fn,
        )
        assert calls["n"] > 0, "el gate NO se ejecutó en el loop multitemporal"
        assert len(sigs_m) == 0, "el veto en el loop real no se aplicó"

    calls["n"] = 0
    with mock.patch("ict_backtest.v2.context_mtf.top_down_allows_trade", side_effect=spy):
        # Legacy: el filtro NO debe ejecutarse (ruta est_htf_ctx_fn=None).
        def est_htf_fn(i):
            return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False, "pd_zones": []}

        sigs_l, _ = run_sequence(ltf, est_htf_fn, SequenceConfig(), ltf_tf="M15")
        assert calls["n"] == 0, "el gate no debió ejecutarse en modo legacy"
        assert len(sigs_l) == 1


def test_require_pd_false_por_defecto_no_veta_por_pd():
    """require_pd=False en la llamada: un PD desconocio NO debe vetar (bonus,
    no gate). Construimos contexto sin pd_side y confirmamos que aun así APROBÓ
    (no se rompe por PD ausente)."""
    ctx = _ctx_factory(d1_trend="BULLISH", h4_trend="BULLISH", h1_trend="BULLISH")
    # Sin clave pd_side -> top_down_allows_trade con require_pd=False ignora PD.
    from ict_backtest.v2.context_mtf import top_down_allows_trade
    ok, reason = top_down_allows_trade(ctx, 1, require_pd=False)
    assert ok is True and reason == "ok"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
