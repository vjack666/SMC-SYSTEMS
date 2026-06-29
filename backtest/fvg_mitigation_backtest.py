from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from modules.fvg.backtest import _load
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import score_frame


@dataclass(frozen=True)
class MitigationBacktestConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    model_path: Path = Path("modules/fvg/models/fvg_v3.pkl")
    confidence_threshold: float = 0.62
    initial_capital_usd: float = 6000.0
    risk_pct_per_trade: float = 0.005
    atr_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    rr_ratio: float = 3.0
    max_hold_bars: int = 16
    train_split: float = 0.6
    mitigation_lookahead_bars: int = 300


def _risk_usd(config: MitigationBacktestConfig) -> float:
    return float(config.initial_capital_usd * config.risk_pct_per_trade)


def _intersects_zone(low: float, high: float, zone_low: float, zone_high: float) -> bool:
    return (low <= zone_high) and (high >= zone_low)


def _simulate_trade(
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    atr_arr: np.ndarray,
    entry_idx: int,
    entry_price: float,
    direction: int,
    sl_mult: float,
    rr_ratio: float,
    max_hold_bars: int,
) -> tuple[float, int]:
    atr = float(atr_arr[entry_idx])
    if not np.isfinite(atr) or atr <= 0.0:
        return 0.0, 0

    sl_dist = atr * sl_mult
    if not np.isfinite(sl_dist) or sl_dist <= 0.0:
        return 0.0, 0

    if direction == 1:
        sl = entry_price - sl_dist
        tp = entry_price + (sl_dist * rr_ratio)
    else:
        sl = entry_price + sl_dist
        tp = entry_price - (sl_dist * rr_ratio)

    for step in range(1, max_hold_bars + 1):
        j = entry_idx + step
        if j >= len(high_arr):
            break

        high = float(high_arr[j])
        low = float(low_arr[j])
        if direction == 1:
            # Conservative intrabar ordering: if both hit, count stop first.
            if low <= sl:
                return -1.0, step
            if high >= tp:
                return rr_ratio, step
        else:
            if high >= sl:
                return -1.0, step
            if low <= tp:
                return rr_ratio, step

    last_idx = min(entry_idx + max_hold_bars, len(close_arr) - 1)
    close_out = float(close_arr[last_idx])
    r = ((close_out - entry_price) / sl_dist) if direction == 1 else ((entry_price - close_out) / sl_dist)
    return float(r), int(max(1, last_idx - entry_idx))


def _build_events(scored: pd.DataFrame, threshold: float, lookahead_bars: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    low_arr = pd.to_numeric(scored["low"], errors="coerce").to_numpy(dtype=float)
    high_arr = pd.to_numeric(scored["high"], errors="coerce").to_numpy(dtype=float)
    close_arr = pd.to_numeric(scored["close"], errors="coerce").to_numpy(dtype=float)
    atr_arr = pd.to_numeric(scored["atr"], errors="coerce").to_numpy(dtype=float)
    conf_arr = pd.to_numeric(scored["ml_confidence"], errors="coerce").to_numpy(dtype=float)
    bull_arr = scored["fvg_bullish"].astype(bool).to_numpy()
    bear_arr = scored["fvg_bearish"].astype(bool).to_numpy()
    time_arr = scored["time"].to_numpy()

    prev2_high = pd.to_numeric(scored["high"].shift(2), errors="coerce").to_numpy(dtype=float)
    prev2_low = pd.to_numeric(scored["low"].shift(2), errors="coerce").to_numpy(dtype=float)

    qualified = np.where((conf_arr >= threshold) & (bull_arr | bear_arr))[0]

    for i in qualified:
        is_bull = bool(bull_arr[i])
        conf = float(conf_arr[i])

        if not np.isfinite(conf):
            continue

        direction = 1 if is_bull else -1
        side = "LONG" if direction == 1 else "SHORT"

        create_close = float(close_arr[i])
        atr_create = float(atr_arr[i])
        if not np.isfinite(atr_create) or atr_create <= 0.0:
            continue

        if direction == 1:
            zone_low = float(prev2_high[i])
            zone_high = float(low_arr[i])
            limit_price = zone_high
        else:
            zone_low = float(high_arr[i])
            zone_high = float(prev2_low[i])
            limit_price = zone_low

        if (not np.isfinite(zone_low)) or (not np.isfinite(zone_high)):
            continue
        if zone_high < zone_low:
            zone_low, zone_high = zone_high, zone_low

        abandoned = False
        first_mitigation_idx: int | None = None
        retest_idx: int | None = None

        j_end = min(len(scored), i + 1 + max(1, int(lookahead_bars)))
        for j in range(i + 1, j_end):
            low_j = float(low_arr[j])
            high_j = float(high_arr[j])
            if not np.isfinite(low_j) or not np.isfinite(high_j):
                continue

            touched_zone = _intersects_zone(low_j, high_j, zone_low, zone_high)
            if first_mitigation_idx is None and touched_zone:
                first_mitigation_idx = j

            if not abandoned:
                if direction == 1:
                    abandoned = low_j > zone_high
                else:
                    abandoned = high_j < zone_low
                continue

            if touched_zone:
                retest_idx = j
                break

        rows.append(
            {
                "create_idx": i,
                "create_time": time_arr[i],
                "direction": direction,
                "side": side,
                "create_close": create_close,
                "atr_create": atr_create,
                "zone_low": zone_low,
                "zone_high": zone_high,
                "limit_price": limit_price,
                "ml_confidence": conf,
                "first_mitigation_idx": first_mitigation_idx,
                "retest_idx": retest_idx,
            }
        )

    return pd.DataFrame(rows)


def _compute_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "total_trades": 0,
            "win_rate": np.nan,
            "profit_factor": np.nan,
            "expectancy": np.nan,
            "net_r": 0.0,
            "max_drawdown": np.nan,
            "sharpe": np.nan,
            "average_holding_bars": np.nan,
        }

    r = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    if r.empty:
        return {
            "total_trades": 0,
            "win_rate": np.nan,
            "profit_factor": np.nan,
            "expectancy": np.nan,
            "net_r": 0.0,
            "max_drawdown": np.nan,
            "sharpe": np.nan,
            "average_holding_bars": np.nan,
        }

    wins = r[r > 0.0]
    losses = r[r < 0.0]
    pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else float("inf")

    eq = r.cumsum()
    dd = float((eq - eq.cummax()).min())

    std = float(r.std(ddof=0))
    sharpe = float((r.mean() / std) * np.sqrt(len(r))) if std > 0 else np.nan

    return {
        "total_trades": int(len(r)),
        "win_rate": float((r > 0.0).mean()),
        "profit_factor": pf,
        "expectancy": float(r.mean()),
        "net_r": float(r.sum()),
        "max_drawdown": dd,
        "sharpe": sharpe,
        "average_holding_bars": float(pd.to_numeric(trades["holding_bars"], errors="coerce").mean()),
    }


def run_fvg_mitigation_comparison(config: MitigationBacktestConfig | None = None) -> dict[str, object]:
    if config is None:
        config = MitigationBacktestConfig()

    payload = joblib.load(config.model_path)
    model = payload["model"]

    risk_usd = _risk_usd(config)

    trade_rows: list[dict[str, object]] = []
    mitigation_rows: list[dict[str, object]] = []

    for symbol in config.symbols:
        frame = _load(config.data_dir, symbol)
        frame = detect_fvg(frame)

        split = int(len(frame) * config.train_split)
        scored = score_frame(frame.iloc[split:].copy(), model).reset_index(drop=True)
        high_arr = pd.to_numeric(scored["high"], errors="coerce").to_numpy(dtype=float)
        low_arr = pd.to_numeric(scored["low"], errors="coerce").to_numpy(dtype=float)
        close_arr = pd.to_numeric(scored["close"], errors="coerce").to_numpy(dtype=float)
        atr_arr = pd.to_numeric(scored["atr"], errors="coerce").to_numpy(dtype=float)

        events = _build_events(scored, config.confidence_threshold, config.mitigation_lookahead_bars)
        if events.empty:
            continue

        for side, direction in (("LONG", 1), ("SHORT", -1)):
            side_events = events[events["direction"] == direction].copy()
            if side_events.empty:
                continue

            never_mitigated = side_events["first_mitigation_idx"].isna()
            mitigation_bars = side_events["first_mitigation_idx"] - side_events["create_idx"]
            retested = side_events["retest_idx"].notna()
            retested_df = side_events[retested].copy()

            if not retested_df.empty:
                retest_distance_atr = (
                    (retested_df["limit_price"] - retested_df["create_close"]).abs() / retested_df["atr_create"].replace(0.0, np.nan)
                )
                avg_retest_distance = float(pd.to_numeric(retest_distance_atr, errors="coerce").mean())
            else:
                avg_retest_distance = np.nan

            mitigation_rows.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "qualified_fvg_count": int(len(side_events)),
                    "retested_count": int(retested.sum()),
                    "avg_bars_to_mitigation": float(pd.to_numeric(mitigation_bars[~never_mitigated], errors="coerce").mean()),
                    "avg_distance_creation_to_retest_atr": avg_retest_distance,
                    "pct_never_mitigated": float(never_mitigated.mean()),
                }
            )

            for _, ev in side_events.iterrows():
                create_idx = int(ev["create_idx"])
                retest_idx = ev["retest_idx"]

                for sl_mult in config.atr_multipliers:
                    # Strategy A: immediate entry on FVG detection.
                    entry_price_a = float(ev["create_close"])
                    pnl_r_a, hold_a = _simulate_trade(
                        high_arr=high_arr,
                        low_arr=low_arr,
                        close_arr=close_arr,
                        atr_arr=atr_arr,
                        entry_idx=create_idx,
                        entry_price=entry_price_a,
                        direction=direction,
                        sl_mult=float(sl_mult),
                        rr_ratio=config.rr_ratio,
                        max_hold_bars=config.max_hold_bars,
                    )
                    trade_rows.append(
                        {
                            "strategy": "A_immediate",
                            "symbol": symbol,
                            "side": side,
                            "sl_atr_mult": float(sl_mult),
                            "create_time": ev["create_time"],
                            "entry_time": ev["create_time"],
                            "entry_idx": create_idx,
                            "pnl_r": float(pnl_r_a),
                            "pnl_usd": float(pnl_r_a * risk_usd),
                            "holding_bars": int(hold_a),
                            "ml_confidence": float(ev["ml_confidence"]),
                            "risk_usd": float(risk_usd),
                        }
                    )

                    # Strategy B: mitigation/retest entry, one entry per FVG.
                    if pd.notna(retest_idx):
                        idx_b = int(retest_idx)
                        entry_price_b = float(ev["limit_price"])
                        pnl_r_b, hold_b = _simulate_trade(
                            high_arr=high_arr,
                            low_arr=low_arr,
                            close_arr=close_arr,
                            atr_arr=atr_arr,
                            entry_idx=idx_b,
                            entry_price=entry_price_b,
                            direction=direction,
                            sl_mult=float(sl_mult),
                            rr_ratio=config.rr_ratio,
                            max_hold_bars=config.max_hold_bars,
                        )
                        trade_rows.append(
                            {
                                "strategy": "B_mitigation",
                                "symbol": symbol,
                                "side": side,
                                "sl_atr_mult": float(sl_mult),
                                "create_time": ev["create_time"],
                                "entry_time": scored.iloc[idx_b]["time"],
                                "entry_idx": idx_b,
                                "pnl_r": float(pnl_r_b),
                                "pnl_usd": float(pnl_r_b * risk_usd),
                                "holding_bars": int(hold_b),
                                "ml_confidence": float(ev["ml_confidence"]),
                                "risk_usd": float(risk_usd),
                            }
                        )

    trades = pd.DataFrame(trade_rows)
    mitigation_stats = pd.DataFrame(mitigation_rows)

    metric_rows: list[dict[str, object]] = []
    if not trades.empty:
        for strategy in sorted(trades["strategy"].unique()):
            for sl_mult in sorted(trades["sl_atr_mult"].unique()):
                for symbol in sorted(trades["symbol"].unique()):
                    base = trades[(trades["strategy"] == strategy) & (trades["sl_atr_mult"] == sl_mult) & (trades["symbol"] == symbol)]

                    all_metrics = _compute_metrics(base)
                    metric_rows.append(
                        {
                            "strategy": strategy,
                            "sl_atr_mult": float(sl_mult),
                            "symbol": symbol,
                            "side": "ALL",
                            **all_metrics,
                        }
                    )

                    for side in ("LONG", "SHORT"):
                        sub = base[base["side"] == side]
                        metric_rows.append(
                            {
                                "strategy": strategy,
                                "sl_atr_mult": float(sl_mult),
                                "symbol": symbol,
                                "side": side,
                                **_compute_metrics(sub),
                            }
                        )

    metrics = pd.DataFrame(metric_rows)

    # Overall strategy-level answers for requested comparison.
    answers: dict[str, object] = {}
    if not metrics.empty:
        overall = metrics[metrics["side"] == "ALL"].copy()
        overall_group = (
            overall.groupby(["strategy", "sl_atr_mult"], dropna=False)
            .agg(
                expectancy_mean=("expectancy", "mean"),
                max_drawdown_mean=("max_drawdown", "mean"),
                profit_factor_mean=("profit_factor", "mean"),
            )
            .reset_index()
        )

        by_strategy = (
            overall_group.groupby("strategy", dropna=False)
            .agg(
                expectancy_mean=("expectancy_mean", "mean"),
                drawdown_mean=("max_drawdown_mean", "mean"),
                pf_mean=("profit_factor_mean", "mean"),
                expectancy_std=("expectancy_mean", "std"),
            )
            .reset_index()
        )

        best_expectancy_row = by_strategy.sort_values("expectancy_mean", ascending=False).iloc[0]
        best_pf_row = by_strategy.sort_values("pf_mean", ascending=False).iloc[0]
        lowest_dd_row = by_strategy.sort_values("drawdown_mean", ascending=False).iloc[0]

        stability_by_symbol: list[dict[str, object]] = []
        for symbol in sorted(overall["symbol"].unique()):
            sym = overall[overall["symbol"] == symbol]
            stable = (
                sym.groupby("strategy", dropna=False)["expectancy"]
                .std(ddof=0)
                .sort_values(ascending=True)
            )
            if not stable.empty:
                stability_by_symbol.append(
                    {
                        "symbol": symbol,
                        "most_stable_strategy": str(stable.index[0]),
                        "expectancy_std": float(stable.iloc[0]),
                    }
                )

        model_use = (
            trades.groupby("strategy", dropna=False)
            .agg(avg_confidence=("ml_confidence", "mean"), trade_count=("pnl_r", "count"))
            .reset_index()
            .sort_values(["avg_confidence", "trade_count"], ascending=[False, False])
        )

        answers = {
            "higher_expectancy": str(best_expectancy_row["strategy"]),
            "lower_drawdown": str(lowest_dd_row["strategy"]),
            "better_profit_factor": str(best_pf_row["strategy"]),
            "stability_by_symbol": stability_by_symbol,
            "better_model_usage_proxy": model_use.to_dict(orient="records"),
        }

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    if not trades.empty:
        trades.to_csv(results_dir / "fvg_mitigation_trade_log.csv", index=False)
    if not metrics.empty:
        metrics.to_csv(results_dir / "fvg_mitigation_metrics.csv", index=False)
    if not mitigation_stats.empty:
        mitigation_stats.to_csv(results_dir / "fvg_mitigation_diagnostics.csv", index=False)

    summary = {
        "config": {
            "initial_capital_usd": config.initial_capital_usd,
            "risk_pct_per_trade": config.risk_pct_per_trade,
            "risk_usd_per_trade": risk_usd,
            "atr_multipliers": list(config.atr_multipliers),
            "rr_ratio": config.rr_ratio,
            "confidence_threshold": config.confidence_threshold,
            "max_hold_bars": config.max_hold_bars,
            "mitigation_lookahead_bars": config.mitigation_lookahead_bars,
            "symbols": list(config.symbols),
        },
        "files": {
            "trade_log": "results/fvg_mitigation_trade_log.csv",
            "metrics": "results/fvg_mitigation_metrics.csv",
            "diagnostics": "results/fvg_mitigation_diagnostics.csv",
        },
        "comparison_answers": answers,
    }

    (results_dir / "fvg_mitigation_comparison_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
