from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast

import numpy as np
import pandas as pd

from agents.orchestrator import AgentOrchestrator
from data import load_frame
from detectors import (
    CHOCH_BEARISH,
    CHOCH_BULLISH,
    BosConfig,
    compute_zones,
    detect_bos,
    detect_choch,
    detect_displacement,
    detect_fvg,
    detect_order_blocks,
    ZoneConfig,
)
from indicators import add_atr, add_ema, add_rsi, add_stochastic
from trend_context import build_trend_context_frame


@dataclass(frozen=True)
class ScalpingSignal:
    symbol: str
    time: str
    direction: int
    confidence: float
    entry: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class ScalpingConfig:
    trend_confidence_threshold: float = 0.45
    require_d1_h4_agreement: bool = False
    ob_fvg_proximity_atr: float = 1.5
    allow_xau_asia_session: bool = False
    relaxed_bos: bool = False
    use_confluence_mode: bool = True
    min_confluence_score: int = 2
    min_atr_ratio: float = 1.0
    use_ml_quality_filter: bool = False
    ml_model_path: str = "ml/models/quality_filter.pkl"
    # --- Item C: pesos de confluencia expuestos como config ---
    # Claves: trend, choch, ob, fvg, displacement, bos, swing, agents, sweep, ote
    # Valores del ICT_RULEBOOK.md (Appendix): MTF=3, CHOCH=3, Displacement=2,
    # FVG=2, OB=2, Liquidity sweep=2, BOS=1, OTE=1. (Item D ya cableo sweep/ote.)
    confluence_weights: dict[str, float] = field(default_factory=lambda: {
        "trend": 3.0,         # MTF alignment (rulebook=3)
        "choch": 3.0,         # CHOCH (rulebook=3)
        "ob": 2.0,            # Order Block (rulebook=2)
        "fvg": 2.0,           # FVG (rulebook=2)
        "displacement": 2.0,  # Displacement (rulebook=2)
        "bos": 1.0,           # BOS (rulebook=1)
        "swing": 1.0,         # OTE estructural (rulebook=1)
        "agents": 2.0,        # capa agentes (no en rulebook; peso conservador)
        "sweep": 2.0,        # sweep de liquidez (rulebook=2)
        "ote": 1.0,           # OTE/premium-discount (rulebook=1)
        "choch_bos_confirm": 2.0,  # CHOCH→BOS confirmación (libro 02 §3.1, SSES)
    })
    # --- Item D: sweep + OTE ---
    enable_sweep_filter: bool = True     # rechazar entradas de reversal sin sweep previo
    enable_ote_filter: bool = True       # requerir zona OTE/discount(premium) segun direccion
    sweep_lookback: int = 8              # ventana de reversal tras el sweep (coherente con INDUCEMENT_LOOKBACK)
    sequence_bos_gap: int = 10           # ventana para el BOS de confirmación tras el CHOCH (libro 02 §3.1)
    mandatory_choch_bos_confirm: bool = False  # GATE: en reversión exige CHOCH→BOS confirmado (libro 02 §3.1). OFF por defecto: medido en EURUSD M15 no aporta edge (PF/WR empeoran); activar solo tras validar en otro contexto.
    enable_detector_invalidation: bool = False  # Item E: degradar BOS/CHOCH/OB muertos (OFF=comportamiento actual)


def _session_filter(times: pd.Series, symbol: str, allow_xau_asia: bool) -> pd.Series:
    hours = pd.to_datetime(times, utc=True).dt.hour
    london = (hours >= 7) & (hours <= 11)
    new_york = (hours >= 13) & (hours <= 17)
    asia = (hours >= 0) & (hours <= 5)
    if allow_xau_asia and symbol == "XAUUSD":
        return london | new_york | asia
    return london | new_york


def _last_anchor(series: pd.Series, condition: pd.Series) -> pd.Series:
    marker = pd.Series(np.nan, index=series.index, dtype=float)
    marker.loc[condition] = series.loc[condition].astype(float)
    return marker.ffill()


def build_scalping_context(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    config: ScalpingConfig | None = None,
    orchestrator: AgentOrchestrator | None = None,
    progress_cb: Callable[[str, int, int, str], None] | None = None,
) -> pd.DataFrame:
    if config is None:
        config = ScalpingConfig()

    steps = [
        "load_frame", "detect_bos", "detect_choch", "detect_fvg",
        "detect_order_blocks", "detect_displacement", "compute_zones",
        "indicators", "trend_context", "filters", "sweep_ote",
        "confluence", "done",
    ]
    total_steps = len(steps)

    def _step(idx: int, msg: str) -> None:
        if progress_cb:
            progress_cb("context", idx, total_steps, f"{symbol} {msg}")

    _step(0, "loading data...")
    data = load_frame(data_dir, symbol, timeframe)

    _step(1, "detecting BOS...")
    data = detect_bos(data, BosConfig(followthrough_bars=18))
    _step(2, "detecting CHOCH...")
    data = detect_choch(data)
    _step(3, "detecting FVG...")
    data = detect_fvg(data)
    _step(4, "detecting order blocks...")
    data = detect_order_blocks(data)
    _step(5, "detecting displacement...")
    data = detect_displacement(data)
    _step(6, "computing zones...")
    data = compute_zones(data, ZoneConfig(swing_lookback=20))

    _step(7, "computing indicators...")
    data["atr"] = add_atr(data, 14)
    data["ema_fast"] = add_ema(data, 20)
    data["ema_slow"] = add_ema(data, 50)
    data["rsi"] = add_rsi(data, 14)
    data["atr_ratio"] = data["atr"] / data["atr"].rolling(20).mean().replace(0.0, np.nan)

    stoch = add_stochastic(data)
    data["stoch_k"] = stoch["stoch_k"]
    data["stoch_d"] = stoch["stoch_d"]

    _step(8, "building trend context (merge D1/H4)...")
    macro = build_trend_context_frame(symbol=symbol, ltf_frame=data, data_dir=data_dir)
    data["time"] = pd.to_datetime(data["time"].values.astype("datetime64[ns]"), utc=True)
    macro["time"] = pd.to_datetime(macro["time"].values.astype("datetime64[ns]"), utc=True)
    data = pd.merge_asof(data.sort_values("time"), macro.sort_values("time"), on="time", direction="backward")

    macro_direction = np.where(
        data["trend_score"] >= 30.0,
        "BULLISH",
        np.where(data["trend_score"] <= -30.0, "BEARISH", "RANGING"),
    )
    data["macro_direction"] = macro_direction
    data["d1_direction"] = np.where(data["d1_trend"].isin(["BULLISH", "BEARISH"]), data["d1_trend"], "RANGING")
    data["macro_trend"] = data["macro_direction"]

    _step(9, "computing filters...")
    regime_pass = ~data["regime_state"].isin(["LOW_VOL", "CHAOTIC"])
    trend_filter = (
        data["macro_direction"].isin(["BULLISH", "BEARISH"])
        & (data["trend_confidence"] >= float(config.trend_confidence_threshold))
        & regime_pass
    )

    session_filter = _session_filter(data["time"], symbol, config.allow_xau_asia_session)
    atr_filter = data["atr_ratio"].fillna(0.0) > config.min_atr_ratio

    if config.relaxed_bos:
        bos_up = data["bos_direction"].rolling(2, min_periods=1).max() > 0
        bos_down = data["bos_direction"].rolling(2, min_periods=1).min() < 0
    else:
        bos_up = data["bos_direction"] > 0
        bos_down = data["bos_direction"] < 0

        # --- Item E: degradar BOS muerto (invalidated/aged) ---
        if config.enable_detector_invalidation and "bos_status" in data.columns:
            bos_alive = data["bos_status"].isin(["active", "none"])
        else:
            bos_alive = pd.Series(True, index=data.index)

        bos_filter = (
            ((data["macro_direction"] == "BULLISH") & bos_up & bos_alive)
            | ((data["macro_direction"] == "BEARISH") & bos_down & bos_alive)
        )

    volume_filter = data["tick_volume"] >= (data["tick_volume"].rolling(20).mean().fillna(0.0) * 0.90)

    ob_cond = (data["ob_status"].isin(["active", "none"]) if (config.enable_detector_invalidation and "ob_status" in data.columns) else True)

    bullish_anchor = _last_anchor(
        data["close"],
        (data["fvg_bullish"] | data["ob_bullish"]) & ob_cond,
    )
    bearish_anchor = _last_anchor(
        data["close"],
        (data["fvg_bearish"] | data["ob_bearish"]) & ob_cond,
    )
    def _near(anchor):
        return ((data["close"] - anchor).abs() / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= config.ob_fvg_proximity_atr

    bull_near = _near(bullish_anchor)
    bear_near = _near(bearish_anchor)
    ob_fvg_filter = (
        ((data["macro_direction"] == "BULLISH") & bull_near)
        | ((data["macro_direction"] == "BEARISH") & bear_near)
    )

    # --- Filtros separados FVG / OB (rulebook=2 cada uno; antes compartian ob_fvg=2.0) ---
    fvg_bull_anchor = _last_anchor(data["close"], data["fvg_bullish"])
    fvg_bear_anchor = _last_anchor(data["close"], data["fvg_bearish"])
    ob_bull_anchor = _last_anchor(data["close"], data["ob_bullish"] & ob_cond)
    ob_bear_anchor = _last_anchor(data["close"], data["ob_bearish"] & ob_cond)
    fvg_bull_near = _near(fvg_bull_anchor)
    fvg_bear_near = _near(fvg_bear_anchor)
    ob_bull_near = _near(ob_bull_anchor)
    ob_bear_near = _near(ob_bear_anchor)
    data["filter_fvg"] = (
        ((data["macro_direction"] == "BULLISH") & fvg_bull_near)
        | ((data["macro_direction"] == "BEARISH") & fvg_bear_near)
    ).to_numpy()
    data["filter_ob"] = (
        ((data["macro_direction"] == "BULLISH") & ob_bull_near)
        | ((data["macro_direction"] == "BEARISH") & ob_bear_near)
    ).to_numpy()

    recent_bearish_choch = (data["choch_signal"] == CHOCH_BEARISH).rolling(10, min_periods=1).max().astype(bool)
    recent_bullish_choch = (data["choch_signal"] == CHOCH_BULLISH).rolling(10, min_periods=1).max().astype(bool)

    # --- Item E: degradar CHOCH muerto ---
    if config.enable_detector_invalidation and "choch_status" in data.columns:
        choch_alive = data["choch_status"].isin(["active", "none"])
    else:
        choch_alive = pd.Series(True, index=data.index)

    choch_filter = (
        ((data["macro_direction"] == "BULLISH") & (~recent_bearish_choch) & choch_alive)
        | ((data["macro_direction"] == "BEARISH") & (~recent_bullish_choch) & choch_alive)
    )

    swing_high_ref = data["high"].rolling(20, min_periods=5).max().shift(1)
    swing_low_ref = data["low"].rolling(20, min_periods=5).min().shift(1)
    swing_dist = np.minimum((data["close"] - swing_high_ref).abs(), (data["close"] - swing_low_ref).abs())
    swing_filter = (swing_dist / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= 1.5

    # --- Displacement reciente (rulebook=2; antes no entraba al score) ---
    recent_bullish_displacement = data["displacement_bullish"].rolling(10, min_periods=1).max().astype(bool)
    recent_bearish_displacement = data["displacement_bearish"].rolling(10, min_periods=1).max().astype(bool)
    data["filter_displacement"] = (
        ((data["macro_direction"] == "BULLISH") & recent_bullish_displacement)
        | ((data["macro_direction"] == "BEARISH") & recent_bearish_displacement)
    ).to_numpy()

    trend_up = data["ema_fast"] > data["ema_slow"]
    trend_down = data["ema_fast"] < data["ema_slow"]
    micro_filter = (
        ((data["macro_direction"] == "BULLISH") & trend_up & data["rsi"].between(40, 74))
        | ((data["macro_direction"] == "BEARISH") & trend_down & data["rsi"].between(26, 60))
    )

    # --- Item D: sweep + OTE (macro_direction ya existe) ---
    _step(10, "sweep + OTE filters...")
    # Sweep canonico compartido (libro 05 §0 #3) via detectors.liquidity_context.
    # Mismo horizonte (5) y ventana minima (2) que antes; la LOGICA ahora es unica.
    from detectors.liquidity_context import canonical_sweep

    swept = canonical_sweep(data, lookback=5, min_periods=2)
    data["liquidity_sweep_detected"] = (
        swept["liquidity_sweep_down"] | swept["liquidity_sweep_up"]
    ).to_numpy()
    data["recent_liquidity_sweep"] = (
        data["liquidity_sweep_detected"].rolling(config.sweep_lookback, min_periods=1).max().astype(bool).to_numpy()
    )
    zone = cast(pd.Series, data.get("premium_discount_zone", pd.Series(["OTE_NONE"] * len(data), index=data.index)))
    data["filter_ote"] = (
        ((data["macro_direction"] == "BULLISH") & zone.isin(["OTE_LONG", "DISCOUNT"]))
        | ((data["macro_direction"] == "BEARISH") & zone.isin(["OTE_SHORT", "PREMIUM"]))
    ).to_numpy()
    data["filter_sweep"] = (
        data["recent_liquidity_sweep"] if config.enable_sweep_filter else True
    )
    if not config.enable_ote_filter:
        data["filter_ote"] = True

    data["filter_trend"] = trend_filter
    data["filter_session"] = session_filter
    data["filter_atr"] = atr_filter
    data["filter_ob_fvg"] = ob_fvg_filter
    data["filter_bos"] = bos_filter
    data["filter_volume"] = volume_filter
    data["filter_micro"] = micro_filter
    data["filter_choch"] = choch_filter
    data["filter_swing"] = swing_filter

    # --- Secuencia canónica BOS→CHOCH→BOS (libro 02 §3.1, SSES): CHOCH (aviso de
    # giro) SEGUIDO de BOS de confirmación en la dirección del giro. Reusa
    # choch_signal (CHOCH_BULLISH/BEARISH) y bos_direction ya calculados (no re-detecta).
    # CHOCH opuesto al macro = aviso de giro; BOS en la dirección del giro posterior
    # en bos_gap velas = confirmación. Mantiene confirmación por cuerpo (market_structure)
    # y caducidad ATR (Item E choch_status/bos_status).
    recent_bos_bull = data["bos_direction"].rolling(config.sequence_bos_gap, min_periods=1).max() > 0
    recent_bos_bear = data["bos_direction"].rolling(config.sequence_bos_gap, min_periods=1).min() < 0
    choch_bos_confirm = (
        ((data["macro_direction"] == "BULLISH") & recent_bearish_choch & recent_bos_bull & choch_alive)
        | ((data["macro_direction"] == "BEARISH") & recent_bullish_choch & recent_bos_bear & choch_alive)
    )
    data["filter_choch_bos_confirm"] = choch_bos_confirm.to_numpy()

    if orchestrator is not None:
        data = orchestrator.analyze_context(data)
        decision_conf = data["agent_decision_confidence"].fillna(0.0)
        decision_bias = data["agent_decision_bias"].fillna("NEUTRAL")
        data["filter_agents"] = (
            (decision_conf >= 0.50)
            & ((decision_bias == "BULLISH") | (decision_bias == "BEARISH"))
        )
    else:
        data["filter_agents"] = True

    if "stoch_k" in data.columns:
        bearish_exhaust = (data["stoch_k"] > 80) & (data["stoch_k"].shift(1) <= 80)
        bullish_exhaust = (data["stoch_k"] < 20) & (data["stoch_k"].shift(1) >= 20)
        data["filter_stoch_exhaust"] = (
            ((data["macro_direction"] == "BULLISH") & ~bearish_exhaust.rolling(5, min_periods=1).max().astype(bool))
            | ((data["macro_direction"] == "BEARISH") & ~bullish_exhaust.rolling(5, min_periods=1).max().astype(bool))
            | (data["macro_direction"] == "RANGING")
        )
    else:
        data["filter_stoch_exhaust"] = True

    w = config.confluence_weights
    _step(11, "computing confluence score...")
    active = {
        "trend": data["filter_trend"].astype(float),
        "bos": data["filter_bos"].astype(float),
        "ob": data["filter_ob"].astype(float),
        "fvg": data["filter_fvg"].astype(float),
        "displacement": data["filter_displacement"].astype(float),
        "choch": data["filter_choch"].astype(float),
        "swing": data["filter_swing"].astype(float),
        "agents": data["filter_agents"].astype(float) if orchestrator is not None else 0.0,
        "sweep": data["filter_sweep"].astype(float) if config.enable_sweep_filter else 0.0,
        "ote": data["filter_ote"].astype(float) if config.enable_ote_filter else 0.0,
        "choch_bos_confirm": data["filter_choch_bos_confirm"].astype(float),
    }
    confluence_score = sum(active[k] * w.get(k, 1.0) for k in active)
    max_confluence = sum(w.get(k, 1.0) for k in active)
    data["confluence_score"] = confluence_score

    data["signal_confidence"] = (0.40 + (confluence_score / max_confluence) * 0.55).clip(lower=0.40, upper=0.95)

    mandatory_pass = data["filter_session"] & data["filter_atr"]

    # --- GATE CHOCH→BOS (libro 02 §3.1): en setups de REVERSION (hay CHOCH reciente
    # opuesto al macro = aviso de giro) la senal SOLO pasa si hay BOS de confirmacion
    # en esa direccion de giro. En a-favor (sin CHOCH opuesto) el gate no aplica.
    reversal_setup = recent_bearish_choch | recent_bullish_choch
    choch_bos_gate = (~reversal_setup) | data["filter_choch_bos_confirm"].astype(bool)
    if config.mandatory_choch_bos_confirm:
        signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score) & choch_bos_gate
    else:
        signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score)

    data["signal_direction"] = 0
    data.loc[signal_pass & (data["macro_direction"] == "BULLISH"), "signal_direction"] = 1
    data.loc[signal_pass & (data["macro_direction"] == "BEARISH"), "signal_direction"] = -1

    swing_low_20 = data["last_swing_low"].ffill().rolling(20, min_periods=1).apply(
        lambda s: s.dropna().iloc[-1] if not s.dropna().empty else float("nan"), raw=False
    )
    swing_high_20 = data["last_swing_high"].ffill().rolling(20, min_periods=1).apply(
        lambda s: s.dropna().iloc[-1] if not s.dropna().empty else float("nan"), raw=False
    )
    data["structural_sl"] = float("nan")
    long_mask = data["signal_direction"] == 1
    short_mask = data["signal_direction"] == -1
    data.loc[long_mask, "structural_sl"] = swing_low_20
    data.loc[short_mask, "structural_sl"] = swing_high_20

    has_swing = data["structural_sl"].notna()
    data.loc[long_mask & ~has_swing, "structural_sl"] = data.loc[long_mask & ~has_swing, "close"] - data.loc[long_mask & ~has_swing, "atr"]
    data.loc[short_mask & ~has_swing, "structural_sl"] = data.loc[short_mask & ~has_swing, "close"] + data.loc[short_mask & ~has_swing, "atr"]

    data["passed_all_filters"] = mandatory_pass & (data["confluence_score"] == max_confluence)
    _step(12, f"context ready ({len(data)} bars)")
    return data


def summarize_filter_diagnosis(context: pd.DataFrame) -> dict[str, int]:
    total = int(len(context))
    return {
        "total_bars": total,
        "rejected_by_trend_filter": int((~context["filter_trend"]).sum()),
        "rejected_by_session_filter": int((~context["filter_session"]).sum()),
        "rejected_by_atr_filter": int((~context["filter_atr"]).sum()),
        "rejected_by_ob_fvg_filter": int((~context["filter_ob_fvg"]).sum()),
        "rejected_by_bos_filter": int((~context["filter_bos"]).sum()),
        "rejected_by_volume_filter": int((~context["filter_volume"]).sum()),
        "passed_all_filters": int(context["passed_all_filters"].sum()),
    }


def build_scalping_signals(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    min_confidence: float = 0.65,
    config: ScalpingConfig | None = None,
) -> list[ScalpingSignal]:
    context = build_scalping_context(symbol=symbol, timeframe=timeframe, data_dir=data_dir, config=config)
    valid = context[(context["signal_direction"] != 0) & (context["signal_confidence"] >= min_confidence)]

    results: list[ScalpingSignal] = []
    for _, row in valid.iterrows():
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0.0:
            continue

        entry = float(row["close"])
        direction = int(row["signal_direction"])
        sl = entry - atr if direction == 1 else entry + atr
        tp = entry + (2.0 * atr) if direction == 1 else entry - (2.0 * atr)

        results.append(
            ScalpingSignal(
                symbol=symbol,
                time=str(row["time"]),
                direction=direction,
                confidence=float(row["signal_confidence"]),
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
            )
        )

    return results
