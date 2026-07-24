"""RED→GREEN — Dashboard operacional (app_observador):

1) FALSO CONSENSO: el veredicto NO debe duplicar artificialmente el voto LONG.
   Antes `engine._canonical_plan` forzaba votes[LONG]=2 al detectar un plan
   canónico LONG (falso consenso). Hoy los votos = alineación real de capas
   (macro/ctx/intraday). Este test blinda que el conteo refleje SOLO las capas,
   sin hardcode de 2.

2) RÉGIMEN DE MERCADO: derivado de avg_candle_range (rango puro, SIN ATR).
   regime_engine(recent, hist) -> HIGH_VOL / NORMAL / LOW_VOL / PENDING.
   Se expone en context_alignment["regime"]; si falta el dato -> PENDING (honesto).

No toca el backtest. Solo librerías de cálculo puras del dashboard.
"""
from __future__ import annotations

from app_observador.core import pipeline as P


# ---------------------------------------------------------------------------
# Helpers: dicts mínimos con el schema de analyze_timeframe
# ---------------------------------------------------------------------------
def _tf(trend="RANGING", **extra):
    base = {
        "trend": trend, "bos_dir": 0, "bos_status": "", "bos_level": 0.0,
        "sweep_up": False, "sweep_down": False,
        "ote_long": (0.0, 0.0), "ote_short": (0.0, 0.0),
        "ob_dir": "-", "fvg_state": "-", "choch_status": "-",
        "zone_high": 0.0, "zone_low": 0.0,
    }
    base.update(extra)
    return base


# ===========================================================================
# 1) FALSO CONSENSO — votes refleja capas reales, no un hardcode de 2
# ===========================================================================
def test_votes_no_duplican_long_artificialmente():
    """3 capas alcistas -> LONG=3; NUNCA un valor forzado ajeno a las capas."""
    d1 = _tf("BULLISH")
    h4 = _tf("BULLISH")
    h1 = _tf("BULLISH")
    m15 = _tf("BULLISH")
    verd = P.run_pipeline(d1, h4, h1, m15)
    votes = verd["votes"]
    # votes cuenta macro(D1)+ctx(H4)+intraday(H1) = 3 capas.
    assert votes["LONG"] == 3
    assert votes["SHORT"] == 0
    # el total de votos NUNCA excede el nº de capas contadas (3)
    assert votes["LONG"] + votes["SHORT"] <= 3


def test_votes_mixtos_reflejan_capas_reales():
    """Capas divididas -> el conteo NO se infla a un consenso falso."""
    d1 = _tf("BULLISH")
    h4 = _tf("BEARISH")
    h1 = _tf("BULLISH")
    m15 = _tf("RANGING")
    verd = P.run_pipeline(d1, h4, h1, m15)
    votes = verd["votes"]
    assert votes["LONG"] == 2   # D1 + H1
    assert votes["SHORT"] == 1  # H4
    # sin plan canónico, sin hardcode: suma exacta de capas
    assert votes["LONG"] + votes["SHORT"] == 3


# ===========================================================================
# 2) RÉGIMEN DE MERCADO — desde avg_candle_range (rango puro, sin ATR)
# ===========================================================================
def test_regime_engine_high_vol():
    r = P.regime_engine(recent=1.6, hist=1.0)
    assert r["state"] == "HIGH_VOL"


def test_regime_engine_low_vol():
    r = P.regime_engine(recent=0.5, hist=1.0)
    assert r["state"] == "LOW_VOL"


def test_regime_engine_normal():
    r = P.regime_engine(recent=1.0, hist=1.0)
    assert r["state"] == "NORMAL"


def test_regime_engine_pending_sin_datos():
    assert P.regime_engine(recent=None, hist=None)["state"] == "PENDING"
    assert P.regime_engine(recent=1.0, hist=0.0)["state"] == "PENDING"


def test_regime_en_context_alignment():
    """run_pipeline expone regime en context_alignment (PENDING si no se pasa)."""
    d1 = _tf("BULLISH"); h4 = _tf("BULLISH"); h1 = _tf("BULLISH"); m15 = _tf("BULLISH")
    # sin régimen -> PENDING honesto
    verd = P.run_pipeline(d1, h4, h1, m15)
    assert verd["context_alignment"]["regime"] == "PENDING"
    # con régimen pasado -> se refleja
    verd2 = P.run_pipeline(d1, h4, h1, m15, regime_range=(1.8, 1.0))
    assert verd2["context_alignment"]["regime"] == "HIGH_VOL"
