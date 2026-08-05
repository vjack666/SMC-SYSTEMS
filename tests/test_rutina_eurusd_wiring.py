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
        "tf", "time", "close", "atr", "trend", "swing_label",
        "bos_dir", "bos_status", "bos_level",
        "ob_top", "ob_bottom", "ob_dir", "fvg_state",
        "zone", "zone_high", "zone_low",
        "ote_long", "ote_short",
        "choch", "choch_status",
        "sweep_up", "sweep_down",
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
