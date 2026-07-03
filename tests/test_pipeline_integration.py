from pathlib import Path

import pandas as pd
import pytest

from smc_successor.agents.orchestrator import AgentOrchestrator
from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from smc_successor.signals.pipeline import ScalpingConfig, build_scalping_context


def _save_synthetic(data_dir: Path, symbol: str, timeframe: str, n_bars: int) -> None:
    # Strong trend so the pipeline fires
    df = generate_synthetic_ohlcv(n_bars=n_bars, start_price=1.1000, trend=0.0005)
    # Shift timestamps to start during London session so session_filter passes
    start = pd.Timestamp("2024-01-01 08:00:00", tz="UTC")
    df["time"] = pd.date_range(start=start, periods=n_bars, freq="15min", tz="UTC")
    df.to_parquet(data_dir / f"{symbol}_{timeframe}.parquet")


@pytest.fixture
def ohlcv_data(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _save_synthetic(data_dir, "EURUSD", "M15", 500)
    _save_synthetic(data_dir, "EURUSD", "H4", 200)
    _save_synthetic(data_dir, "EURUSD", "D1", 100)
    return data_dir


def test_build_scalping_context_runs(ohlcv_data: Path) -> None:
    context = build_scalping_context(
        symbol="EURUSD",
        timeframe="M15",
        data_dir=ohlcv_data,
    )
    assert isinstance(context, pd.DataFrame), "Expected DataFrame output"
    assert len(context) > 0, "Expected non-empty context"


def test_build_scalping_context_has_required_columns(ohlcv_data: Path) -> None:
    orchestrator = AgentOrchestrator()
    context = build_scalping_context(
        symbol="EURUSD",
        timeframe="M15",
        data_dir=ohlcv_data,
        orchestrator=orchestrator,
    )
    required = [
        "displacement_bullish",
        "premium_discount_zone",
        "agent_ict_bias",
        "agent_decision_confidence",
    ]
    for col in required:
        assert col in context.columns, f"Missing required column: {col}"


def test_build_scalping_context_produces_signals(ohlcv_data: Path) -> None:
    config = ScalpingConfig(min_confluence_score=1, trend_confidence_threshold=0.0)
    context = build_scalping_context(
        symbol="EURUSD",
        timeframe="M15",
        data_dir=ohlcv_data,
        config=config,
    )
    n_signals = int((context["signal_direction"] != 0).sum())
    assert n_signals > 0, (
        f"Expected at least one signal, got {n_signals}. "
        f"Confluence score distribution:\n{context['confluence_score'].value_counts().to_string()}"
    )
