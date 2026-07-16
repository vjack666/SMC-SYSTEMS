"""tests/test_r9_object_adapter.py — R9 Paso 2+3: equivalencia objeto<->columna.

NO cambia ninguna regla ICT. Solo certifica que alimentar el motor a través de
la capa de objetos (MarketObject) produce EXACTAMENTE las mismas señales,
trades y métricas que el camino legacy de columnas sueltas.

- Paso 2: objects_view() (DataFrame reconstruido) == frames originales.
- Paso 3: run_sequence() leyendo MarketObject[] == run_sequence() leyendo
  el DataFrame (la migración de tipo de dato es fiel).

Usa XAUUSD D1->H4 (datos reales, pocas velas, sin OOM del host).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import (run_sequence, SequenceConfig,
                                _candle_objects)
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.engine import simulate_trade, ICTSignal
from ict_backtest.object_adapter import objects_view


SYMBOL = "XAUUSD"
HTF = "D1"
LTF = "H4"


def _load():
    frames = load_frames(SYMBOL, (HTF, LTF))
    # Recorte determinista para que el test sea rápido y sin OOM del host
    # (ENV QUIRK: 50000 velas M15 mueren por OOM). Usa datos REALES (parquet
    # XAUUSD) recortados; la fidelidad del puente no depende del tamaño.
    cut = {"D1": 400, "H4": 1500}
    frames = {tf: df.iloc[:cut.get(tf, len(df))].reset_index(drop=True)
              for tf, df in frames.items()}
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    return frames, ms


def _est_htf_fn(ms, ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }
    return fn


def _signals_and_metrics(frames, ms, use_objects=False):
    ltf_df = ms[LTF]
    htf_df = ms.get(HTF, ltf_df)
    cfg = SequenceConfig()
    est_fn = _est_htf_fn(ms, ltf_df, htf_df)
    if use_objects:
        # R9 Paso 3: sequence recibe MarketObject[] directamente (no DataFrame).
        objs = _candle_objects(ltf_df, LTF)
        sigs, phases = run_sequence(objs, est_fn, cfg, ltf_tf=LTF)
    else:
        sigs, phases = run_sequence(
            ltf_df, est_fn, cfg, ltf_tf=LTF
        )
    # Simular para métricas (usando SL estructural + RR 1:3 estilo run_backtest)
    from ict_backtest.engine import calc_structural_sl, _tp_liquidity, STRUCT_SL_MAX_ATR
    pnls = []
    for s in sigs:
        direction = s["direction"]
        entry = s["entry"]
        entry_row = ltf_df.iloc[s["entry_at"]]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        sl = calc_structural_sl(ltf_df.iloc[s["sweep_at"]], direction, atr)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_ATR * atr:
            continue
        liq = _tp_liquidity(entry_row, direction)
        tp = liq if liq is not None else (entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk)
        sig = ICTSignal(symbol=SYMBOL, time=s["time"], direction=direction,
                        entry=entry, stop_loss=sl, take_profit=tp, model="sequence")
        trade, _ = simulate_trade(ltf_df, sig, max_hold_bars=40, cost=None)
        if trade is not None:
            pnls.append(trade.pnl_r)
    n = len(pnls)
    pf = (sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))) if any(p < 0 for p in pnls) else float("inf")
    wr = (len([p for p in pnls if p > 0]) / n) if n else 0.0
    exp = (sum(pnls) / n) if n else 0.0
    return sigs, {"trades": n, "pf": pf, "wr": wr, "exp": exp}


def test_objects_view_preserves_columns_and_rows():
    frames, ms = _load()
    ov = objects_view(frames, symbol=SYMBOL)
    assert set(ov.keys()) == set(frames.keys()), "mismos TF"
    for tf in frames:
        assert len(ov[tf]) == len(frames[tf]), f"{tf}: mismo nro de filas"
        # Columnas legacy críticas que lee sequence deben existir en ambos
        for col in ("time", "trend", "bos_direction", "choch_dir",
                    "fvg_bullish", "ob_direction", "atr", "low", "high", "close"):
            assert col in ov[tf].columns, f"{tf}: falta columna {col} en objects_view"


def test_objects_view_equivalent_signals():
    frames, ms = _load()
    ov = objects_view(frames, symbol=SYMBOL)
    ms_ov = {tf: detect_market_structure(df) for tf, df in ov.items()}

    sigs_a, _ = _signals_and_metrics(frames, ms)
    sigs_b, _ = _signals_and_metrics(ov, ms_ov)

    # Mismas señales: misma cantidad y mismos (time, direction, entry)
    assert len(sigs_a) == len(sigs_b), f"señales distintas: {len(sigs_a)} vs {len(sigs_b)}"
    for a, b in zip(sigs_a, sigs_b):
        assert a["time"] == b["time"], f"time distinto: {a['time']} vs {b['time']}"
        assert a["direction"] == b["direction"]
        assert a["entry"] == b["entry"]


def test_objects_view_equivalent_metrics():
    frames, ms = _load()
    ov = objects_view(frames, symbol=SYMBOL)
    ms_ov = {tf: detect_market_structure(df) for tf, df in ov.items()}

    _, m_a = _signals_and_metrics(frames, ms)
    _, m_b = _signals_and_metrics(ov, ms_ov)

    assert m_a["trades"] == m_b["trades"], f"trades: {m_a['trades']} vs {m_b['trades']}"
    # PF puede ser inf si no hay pérdidas; comparar con tolerancia numérica.
    if m_a["pf"] == float("inf") or m_b["pf"] == float("inf"):
        assert m_a["pf"] == m_b["pf"], "PF inf debe coincidir"
    else:
        assert abs(m_a["pf"] - m_b["pf"]) < 1e-9, f"PF distinto: {m_a['pf']} vs {m_b['pf']}"
    assert abs(m_a["wr"] - m_b["wr"]) < 1e-9, f"WR distinto: {m_a['wr']} vs {m_b['wr']}"
    assert abs(m_a["exp"] - m_b["exp"]) < 1e-9, f"expectancy distinta"


def test_sequence_consumes_marketobject_equivalent():
    """R9 Paso 3 (prueba fuerte): sequence leyendo MarketObject[] produce
    EXACTAMENTE las mismas señales que sequence leyendo el DataFrame.

    Esto certifica que la migración de tipo de dato es fiel: el motor ya no
    depende de columnas sueltas del DataFrame, sino de MarketObject[].
    """
    frames, ms = _load()

    sigs_df, _ = _signals_and_metrics(frames, ms, use_objects=False)
    sigs_obj, _ = _signals_and_metrics(frames, ms, use_objects=True)

    assert len(sigs_df) == len(sigs_obj), \
        f"señales distintas: {len(sigs_df)} (df) vs {len(sigs_obj)} (objetos)"
    for a, b in zip(sigs_df, sigs_obj):
        assert a["time"] == b["time"], f"time: {a['time']} vs {b['time']}"
        assert a["direction"] == b["direction"]
        assert a["entry"] == b["entry"]
        assert a["sweep_at"] == b["sweep_at"]
        assert a["bos_at"] == b["bos_at"]
        assert a["entry_at"] == b["entry_at"]


if __name__ == "__main__":
    # Corrida manual: imprime métricas de ambos caminos.
    frames, ms = _load()
    ov = objects_view(frames, symbol=SYMBOL)
    ms_ov = {tf: detect_market_structure(df) for tf, df in ov.items()}
    sa, ma = _signals_and_metrics(frames, ms)
    sb, mb = _signals_and_metrics(ov, ms_ov)
    print(f"LEGACY : sigs={len(sa)} trades={ma['trades']} PF={ma['pf']:.3f} WR={ma['wr']*100:.1f}% exp={ma['exp']:.3f}")
    print(f"OBJECTS: sigs={len(sb)} trades={mb['trades']} PF={mb['pf']:.3f} WR={mb['wr']*100:.1f}% exp={mb['exp']:.3f}")
