from __future__ import annotations

from pathlib import Path

import pytest

from smc_successor.agents.orchestrator import AGENT_COLUMNS
from smc_successor.ml.dataset_builder import DatasetBuildConfig, build_ml_dataset

DATA_DIR = Path("data/raw")
EURUSD_M15 = DATA_DIR / "EURUSD_M15.parquet"

pytestmark = pytest.mark.skipif(
    not EURUSD_M15.exists(),
    reason="EURUSD M15 parquet data required",
)


def _minimal_config(max_bars: int = 1000) -> DatasetBuildConfig:
    return DatasetBuildConfig(
        symbols=("EURUSD",),
        timeframe="M15",
        data_dir=DATA_DIR,
        output_dir=Path("data/ml"),
        max_bars=max_bars,
        min_confidence=0.0,
        scalping_config={
            "trend_confidence_threshold": 0.0,
            "min_atr_ratio": 0.0,
        },
    )


class TestDatasetBuilder:
    def test_build_returns_symbol_count_map(self) -> None:
        config = _minimal_config(max_bars=500)
        result = build_ml_dataset(config)
        assert isinstance(result, dict)
        assert "EURUSD" in result
        assert result["EURUSD"] > 0

    def test_output_has_all_agent_columns(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        output_path = config.output_dir / "EURUSD"

        import pandas as pd
        df = pd.read_parquet(output_path / f"{config.schema_version}_EURUSD.parquet")
        for col in AGENT_COLUMNS:
            assert col in df.columns, f"Missing agent column: {col}"

    def test_output_has_all_label_columns(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        import pandas as pd
        df = pd.read_parquet(config.output_dir / "EURUSD" / f"{config.schema_version}_EURUSD.parquet")
        for col in ("pnl_r", "win", "max_favorable_excursion", "max_adverse_excursion", "holding_time", "exit_reason"):
            assert col in df.columns, f"Missing label column: {col}"

    def test_deterministic_output(self) -> None:
        config = _minimal_config(max_bars=500)
        output_path = config.output_dir / "EURUSD"
        output_path.mkdir(parents=True, exist_ok=True)

        build_ml_dataset(config)
        import pandas as pd
        df1 = pd.read_parquet(output_path / f"{config.schema_version}_EURUSD.parquet")

        build_ml_dataset(config)
        df2 = pd.read_parquet(output_path / f"{config.schema_version}_EURUSD.parquet")

        assert df1.equals(df2), "Re-running with same config should produce identical output"

    def test_agent_decision_confidence_in_range(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        import pandas as pd
        df = pd.read_parquet(config.output_dir / "EURUSD" / f"{config.schema_version}_EURUSD.parquet")
        conf = df["agent_decision_confidence"].dropna()
        assert (conf >= 0.0).all()
        assert (conf <= 1.0).all()

    def test_no_feature_leakage(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        import pandas as pd
        df = pd.read_parquet(config.output_dir / "EURUSD" / f"{config.schema_version}_EURUSD.parquet")
        leakage = [c for c in ("future_return",) if c in df.columns]
        assert len(leakage) == 0, f"Leakage columns found: {leakage}"

    def test_symbol_column_present(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        import pandas as pd
        df = pd.read_parquet(config.output_dir / "EURUSD" / f"{config.schema_version}_EURUSD.parquet")
        assert "symbol" in df.columns
        assert (df["symbol"] == "EURUSD").all()

    def test_schema_version_column(self) -> None:
        config = _minimal_config(max_bars=500)
        build_ml_dataset(config)
        import pandas as pd
        df = pd.read_parquet(config.output_dir / "EURUSD" / f"{config.schema_version}_EURUSD.parquet")
        assert "schema_version" in df.columns
        assert (df["schema_version"] == "v4").all()
