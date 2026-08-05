"""
FASE 10 – Forensic Dataset y Visual Analytics
Genera el dataset forense completo, gráficas, replay dataset, tops/peors y forensic_report.md.
"""
from __future__ import annotations

import sys
import warnings
warnings.filterwarnings("ignore")

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats as sp_stats

# Project imports
from backtest.fvg_mitigation_backtest import _build_events, _simulate_trade, MitigationBacktestConfig, _risk_usd
from modules.bos.detector import BosConfig, detect_bos
from modules.choch.detector import detect_choch
from modules.fvg.backtest import _load
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import score_frame
from modules.ob.detector import detect_order_blocks
from pac_sequence.feature_builder import build_prev_day_levels
from pac_sequence.state_machine import StateMachineConfig, run_state_machine

import joblib

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path("data/mt5")
MODEL_PATH = Path("modules/fvg/models/fvg_v3.pkl")
OUT = Path("results")
CHARTS = OUT / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
TRAIN_SPLIT = 0.6
CONFIDENCE_THRESHOLD = 0.62
MITIGATION_LOOKAHEAD = 300
TTL_BARS = 64
RR_RATIO = 3.0
ATR_MULTIPLIERS = (1.0, 1.5, 2.0)
MAX_HOLD_BARS = 16
INITIAL_CAPITAL = 6000.0
RISK_PCT = 0.005

sns.set_theme(style="darkgrid", palette="muted", font_scale=0.9)
plt.rcParams.update({"figure.dpi": 120, "figure.figsize": (10, 5)})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _risk_usd_val():
    cfg = MitigationBacktestConfig(initial_capital_usd=INITIAL_CAPITAL, risk_pct_per_trade=RISK_PCT)
    return _risk_usd(cfg)


def _hour_from_sincos(sin_val: float, cos_val: float) -> int:
    angle = math.atan2(float(sin_val), float(cos_val))
    h = round((angle / (2 * math.pi) * 24) % 24)
    return int(h % 24)


def _safe_float(value):
    if value is None:
        return np.nan
    if isinstance(value, str) and value.strip().upper() == "NONE":
        return np.nan
    return float(value) if pd.notna(value) else np.nan


def _session_bucket(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 7 <= h < 11:
        return "london"
    if 13 <= h < 17:
        return "new_york"
    if 11 <= h < 13:
        return "overlap"
    if 0 <= h < 7:
        return "asia"
    return "off_session"


def savefig(name: str) -> None:
    path = CHARTS / name
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"  -> {path.name}")


# ---------------------------------------------------------------------------
# PHASE 0 – Load existing results
# ---------------------------------------------------------------------------
def load_base_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load D (base setups), E (ML-filtered), transitions, invalidations."""
    df_d = pd.read_csv(OUT / "experiment_D.csv")
    df_e = pd.read_csv(OUT / "experiment_E.csv")
    trans = pd.read_csv(OUT / "state_transition_log.csv")
    inv = pd.read_csv(OUT / "invalidation_log.csv")
    for df in [df_d, df_e]:
        for col in ["create_time", "entry_time", "exit_time"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True)
    trans["time"] = pd.to_datetime(trans["time"], utc=True)
    inv["time"] = pd.to_datetime(inv["time"], utc=True)
    return df_d, df_e, trans, inv


# ---------------------------------------------------------------------------
# PHASE 1 – Reconstruct FVG zone + price data from parquet
# ---------------------------------------------------------------------------
def reconstruct_price_data(df_d: pd.DataFrame) -> pd.DataFrame:
    """
    For each unique (symbol, create_idx) in D, reload parquet and extract:
    fvg_top, fvg_bottom, atr_create, entry_price, stop_price, take_profit_price,
    exit_price, bos_direction, choch_direction, swing_high, swing_low,
    ob_top, ob_bottom.
    """
    payload = joblib.load(MODEL_PATH)
    base_model = payload["model"]

    # Parse create_idx from setup_id: format = symbol_createidx_side_eventno
    def parse_create_idx(sid: str) -> int | None:
        parts = sid.split("_")
        try:
            return int(parts[1])
        except Exception:
            return None

    df_d = df_d.copy()
    df_d["create_idx_raw"] = df_d["setup_id"].apply(parse_create_idx)

    price_records: dict[str, dict[int, dict]] = {sym: {} for sym in SYMBOLS}

    for symbol in SYMBOLS:
        print(f"  Reconstructing {symbol}...")
        frame = _load(DATA_DIR, symbol)
        frame = detect_fvg(frame)
        frame = detect_bos(frame, BosConfig(followthrough_bars=18))
        frame = detect_choch(frame)
        frame = detect_order_blocks(frame)

        split = int(len(frame) * TRAIN_SPLIT)
        scored = score_frame(frame.iloc[split:].copy(), base_model).reset_index(drop=True)
        events = _build_events(scored, CONFIDENCE_THRESHOLD, MITIGATION_LOOKAHEAD)
        if events.empty:
            continue

        high_arr = pd.to_numeric(scored["high"], errors="coerce").to_numpy(dtype=float)
        low_arr = pd.to_numeric(scored["low"], errors="coerce").to_numpy(dtype=float)
        close_arr = pd.to_numeric(scored["close"], errors="coerce").to_numpy(dtype=float)
        atr_arr = pd.to_numeric(scored["atr"], errors="coerce").to_numpy(dtype=float)

        for _, ev in events.reset_index(drop=True).iterrows():
            create_idx = int(ev["create_idx"])
            direction = int(ev["direction"])
            zone_low = float(ev["zone_low"])
            zone_high = float(ev["zone_high"])
            atr_create = float(ev["atr_create"])
            fvg_mid = (zone_low + zone_high) / 2.0

            # State machine for this event
            sm = run_state_machine(
                scored=scored,
                create_idx=create_idx,
                direction=direction,
                zone_low=zone_low,
                zone_high=zone_high,
                config=StateMachineConfig(ttl_bars=TTL_BARS, mitigation_method="wick"),
                setup_id=f"{symbol}_{create_idx}",
            )
            entry_idx = sm["entry_idx"]
            mitigation_idx = sm["mitigation_idx"]

            # Entry on D/E: close at entry_idx
            if entry_idx is not None:
                entry_price = float(close_arr[int(entry_idx)])
                atr_entry = float(atr_arr[int(entry_idx)])
                for sl_mult in ATR_MULTIPLIERS:
                    sl_dist = atr_entry * float(sl_mult)
                    if direction == 1:
                        stop_price = entry_price - sl_dist
                        tp_price = entry_price + sl_dist * RR_RATIO
                    else:
                        stop_price = entry_price + sl_dist
                        tp_price = entry_price - sl_dist * RR_RATIO

                    key = (create_idx, round(sl_mult, 1))
                    row_data = scored.iloc[int(entry_idx)]
                    price_records[symbol][key] = {
                        "fvg_bottom": min(zone_low, zone_high),
                        "fvg_top": max(zone_low, zone_high),
                        "fvg_mid": fvg_mid,
                        "fvg_size_points": abs(zone_high - zone_low),
                        "fvg_size_atr": abs(zone_high - zone_low) / atr_create if atr_create > 0 else np.nan,
                        "atr_create": atr_create,
                        "entry_price": entry_price,
                        "stop_price": stop_price,
                        "take_profit_price": tp_price,
                        "mitigation_time": str(scored.iloc[int(mitigation_idx)]["time"]) if mitigation_idx is not None else None,
                        "bos_direction": _safe_float(row_data.get("bos_direction", np.nan)) if "bos_direction" in scored.columns else np.nan,
                        "choch_direction": 1 if str(row_data.get("choch_signal", "NONE")) == "CHOCH_BULLISH"
                                          else (-1 if str(row_data.get("choch_signal", "NONE")) == "CHOCH_BEARISH" else 0)
                                          if "choch_signal" in scored.columns else np.nan,
                        "swing_high_reference": _safe_float(row_data.get("swing_high", np.nan)) if "swing_high" in scored.columns else np.nan,
                        "swing_low_reference": _safe_float(row_data.get("swing_low", np.nan)) if "swing_low" in scored.columns else np.nan,
                        "ob_top": _safe_float(row_data.get("ob_top", np.nan)) if "ob_top" in scored.columns else np.nan,
                        "ob_bottom": _safe_float(row_data.get("ob_bottom", np.nan)) if "ob_bottom" in scored.columns else np.nan,
                    }

    # Merge back into df_d
    enriched_rows = []
    for _, row in df_d.iterrows():
        sym = str(row["symbol"])
        cidx = row["create_idx_raw"]
        sl = round(float(row["sl_atr_mult"]), 1)
        key = (cidx, sl) if cidx is not None else None
        pr = price_records.get(sym, {}).get(key, {}) if key is not None else {}
        enriched_rows.append({**row.to_dict(), **pr})

    return pd.DataFrame(enriched_rows)


# ---------------------------------------------------------------------------
# PHASE 2 – Build forensic_trades_dataset.csv
# ---------------------------------------------------------------------------
def build_forensic_dataset(df_d: pd.DataFrame, df_e: pd.DataFrame,
                            trans: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    # Mark accepted_by_ml
    e_ids = set(df_e["setup_id"].astype(str) + "_" + df_e["sl_atr_mult"].astype(str))
    df_d["_key"] = df_d["setup_id"].astype(str) + "_" + df_d["sl_atr_mult"].astype(str)
    df_d["accepted_by_ml"] = df_d["_key"].isin(e_ids)

    # Merge ml_oof_probability from E
    e_probs = df_e[["setup_id", "sl_atr_mult", "ml_oof_probability", "ml_confidence"]].copy()
    e_probs["_key"] = e_probs["setup_id"].astype(str) + "_" + e_probs["sl_atr_mult"].astype(str)
    prob_map = e_probs.set_index("_key")["ml_oof_probability"].to_dict()
    df_d["ml_oof_probability"] = df_d["_key"].map(prob_map)

    # ml_rank_percentile (among E trades only)
    e_prob_arr = df_e["ml_oof_probability"].dropna().to_numpy()
    def rank_pct(p):
        if pd.isna(p):
            return np.nan
        return float(sp_stats.percentileofscore(e_prob_arr, p, kind="rank")) / 100.0
    df_d["ml_rank_percentile"] = df_d["ml_oof_probability"].apply(rank_pct)

    # Timing extras
    df_d["hour"] = pd.to_datetime(df_d["entry_time"], utc=True).dt.hour
    df_d["weekday"] = pd.to_datetime(df_d["entry_time"], utc=True).dt.day_name()
    df_d["year"] = pd.to_datetime(df_d["entry_time"], utc=True).dt.year
    df_d["year_month"] = pd.to_datetime(df_d["entry_time"], utc=True).dt.to_period("M").astype(str)

    # Winner
    df_d["winner"] = (df_d["pnl_r"] > 0).astype(int)

    # Invalidation info from inv log
    inv_latest = inv.sort_values("time").groupby("setup_id").last().reset_index()
    inv_map = inv_latest.set_index("setup_id")[["time", "reason"]].to_dict(orient="index")
    df_d["invalidated"] = df_d["setup_id"].isin(inv_map)
    df_d["invalid_reason"] = df_d["setup_id"].map(lambda x: inv_map.get(x, {}).get("reason", None))
    df_d["invalidation_time"] = df_d["setup_id"].map(lambda x: inv_map.get(x, {}).get("time", None))

    # BOS / CHoCH timing from transitions
    def get_transition_time(setup_id, to_state):
        rows = trans[(trans["setup_id"] == setup_id) & (trans["to_state"] == to_state)]
        return rows["time"].min() if not rows.empty else None

    # For E trades only (manageable subset for performance)
    e_setup_ids = set(df_e["setup_id"].astype(str))
    bos_times = {sid: get_transition_time(sid, "STRUCTURE_CONFIRMED") for sid in e_setup_ids}
    choch_times = {sid: get_transition_time(sid, "CHOCH_DETECTED") for sid in e_setup_ids}
    df_d["bos_time"] = df_d["setup_id"].map(lambda x: bos_times.get(x))
    df_d["choch_time"] = df_d["setup_id"].map(lambda x: choch_times.get(x))

    # Approximate exit_price from pnl_r + entry/stop info
    def approx_exit(row):
        ep = row.get("entry_price", np.nan)
        sp = row.get("stop_price", np.nan)
        pnl_r = row.get("pnl_r", np.nan)
        if pd.isna(ep) or pd.isna(sp) or pd.isna(pnl_r):
            return np.nan
        sl_dist = abs(ep - sp)
        direction = 1 if str(row.get("side", "LONG")) == "LONG" else -1
        return ep + direction * pnl_r * sl_dist

    df_d["exit_price"] = df_d.apply(approx_exit, axis=1)

    # pnl_points
    df_d["pnl_points"] = df_d.apply(
        lambda r: (r.get("exit_price", np.nan) - r.get("entry_price", np.nan))
                  * (1 if str(r.get("side", "LONG")) == "LONG" else -1),
        axis=1
    )

    # Column ordering
    ordered_cols = [
        # IDENTIFICACIÓN
        "setup_id", "symbol", "side",
        # TEMPORALIDAD
        "create_time", "mitigation_time", "bos_time", "choch_time",
        "entry_time", "exit_time", "invalidation_time",
        # ESTRUCTURA
        "structure_scale", "structure_event", "bos_direction", "choch_direction",
        "swing_high_reference", "swing_low_reference",
        # FVG
        "fvg_top", "fvg_bottom", "fvg_size_points", "fvg_size_atr",
        "bars_since_fvg_creation",
        # MITIGACIÓN
        "mitigation_depth_pct", "mitigation_touch_count", "bars_since_mitigation",
        # ORDER BLOCK
        "ob_state", "ob_overlap_with_fvg", "ob_top", "ob_bottom",
        # LIQUIDEZ
        "distance_eqh", "distance_eql",
        "distance_prev_day_high", "distance_prev_day_low",
        # SESIÓN
        "session_bucket", "hour", "weekday",
        # ML
        "ml_confidence", "ml_oof_probability", "ml_rank_percentile", "accepted_by_ml",
        # ENTRADA
        "entry_price", "stop_price", "take_profit_price", "sl_atr_mult",
        # RESULTADO
        "exit_price", "pnl_points", "pnl_r", "pnl_usd",
        "holding_bars", "winner",
        # INVALIDACIÓN
        "invalidated", "invalid_reason",
        # EXTRAS
        "year", "year_month", "fvg_mid", "atr_create",
    ]
    existing = [c for c in ordered_cols if c in df_d.columns]
    extra = [c for c in df_d.columns if c not in ordered_cols and not c.startswith("_")]
    final = df_d[existing + extra].copy()
    final.drop(columns=["create_idx_raw"], errors="ignore", inplace=True)

    final.to_csv(OUT / "forensic_trades_dataset.csv", index=False)
    print(f"forensic_trades_dataset.csv: {len(final)} rows, {len(final.columns)} cols")
    return final


# ---------------------------------------------------------------------------
# PHASE 3 – Event Timeline
# ---------------------------------------------------------------------------
def build_event_timeline(df_forensic: pd.DataFrame, trans: pd.DataFrame,
                          inv: pd.DataFrame) -> pd.DataFrame:
    rows = []

    # State machine transitions
    for _, t in trans.iterrows():
        rows.append({
            "timestamp": t["time"],
            "setup_id": t["setup_id"],
            "event_type": t["to_state"],
            "bar_idx": t["bar_idx"],
            "state_before": t["from_state"],
            "state_after": t["to_state"],
            "reason": t["reason"],
        })

    # Invalidations
    for _, i in inv.iterrows():
        rows.append({
            "timestamp": i["time"],
            "setup_id": i["setup_id"],
            "event_type": "INVALIDATED",
            "bar_idx": i["bar_idx"],
            "state_before": None,
            "state_after": "INVALIDATED",
            "reason": i["reason"],
        })

    # Trade open/close from forensic (E trades)
    e_trades = df_forensic[df_forensic["accepted_by_ml"] == True].copy()
    for _, t in e_trades.iterrows():
        rows.append({
            "timestamp": t["entry_time"],
            "setup_id": t["setup_id"],
            "event_type": "TRADE_OPENED",
            "bar_idx": t.get("entry_idx", None),
            "state_before": "ENTRY_READY",
            "state_after": "TRADE_OPEN",
            "reason": f"ml_prob={t.get('ml_oof_probability', 'N/A'):.4f}" if pd.notna(t.get("ml_oof_probability")) else "ml_accepted",
        })
        rows.append({
            "timestamp": t["exit_time"],
            "setup_id": t["setup_id"],
            "event_type": "TRADE_CLOSED",
            "bar_idx": None,
            "state_before": "TRADE_OPEN",
            "state_after": "DONE",
            "reason": f"pnl_r={t.get('pnl_r', 0):.3f}",
        })

    timeline = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    timeline.to_csv(OUT / "forensic_event_timeline.csv", index=False)
    print(f"forensic_event_timeline.csv: {len(timeline)} rows")
    return timeline


# ---------------------------------------------------------------------------
# PHASE 4 – Replay Dataset (OHLCV + setup overlay)
# ---------------------------------------------------------------------------
def build_replay_dataset(df_forensic: pd.DataFrame) -> None:
    """Build OHLCV bars for each E trade: N_PRE bars before + trade duration bars."""
    N_PRE = 20
    payload = joblib.load(MODEL_PATH)
    base_model = payload["model"]

    e_trades = df_forensic[df_forensic["accepted_by_ml"] == True].drop_duplicates("setup_id").copy()
    replay_rows = []

    for symbol in SYMBOLS:
        sym_trades = e_trades[e_trades["symbol"] == symbol]
        if sym_trades.empty:
            continue

        frame = _load(DATA_DIR, symbol)
        frame = detect_fvg(frame)
        split = int(len(frame) * TRAIN_SPLIT)
        scored = score_frame(frame.iloc[split:].copy(), base_model).reset_index(drop=True)

        for _, t in sym_trades.iterrows():
            try:
                entry_idx = int(t["entry_idx"]) if "entry_idx" in t and pd.notna(t.get("entry_idx")) else None
            except Exception:
                entry_idx = None
            if entry_idx is None:
                continue

            duration = int(t.get("holding_bars", MAX_HOLD_BARS))
            start = max(0, entry_idx - N_PRE)
            end = min(len(scored), entry_idx + duration + 1)

            for idx in range(start, end):
                row = scored.iloc[idx]
                replay_rows.append({
                    "setup_id": t["setup_id"],
                    "symbol": symbol,
                    "timestamp": str(row["time"]),
                    "open": float(pd.to_numeric(row.get("open", np.nan), errors="coerce")),
                    "high": float(pd.to_numeric(row.get("high", np.nan), errors="coerce")),
                    "low": float(pd.to_numeric(row.get("low", np.nan), errors="coerce")),
                    "close": float(pd.to_numeric(row.get("close", np.nan), errors="coerce")),
                    "volume": float(pd.to_numeric(row.get("tick_volume", row.get("volume", np.nan)), errors="coerce")),
                    "bar_type": "pre" if idx < entry_idx else ("entry" if idx == entry_idx else "trade"),
                    "fvg_top": t.get("fvg_top", np.nan),
                    "fvg_bottom": t.get("fvg_bottom", np.nan),
                    "entry_price": t.get("entry_price", np.nan),
                    "stop_price": t.get("stop_price", np.nan),
                    "take_profit_price": t.get("take_profit_price", np.nan),
                    "pnl_r": t.get("pnl_r", np.nan),
                    "ml_oof_probability": t.get("ml_oof_probability", np.nan),
                })
    replay_df = pd.DataFrame(replay_rows)
    replay_df.to_csv(OUT / "replay_dataset.csv", index=False)
    print(f"replay_dataset.csv: {len(replay_df)} rows")


# ---------------------------------------------------------------------------
# PHASE 5 – Tops & Losers
# ---------------------------------------------------------------------------
def build_tops(df_forensic: pd.DataFrame) -> None:
    e = df_forensic[df_forensic["accepted_by_ml"] == True].copy()
    cols = ["setup_id", "symbol", "entry_time", "exit_time", "pnl_r",
            "ml_confidence", "ml_oof_probability", "session_bucket", "side",
            "structure_event", "mitigation_depth_pct", "fvg_size_atr", "hour", "weekday"]
    cols_avail = [c for c in cols if c in e.columns]

    top = e.nlargest(100, "pnl_r")[cols_avail]
    top.to_csv(OUT / "top_100_winners.csv", index=False)

    worst = e.nsmallest(100, "pnl_r")[cols_avail]
    worst.to_csv(OUT / "top_100_losers.csv", index=False)
    print(f"top_100_winners.csv / top_100_losers.csv saved")


# ---------------------------------------------------------------------------
# PHASE 6 – Charts
# ---------------------------------------------------------------------------
def _e_df(df_forensic: pd.DataFrame) -> pd.DataFrame:
    return df_forensic[df_forensic["accepted_by_ml"] == True].copy()


def chart_equity_curve(e: pd.DataFrame) -> None:
    e = e.sort_values("entry_time").reset_index(drop=True)
    equity = e["pnl_r"].cumsum()
    fig, ax = plt.subplots()
    ax.plot(equity.values, linewidth=1.5, color="#2196F3")
    ax.fill_between(range(len(equity)), 0, equity.values,
                    where=(equity.values > 0), alpha=0.2, color="#4CAF50")
    ax.fill_between(range(len(equity)), 0, equity.values,
                    where=(equity.values < 0), alpha=0.2, color="#F44336")
    ax.set_title(f"Equity Curve – Experiment E  (Total R = {equity.iloc[-1]:.1f})")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative R")
    savefig("equity_curve.png")


def chart_drawdown(e: pd.DataFrame) -> None:
    e = e.sort_values("entry_time").reset_index(drop=True)
    equity = e["pnl_r"].cumsum()
    drawdown = equity - equity.cummax()
    fig, ax = plt.subplots()
    ax.fill_between(range(len(drawdown)), drawdown.values, 0, color="#F44336", alpha=0.7)
    ax.plot(drawdown.values, color="#D32F2F", linewidth=0.8)
    ax.set_title("Drawdown Curve – Experiment E")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Drawdown (R)")
    savefig("drawdown_curve.png")


def chart_monthly_returns(e: pd.DataFrame) -> None:
    monthly = e.groupby("year_month")["pnl_r"].sum().reset_index()
    colors = ["#4CAF50" if v > 0 else "#F44336" for v in monthly["pnl_r"]]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(monthly["year_month"], monthly["pnl_r"], color=colors)
    ax.axhline(0, color="white", linewidth=0.8)
    ax.set_title("Monthly Returns (R) – Experiment E")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total R")
    plt.xticks(rotation=45, ha="right")
    savefig("monthly_returns.png")


def chart_yearly_returns(e: pd.DataFrame) -> None:
    yearly = e.groupby("year")["pnl_r"].sum().reset_index()
    colors = ["#4CAF50" if v > 0 else "#F44336" for v in yearly["pnl_r"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(yearly["year"].astype(str), yearly["pnl_r"], color=colors)
    ax.axhline(0, color="white", linewidth=0.8)
    for i, v in enumerate(yearly["pnl_r"]):
        ax.text(i, v + (2 if v >= 0 else -4), f"{v:.1f}R", ha="center", fontsize=9)
    ax.set_title("Yearly Returns (R) – Experiment E")
    ax.set_ylabel("Total R")
    savefig("yearly_returns.png")


def chart_pnl_distribution(e: pd.DataFrame) -> None:
    fig, ax = plt.subplots()
    ax.hist(e["pnl_r"], bins=50, color="#7986CB", edgecolor="none", alpha=0.85)
    ax.axvline(e["pnl_r"].mean(), color="#FFD54F", linewidth=1.5,
               label=f"Mean={e['pnl_r'].mean():.3f}R")
    ax.axvline(0, color="white", linewidth=1, linestyle="--")
    ax.set_title("PnL Distribution (R) – Experiment E")
    ax.set_xlabel("PnL (R)")
    ax.set_ylabel("Count")
    ax.legend()
    savefig("pnl_distribution.png")


def chart_expectancy_distribution(e: pd.DataFrame) -> None:
    if "year_month" not in e.columns:
        return
    monthly_exp = e.groupby("year_month")["pnl_r"].mean()
    fig, ax = plt.subplots()
    ax.hist(monthly_exp, bins=20, color="#26A69A", edgecolor="none", alpha=0.85)
    ax.axvline(monthly_exp.mean(), color="#FFD54F", linewidth=1.5,
               label=f"Mean={monthly_exp.mean():.3f}R")
    ax.axvline(0, color="white", linewidth=1, linestyle="--")
    ax.set_title("Monthly Expectancy Distribution – Experiment E")
    ax.set_xlabel("Monthly Expectancy (R/trade)")
    ax.legend()
    savefig("expectancy_distribution.png")


def chart_trade_duration(e: pd.DataFrame) -> None:
    fig, ax = plt.subplots()
    ax.hist(e["holding_bars"], bins=30, color="#FF8A65", edgecolor="none", alpha=0.85)
    ax.set_title("Trade Duration Distribution (bars) – Experiment E")
    ax.set_xlabel("Bars Held")
    ax.set_ylabel("Count")
    savefig("trade_duration_distribution.png")


def chart_winrate_by_hour(e: pd.DataFrame) -> None:
    if "hour" not in e.columns:
        return
    hr = e.groupby("hour")["winner"].agg(["mean", "count"]).reset_index()
    hr.columns = ["hour", "winrate", "trades"]
    hr = hr[hr["trades"] >= 5]
    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(hr["hour"], hr["winrate"], color="#42A5F5")
    ax.axhline(e["winner"].mean(), color="#FFD54F", linewidth=1.5, linestyle="--",
               label=f"Overall WR={e['winner'].mean():.2%}")
    ax.set_title("Win Rate by Hour (UTC) – Experiment E")
    ax.set_xlabel("Hour (UTC)")
    ax.set_ylabel("Win Rate")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend()
    savefig("winrate_by_hour.png")


def chart_winrate_by_weekday(e: pd.DataFrame) -> None:
    if "weekday" not in e.columns:
        return
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    wd = e.groupby("weekday")["winner"].agg(["mean", "count"]).reset_index()
    wd.columns = ["weekday", "winrate", "trades"]
    wd["weekday"] = pd.Categorical(wd["weekday"], categories=order, ordered=True)
    wd = wd.sort_values("weekday")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(wd["weekday"], wd["winrate"], color="#66BB6A")
    ax.axhline(e["winner"].mean(), color="#FFD54F", linewidth=1.5, linestyle="--",
               label=f"Overall WR={e['winner'].mean():.2%}")
    ax.set_title("Win Rate by Weekday – Experiment E")
    ax.set_ylabel("Win Rate")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend()
    savefig("winrate_by_weekday.png")


def chart_expectancy_by_symbol(e: pd.DataFrame) -> None:
    sym = e.groupby("symbol")["pnl_r"].agg(["mean", "sum", "count"]).reset_index()
    sym.columns = ["symbol", "expectancy", "total_r", "trades"]
    colors = ["#4CAF50" if v > 0 else "#F44336" for v in sym["expectancy"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(sym["symbol"], sym["expectancy"], color=colors)
    for bar, t in zip(bars, sym["trades"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"n={t}", ha="center", fontsize=8)
    ax.axhline(0, color="white", linewidth=0.8)
    ax.set_title("Expectancy by Symbol – Experiment E")
    ax.set_ylabel("Expectancy (R/trade)")
    savefig("expectancy_by_symbol.png")


def chart_expectancy_by_session(e: pd.DataFrame) -> None:
    sess = e.groupby("session_bucket")["pnl_r"].agg(["mean", "count"]).reset_index()
    sess.columns = ["session", "expectancy", "trades"]
    colors = ["#4CAF50" if v > 0 else "#F44336" for v in sess["expectancy"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(sess["session"], sess["expectancy"], color=colors)
    for bar, t in zip(bars, sess["trades"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                f"n={t}", ha="center", fontsize=8)
    ax.axhline(0, color="white", linewidth=0.8)
    ax.set_title("Expectancy by Session – Experiment E")
    ax.set_ylabel("Expectancy (R/trade)")
    savefig("expectancy_by_session.png")


def chart_ml_score_vs_expectancy(e: pd.DataFrame) -> None:
    if "ml_oof_probability" not in e.columns:
        return
    bins = pd.cut(e["ml_oof_probability"], bins=10)
    grp = e.groupby(bins, observed=True)["pnl_r"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(range(len(grp)), grp["pnl_r"].values, marker="o", color="#AB47BC", linewidth=2)
    ax.axhline(0, color="white", linewidth=0.8, linestyle="--")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels([str(b) for b in grp["ml_oof_probability"]], rotation=40, ha="right", fontsize=7)
    ax.set_title("ML Score Decile vs Mean Expectancy – Experiment E")
    ax.set_xlabel("ML Score Bin")
    ax.set_ylabel("Mean PnL (R)")
    savefig("ml_score_vs_expectancy.png")


def chart_ml_score_vs_winrate(e: pd.DataFrame) -> None:
    if "ml_oof_probability" not in e.columns:
        return
    bins = pd.cut(e["ml_oof_probability"], bins=10)
    grp = e.groupby(bins, observed=True)["winner"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(range(len(grp)), grp["winner"].values, marker="o", color="#26C6DA", linewidth=2)
    ax.axhline(e["winner"].mean(), color="#FFD54F", linewidth=1.2, linestyle="--",
               label=f"Overall WR={e['winner'].mean():.2%}")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels([str(b) for b in grp["ml_oof_probability"]], rotation=40, ha="right", fontsize=7)
    ax.set_title("ML Score Decile vs Win Rate – Experiment E")
    ax.set_xlabel("ML Score Bin")
    ax.set_ylabel("Win Rate")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend()
    savefig("ml_score_vs_winrate.png")


def chart_mitigation_depth_vs_expectancy(e: pd.DataFrame) -> None:
    if "mitigation_depth_pct" not in e.columns:
        return
    col = "mitigation_depth_pct"
    valid = e[[col, "pnl_r"]].dropna()
    bins = pd.cut(valid[col], bins=10)
    grp = valid.groupby(bins, observed=True)["pnl_r"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(range(len(grp)), grp["pnl_r"].values, marker="o", color="#EF5350", linewidth=2)
    ax.axhline(0, color="white", linewidth=0.8, linestyle="--")
    ax.set_title("Mitigation Depth % vs Mean Expectancy – Experiment E")
    ax.set_xlabel("Mitigation Depth Bin")
    ax.set_ylabel("Mean PnL (R)")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels([str(b) for b in grp[col]], rotation=40, ha="right", fontsize=7)
    savefig("mitigation_depth_vs_expectancy.png")


def chart_fvg_size_vs_expectancy(e: pd.DataFrame) -> None:
    col = "fvg_size_atr" if "fvg_size_atr" in e.columns else None
    if col is None:
        return
    valid = e[[col, "pnl_r"]].dropna()
    if valid.empty:
        return
    bins = pd.cut(valid[col], bins=10)
    grp = valid.groupby(bins, observed=True)["pnl_r"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(range(len(grp)), grp["pnl_r"].values, marker="o", color="#FFA726", linewidth=2)
    ax.axhline(0, color="white", linewidth=0.8, linestyle="--")
    ax.set_title("FVG Size (ATR) vs Mean Expectancy – Experiment E")
    ax.set_xlabel("FVG Size Bin")
    ax.set_ylabel("Mean PnL (R)")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels([str(b) for b in grp[col]], rotation=40, ha="right", fontsize=7)
    savefig("fvg_size_vs_expectancy.png")


def chart_bos_age_vs_expectancy(e: pd.DataFrame) -> None:
    col = "bars_since_fvg_creation"
    valid = e[[col, "pnl_r"]].dropna()
    bins = pd.cut(valid[col], bins=10)
    grp = valid.groupby(bins, observed=True)["pnl_r"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(range(len(grp)), grp["pnl_r"].values, marker="o", color="#8D6E63", linewidth=2)
    ax.axhline(0, color="white", linewidth=0.8, linestyle="--")
    ax.set_title("FVG Age (bars since creation) vs Mean Expectancy – Experiment E")
    ax.set_xlabel("FVG Age Bin")
    ax.set_ylabel("Mean PnL (R)")
    ax.set_xticks(range(len(grp)))
    ax.set_xticklabels([str(b) for b in grp[col]], rotation=40, ha="right", fontsize=7)
    savefig("bos_age_vs_expectancy.png")


def chart_feature_correlation_heatmap(e: pd.DataFrame) -> None:
    num_cols = [c for c in [
        "pnl_r", "ml_oof_probability", "ml_confidence",
        "mitigation_depth_pct", "mitigation_touch_count",
        "bars_since_fvg_creation", "bars_since_mitigation",
        "distance_prev_day_high", "distance_prev_day_low",
        "distance_eqh", "distance_eql", "ob_overlap_with_fvg",
        "fvg_size_atr", "holding_bars", "hour",
    ] if c in e.columns]
    corr = e[num_cols].corr()
    fig, ax = plt.subplots(figsize=(13, 11))
    sns.heatmap(corr, ax=ax, cmap="RdBu_r", center=0, annot=True, fmt=".2f",
                linewidths=0.4, annot_kws={"size": 7})
    ax.set_title("Feature Correlation Heatmap – Experiment E")
    savefig("feature_correlation_heatmap.png")


def chart_feature_importance_barplot() -> None:
    try:
        fi = pd.read_csv(OUT / "permutation_importance.csv")
    except Exception:
        return
    fi = fi.sort_values("importance_mean", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = ["#42A5F5" if v > 0 else "#90A4AE" for v in fi["importance_mean"]]
    ax.barh(fi["feature"], fi["importance_mean"], color=colors, xerr=fi["importance_std"], capsize=3)
    ax.set_title("Permutation Importance – Experiment E")
    ax.set_xlabel("Mean Importance (±std)")
    savefig("feature_importance_barplot.png")


# ---------------------------------------------------------------------------
# PHASE 7 – Scatter Plots
# ---------------------------------------------------------------------------
def scatter_plots(e: pd.DataFrame) -> None:
    scatter_pairs = [
        ("mitigation_depth_pct", "pnl_r", "mitigation_depth_pct_vs_pnl_r"),
        ("bars_since_fvg_creation", "pnl_r", "bars_since_fvg_creation_vs_pnl_r"),
        ("ml_oof_probability", "pnl_r", "ml_score_vs_pnl_r"),
        ("distance_prev_day_high", "pnl_r", "distance_prev_day_high_vs_pnl_r"),
        ("distance_prev_day_low", "pnl_r", "distance_prev_day_low_vs_pnl_r"),
        ("distance_eqh", "pnl_r", "distance_eqh_vs_pnl_r"),
        ("distance_eql", "pnl_r", "distance_eql_vs_pnl_r"),
    ]
    for x_col, y_col, fname in scatter_pairs:
        if x_col not in e.columns or y_col not in e.columns:
            continue
        valid = e[[x_col, y_col]].dropna()
        if valid.empty:
            continue
        fig, ax = plt.subplots(figsize=(9, 5))
        colors = ["#4CAF50" if v > 0 else "#F44336" for v in valid[y_col]]
        ax.scatter(valid[x_col], valid[y_col], c=colors, s=8, alpha=0.5)
        # Regression line
        try:
            slope, intercept, r, p, _ = sp_stats.linregress(valid[x_col], valid[y_col])
            xs = np.linspace(valid[x_col].min(), valid[x_col].max(), 100)
            ax.plot(xs, intercept + slope * xs, color="#FFD54F", linewidth=1.5,
                    label=f"r={r:.3f}, p={p:.3f}")
            ax.legend(fontsize=8)
        except Exception:
            pass
        ax.axhline(0, color="white", linewidth=0.8, linestyle="--")
        ax.set_title(f"Scatter: {x_col} vs {y_col} – Experiment E")
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        savefig(f"{fname}.png")
        print(f"  scatter -> {fname}.png")


# ---------------------------------------------------------------------------
# PHASE 8 – Forensic Report
# ---------------------------------------------------------------------------
def build_forensic_report(e: pd.DataFrame) -> None:
    top100 = pd.read_csv(OUT / "top_100_winners.csv")
    worst100 = pd.read_csv(OUT / "top_100_losers.csv")

    def profile(df):
        out = {}
        if "session_bucket" in df.columns:
            out["top_session"] = df["session_bucket"].mode().iloc[0] if not df.empty else "N/A"
        if "side" in df.columns:
            out["top_side"] = df["side"].mode().iloc[0] if not df.empty else "N/A"
        if "structure_event" in df.columns:
            out["top_structure"] = df["structure_event"].mode().iloc[0] if not df.empty else "N/A"
        if "hour" in df.columns:
            out["top_hour"] = int(df["hour"].mode().iloc[0]) if not df.empty else "N/A"
        if "symbol" in df.columns:
            out["top_symbol"] = df["symbol"].mode().iloc[0] if not df.empty else "N/A"
        if "ml_oof_probability" in df.columns:
            out["mean_ml_prob"] = round(df["ml_oof_probability"].mean(), 4)
        if "mitigation_depth_pct" in df.columns:
            out["mean_mit_depth"] = round(df["mitigation_depth_pct"].mean(), 4)
        return out

    win_profile = profile(top100)
    loss_profile = profile(worst100)

    # Best zone: ml_score decile
    if "ml_oof_probability" in e.columns:
        decile_exp = e.groupby(pd.cut(e["ml_oof_probability"], bins=5), observed=True)["pnl_r"].mean()
        best_ml_bin = str(decile_exp.idxmax())
        best_ml_exp = float(decile_exp.max())
    else:
        best_ml_bin = "N/A"
        best_ml_exp = np.nan

    # Best FVG size
    if "fvg_size_atr" in e.columns and e["fvg_size_atr"].notna().any():
        fvg_exp = e.groupby(pd.cut(e["fvg_size_atr"], bins=5), observed=True)["pnl_r"].mean()
        best_fvg_bin = str(fvg_exp.idxmax())
        best_fvg_exp = float(fvg_exp.max())
    else:
        best_fvg_bin = "N/A"
        best_fvg_exp = np.nan

    # Best mitigation depth
    mit_exp = e.groupby(pd.cut(e["mitigation_depth_pct"], bins=5), observed=True)["pnl_r"].mean()
    best_mit_bin = str(mit_exp.idxmax())
    best_mit_exp = float(mit_exp.max())

    # Best session
    sess_exp = e.groupby("session_bucket")["pnl_r"].mean().sort_values(ascending=False)
    best_session = sess_exp.index[0]
    best_session_exp = float(sess_exp.iloc[0])

    # Best hour
    hour_exp = e.groupby("hour")["pnl_r"].agg(["mean", "count"])
    hour_exp = hour_exp[hour_exp["count"] >= 10].sort_values("mean", ascending=False)
    best_hour = int(hour_exp.index[0]) if not hour_exp.empty else "N/A"
    best_hour_exp = float(hour_exp["mean"].iloc[0]) if not hour_exp.empty else np.nan

    # Best combination (session + side + structure_event)
    combo = e.groupby(["session_bucket", "side", "structure_event"], dropna=False)["pnl_r"].agg(["mean", "count"])
    combo = combo[combo["count"] >= 10].sort_values("mean", ascending=False)
    best_combo = combo.index[0] if not combo.empty else "N/A"
    best_combo_exp = float(combo["mean"].iloc[0]) if not combo.empty else np.nan
    best_combo_n = int(combo["count"].iloc[0]) if not combo.empty else 0

    lines = [
        "# Informe Forense – Experimento E",
        f"Fecha: 2026-05-30  |  Trades E: {len(e)}  |  Total R: {e['pnl_r'].sum():.2f}  |  PF: {len(e[e['pnl_r']>0])*3 / max(len(e[e['pnl_r']<=0]),1):.2f}",
        "",
        "---",
        "",
        "## 1. Qué tienen en común los mejores trades (top 100)",
        "",
        f"- Sesión dominante: **{win_profile.get('top_session', 'N/A')}**",
        f"- Dirección dominante: **{win_profile.get('top_side', 'N/A')}**",
        f"- Estructura dominante: **{win_profile.get('top_structure', 'N/A')}**",
        f"- Hora más frecuente (UTC): **{win_profile.get('top_hour', 'N/A')}h**",
        f"- Símbolo dominante: **{win_profile.get('top_symbol', 'N/A')}**",
        f"- Media ML probability: **{win_profile.get('mean_ml_prob', 'N/A')}**",
        f"- Media mitigation_depth_pct: **{win_profile.get('mean_mit_depth', 'N/A')}**",
        f"- Fuente: results/top_100_winners.csv",
        "",
        "---",
        "",
        "## 2. Qué tienen en común los peores trades (top 100 losers)",
        "",
        f"- Sesión dominante: **{loss_profile.get('top_session', 'N/A')}**",
        f"- Dirección dominante: **{loss_profile.get('top_side', 'N/A')}**",
        f"- Estructura dominante: **{loss_profile.get('top_structure', 'N/A')}**",
        f"- Hora más frecuente (UTC): **{loss_profile.get('top_hour', 'N/A')}h**",
        f"- Símbolo dominante: **{loss_profile.get('top_symbol', 'N/A')}**",
        f"- Media ML probability: **{loss_profile.get('mean_ml_prob', 'N/A')}**",
        f"- Media mitigation_depth_pct: **{loss_profile.get('mean_mit_depth', 'N/A')}**",
        f"- Fuente: results/top_100_losers.csv",
        "",
        "---",
        "",
        "## 3. Variables con mayor frecuencia en ganancias",
        "",
    ]

    # Feature frequency analysis
    win_trades = e[e["winner"] == 1]
    loss_trades = e[e["winner"] == 0]
    cat_cols = ["session_bucket", "side", "structure_event", "ob_state", "structure_scale"]
    for col in cat_cols:
        if col not in e.columns:
            continue
        wf = win_trades[col].value_counts(normalize=True)
        lf = loss_trades[col].value_counts(normalize=True)
        top_win = wf.index[0] if not wf.empty else "N/A"
        top_win_pct = wf.iloc[0] if not wf.empty else 0
        lines.append(f"- **{col}**: ganadores → `{top_win}` ({top_win_pct:.1%})")

    lines += [
        "",
        "---",
        "",
        "## 4. Variables con mayor frecuencia en pérdidas",
        "",
    ]
    for col in cat_cols:
        if col not in e.columns:
            continue
        lf = loss_trades[col].value_counts(normalize=True)
        top_loss = lf.index[0] if not lf.empty else "N/A"
        top_loss_pct = lf.iloc[0] if not lf.empty else 0
        lines.append(f"- **{col}**: perdedores → `{top_loss}` ({top_loss_pct:.1%})")

    lines += [
        "",
        "---",
        "",
        "## 5. Zonas de ML Score con mayor retorno",
        "",
        f"- Mejor quintil ML: **{best_ml_bin}** → mean expectancy = **{best_ml_exp:.4f}R**",
        f"- Fuente: results/experiment_E.csv / results/charts/ml_score_vs_expectancy.png",
        "",
        "---",
        "",
        "## 6. Tamaño de FVG que funciona mejor",
        "",
        f"- Mejor quintil FVG size (ATR): **{best_fvg_bin}** → mean expectancy = **{best_fvg_exp:.4f}R**",
        f"- Fuente: results/forensic_trades_dataset.csv / results/charts/fvg_size_vs_expectancy.png",
        "",
        "---",
        "",
        "## 7. Profundidad de mitigación óptima",
        "",
        f"- Mejor quintil mitigation_depth_pct: **{best_mit_bin}** → mean expectancy = **{best_mit_exp:.4f}R**",
        f"- Fuente: results/forensic_trades_dataset.csv / results/charts/mitigation_depth_vs_expectancy.png",
        "",
        "---",
        "",
        "## 8. Sesión con mejor rendimiento",
        "",
    ]

    for sess, exp in sess_exp.items():
        n = int(e[e["session_bucket"] == sess]["pnl_r"].count())
        lines.append(f"- **{sess}**: expectancy={exp:.4f}R  n={n}")
    lines += [
        "",
        f"→ Sesión óptima: **{best_session}** ({best_session_exp:.4f}R/trade)",
        f"- Fuente: results/charts/expectancy_by_session.png",
        "",
        "---",
        "",
        "## 9. Horas con mejor rendimiento",
        "",
    ]
    top_hours = hour_exp.head(5)
    for h, row in top_hours.iterrows():
        lines.append(f"- **{h}:00 UTC**: mean={row['mean']:.4f}R  n={int(row['count'])}")
    lines += [
        "",
        f"→ Mejor hora individual: **{best_hour}:00 UTC** ({best_hour_exp:.4f}R/trade)",
        f"- Fuente: results/charts/winrate_by_hour.png",
        "",
        "---",
        "",
        "## 10. Combinación exacta con mayor expectancy observado",
        "",
        f"- Combinación: **session={best_combo[0] if best_combo != 'N/A' else 'N/A'} | side={best_combo[1] if best_combo != 'N/A' else 'N/A'} | structure={best_combo[2] if best_combo != 'N/A' else 'N/A'}**",
        f"- Expectancy: **{best_combo_exp:.4f}R/trade**  n={best_combo_n}",
        f"- Fuente: results/forensic_trades_dataset.csv",
        "",
        "---",
        "",
        "## Archivos generados",
        "- `results/forensic_trades_dataset.csv`",
        "- `results/forensic_event_timeline.csv`",
        "- `results/replay_dataset.csv`",
        "- `results/top_100_winners.csv`",
        "- `results/top_100_losers.csv`",
        "- `results/charts/` — 18 gráficas + 7 scatter plots",
        "",
    ]

    (OUT / "forensic_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("forensic_report.md guardado")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== FASE 10: Forensic Analytics ===")
    print()

    print("Cargando datos base...")
    df_d, df_e, trans, inv = load_base_data()
    print(f"  D: {len(df_d)} rows | E: {len(df_e)} rows | trans: {len(trans)} | inv: {len(inv)}")

    print()
    print("PHASE 1 – Reconstruyendo precios desde parquet...")
    df_d_enriched = reconstruct_price_data(df_d)

    print()
    print("PHASE 2 – Construyendo forensic_trades_dataset.csv...")
    df_forensic = build_forensic_dataset(df_d_enriched, df_e, trans, inv)

    print()
    print("PHASE 3 – Construyendo forensic_event_timeline.csv...")
    build_event_timeline(df_forensic, trans, inv)

    print()
    print("PHASE 4 – Construyendo replay_dataset.csv...")
    build_replay_dataset(df_forensic)

    print()
    print("PHASE 5 – Tops y peors...")
    build_tops(df_forensic)

    print()
    print("PHASE 6 – Gráficas...")
    e = _e_df(df_forensic)
    chart_equity_curve(e)
    chart_drawdown(e)
    chart_monthly_returns(e)
    chart_yearly_returns(e)
    chart_pnl_distribution(e)
    chart_expectancy_distribution(e)
    chart_trade_duration(e)
    chart_winrate_by_hour(e)
    chart_winrate_by_weekday(e)
    chart_expectancy_by_symbol(e)
    chart_expectancy_by_session(e)
    chart_ml_score_vs_expectancy(e)
    chart_ml_score_vs_winrate(e)
    chart_mitigation_depth_vs_expectancy(e)
    chart_fvg_size_vs_expectancy(e)
    chart_bos_age_vs_expectancy(e)
    chart_feature_correlation_heatmap(e)
    chart_feature_importance_barplot()

    print()
    print("PHASE 7 – Scatter plots...")
    scatter_plots(e)

    print()
    print("PHASE 8 – Forensic Report...")
    build_forensic_report(e)

    print()
    print("=== COMPLETADO ===")
    charts_list = sorted(CHARTS.glob("*.png"))
    print(f"Charts generadas: {len(charts_list)}")
    for p in charts_list:
        print(f"  {p.name}")

    # Summary
    artifacts = [
        OUT / "forensic_trades_dataset.csv",
        OUT / "forensic_event_timeline.csv",
        OUT / "replay_dataset.csv",
        OUT / "top_100_winners.csv",
        OUT / "top_100_losers.csv",
        OUT / "forensic_report.md",
    ]
    print()
    print("Artefactos principales:")
    for a in artifacts:
        sz = a.stat().st_size if a.exists() else 0
        rows = ""
        if a.suffix == ".csv" and a.exists():
            try:
                rows = f"  ({len(pd.read_csv(a))} rows)"
            except Exception:
                pass
        print(f"  {a.name}  {sz//1024}KB{rows}")


if __name__ == "__main__":
    main()
