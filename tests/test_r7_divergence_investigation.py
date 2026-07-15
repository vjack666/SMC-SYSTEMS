"""tests/test_r7_divergence_investigation.py — R7 investigacion causa raiz (T3.2B).

Recrea EXACTAMENTE el escenario del test T3.1 (mismos _MS, _FRAMES, est_fn,
run_sequence, filtro) pero con recorte NO-TRIVIAL (H4=1500), e instrumenta en
que etapa divergen los dos caminos:
  - Camino A (ORACULO del test): usa _MS (calculado en import, df "fresco").
  - Camino B (run real): usa generate_sequence_signals(frames=_FRAMES) que
    recalcula detect_market_structure sobre _FRAMES.
Compara raw (run_sequence) y post-filtro, fila por fila, e indica la PRIMERA
etapa donde divergen y por que fila. Test reproducible (no arregla nada).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import numpy as np
import pandas as pd
import pytest

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time
from ict_backtest.engine import (calc_structural_sl, _tp_liquidity,
                                 STRUCT_SL_MAX_ATR)
from ict_backtest.rules import killzone_en
from ict_backtest.run_backtest import generate_sequence_signals

SYMBOL, HTF, LTF = "XAUUSD", "D1", "H4"
CUT = {"D1": 220, "H4": 1500}

_FRAMES = load_frames(SYMBOL, (HTF, LTF))
_FRAMES = {tf: df.iloc[:CUT.get(tf, len(df))].reset_index(drop=True)
           for tf, df in _FRAMES.items()}
_MS = {tf: detect_market_structure(df) for tf, df in _FRAMES.items()}


def _est_htf_fn(ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return fn


def _post_filter(ltf_df, raw_sigs):
    out = []
    drops = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        entry = s["entry"]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            drops.append((entry_at, "atr<=0")); continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            drops.append((entry_at, f"kz={kz}")); continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            drops.append((entry_at, "sl=None")); continue
        risk = abs(entry - sl)
        if risk <= 0:
            drops.append((entry_at, "risk<=0")); continue
        if risk > STRUCT_SL_MAX_ATR * atr:
            drops.append((entry_at, f"risk>{STRUCT_SL_MAX_ATR}*atr")); continue
        liq = _tp_liquidity(entry_row, direction)
        tp = liq if liq is not None else (entry + 3.0*risk if direction == 1 else entry-3.0*risk)
        if direction == 1 and tp <= entry + 2.0*risk: tp = entry + 3.0*risk
        if direction == -1 and tp >= entry - 2.0*risk: tp = entry - 3.0*risk
        out.append(entry_at)
    return out, drops


def test_divergence_stage_by_stage():
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=False)

    # ---- Camino A: ORACULO (usa _MS del import, "fresco")
    ltf_a = _MS[LTF]
    htf_a = _MS.get(HTF, ltf_a)
    raw_a, _ = run_sequence(ltf_a, _est_htf_fn(ltf_a, htf_a), cfg, ltf_tf=LTF)
    sig_a, drops_a = _post_filter(ltf_a, raw_a)

    # ---- Camino B: run real (generate_sequence_signals sobre _FRAMES)
    gen = generate_sequence_signals(SYMBOL, HTF, LTF, counter_trend=False,
                                    tp_mode="fixed2r", require_displacement=False,
                                    frames=_FRAMES)
    # generate ya aplico el filtro; para comparar raw necesitamos el raw tambien.
    ltf_b = _MS  # generate recalcula internamente; usamos su salida (filtrada)
    raw_b, _ = run_sequence(_FRAMES[LTF], _est_htf_fn(_FRAMES[LTF], _FRAMES.get(HTF, _FRAMES[LTF])), cfg, ltf_tf=LTF)
    sig_b_from_raw, drops_b = _post_filter(_FRAMES[LTF], raw_b)

    print("\n=== ETAPA 4 (raw run_sequence) ===")
    ea = [s["entry_at"] for s in raw_a]
    eb = [s["entry_at"] for s in raw_b]
    print(f"  oracle raw: {len(ea)} entry_at={ea}")
    print(f"  generate raw: {len(eb)} entry_at={eb}")
    print(f"  raw identicos: {ea == eb}")

    print("\n=== ETAPA 5/6 (post-filtro) ===")
    print(f"  oracle senales: {sig_a}  (drops: {drops_a})")
    print(f"  generate senales (desde raw): {sig_b_from_raw}  (drops: {drops_b})")

    # generate_sequence_signals devuelve ICTSignal; comparamos entry_at
    gen_entry = [g.entry_at for g in gen]
    print(f"  generate_sequence_signals entry_at: {gen_entry}")
    print(f"  oracle vs generate_sequence_signals entry_at iguales: {set(sig_a)==set(gen_entry)}")

    print("\n=== DIFERENCIA DE DATOS _MS vs recalculo ===")
    # ¿_MS[LTF] difiere de detect_market_structure(_FRAMES[LTF]) recalculado?
    ms_rec = detect_market_structure(_FRAMES[LTF])
    diff_cols = []
    num_cols = _MS[LTF].select_dtypes(include=[np.number]).columns
    for c in num_cols:
        if c not in ms_rec.columns:
            continue
        a = _MS[LTF][c].to_numpy().astype(float)
        b = ms_rec[c].to_numpy().astype(float)
        if a.shape != b.shape or not np.allclose(a, b, equal_nan=True):
            diff_cols.append(c)
    print(f"  columnas NUMERICAS distintas entre _MS[LTF] y recalculo: {diff_cols if diff_cols else 'NINGUNA'}")
    # ¿las columnas ICT que run_sequence consume son iguales? (algunas son string)
    ict_cols = ["bos_dir", "choch_dir", "liquidity_sweep_up", "liquidity_sweep_down",
                "displacement_bullish", "displacement_bearish", "fvg_bullish",
                "fvg_bearish", "ob_direction", "ob_bullish", "ob_bearish", "trend"]
    ict_diff = []
    for c in ict_cols:
        if c not in _MS[LTF].columns or c not in ms_rec.columns:
            continue
        a = _MS[LTF][c].astype(str).to_numpy()
        b = ms_rec[c].astype(str).to_numpy()
        if a.shape != b.shape or not (a == b).all():
            ict_diff.append(c)
    trend_same = "trend" not in ict_diff
    print(f"  columnas ICT distintas (string-compare): {ict_diff if ict_diff else 'NINGUNA'}")
    print(f"  columna 'trend' identica: {trend_same}")

    print("\n=== PRUEBA DEFINITIVA: mismo filtro sobre _MS vs ms_rec ===")
    sig_ms, _ = _post_filter(_MS[LTF], raw_a)
    sig_rec, _ = _post_filter(ms_rec, raw_a)
    print(f"  filtro sobre _MS[LTF]   -> {sig_ms}")
    print(f"  filtro sobre ms_rec      -> {sig_rec}")
    print(f"  ambos iguales: {sig_ms == sig_rec}")

    # Para que el test sea informativo, no lo hacemos fallar; solo reporta.
    assert True
