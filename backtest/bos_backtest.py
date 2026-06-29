from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd

from modules.bos.data_loader import MarketDataRequest, load_batch
from modules.bos.detector import BosConfig, detect_bos
from modules.bos.ml_model import BosMlConfig, build_training_set, score_events, train_model


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    timeframe: str = "M15"
    confidence_threshold: float = 0.70
    trend_confidence_threshold: float = 0.65
    rr_ratio: float = 2.0
    max_hold_bars: int = 24
    use_session_filter: bool = True
    session_start_hour_utc: int = 7
    session_end_hour_utc: int = 20
    require_trend_alignment: bool = True
    require_liquidity_sweep: bool = False
    bos_followthrough_bars: int = 24
    atr_regime_window: int = 20
    train_ratio: float = 0.40
    test_ratio: float = 0.30
    step_ratio: float = 0.15


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    pnl_r: float


def _simulate_trade(
    frame: pd.DataFrame,
    idx: int,
    direction: int,
    rr_ratio: float,
    max_hold_bars: int,
) -> float:
    atr = float(frame.iloc[idx]["atr"])
    if atr <= 0.0:
        return 0.0

    entry = float(frame.iloc[idx]["close"])
    sl_distance = atr
    tp_distance = atr * rr_ratio

    sl_price = entry - sl_distance if direction == 1 else entry + sl_distance
    tp_price = entry + tp_distance if direction == 1 else entry - tp_distance

    for offset in range(1, max_hold_bars + 1):
        if idx + offset >= len(frame):
            break
        row = frame.iloc[idx + offset]
        high = float(row["high"])
        low = float(row["low"])

        if direction == 1:
            if low <= sl_price:
                return -1.0
            if high >= tp_price:
                return rr_ratio
        else:
            if high >= sl_price:
                return -1.0
            if low <= tp_price:
                return rr_ratio

    final_close = float(frame.iloc[min(idx + max_hold_bars, len(frame) - 1)]["close"])
    if direction == 1:
        return (final_close - entry) / sl_distance
    return (entry - final_close) / sl_distance


def _max_drawdown(equity: pd.Series) -> float:
    running_peak = equity.cummax()
    drawdown = equity - running_peak
    return float(drawdown.min())


def _max_daily_drawdown_pct(times: pd.Series, pnl_r: pd.Series, risk_per_trade_pct: float = 1.0) -> float:
    frame = pd.DataFrame({"time": pd.to_datetime(times, utc=True), "pnl_r": pnl_r})
    if frame.empty:
        return 0.0

    frame["date"] = frame["time"].dt.date
    worst = 0.0
    for _, group in frame.groupby("date"):
        day_equity_pct = group["pnl_r"].cumsum() * risk_per_trade_pct
        day_peak = day_equity_pct.cummax()
        day_dd = day_equity_pct - day_peak
        worst = min(worst, float(day_dd.min()))
    return worst


def _sharpe(pnl_r: pd.Series) -> float:
    if pnl_r.empty:
        return 0.0
    std = float(pnl_r.std(ddof=0))
    if std == 0.0:
        return 0.0
    return float((pnl_r.mean() / std) * np.sqrt(252.0))


def _load_timeframe_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing timeframe data: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _macro_trend_frame(data_dir: Path, symbol: str) -> pd.DataFrame:
    d1 = _load_timeframe_frame(data_dir, symbol, "D1")
    h4 = _load_timeframe_frame(data_dir, symbol, "H4")

    for frame in (d1, h4):
        frame["atr"] = _compute_atr(frame, 14)
        ema_fast = frame["close"].ewm(span=20, adjust=False).mean()
        ema_slow = frame["close"].ewm(span=50, adjust=False).mean()
        frame["spread"] = (ema_fast - ema_slow) / frame["atr"].replace(0.0, np.nan)

    d1_state = pd.Series("RANGING", index=d1.index, dtype=object)
    d1_state[d1["spread"] > 0.01] = "BULLISH"
    d1_state[d1["spread"] < -0.01] = "BEARISH"

    h4_state = pd.Series("RANGING", index=h4.index, dtype=object)
    h4_state[h4["spread"] > 0.01] = "BULLISH"
    h4_state[h4["spread"] < -0.01] = "BEARISH"

    d1_trend = pd.DataFrame(
        {
            "time": d1["time"],
            "d1_trend": d1_state,
            "d1_conf": d1["spread"].abs().clip(lower=0.0, upper=2.0) / 2.0,
        }
    )
    h4_trend = pd.DataFrame(
        {
            "time": h4["time"],
            "h4_trend": h4_state,
            "h4_conf": h4["spread"].abs().clip(lower=0.0, upper=2.0) / 2.0,
        }
    )

    merged = pd.merge_asof(
        d1_trend.sort_values("time"),
        h4_trend.sort_values("time"),
        on="time",
        direction="forward",
    )
    merged["trend_agreement"] = (
        merged["d1_trend"].isin(["BULLISH", "BEARISH"])
        & (merged["d1_trend"] == merged["h4_trend"])
    )
    merged["macro_trend"] = np.where(merged["trend_agreement"], merged["d1_trend"], "RANGING")
    merged["macro_trend_confidence"] = merged[["d1_conf", "h4_conf"]].mean(axis=1)
    return merged[["time", "macro_trend", "trend_agreement", "macro_trend_confidence"]].sort_values("time")


def _walk_forward_ranges(length: int, train_ratio: float, test_ratio: float, step_ratio: float) -> Iterable[tuple[int, int]]:
    train_size = max(int(length * train_ratio), 500)
    test_size = max(int(length * test_ratio), 200)
    step_size = max(int(length * step_ratio), test_size)

    start = 0
    while True:
        train_end = start + train_size
        test_end = train_end + test_size
        if test_end > length:
            break
        yield train_end, test_end
        start += step_size


def run_backtest(config: BacktestConfig | None = None) -> dict[str, float | int]:
    if config is None:
        config = BacktestConfig()

    requests = [MarketDataRequest(symbol=item, timeframe=config.timeframe) for item in config.symbols]
    raw = load_batch(config.data_dir, requests)

    trades: List[TradeResult] = []
    for symbol in config.symbols:
        symbol_data = raw.loc[raw["symbol"] == symbol].copy()
        symbol_data = detect_bos(symbol_data, BosConfig(followthrough_bars=config.bos_followthrough_bars))
        symbol_data = build_training_set(symbol_data, BosMlConfig())
        symbol_data = symbol_data.sort_values("time").reset_index(drop=True)

        macro = _macro_trend_frame(config.data_dir, symbol)
        symbol_data = pd.merge_asof(
            symbol_data.sort_values("time"),
            macro,
            on="time",
            direction="backward",
        )

        symbol_data["atr_mean_20"] = symbol_data["atr"].rolling(config.atr_regime_window).mean()

        for train_end, test_end in _walk_forward_ranges(
            len(symbol_data),
            config.train_ratio,
            config.test_ratio,
            config.step_ratio,
        ):
            train_set = symbol_data.iloc[:train_end].copy()
            test_set = symbol_data.iloc[train_end:test_end].copy()

            try:
                model = train_model(train_set)
            except ValueError:
                continue
            scored = score_events(test_set, model)

            signal_mask = (
                (scored["bos_direction"] != 0)
                & (scored["ml_confidence"] >= config.confidence_threshold)
            )

            regime_ok = scored["atr"] >= scored["atr_mean_20"]
            signal_mask = signal_mask & regime_ok.fillna(False)

            macro_ok = (
                scored["trend_agreement"].fillna(False)
                & (scored["macro_trend_confidence"].fillna(0.0) > config.trend_confidence_threshold)
                & (
                    ((scored["bos_direction"] == 1) & (scored["macro_trend"] == "BULLISH"))
                    | ((scored["bos_direction"] == -1) & (scored["macro_trend"] == "BEARISH"))
                )
            )
            signal_mask = signal_mask & macro_ok

            if config.require_trend_alignment:
                trend_aligned = (
                    ((scored["bos_direction"] == 1) & (scored["ema_spread"] > 0.0))
                    | ((scored["bos_direction"] == -1) & (scored["ema_spread"] < 0.0))
                )
                signal_mask = signal_mask & trend_aligned

            if config.use_session_filter:
                utc_hours = pd.to_datetime(scored["time"], utc=True).dt.hour
                if symbol == "XAUUSD":
                    start_hour = 6
                    end_hour = 20
                else:
                    start_hour = config.session_start_hour_utc
                    end_hour = 21
                in_session = (utc_hours >= start_hour) & (utc_hours <= end_hour)
                signal_mask = signal_mask & in_session

            if config.require_liquidity_sweep:
                sweep_confirmed = (
                    ((scored["bos_direction"] == 1) & scored["recent_sweep_down"])
                    | ((scored["bos_direction"] == -1) & scored["recent_sweep_up"])
                )
                signal_mask = signal_mask & sweep_confirmed

            signals = scored.loc[signal_mask]

            for idx in signals.index:
                direction = int(scored.loc[idx, "bos_direction"])
                pnl_r = _simulate_trade(scored, scored.index.get_loc(idx), direction, config.rr_ratio, config.max_hold_bars)
                trade = TradeResult(
                    symbol=symbol,
                    entry_time=str(scored.loc[idx, "time"]),
                    exit_time=str(scored.iloc[min(scored.index.get_loc(idx) + config.max_hold_bars, len(scored) - 1)]["time"]),
                    direction=direction,
                    pnl_r=float(pnl_r),
                )
                trades.append(trade)

    if not trades:
        raise RuntimeError("No trades were produced by BOS strategy.")

    pnl_series = pd.Series([item.pnl_r for item in trades], dtype=float)
    wins = pnl_series[pnl_series > 0.0]
    losses = pnl_series[pnl_series < 0.0]
    equity = pnl_series.cumsum()

    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = float(losses.sum()) if not losses.empty else 0.0
    profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0.0 else float("inf")

    metrics: dict[str, float | int] = {
        "total_trades": int(len(trades)),
        "win_rate": float((pnl_series > 0.0).mean()),
        "profit_factor": float(profit_factor),
        "max_drawdown_r": float(_max_drawdown(equity)),
        "max_drawdown_pct": float(abs(_max_drawdown(equity)) * 1.0),
        "max_daily_drawdown_pct": float(
            abs(_max_daily_drawdown_pct(pd.Series([item.entry_time for item in trades], dtype="string"), pnl_series))
        ),
        "sharpe_ratio": float(_sharpe(pnl_series)),
        "expectancy_r": float(pnl_series.mean()),
    }

    output_dir = Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "bos_trades.json").write_text(
        json.dumps([asdict(item) for item in trades], indent=2),
        encoding="utf-8",
    )
    (output_dir / "bos_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    print("Starting backtest, this may take a few minutes.")
    metrics = run_backtest()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
