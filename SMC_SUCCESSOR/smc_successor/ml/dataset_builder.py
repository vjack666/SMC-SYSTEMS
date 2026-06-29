from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smc_successor.agents.orchestrator import AGENT_COLUMNS, AgentOrchestrator
from smc_successor.backtest.engine import _build_signals_from_context, _simulate_trade_with_stats
from smc_successor.data import load_frame
from smc_successor.features import FeatureEngine
from smc_successor.regime import detect_regimes
from smc_successor.signals.pipeline import ScalpingConfig, build_scalping_context


@dataclass
class DatasetBuildConfig:
    symbols: tuple[str, ...] = ("EURUSD",)
    timeframe: str = "M15"
    data_dir: Path = Path("data/raw")
    output_dir: Path = Path("data/ml")
    max_bars: int | None = None
    max_hold_bars: int = 16
    min_confidence: float = 0.0
    scalping_config: ScalpingConfig = field(default_factory=ScalpingConfig)
    schema_version: str = "v4"
    format: str = "parquet"
    auto_download: bool = True
    combined_output: bool = True
    download_count: int = 100_000

    def __post_init__(self) -> None:
        self.symbols = tuple(self.symbols) if not isinstance(self.symbols, tuple) else self.symbols


TRADE_CONTEXT_FEATURES = (
    "sl_distance", "tp_distance", "rr_ratio", "expected_hold_bars",
)

DATASET_LABELS = (
    "pnl_r", "win", "max_favorable_excursion", "max_adverse_excursion",
    "holding_time", "exit_reason",
)


def _coerce_utc_timestamp(value: Any) -> pd.Timestamp | None:
    if isinstance(value, pd.Timestamp):
        ts = value
    else:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _build_dataset_row(
    feature_row: dict[str, Any],
    context_row: pd.Series,
    labels: dict[str, Any],
    schema_version: str,
    agent_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": schema_version,
    }
    row.update(feature_row)

    for col in AGENT_COLUMNS:
        if col == "agent_decision_ml_probability":
            continue
        row[col] = context_row.get(col, None)

    for col in TRADE_CONTEXT_FEATURES:
        row[col] = feature_row.get(col, 0.0)

    row.update(labels)
    return row


def _build_context_truncated(
    symbol: str,
    timeframe: str,
    data_dir: Path,
    scalping_cfg: ScalpingConfig,
    max_bars: int | None = None,
) -> pd.DataFrame:
    context = build_scalping_context(
        symbol=symbol,
        timeframe=timeframe,
        data_dir=data_dir,
        config=scalping_cfg,
        orchestrator=None,
    )
    context = detect_regimes(context)
    if max_bars is not None and max_bars > 0:
        context = context.tail(int(max_bars)).reset_index(drop=True)
    return context


def _download_if_missing(
    symbol: str,
    timeframe: str,
    data_dir: Path,
    count: int = 100_000,
) -> None:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if path.exists():
        return
    try:
        from smc_successor.data.mt5.connector import MT5Connector
        connector = MT5Connector()
        print(f"  Downloading {symbol} {timeframe}...")
        connector.download_and_save(symbol, timeframe, count=count, output_dir=data_dir)
    except Exception as e:
        print(f"  WARNING: Could not download {symbol} {timeframe}: {e}")


def _add_year_month(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
    elif "time" in df.columns:
        ts = pd.to_datetime(df["time"], errors="coerce")
    else:
        return df
    df["year_month"] = ts.dt.strftime("%Y%m")
    return df


def build_ml_dataset(
    config: DatasetBuildConfig | None = None,
    progress_cb: Any = None,
) -> dict[str, int]:
    if config is None:
        config = DatasetBuildConfig()

    scalping_cfg = (
        ScalpingConfig(**config.scalping_config)
        if isinstance(config.scalping_config, dict)
        else config.scalping_config
    )

    feature_engine = FeatureEngine()
    orchestrator = AgentOrchestrator()
    symbol_counts: dict[str, int] = {}

    all_dfs: list[pd.DataFrame] = []

    for sym_idx, symbol in enumerate(config.symbols):
        if progress_cb:
            progress_cb("symbol", sym_idx, len(config.symbols), symbol)

        print(f"[{sym_idx + 1}/{len(config.symbols)}] {symbol} {config.timeframe}")

        if config.auto_download:
            _download_if_missing(symbol, config.timeframe, config.data_dir, config.download_count)

        try:
            context = _build_context_truncated(
                symbol=symbol,
                timeframe=config.timeframe,
                data_dir=config.data_dir,
                scalping_cfg=scalping_cfg,
                max_bars=config.max_bars,
            )
        except Exception as e:
            print(f"  WARNING: Could not build context for {symbol}: {e}")
            continue

        if len(context) == 0:
            print(f"  WARNING: Empty context for {symbol}, skipping")
            continue

        try:
            frame = load_frame(config.data_dir, symbol, config.timeframe)
        except Exception as e:
            print(f"  WARNING: Could not load frame for {symbol}: {e}")
            continue

        if config.max_bars is not None and config.max_bars > 0:
            frame = frame.tail(int(config.max_bars)).reset_index(drop=True)

        print(f"  Candles: {len(context)}")

        context = orchestrator.analyze_context(context)

        signals = _build_signals_from_context(
            symbol=symbol,
            context=context,
            min_confidence=config.min_confidence,
        )

        print(f"  Signals: {len(signals)}")

        context_map = {str(row["time"]): row for _, row in context.iterrows()}
        rows: list[dict[str, Any]] = []
        total_signals = len(signals)

        for signal_idx, signal in enumerate(signals):
            if progress_cb:
                progress_cb("signals", signal_idx, total_signals, f"{symbol} | rows={len(rows)}")

            context_row = context_map.get(signal.time)
            if context_row is None:
                continue

            core_features = feature_engine.extract_features(context, int(context_row.name))

            feature_row: dict[str, Any] = {}
            feature_row.update(core_features)
            feature_row["sl_distance"] = abs(signal.entry - signal.stop_loss)
            feature_row["tp_distance"] = abs(signal.take_profit - signal.entry)
            feature_row["rr_ratio"] = abs(signal.take_profit - signal.entry) / max(
                abs(signal.entry - signal.stop_loss), 1e-9
            )
            feature_row["expected_hold_bars"] = config.max_hold_bars

            trade, stats = _simulate_trade_with_stats(
                frame=frame,
                signal=signal,
                max_hold_bars=config.max_hold_bars,
            )

            if trade is not None:
                labels = {
                    "pnl_r": float(trade.pnl_r),
                    "win": int(trade.pnl_r > 0),
                    "max_favorable_excursion": stats["mfe_r"],
                    "max_adverse_excursion": stats["mae_r"],
                    "holding_time": stats["hold_bars"],
                    "exit_reason": stats["exit_reason"],
                }
            else:
                labels = {
                    "pnl_r": None,
                    "win": None,
                    "max_favorable_excursion": None,
                    "max_adverse_excursion": None,
                    "holding_time": None,
                    "exit_reason": stats.get("exit_reason", "UNKNOWN"),
                }

            row = _build_dataset_row(
                feature_row=feature_row,
                context_row=context_row,
                labels=labels,
                schema_version=config.schema_version,
            )
            row["symbol"] = symbol
            row["timestamp"] = str(context_row.get("time", ""))
            rows.append(row)

        if rows:
            df = pd.DataFrame(rows)
            df["symbol"] = symbol
            df = _add_year_month(df)

            output_dir = config.output_dir / symbol
            output_dir.mkdir(parents=True, exist_ok=True)

            if config.format == "parquet":
                path = output_dir / f"{config.schema_version}_{symbol}.parquet"
                df.to_parquet(path, index=False, compression="zstd")
            else:
                path = output_dir / f"{config.schema_version}_{symbol}.csv"
                df.to_csv(path, index=False)

            symbol_counts[symbol] = len(df)
            all_dfs.append(df)
            print(f"  -> {len(df)} samples saved to {path}")

    # Combined output
    if config.combined_output and all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = _add_year_month(combined)
        combined_output_dir = config.output_dir / "multi_symbol"
        combined_output_dir.mkdir(parents=True, exist_ok=True)
        combined_path = combined_output_dir / f"{config.schema_version}_dataset.parquet"
        combined.to_parquet(combined_path, index=False, compression="zstd")
        print(f"\nCombined dataset: {combined_path}")
        print(f"  Total samples: {len(combined)}")
        for sym in config.symbols:
            n = int((combined["symbol"] == sym).sum()) if "symbol" in combined.columns else 0
            print(f"  {sym}: {n} samples")
        print(f"  Win rate: {combined['win'].mean():.3f}" if "win" in combined.columns else "")

    return symbol_counts
