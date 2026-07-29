"""RED: rutina_eurusd.analyze_timeframe debe producir las keys que el motor
del dashboard (app_observador/core/engine.py) consume, USANDO los detectores
modernos (market_structure + liquidity_context), NO los legacy borrados
(detectors.bos / detectors.choch / detectors.trend).

No toca el backtest. Solo valida el re-wire del script operacional.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _synthetic_ohlc(n: int = 60, seed: int = 7) -> pd.DataFrame:
    """Serie OHLC determinista y monotona-ish para que haya swings/BOS."""
    rng = np.random.default_rng(seed)
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0002, n))
    high = close + rng.uniform(0, 0.0003, n)
    low = close - rng.uniform(0, 0.0003, n)
    # body up/down alternado para forzar swings
    idx = pd.date_range("2026-07-20 00:00", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close,
         "volume": 1000.0, "time": idx}
    )


def test_analyze_timeframe_imports_without_legacy_detectors():
    """El modulo NO debe importar detectors.bos/choch/trend (borrados)."""
    mod = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py")
    src = Path(ROOT / "scripts" / "rutina_eurusd.py").read_text(encoding="utf-8")
    assert "from detectors import BosConfig" not in src
    assert "from detectors.bos import" not in src
    assert "from detectors.choch import" not in src
    assert "from detectors.trend import" not in src
    assert "detect_trend(" not in src
    assert "detect_bos(" not in src
    assert "detect_choch(" not in src
    # re-exporta las herramientas modernas
    assert hasattr(mod, "analyze_timeframe")


def test_analyze_timeframe_emits_keys_consumed_by_dashboard():
    """analyze_timeframe debe devolver TODAS las keys que engine.run_cycle lee."""
    mod = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py")
    df = _synthetic_ohlc()
    out = mod.analyze_timeframe(df, "M15")

    required = {
        "tf", "time", "close", "range_pips", "trend", "swing_label",
        "bos_dir", "bos_signal", "bos_distance_bars", "bos_status", "bos_level",
        "ob_top", "ob_bottom", "ob_dir", "fvg_state",
        "zone", "zone_high", "zone_low",
        "ote_long", "ote_short",
        "choch", "choch_status",
        "sweep_up", "sweep_down", "sweep_up_bars", "sweep_down_bars",
    }
    missing = required - set(out.keys())
    assert not missing, f"Faltan keys en analyze_timeframe: {missing}"

    # tipos esperados (sin crash)
    assert isinstance(out["ote_long"], tuple) and len(out["ote_long"]) == 2
    assert isinstance(out["ote_short"], tuple) and len(out["ote_short"]) == 2
    assert out["trend"] in ("BULLISH", "BEARISH", "RANGING")
    assert out["choch"] in ("CHOCH_BULLISH", "CHOCH_BEARISH", "NONE")


def test_build_verdict_still_works_after_rewire():
    """El veredicto (sesgo) debe seguir calculandose con los campos nuevos."""
    mod = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py")
    df = _synthetic_ohlc()
    d1 = mod.analyze_timeframe(df, "D1")
    h4 = mod.analyze_timeframe(df, "H4")
    m15 = mod.analyze_timeframe(df, "M15")
    verdict = mod.build_verdict(d1, h4, m15)
    assert "bias" in verdict and "votes" in verdict and "reasons" in verdict
    assert verdict["bias"] in ("LONG", "SHORT", "NEUTRAL (esperar)")


def test_pipeline_emits_context_alignment_not_democracy():
    """FASE NUCLEO (RED): el pipeline jerarquico reemplaza votos por context_alignment.

    Cada TF cumple UNA responsabilidad (Bias/Context/Intraday/POI/Trigger),
    no una votacion. La salida debe traer context_alignment con macro/intraday/
    poi/trigger + confidence + stages, y un votes LEGADO derivado (no fuente de verdad).
    """
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import run_pipeline

    df = _synthetic_ohlc()
    d1 = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py").analyze_timeframe(df, "D1")
    h4 = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py").analyze_timeframe(df, "H4")
    h1 = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py").analyze_timeframe(df, "H1")
    m15 = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py").analyze_timeframe(df, "M15")

    out = run_pipeline(d1, h4, h1, m15)
    # Salida nueva: context_alignment es la fuente de verdad
    assert "context_alignment" in out, "falta context_alignment"
    ca = out["context_alignment"]
    for k in ("macro", "intraday", "poi", "trigger", "confidence", "setup_quality_pct", "stages"):
        assert k in ca, f"falta clave {k} en context_alignment"
    # trigger siempre presente (M5 es stub EN CONSTRUCCION)
    assert ca["trigger"] in ("PENDING", "VALID"), "trigger debe estar definido (aun PENDING)"
    assert "M5_TRIGGER" in ca["stages"], "falta etapa M5 en stages"
    # votes queda como LEGADO derivado, no fuente de verdad
    assert "votes" in out, "votes legacy debe seguir existiendo para no romper UI"
    assert "bias" in out


def test_trigger_engine_reports_both_sides_no_bias():
    """FASE M5 TWOPASS (RED): TriggerEngine NO recibe bias y reporta ambos lados.

    El Trigger no piensa: devuelve long/short con sus checks (sweep/bos/fvg)
    y el VerdictBuilder elige segun el contexto. Sin M5 -> PENDING honesto.
    """
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import trigger_engine

    # Sin M5 -> PENDING, sin inventar
    none_out = trigger_engine(None)
    assert none_out["state"] == "PENDING"
    assert none_out["valid"] is False
    assert "long" in none_out and "short" in none_out

    # M5 valido LONG: sweep_up + bos_dir==1 + fvg_state activo.
    # §5A: sweep+bos+fvg ya NO es TRIGGER_READY por si solo; sin zona de
    # pullback computable queda STRUCTURE_READY (estructura lista, sin zona).
    m5_long = {
        "trend": "BULLISH", "sweep_up": True, "sweep_down": False,
        "bos_dir": 1, "bos_status": "active", "fvg_state": "bullish",
    }
    long_out = trigger_engine(m5_long)
    assert long_out["long"]["checks"]["sweep"] is True
    assert long_out["long"]["checks"]["bos"] is True
    assert long_out["long"]["checks"]["fvg"] is True
    assert long_out["long"]["machine_state"] in (
        "STRUCTURE_READY", "WAITING_PULLBACK")
    assert long_out["long"]["valid"] is False  # sin pullback+killzone no valida
    # El lado contrario no debe validar solo por tener bos activo
    assert long_out["short"]["valid"] is False

    # M5 sin BOS -> lado LONG queda PENDING (falta bos)
    m5_no_bos = {
        "trend": "BULLISH", "sweep_up": True, "sweep_down": False,
        "bos_dir": 0, "bos_status": "", "fvg_state": "bullish",
    }
    no_bos = trigger_engine(m5_no_bos)
    assert no_bos["long"]["valid"] is False
    assert no_bos["long"]["checks"]["bos"] is False
    assert no_bos["long"]["checks"]["sweep"] is True


def test_pipeline_trigger_valid_boosts_confidence_and_stages():
    """FASE M5 §5A: run_pipeline conserva el contrato UI del trigger.

    §5A cambió la semántica: el trigger ya NO valida solo por sweep+bos+fvg;
    requiere pullback a zona + reacción DENTRO de killzone (reloj real inyectado
    por run_pipeline). Por eso aquí NO se afirma VALID (depende del reloj), sino
    que el string legado 'trigger' y el 'trigger_machine' fino existen, que
    stages['M5_TRIGGER'] refleja checks reales (no el stub) y que el dict rico
    del dashboard sigue presente.
    """
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import run_pipeline

    df = _synthetic_ohlc()
    rut = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py")
    d1 = rut.analyze_timeframe(df, "D1")
    h4 = rut.analyze_timeframe(df, "H4")
    h1 = rut.analyze_timeframe(df, "H1")
    m15 = rut.analyze_timeframe(df, "M15")

    # Fuerza sesgo LONG coherente en las capas altas para aislar el efecto del trigger
    d1 = {**d1, "trend": "BULLISH"}
    h4 = {**h4, "trend": "BULLISH"}
    h1 = {**h1, "trend": "BULLISH"}
    m15 = {**m15, "ob_dir": "bullish", "fvg_state": "bullish",
           "ote_long": (1.10, 1.11), "ote_short": (0.0, 0.0)}

    m5_valid = {
        "trend": "BULLISH", "sweep_up": True, "sweep_down": False,
        "bos_dir": 1, "bos_status": "active", "fvg_state": "bullish",
    }

    out = run_pipeline(d1, h4, h1, m15, m5=m5_valid)
    ca = out["context_alignment"]
    # El string legado se conserva (VALID|PENDING) — no rompe lecturas UI.
    assert ca["trigger"] in ("VALID", "PENDING")
    # El detalle fino de la máquina de estados está disponible.
    assert ca["trigger_machine"] in (
        "PENDING", "STRUCTURE_READY", "WAITING_PULLBACK",
        "TRIGGER_READY", "TRIGGER_READY_OFF_SESSION")
    # El M5_TRIGGER en stages debe reflejar checks REALES, no el stub fijo
    m5_stage = ca["stages"]["M5_TRIGGER"]
    assert "sweep" in m5_stage and "bos" in m5_stage and "fvg" in m5_stage
    # dict rico para el dashboard: ambos lados reportados
    assert "long" in out["trigger"] and "short" in out["trigger"]
    assert out["trigger"]["long"]["machine_state"] in (
        "PENDING", "STRUCTURE_READY", "WAITING_PULLBACK",
        "TRIGGER_READY", "TRIGGER_READY_OFF_SESSION")


def test_smt_engine_reports_divergence_no_bias():
    """FASE SMT (RED): smt_engine NO recibe bias; reporta divergencia de AMBOS lados.

    SMT = par correlacionado (EURUSD vs GBPUSD) en el MISMO TF (H1). La senal
    vive en el DESENCUENTRO: si EURUSD hace sweep_up y GBPUSD NO -> diverge SHORT
    (el barrido de EURUSD fue trampa, GBPUSD lo delato). Sin segundo par -> PENDING.
    """
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import smt_engine

    # Sin segundo par -> PENDING honesto
    none_out = smt_engine(None, None)
    assert none_out["state"] == "PENDING"
    assert none_out["diverge"] is False

    # EURUSD hace sweep_up; GBPUSD NO -> diverge SHORT (trampa de EURUSD)
    eur = {"trend": "BULLISH", "sweep_up": True, "sweep_down": False,
           "bos_dir": 1, "ob_dir": "bullish"}
    gbp_no = {"trend": "BULLISH", "sweep_up": False, "sweep_down": False,
              "bos_dir": 1, "ob_dir": "bullish"}
    smt = smt_engine(eur, gbp_no)
    assert smt["short"]["diverge"] is True, "EURUSD sweep_up sin GBPUSD -> diverge SHORT"
    assert smt["long"]["diverge"] is False
    assert smt["diverge"] is True

    # Ambos hacen sweep_up -> ALINEADOS (no aporta senal)
    gbp_si = {"trend": "BULLISH", "sweep_up": True, "sweep_down": False,
              "bos_dir": 1, "ob_dir": "bullish"}
    smt_ok = smt_engine(eur, gbp_si)
    assert smt_ok["diverge"] is False, "ambos alineados -> no diverge"


def test_pipeline_smt_feeds_context_alignment():
    """FASE SMT (RED): run_pipeline con SMT diverSHORT baja confianza / marca stages."""
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import run_pipeline

    df = _synthetic_ohlc()
    rut = _load_module("rutina_eurusd", ROOT / "scripts" / "rutina_eurusd.py")
    d1 = rut.analyze_timeframe(df, "D1")
    h4 = rut.analyze_timeframe(df, "H4")
    h1 = rut.analyze_timeframe(df, "H1")
    m15 = rut.analyze_timeframe(df, "M15")
    d1 = {**d1, "trend": "BULLISH"}
    h4 = {**h4, "trend": "BULLISH"}
    h1 = {**h1, "trend": "BULLISH"}
    m15 = {**m15, "ob_dir": "bullish", "fvg_state": "bullish",
           "ote_long": (1.10, 1.11), "ote_short": (0.0, 0.0)}

    # EURUSD H1 con sweep_up; GBPUSD H1 sin sweep -> diverge SHORT (trampa)
    eur_h1 = {"trend": "BULLISH", "sweep_up": True, "sweep_down": False,
              "bos_dir": 1, "ob_dir": "bullish"}
    gbp_h1 = {"trend": "BULLISH", "sweep_up": False, "sweep_down": False,
              "bos_dir": 1, "ob_dir": "bullish"}

    out = run_pipeline(d1, h4, h1, m15, smt_a=eur_h1, smt_b=gbp_h1)
    ca = out["context_alignment"]
    assert "smt" in ca, "context_alignment debe traer smt"
    assert ca["smt"] == "DIVERGE", "SMT debe marcar DIVERGE cuando los pares se desencuentran"
    assert "SMT" in ca["stages"]
    # dict rico para el dashboard
    assert out["smt"]["diverge"] is True
    assert out["smt"]["short"]["diverge"] is True


def test_poi_premium_discount_against_d1_range():
    """FASE PREMIUM/DISCOUNT (RED): poi_engine calcula PD del POI vs rango D1.

    Premium/Discount = donde cae el POI respecto al rango del D1 (dealing range).
    POI en DISCOUNT + sesgo LONG -> alineado. Reusa zone_high/zone_low del D1.
    Sin D1 -> PD queda PENDING (no inventa).
    """
    sys.path.insert(0, str(ROOT / "app_observador"))
    from app_observador.core.pipeline import poi_engine

    # Sin D1 -> PD PENDING
    poi_no_d1 = poi_engine({"ob_dir": "bullish", "fvg_state": "bullish",
                            "ote_long": (1.10, 1.11), "zone_low": 1.09, "zone_high": 1.12})
    assert poi_no_d1["premium_discount"] == "PENDING"

    # D1 rango [1.08, 1.12]; POI rango [1.085, 1.095] (abajo del 50%) -> DISCOUNT
    d1 = {"zone_low": 1.08, "zone_high": 1.12}
    poi_disc = poi_engine({"ob_dir": "bullish", "fvg_state": "bullish",
                           "ote_long": (1.10, 1.11), "zone_low": 1.085, "zone_high": 1.095},
                          d1=d1)
    assert poi_disc["premium_discount"] == "DISCOUNT", f"esperado DISCOUNT, got {poi_disc['premium_discount']}"
    # DISCOUNT + sesgo LONG -> alineado
    assert poi_disc["pd_aligned"] is True

    # POI en 1.118 (arriba del 50%) -> PREMIUM; sesgo LONG -> NO alineado
    poi_prem = poi_engine({"ob_dir": "bullish", "fvg_state": "bullish",
                           "ote_long": (1.10, 1.11), "zone_low": 1.115, "zone_high": 1.125},
                          d1=d1)
    assert poi_prem["premium_discount"] == "PREMIUM"
    assert poi_prem["pd_aligned"] is False


def test_market_state_widget_shows_smt_and_pd():
    """FASE SMT+PD (RED->GREEN): el MarketStateWidget pinta SMT y Premium/Discount."""
    sys.path.insert(0, str(ROOT))
    from app_observador.ui.market_state_widget import MarketStateWidget

    ca = {
        "macro": "SHORT", "intraday": "SHORT", "poi": "VALID",
        "premium_discount": "DISCOUNT", "trigger": "PENDING", "smt": "DIVERGE",
        "confidence": 65,
        "stages": {"D1": "✔", "H4": "□", "H1": "✔",
                   "M15_POI": "✔ discount/OB/FVG", "SMT": "□ diverge",
                   "M5_TRIGGER": "□ sweep / □ bos / □ fvg (PENDING)"},
    }
    w = MarketStateWidget()
    w.update_state({"veredicto": {"context_alignment": ca}, "semaforo": {"color": "verde"}})
    assert "DIVERGE" in w.lbl_smt.text(), "SMT no pinta DIVERGE"
    assert "DISCOUNT" in w.lbl_pd.text(), "PD no pinta DISCOUNT"
