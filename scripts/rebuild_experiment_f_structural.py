"""
FASE 4 & 5: Full pipeline rebuild from raw OHLC data.

Generates experiment_F_structural_sl completely from scratch:
1. Load raw OHLC data
2. Detect BOS+FVG
3. Generate signals
4. Simulate trades using structural stop loss
5. Save experiment dataset + metrics

NO reuse of historical datasets, signals, or events.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.structural_sl import calculate_structural_stop


class ExperimentFBuilder:
    """Builder for experiment_F from raw OHLC data."""

    def __init__(
        self,
        data_dir: Path = Path("data/mt5"),
        results_dir: Path = Path("results"),
        symbols: list[str] = None,
        max_hold_bars: int = 100,
        rr_ratio: float = 2.0,
        entry_retest_lookahead: int = 32,
    ):
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.symbols = symbols or ["EURUSD", "GBPUSD", "XAUUSD"]
        self.max_hold_bars = max_hold_bars
        self.rr_ratio = rr_ratio
        self.entry_retest_lookahead = entry_retest_lookahead

        self.master_frame: Optional[pd.DataFrame] = None
        self.signals: list[dict] = []
        self.trades: Optional[pd.DataFrame] = None

    def load_all_ohlc(self) -> pd.DataFrame:
        """Load and concatenate all raw OHLC data."""
        frames: list[pd.DataFrame] = []

        for symbol in self.symbols:
            parquet_path = self.data_dir / f"{symbol}_H1.parquet"
            if not parquet_path.exists():
                print(f"Warning: No data for {symbol}")
                continue

            df = pd.read_parquet(parquet_path)
            df["symbol"] = symbol
            df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
            frames.append(df)
            print(f"Loaded {symbol}: {len(df)} candles")

        if not frames:
            raise ValueError("No OHLC data found")

        master = pd.concat(frames, ignore_index=True).sort_values(["symbol", "time"]).reset_index(drop=True)
        self.master_frame = master
        return master

    def _load_symbol_data(self, symbol: str) -> pd.DataFrame:
        from modules.bos.detector import detect_bos

        parquet_path = self.data_dir / f"{symbol}_H1.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(f"Missing OHLC file: {parquet_path}")

        df = pd.read_parquet(parquet_path).copy()
        df["symbol"] = symbol
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        df = detect_bos(df)
        return df.sort_values("time").reset_index(drop=True)

    @staticmethod
    def _intersects_zone(low: float, high: float, zone_low: float, zone_high: float) -> bool:
        return (low <= zone_high) and (high >= zone_low)

    def _find_entry_signals(self, frame: pd.DataFrame) -> list[dict]:
        from modules.bos.detector import detect_bos
        from modules.fvg.detector import detect_fvg

        df = frame.copy().reset_index(drop=True)
        df = detect_bos(df)
        df = detect_fvg(df)
        df["prev2_high"] = df["high"].shift(2)
        df["prev2_low"] = df["low"].shift(2)

        signals: list[dict] = []
        for create_idx, row in df.iterrows():
            is_bullish = bool(row.get("fvg_bullish", False))
            is_bearish = bool(row.get("fvg_bearish", False))
            if not is_bullish and not is_bearish:
                continue

            direction = 1 if is_bullish else -1
            bos_direction = int(row.get("bos_direction", 0) or 0)
            if bos_direction != direction:
                continue

            if direction == 1:
                zone_low = float(row["prev2_high"]) if np.isfinite(row["prev2_high"]) else np.nan
                zone_high = float(row["low"])
                side = "LONG"
                fvg_type = "fvg_bullish"
            else:
                zone_low = float(row["high"])
                zone_high = float(row["prev2_low"]) if np.isfinite(row["prev2_low"]) else np.nan
                side = "SHORT"
                fvg_type = "fvg_bearish"

            if not np.isfinite(zone_low) or not np.isfinite(zone_high):
                continue
            if zone_high <= zone_low:
                continue

            atr_value = float(row.get("atr", np.nan))
            zone_size_atr = abs(zone_high - zone_low) / atr_value if np.isfinite(atr_value) and atr_value > 0 else np.nan
            create_time = pd.to_datetime(row["time"], utc=True)
            bos_level = float(row.get("bos_level", np.nan)) if np.isfinite(row.get("bos_level", np.nan)) else np.nan

            for entry_idx in range(create_idx + 1, min(len(df), create_idx + 1 + self.entry_retest_lookahead)):
                entry_row = df.iloc[entry_idx]
                low_j = float(entry_row["low"])
                high_j = float(entry_row["high"])
                if not self._intersects_zone(low_j, high_j, zone_low, zone_high):
                    continue

                entry_price = float(entry_row["close"])
                if not np.isfinite(entry_price):
                    continue

                signals.append(
                    {
                        "symbol": row["symbol"],
                        "create_idx": int(create_idx),
                        "create_time": create_time,
                        "entry_idx": int(entry_idx),
                        "entry_time": pd.to_datetime(entry_row["time"], utc=True),
                        "direction": direction,
                        "side": side,
                        "entry_price": entry_price,
                        "bos_direction": bos_direction,
                        "bos_level": bos_level,
                        "zone_low": zone_low,
                        "zone_high": zone_high,
                        "zone_size_atr": zone_size_atr,
                        "bars_since_fvg_creation": int(entry_idx - create_idx),
                        "fvg_type": fvg_type,
                        "fvg_mid": float(row.get("fvg_mid", np.nan)) if np.isfinite(row.get("fvg_mid", np.nan)) else np.nan,
                    }
                )
                break

        signals_df = pd.DataFrame(signals)
        if not signals_df.empty:
            signals_df = signals_df.drop_duplicates(subset=["symbol", "entry_idx"], keep="first")
        return signals_df.to_dict("records")

    def generate_signals(self) -> list[dict]:
        if self.master_frame is None:
            raise RuntimeError("Raw OHLC data is not loaded")

        signals: list[dict] = []
        for symbol in self.symbols:
            print(f"Generating signals for {symbol}...")
            symbol_data = self._load_symbol_data(symbol)
            symbol_signals = self._find_entry_signals(symbol_data)
            print(f"  Detected {len(symbol_signals)} raw BOS+FVG signals for {symbol}")
            signals.extend(symbol_signals)

        self.signals = signals
        return signals

    def simulate_trades(self) -> pd.DataFrame:
        if not self.signals:
            raise RuntimeError("No signals available to simulate trades")

        symbol_frames: dict[str, pd.DataFrame] = {}
        trades: list[dict] = []

        for signal in self.signals:
            symbol = signal["symbol"]
            if symbol not in symbol_frames:
                symbol_frames[symbol] = self._load_symbol_data(symbol)
            symbol_data = symbol_frames[symbol]
            entry_idx = int(signal["entry_idx"])
            direction = int(signal["direction"])
            entry_price = float(signal["entry_price"])

            stop = calculate_structural_stop(symbol_data, entry_idx, direction)
            if stop is None:
                continue

            sl_price = float(stop.structural_stop_price)
            risk = abs(entry_price - sl_price)
            if risk <= 0 or not np.isfinite(risk):
                continue

            tp_price = float(entry_price + (risk * self.rr_ratio * direction))
            mfe_r = -np.inf
            mae_r = np.inf
            exit_price = entry_price
            exit_reason = "timeout"
            holding_bars = 0

            for step in range(1, self.max_hold_bars + 1):
                j = entry_idx + step
                if j >= len(symbol_data):
                    break

                row = symbol_data.iloc[j]
                high = float(row["high"])
                low = float(row["low"])
                close = float(row["close"])

                if direction == 1:
                    mfe_r = max(mfe_r, (high - entry_price) / risk)
                    mae_r = min(mae_r, (low - entry_price) / risk)
                    if low <= sl_price:
                        exit_price = sl_price
                        exit_reason = "sl_hit"
                        holding_bars = step
                        break
                    if high >= tp_price:
                        exit_price = tp_price
                        exit_reason = "tp_hit"
                        holding_bars = step
                        break
                else:
                    mfe_r = max(mfe_r, (entry_price - low) / risk)
                    mae_r = min(mae_r, (entry_price - high) / risk)
                    if high >= sl_price:
                        exit_price = sl_price
                        exit_reason = "sl_hit"
                        holding_bars = step
                        break
                    if low <= tp_price:
                        exit_price = tp_price
                        exit_reason = "tp_hit"
                        holding_bars = step
                        break

                exit_price = close
                holding_bars = step

            pnl_r = float((exit_price - entry_price) / risk) if direction == 1 else float((entry_price - exit_price) / risk)
            exit_idx = int(min(entry_idx + holding_bars, len(symbol_data) - 1))
            exit_time = pd.to_datetime(symbol_data.iloc[exit_idx]["time"], utc=True)

            trades.append(
                {
                    "symbol": signal["symbol"],
                    "side": signal["side"],
                    "direction": direction,
                    "create_time": signal["create_time"],
                    "entry_time": signal["entry_time"],
                    "exit_time": exit_time,
                    "create_idx": signal["create_idx"],
                    "entry_idx": entry_idx,
                    "exit_idx": exit_idx,
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "structural_stop_price": sl_price,
                    "stop_distance_pips": abs(entry_price - sl_price),
                    "stop_distance_atr": float(stop.stop_distance_atr),
                    "origin_swing_price": float(stop.origin_swing_price),
                    "origin_swing_idx": int(stop.origin_swing_idx),
                    "sweep_price": float(stop.sweep_price),
                    "sweep_idx": int(stop.sweep_idx),
                    "bos_break_price": float(stop.bos_break_price),
                    "bos_break_idx": int(stop.bos_break_idx),
                    "bos_level": signal.get("bos_level", np.nan),
                    "bos_direction": signal.get("bos_direction", np.nan),
                    "zone_low": signal.get("zone_low", np.nan),
                    "zone_high": signal.get("zone_high", np.nan),
                    "zone_size_atr": signal.get("zone_size_atr", np.nan),
                    "bars_since_fvg_creation": signal.get("bars_since_fvg_creation", np.nan),
                    "fvg_type": signal.get("fvg_type", "unknown"),
                    "fvg_mid": signal.get("fvg_mid", np.nan),
                    "pnl_r": pnl_r,
                    "holding_bars": holding_bars,
                    "exit_reason": exit_reason,
                    "mfe_r": float(mfe_r) if np.isfinite(mfe_r) else np.nan,
                    "mae_r": float(mae_r) if np.isfinite(mae_r) else np.nan,
                }
            )

        self.trades = pd.DataFrame(trades)
        if self.trades is not None and not self.trades.empty:
            self.trades = self.trades.sort_values(["symbol", "entry_time"]).reset_index(drop=True)
        return self.trades

    def save_experiment(self, name: str = "experiment_F_structural_sl") -> Path:
        if self.trades is None or self.trades.empty:
            raise ValueError("No trades to save")

        output_path = self.results_dir / f"{name}.csv"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.trades.to_csv(output_path, index=False)
        print(f"\nExperiment saved to {output_path}")
        return output_path

    def save_metrics(self, name: str = "experiment_F_structural_sl_metrics.json") -> Path:
        if self.trades is None or self.trades.empty:
            raise ValueError("No trades to save metrics")

        df = self.trades
        wins = df[df["pnl_r"] > 0]
        losses = df[df["pnl_r"] < 0]
        total = len(df)
        profit_factor = float(wins["pnl_r"].sum() / abs(losses["pnl_r"].sum())) if len(losses) > 0 else float("inf")
        metrics = {
            "total_trades": total,
            "wins": int(len(wins)),
            "losses": int(len(losses)),
            "win_rate": float(len(wins) / total) if total > 0 else 0.0,
            "expectancy_r": float(df["pnl_r"].mean()) if total > 0 else 0.0,
            "std_dev_r": float(df["pnl_r"].std()) if total > 1 else 0.0,
            "profit_factor": profit_factor,
            "avg_stop_distance_atr": float(df["stop_distance_atr"].mean()) if total > 0 else np.nan,
            "avg_holding_bars": float(df["holding_bars"].mean()) if total > 0 else np.nan,
        }
        output_path = self.results_dir / name
        self.results_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Metrics saved to {output_path}")
        return output_path

    def run(self) -> tuple[Path, Path]:
        self.load_all_ohlc()
        self.generate_signals()
        self.simulate_trades()
        csv_path = self.save_experiment()
        metrics_path = self.save_metrics()
        return csv_path, metrics_path


def main() -> None:
    builder = ExperimentFBuilder()

    print("=== FASE 4-5: FULL REBUILD FROM OHLC ===\n")
    print("Step 1: Load raw OHLC data...")
    builder.load_all_ohlc()
    print("Step 2: Generate BOS+FVG signals...")
    builder.generate_signals()
    print("Step 3: Simulate trades with structural stop loss...")
    builder.simulate_trades()
    print("Step 4: Save experiment and metrics...")
    builder.save_experiment()
    builder.save_metrics()


if __name__ == "__main__":
    main()
