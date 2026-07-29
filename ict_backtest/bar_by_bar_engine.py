"""Bar-by-bar engine — módulo autónomo.

Uso:
    from bar_by_bar_engine import analyze_bar_by_bar, compute_backtest_metrics
    signals = analyze_bar_by_bar(m5_df, htf_bias="BULLISH")
    metrics = compute_backtest_metrics(m5_df, signals)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers scoring M5 (0-3)
# ---------------------------------------------------------------------------
def _near_level(level: float, m15_zone_mid: float, tol: float = 0.0020) -> bool:
    return abs(level - m15_zone_mid) <= tol


def _score_m5_for_signal(
    last_m5_low: float,
    last_m5_high: float,
    last_m5_close: float,
    last_m5_open: float,
    m15_zone_high: float,
    m15_zone_low: float,
    direction: int,
) -> tuple[int, list[str]]:
    matches: list[str] = []
    # simple proximity-based scoring (±20 pips = 0.0020)
    touches_m15 = (last_m5_low <= m15_zone_high + 0.0020) and (last_m5_high >= m15_zone_low - 0.0020)
    if touches_m15:
        matches.append("overlap")
    if direction == 1 and last_m5_close > last_m5_open and last_m5_low <= m15_zone_low + 0.0020:
        matches.append("displacement")
    if direction == -1 and last_m5_close < last_m5_open and last_m5_high >= m15_zone_high - 0.0020:
        matches.append("displacement")
    return len(matches), matches


# ---------------------------------------------------------------------------
# Tipos internos (privados)
# ---------------------------------------------------------------------------
class _Candle:
    __slots__ = ("tf", "time", "open", "high", "low", "close", "bar_index")
    def __init__(self, tf: str, time: pd.Timestamp, open: float, high: float,
                 low: float, close: float, bar_index: int) -> None:
        self.tf = tf
        self.time = time
        self.open = float(open)
        self.high = float(high)
        self.low = float(low)
        self.close = float(close)
        self.bar_index = bar_index


class _TFState:
    __slots__ = ("tf", "candles", "trend", "last_bos_bar",
                 "last_bos_direction", "zone_high", "zone_low",
                 "sweep_high", "sweep_low")
    def __init__(self, tf: str) -> None:
        self.tf = tf
        self.candles: list[_Candle] = []
        self.trend: str = "RANGING"
        self.last_bos_bar: int | None = None
        self.last_bos_direction: int = 0
        self.zone_high: float = 0.0
        self.zone_low: float = 0.0
        self.sweep_high: float = 0.0
        self.sweep_low: float = 0.0

    @property
    def closed_count(self) -> int:
        return len(self.candles)

    @property
    def last_candle(self) -> _Candle | None:
        return self.candles[-1] if self.candles else None


class _MultiTFState:
    def __init__(self) -> None:
        self._tfs: dict[str, _TFState] = {
            tf: _TFState(tf) for tf in ("M5", "M15", "H1", "H4", "D1")
        }

    def update(self, tf: str, candle: _Candle) -> None:
        st = self._tfs[tf]
        st.candles.append(candle)
        if len(st.candles) >= 2:
            recent = st.candles[-6:-1]
            if len(recent) >= 2:
                swing_high = max(c.high for c in recent)
                swing_low = min(c.low for c in recent)
                if candle.close > swing_high:
                    st.last_bos_bar = candle.bar_index
                    st.last_bos_direction = 1
                    st.zone_low = swing_low
                    st.zone_high = candle.high
                    st.trend = "BULLISH"
                elif candle.close < swing_low:
                    st.last_bos_bar = candle.bar_index
                    st.last_bos_direction = -1
                    st.zone_low = candle.low
                    st.zone_high = swing_high
                    st.trend = "BEARISH"
        prev = st.candles[-2] if len(st.candles) >= 2 else None
        if prev is not None:
            if candle.low < prev.low and candle.close > prev.low:
                st.sweep_low = candle.low
            if candle.high > prev.high and candle.close < prev.high:
                st.sweep_high = candle.high

    def get_tf(self, tf: str) -> _TFState:
        return self._tfs[tf]

    def get_bias(self) -> str:
        d1 = self._tfs["D1"]
        return d1.trend if d1.trend != "RANGING" else "RANGING"


class _BarAggregator:
    def __init__(self) -> None:
        self._bufs: dict[str, list[tuple[int, dict]]] = {tf: [] for tf in ("M15", "H1", "H4", "D1")}
        self._rules = {"M15": 3, "H1": 12, "H4": 48, "D1": 288}

    def add_bar(self, row: pd.Series, bar_idx: int) -> dict[str, _Candle]:
        bar = {
            "time": row["time"], "open": float(row["open"]),
            "high": float(row["high"]), "low": float(row["low"]),
            "close": float(row["close"]),
        }
        out: dict[str, _Candle] = {}
        for tf, need in self._rules.items():
            buf = self._bufs[tf]
            buf.append((bar_idx, bar))
            if len(buf) >= need:
                seg = buf[:need]
                self._bufs[tf] = buf[need:]
                out[tf] = _Candle(
                    tf=tf, time=seg[0][1]["time"],
                    open=seg[0][1]["open"], high=max(b[1]["high"] for b in seg),
                    low=min(b[1]["low"] for b in seg), close=seg[-1][1]["close"],
                    bar_index=seg[-1][0],
                )
        return out


# ---------------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------------
@dataclass
class BarByBarSignal:
    direction: int
    entry: float
    sl: float
    tp: float
    entry_bar: int
    entry_time: pd.Timestamp
    d1_bias: str
    m15_zone_high: float
    m15_zone_low: float
    exec_tf: str = "M5"
    exec_m5_score: int = 0
    exec_m5_matches: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class BarByBarTrade:
    signal: BarByBarSignal
    entry: float
    exit_price: float
    direction: int
    pnl_r: float
    exit_reason: str
    hold_bars: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp


@dataclass
class BarByBarMetrics:
    trades: list[BarByBarTrade]
    total_trades: int
    wins: int
    losses: int
    winrate: float
    pf: float
    expectancy_r: float
    total_r: float
    max_dd_r: float
    signals_generated: int


# ---------------------------------------------------------------------------
# Motor público
# ---------------------------------------------------------------------------
def analyze_bar_by_bar(
    m5_df: pd.DataFrame,
    *,
    htf_bias: str = "BULLISH",
    min_rr: float = 3.0,
    cooldown_bars: int = 60,
) -> list[BarByBarSignal]:
    """Analiza M5 barra por barra y emite señales como dicts planos."""
    if m5_df is None or len(m5_df) == 0:
        return []

    state = _MultiTFState()
    agg = _BarAggregator()
    signals: list[BarByBarSignal] = []
    last_sig_bar = -9999

    bias = htf_bias.upper()
    if bias not in ("BULLISH", "BEARISH"):
        bias = "BULLISH"

    for i in range(len(m5_df)):
        row = m5_df.iloc[i]
        m5_candle = _Candle("M5", row["time"],
                            float(row["open"]), float(row["high"]),
                            float(row["low"]), float(row["close"]), i)
        state.update("M5", m5_candle)
        new_candles = agg.add_bar(row, i)
        for tf, candle in new_candles.items():
            state.update(tf, candle)

        if i - last_sig_bar < cooldown_bars:
            continue

        m15 = state.get_tf("M15")
        if m15.zone_high <= 0 or m15.zone_low <= 0:
            continue

        m5_state = state.get_tf("M5")
        if m5_state.closed_count < 3:
            continue

        last_m5 = m5_state.last_candle
        if last_m5 is None:
            continue

        if not (last_m5.low <= m15.zone_high and last_m5.high >= m15.zone_low):
            continue

        if bias == "BULLISH":
            if last_m5.low < m15.zone_low and last_m5.close > m15.zone_low:
                if last_m5.close > last_m5.open:
                    entry = float(row["open"]) if i + 1 < len(m5_df) else float(last_m5.close)
                    sl = float(last_m5.low) - 0.3 * (last_m5.high - last_m5.low)
                    risk = abs(entry - sl)
                    if risk <= 0.00001:
                        continue
                    tp = entry + min_rr * risk
                    score, matches = _score_m5_for_signal(
                        last_m5.low, last_m5.high, last_m5.close, last_m5.open,
                        m15.zone_high, m15.zone_low, 1,
                    )
                    signals.append(BarByBarSignal(
                        direction=1, entry=entry, sl=sl, tp=tp,
                        entry_bar=i, entry_time=row["time"],
                        d1_bias=bias, m15_zone_high=m15.zone_high,
                        m15_zone_low=m15.zone_low,
                        exec_m5_score=score, exec_m5_matches=matches,
                        meta={"type": "sweep_long", "m5_sweep_low": last_m5.low},
                    ))
                    last_sig_bar = i

        elif bias == "BEARISH":
            if last_m5.high > m15.zone_high and last_m5.close < m15.zone_high:
                if last_m5.close < last_m5.open:
                    entry = float(row["open"]) if i + 1 < len(m5_df) else float(last_m5.close)
                    sl = float(last_m5.high) + 0.3 * (last_m5.high - last_m5.low)
                    risk = abs(sl - entry)
                    if risk <= 0.00001:
                        continue
                    tp = entry - min_rr * risk
                    score, matches = _score_m5_for_signal(
                        last_m5.low, last_m5.high, last_m5.close, last_m5.open,
                        m15.zone_high, m15.zone_low, -1,
                    )
                    signals.append(BarByBarSignal(
                        direction=-1, entry=entry, sl=sl, tp=tp,
                        entry_bar=i, entry_time=row["time"],
                        d1_bias=bias, m15_zone_high=m15.zone_high,
                        m15_zone_low=m15.zone_low,
                        exec_m5_score=score, exec_m5_matches=matches,
                        meta={"type": "sweep_short", "m5_sweep_high": last_m5.high},
                    ))
                    last_sig_bar = i

    return signals


def compute_backtest_metrics(
    m5_df: pd.DataFrame,
    signals: list[BarByBarSignal],
    max_hold_bars: int = 192,
    cost: dict | None = None,
) -> BarByBarMetrics:
    """Simula trades sobre M5 y devuelve métricas agregadas."""
    if not signals:
        return BarByBarMetrics([], 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

    pip = 0.0001
    spread = (cost or {}).get("spread_pips", 0.0) * pip
    comm = (cost or {}).get("commission_pips", 0.0) * pip
    slip = (cost or {}).get("slippage_pips", 0.0) * pip

    trades: list[BarByBarTrade] = []
    for sig in signals:
        fill_idx = sig.entry_bar + 1
        if fill_idx >= len(m5_df):
            continue
        m5_row = m5_df.iloc[fill_idx]
        dirn = sig.direction
        entry_fill = sig.entry + dirn * (slip + spread / 2.0)
        sl = sig.sl
        tp = sig.tp
        risk = abs(entry_fill - sl)
        if risk <= pip:
            continue

        exit_price = entry_fill
        exit_reason = "hold_limit"
        hold_bars = 0

        for step in range(1, max_hold_bars + 1):
            j = fill_idx + step
            if j >= len(m5_df):
                break
            r = m5_df.iloc[j]
            high, low = float(r["high"]), float(r["low"])
            if dirn == 1:
                if low <= sl:
                    exit_price = sl - comm
                    exit_reason = "SL"
                    hold_bars = step
                    break
                if high >= tp:
                    exit_price = tp - comm
                    exit_reason = "TP"
                    hold_bars = step
                    break
            else:
                if high >= sl:
                    exit_price = sl + comm
                    exit_reason = "SL"
                    hold_bars = step
                    break
                if low <= tp:
                    exit_price = tp + comm
                    exit_reason = "TP"
                    hold_bars = step
                    break
            exit_price = float(r["close"])
            hold_bars = step

        pnl_price = (exit_price - entry_fill) if dirn == 1 else (entry_fill - exit_price)
        pnl_r = pnl_price / risk if risk > 0 else 0.0
        et = m5_df.iloc[fill_idx]["time"] if fill_idx < len(m5_df) else sig.entry_time
        xt = m5_df.iloc[fill_idx + hold_bars]["time"] if fill_idx + hold_bars < len(m5_df) else sig.entry_time

        trades.append(BarByBarTrade(
            signal=sig, entry=entry_fill, exit_price=exit_price, direction=dirn,
            pnl_r=pnl_r, exit_reason=exit_reason, hold_bars=hold_bars,
            entry_time=et, exit_time=xt,
        ))

    pnls = [t.pnl_r for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = min(gross_win / gross_loss, 10.0) if gross_loss > 0 else (10.0 if gross_win > 0 else 0.0)

    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return BarByBarMetrics(
        trades=trades, total_trades=len(trades),
        wins=len(wins), losses=len(losses),
        winrate=len(wins) / len(trades) if trades else 0.0,
        pf=pf, expectancy_r=sum(pnls) / len(trades) if trades else 0.0,
        total_r=sum(pnls), max_dd_r=max_dd,
        signals_generated=len(signals),
    )


def to_plain_dicts(signals: list[BarByBarSignal]) -> list[dict[str, Any]]:
    """Convierte señales a dicts planos para consumo externo."""
    out = []
    for s in signals:
        d = {
            "direction": s.direction,
            "entry": s.entry,
            "sl": s.sl,
            "tp": s.tp,
            "entry_bar": s.entry_bar,
            "entry_time": str(s.entry_time),
            "d1_bias": s.d1_bias,
            "m15_zone_high": s.m15_zone_high,
            "m15_zone_low": s.m15_zone_low,
            "exec_tf": s.exec_tf,
            "exec_m5_score": s.exec_m5_score,
            "exec_m5_matches": s.exec_m5_matches,
            "meta": s.meta,
        }
        out.append(d)
    return out
