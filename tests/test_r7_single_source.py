"""R7 — single source of truth guards (no second ICT decision motor in-scope)."""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from agents.ict_agent import ICTAgent
from ict_backtest.canonical import (
    CANONICAL_ENGINE,
    R7_DOCUMENTED_DEBT,
    evaluate_signals,
)
from ict_backtest.run_backtest import generate_sequence_signals

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_engine_name():
    assert CANONICAL_ENGINE == "sequence"


def test_documented_debt_lists_legacy_and_ml():
    assert "legacy/backtest/engine.py" in R7_DOCUMENTED_DEBT
    assert "ml/dataset_builder.py" in R7_DOCUMENTED_DEBT


def test_build_signals_from_frames_gone_from_ict_backtest():
    engine_src = (ROOT / "ict_backtest" / "engine.py").read_text(encoding="utf-8")
    assert "def build_signals_from_frames" not in engine_src


def test_generate_sequence_signals_is_canonical_wrapper():
    # Same callable surface; implementation delegates to evaluate_signals
    assert callable(generate_sequence_signals)
    assert callable(evaluate_signals)


def test_ict_agent_is_not_a_geometry_motor():
    """Agent must not reimplement structure geometry methods (R7 H1)."""
    # FASE 3A-1 (F): la fuente única de ICTAgent vive ahora en analysis/ict_agent.py;
    # agents/ict_agent.py es solo fachada de compatibilidad (re-export).
    src = (ROOT / "analysis" / "ict_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    method_names = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    # Old parallel-motor names must be gone
    assert "_detect_bos" not in method_names
    assert "_detect_choch" not in method_names
    assert "_detect_fvg" not in method_names
    # Readers of precomputed columns are OK
    assert "_read_bos" in method_names
    agent = ICTAgent()
    assert getattr(agent, "decision_engine", None) == "sequence"


def test_ict_agent_reads_columns_only():
    n = 40
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": [1.1] * n,
        "high": [1.11] * n,
        "low": [1.09] * n,
        "close": [1.105] * n,
        "atr": [0.001] * n,
        "swing_label": ["HH"] * n,
        "macro_direction": ["BULLISH"] * n,
        "d1_direction": ["BULLISH"] * n,
        "bos_direction": [1] * n,
        "choch_signal": ["NONE"] * n,
        "fvg_bullish": [False] * n,
        "fvg_bearish": [False] * n,
        "fvg_size": [0.0] * n,
        "ob_bullish": [False] * n,
        "ob_bearish": [False] * n,
        "ob_distance": [99.0] * n,
        "liquidity_sweep_up": [False] * n,
        "liquidity_sweep_down": [False] * n,
        "displacement_bullish": [False] * n,
        "displacement_bearish": [False] * n,
        "premium_discount_zone": ["DISCOUNT"] * n,
    })
    df.loc[n - 1, "fvg_bullish"] = True
    df.loc[n - 1, "fvg_size"] = 0.0005
    df.loc[n - 1, "displacement_bullish"] = True
    result = ICTAgent().analyze(df, n - 1)
    assert result.agent_name == "ICT"
    assert result.evidence.get("decision_engine") == "sequence"
    assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")


def test_extract_levels_prefers_canonical():
    from app_observador.core.position_sizer_bridge import extract_levels

    result = {
        "canonical": {
            "engine": "sequence",
            "symbol": "EURUSD",
            "side": "SHORT",
            "entry": 1.10,
            "sl": 1.11,
            "tp": 1.07,
            "rr": 3.0,
        },
        "veredicto": {
            "votes": {"LONG": 3, "SHORT": 0},
            "invalidation": 9.9,
            "target": 9.8,
        },
        "estructura": {
            "M15": {"ote_long": [1.0, 1.01], "ote_short": [1.0, 1.01]},
        },
    }
    levels = extract_levels(result)
    assert levels is not None
    assert levels.side == "SHORT"
    assert abs(levels.entry - 1.10) < 1e-9
    assert abs(levels.sl - 1.11) < 1e-9
    assert abs(levels.tp - 1.07) < 1e-9
