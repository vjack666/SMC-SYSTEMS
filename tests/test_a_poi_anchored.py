"""BRECHA A (Fase C) — RED -> GREEN: cablear htf_poi_fn REAL.

El motor (sequence.run_sequence) ya tiene el hook::

    poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))

pero canonical.py pasaba htf_poi_fn=None -> hook MUERTO.

Este test verifica (sin datos reales, sintético puro):

1. RED: cuando enable_pd_index=True, run_sequence recibe htf_poi_fn no-None
   y la señal resultante trae ``poi_present`` poblado acorde al POI anclado.
   Hoy FALLA porque canonical.py no pasa htf_poi_fn (queda None) y el dict
   de señal de run_sequence no trae ``poi_present``.

2. REGRESIÓN: enable_pd_index=False (htf_pd_index=None) -> htf_poi_fn=None
   -> comportamiento IDÉNTICO al de hoy (run_sequence no recibe poi_fn, la
   señal no trae poi_present / queda None).

3. CALL SITE: evaluate_signals llama run_sequence con htf_poi_fn no-None
   cuando enable_pd_index=True, y la señal ICTSignal trae poi_present=True
   cuando el HTF tiene POI en la dirección de la señal.

Principio Brecha D / Fase E: el POI anclado es BONUS (no gate duro) -> con
as_gate=False la fn SIEMPRE devuelve True; la presencia real se anota en
``poi_present``. El conteo de señales NO cambia.

No toca datos reales (parquet). Frames sintéticos inyectados vía patch de
load_frames.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.poi_filter import make_htf_poi_fn, poi_present
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest.multitf_context import MultiTFContext

_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")


# ---------------------------------------------------------------------------
# LTF sintético que produce UNA señal LONG limpia (sweep->displace->bos->touch)
# (mismo patrón que test_a1_topdown_filter)
# ---------------------------------------------------------------------------
def _make_ltf_long() -> pd.DataFrame:
    """LTF (M15 conceptual, pero uso freq 4h en el fixture para que su rango
    temporal CUBRA el POI del H4) que produce UNA señal LONG limpia
    (sweep->displace->bos->touch). Los tiempos 00/04/08/12h alinean la
    vela 2 (08:00) con el POI bullish anclado del H4 (mismo instante)."""
    rows = [
        # bar0: SWEEP DOWN (long busca barrer SSL)
        {"time": "2026-01-01 00:00", "open": 1.100, "high": 1.102, "low": 1.098,
         "close": 1.099, "atr": 0.001,
         "liquidity_sweep_down": True, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
        # bar1: DISPLACE BULLISH + FVG (zona congelada high=1.110 low=1.106)
        {"time": "2026-01-01 04:00", "open": 1.100, "high": 1.110, "low": 1.106,
         "close": 1.109, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": True, "displacement_bearish": False,
         "fvg_bullish": True, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
        # bar2: BOS bullish (continuación) — coincide con POI H4 (08:00)
        {"time": "2026-01-01 08:00", "open": 1.110, "high": 1.115, "low": 1.111,
         "close": 1.114, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 1, "choch_dir": 0, "bos_level": 1.111},
        # bar3: retorno al cuadro FVG (toca zona 1.106..1.110)
        {"time": "2026-01-01 12:00", "open": 1.108, "high": 1.111, "low": 1.105,
         "close": 1.106, "atr": 0.001,
         "liquidity_sweep_down": False, "liquidity_sweep_up": False,
         "displacement_bullish": False, "displacement_bearish": False,
         "fvg_bullish": False, "fvg_bearish": False, "ob_direction": "-",
         "bos_dir": 0, "choch_dir": 0, "bos_level": float("nan")},
    ]
    return pd.DataFrame(rows)


def _make_htf_with_poi() -> pd.DataFrame:
    """HTF (H4) con trend BULLISH y un POI BULLISH anclado en la vela 2
    (08:00), que cae DENTRO del rango del LTF (ver _make_ltf_long).

    El detector FVG exige >=3 velas y detect_market_structure necesita
    swings para marcar trend; armamos 5 velas en clara subida y forzamos
    'trend' a BULLISH en el fixture (sintético, sin datos reales) para
    aislar la prueba del heurística de trend. Marcamos fvg_bullish=True en
    la vela 2 -> el HtfPdIndex lo propaga (forward-fill) a todas las
    velas LTF posteriores al cierre closed-only de esa vela H4.
    """
    base = pd.Timestamp("2026-01-01 00:00", tz="UTC")
    times = pd.date_range(base, periods=5, freq="4h", tz="UTC")
    closes = [1.090, 1.095, 1.102, 1.110, 1.118]
    highs = [c + 0.004 for c in closes]
    lows = [c - 0.004 for c in closes]
    fvg_bull = [False, False, True, False, False]  # POI anclado en vela 2 (08:00)
    df = pd.DataFrame({
        "time": times,
        "open": closes, "high": highs, "low": lows, "close": closes,
        "volume": [100.0] * 5,
        "fvg_bullish": fvg_bull, "fvg_bearish": [False] * 5,
        "ob_bullish": [False] * 5, "ob_bearish": [False] * 5,
        "ob_direction": ["-"] * 5,
    })
    out = detect_market_structure(df)
    # Fixture: forzamos trend BULLISH para aislar la prueba del POI.
    out["trend"] = "BULLISH"
    return out


def _make_frames(n: int = 40) -> dict:
    """Frames sintéticos de 6 TF con UN POI BULLISH anclado en H4.

    Para aislar la Brecha A del filtro A1 (cascada top-down), forzamos
    trend BULLISH en TODOS los TF (fixture sintético, sin datos reales):
    así la cascada D1->H4->H1 APRUEBA y run_sequence genera la señal
    LONG. El H4 lleva el POI bullish real (para poi_present).
    """
    frames = {"H4": _make_htf_with_poi()}
    # El resto de TF: series planas con trend BULLISH forzado (aprueban cascada).
    for tf in ("D1", "H1", "M15", "M5", "M1"):
        freq = {"D1": "1D", "H1": "1h", "M15": "15min",
                "M5": "5min", "M1": "1min"}[tf]
        base = pd.Timestamp("2026-01-01 00:00", tz="UTC")
        times = pd.date_range(base, periods=n, freq=freq, tz="UTC")
        close = pd.Series([1.10] * n, dtype=float)
        df = pd.DataFrame({
            "time": times,
            "open": close, "high": close + 0.002,
            "low": close - 0.002, "close": close, "volume": 100.0,
        })
        det = detect_market_structure(df)
        det["trend"] = "BULLISH"  # fixture: aprueba cascada A1
        frames[tf] = det
    # El LTF con la secuencia LONG de la señal (POI H4 cae en su vela 2).
    frames["M15"] = _make_ltf_long()
    return frames


def _dummy_est_htf_fn(i):
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False, "pd_zones": []}


# ---------------------------------------------------------------------------
# UNITARIOS: poi_filter aisladamente (sin tocar run_sequence)
# ---------------------------------------------------------------------------
class TestPoiFilterUnit:
    def test_poi_present_true_when_htf_poi_anclado(self):
        from unittest.mock import MagicMock
        from ict_backtest.htf_pd_index import HtfPdZone

        idx = MagicMock()
        idx.timeframes = ["H4"]
        idx.zones_at.return_value = [
            HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                       direction=1, zone_high=1.1, zone_low=1.0)
        ]
        ltf_map = {"H4": pd.DataFrame(index=range(10))}
        # target=1 (long) y el POI es bullish -> presente.
        assert poi_present(idx, ltf_map, 5, 1) is True

    def test_poi_present_false_when_no_htf_poi(self):
        from unittest.mock import MagicMock

        idx = MagicMock()
        idx.timeframes = ["H4"]
        idx.zones_at.return_value = []  # sin POI HTF padre
        ltf_map = {"H4": pd.DataFrame(index=range(10))}
        assert poi_present(idx, ltf_map, 5, 1) is False

    def test_poi_present_false_when_direccion_opuesta(self):
        from unittest.mock import MagicMock
        from ict_backtest.htf_pd_index import HtfPdZone

        idx = MagicMock()
        idx.timeframes = ["H4"]
        # POI bearish pero target=long -> NO presente en esa dirección.
        idx.zones_at.return_value = [
            HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                       direction=-1, zone_high=1.1, zone_low=1.0)
        ]
        ltf_map = {"H4": pd.DataFrame(index=range(10))}
        assert poi_present(idx, ltf_map, 5, 1) is False

    def test_poi_present_none_index_returns_false(self):
        # Sin índice HTF (modo histórico) -> no aporta bonus.
        assert poi_present(None, None, 5, 1) is False

    def test_make_htf_poi_fn_default_no_gate_siempre_true(self):
        """as_gate=False (DEFAULT): NUNCA veta (bonus), pese a no haber POI."""
        from unittest.mock import MagicMock

        idx = MagicMock()
        idx.timeframes = ["H4"]
        idx.zones_at.return_value = []  # sin POI
        ltf_map = {"H4": pd.DataFrame(index=range(10))}
        fn = make_htf_poi_fn(idx, ltf_map)  # as_gate=False por defecto
        assert fn(5, 1) is True  # no veta aunque no haya POI (bonus)

    def test_make_htf_poi_fn_as_gate_true_veta_sin_poi(self):
        """as_gate=True (experimental): veta cuando no hay POI. NO producción."""
        from unittest.mock import MagicMock

        idx = MagicMock()
        idx.timeframes = ["H4"]
        idx.zones_at.return_value = []
        ltf_map = {"H4": pd.DataFrame(index=range(10))}
        fn = make_htf_poi_fn(idx, ltf_map, as_gate=True)
        assert fn(5, 1) is False


# ---------------------------------------------------------------------------
# RED -> GREEN: run_sequence con htf_poi_fn REAL anota poi_present
# ---------------------------------------------------------------------------
def test_run_sequence_anota_poi_present_cuando_hay_poi():
    """El hook poi_ok ahora DEBE anotar poi_present=True cuando hay POI HTF.

    RED: hoy run_sequence NI SIQUIERA recibe htf_poi_fn (canonical lo pasa
    None) y el dict de señal no trae 'poi_present'. Tras el cableado GREEN
    lo trae y es True.
    """
    from ict_backtest.htf_pd_index import HtfPdIndex

    ltf = _make_ltf_long()
    # HTF con POI bullish anclado, alineado al LTF vía build_ltf_map.
    htf_df = _make_htf_with_poi()
    htf_pd_index = HtfPdIndex({"H4": htf_df})
    ltf_map = htf_pd_index.build_ltf_map(ltf)

    htf_poi_fn = make_htf_poi_fn(htf_pd_index, ltf_map)  # as_gate=False
    assert htf_poi_fn is not None

    sigs, _ = run_sequence(
        ltf, _dummy_est_htf_fn, SequenceConfig(),
        htf_poi_fn=htf_poi_fn, ltf_tf="M15",
        htf_pd_index=htf_pd_index, ltf_map=ltf_map, htf="H4",
    )
    # No rompe el conteo: con bonus (as_gate=False) sigue saliendo la señal.
    assert len(sigs) == 1, f"esperada 1 señal (bonus no veta), got {len(sigs)}"
    assert sigs[0]["direction"] == 1
    # La anotación poi_present debe estar presente y ser True (hay POI bullish).
    assert "poi_present" in sigs[0], "run_sequence NO anotó poi_present"
    assert sigs[0]["poi_present"] is True


def test_run_sequence_poi_present_false_sin_htf_poi():
    """Sin POI HTF anclado, poi_present=False (bonus informativo)."""
    from ict_backtest.htf_pd_index import HtfPdIndex

    ltf = _make_ltf_long()
    # HTF SIN pozos PD (no marcamos fvg/ob) -> no hay POI anclado.
    base = pd.Timestamp("2026-01-01 00:00", tz="UTC")
    htf_df = pd.DataFrame({
        "time": pd.date_range(base, periods=2, freq="4h", tz="UTC"),
        "open": [1.098, 1.100], "high": [1.110, 1.112],
        "low": [1.090, 1.095], "close": [1.105, 1.108], "volume": [100.0, 100.0],
    })
    htf_pd_index = HtfPdIndex({"H4": htf_df})
    ltf_map = htf_pd_index.build_ltf_map(ltf)

    htf_poi_fn = make_htf_poi_fn(htf_pd_index, ltf_map)
    sigs, _ = run_sequence(
        ltf, _dummy_est_htf_fn, SequenceConfig(),
        htf_poi_fn=htf_poi_fn, ltf_tf="M15",
        htf_pd_index=htf_pd_index, ltf_map=ltf_map, htf="H4",
    )
    assert len(sigs) == 1
    assert sigs[0]["poi_present"] is False


def test_run_sequence_sin_htf_poi_fn_no_anota_poi_present():
    """REGRESIÓN: si no se pasa htf_poi_fn (None), comportamiento histórico.

    El hook poi_ok queda no-op y poi_present NO se anota (o queda falsy en
    modo compat). Tras el parche, con htf_poi_fn=None el dict NO trae
    'poi_present' (None), igual que antes.
    """
    ltf = _make_ltf_long()
    sigs, _ = run_sequence(ltf, _dummy_est_htf_fn, SequenceConfig(), ltf_tf="M15")
    assert len(sigs) == 1
    # Sin htf_poi_fn: la clave poi_present no se anota (comportamiento previo).
    assert sigs[0].get("poi_present", None) is None


# ---------------------------------------------------------------------------
# CALL SITE real: evaluate_signals cablea htf_poi_fn y propaga poi_present
# ---------------------------------------------------------------------------
def test_call_site_evaluate_signals_pasa_htf_poi_fn(monkeypatch):
    """AUDITORÍA DE CALL SITE: evaluate_signals(enable_pd_index=True) debe
    pasarle htf_poi_fn NO-None a run_sequence."""
    import ict_backtest.canonical as canon_mod
    import ict_backtest.data_feed as df_mod
    import ict_backtest.sequence as seq_mod

    frames = _make_frames()

    captured = {}

    real_run = seq_mod.run_sequence

    def spy_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        captured["htf_poi_fn"] = kwargs.get("htf_poi_fn")
        captured["htf_pd_index"] = kwargs.get("htf_pd_index")
        captured["ltf_map"] = kwargs.get("ltf_map")
        return real_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs)

    monkeypatch.setattr(seq_mod, "run_sequence", spy_run)
    monkeypatch.setattr(canon_mod, "run_sequence", spy_run)

    def fake_load(symbol, tfs, **kw):
        return {tf: frames[tf] for tf in tfs if tf in frames}

    monkeypatch.setattr(df_mod, "load_frames", fake_load)

    evaluate_signals("SYN", "H4", "M15", enable_pd_index=True, frames=frames,
                     use_semantic=False)

    assert captured.get("htf_poi_fn") is not None, \
        "evaluate_signals NO pasó htf_poi_fn no-None a run_sequence"
    assert captured.get("htf_pd_index") is not None


def test_call_site_senal_trae_poi_present_true_con_poi(monkeypatch):
    """CALL SITE + propagación: run_sequence con contexto mock BULLISH (aisla
    Brecha A de la cascada A1 y del detector de trend) + htf_poi_fn REAL
    (HtfPdIndex mock con POI bullish) -> la señal trae poi_present=True.

    Se aísla de A1 usando est_htf_ctx_fn mock (como test_a1), porque el
    detector de trend del HTF sintético no alcanza el umbral BULLISH y A1
    vetaría la señal (eso lo cubre test_a1, no este)."""
    from unittest.mock import MagicMock
    from ict_backtest.htf_pd_index import HtfPdZone, HtfPdIndex
    from ict_backtest.sequence import run_sequence, SequenceConfig

    # Contexto mock BULLISH en la cadena (igual que test_a1 aísla la cascada).
    ctx = MultiTFContext({
        "D1": {"tf": "D1", "available": True, "trend": "BULLISH"},
        "H4": {"tf": "H4", "available": True, "trend": "BULLISH"},
        "H1": {"tf": "H1", "available": True, "trend": "BULLISH"},
    })

    def est_htf_ctx_fn(i):
        return ctx

    # HtfPdIndex mock con POI bullish anclado -> poi_present debe ser True.
    idx = MagicMock(spec=HtfPdIndex)
    idx.timeframes = ["H4"]
    idx.zones_at.return_value = [
        HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                  direction=1, zone_high=1.1, zone_low=1.0)
    ]
    ltf_map = {"H4": pd.DataFrame(index=range(10))}
    fn = make_htf_poi_fn(idx, ltf_map)  # as_gate=False (bonus)

    ltf = _make_ltf_long()
    sigs, _ = run_sequence(
        ltf, _dummy_est_htf_fn, SequenceConfig(), ltf_tf="M15",
        htf_pd_index=idx, ltf_map=ltf_map, htf="H4", est_htf_ctx_fn=est_htf_ctx_fn,
        htf_poi_fn=fn,
    )
    assert len(sigs) >= 1, f"run_sequence no generó señal con ctx BULLISH; sigs={sigs}"
    assert any(s.get("poi_present") is True for s in sigs), \
        f"ninguna señal trajo poi_present=True; sigs={sigs}"


def test_call_site_regresion_sin_pd_index_htf_poi_fn_none(monkeypatch):
    """REGRESIÓN CALL SITE: enable_pd_index=False -> htf_poi_fn=None -> idéntico."""
    import ict_backtest.canonical as canon_mod
    import ict_backtest.data_feed as df_mod
    import ict_backtest.sequence as seq_mod

    frames = _make_frames()

    captured = {}
    real_run = seq_mod.run_sequence

    def spy_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        captured["htf_poi_fn"] = kwargs.get("htf_poi_fn")
        return real_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs)

    monkeypatch.setattr(seq_mod, "run_sequence", spy_run)
    monkeypatch.setattr(canon_mod, "run_sequence", spy_run)

    def fake_load(symbol, tfs, **kw):
        return {tf: frames[tf] for tf in tfs if tf in frames}

    monkeypatch.setattr(df_mod, "load_frames", fake_load)

    evaluate_signals("SYN", "H4", "M15", enable_pd_index=False, frames=frames)
    assert captured.get("htf_poi_fn") is None, \
        "enable_pd_index=False debe dejar htf_poi_fn=None (regresión cero)"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
