"""scripts/diag_columns_fix.py — Evidencia aislada del fix en data_feed.

Usa el pipeline REAL H4->M15 y aisa el efecto de las 6 columnas que el fix
expone (fvg_bullish, fvg_bearish, ob_bullish, ob_bearish, choch_dir, bos_dir):
  DESPUES = build_features actual (columnas presentes)
  ANTES   = mismo df pero SIN esas 6 columnas (simula pre-fix)

Cuenta FVG / OB / CHOCH / SENALES run_sequence en ambos casos.

Uso: C:/Python314/python.exe scripts/diag_columns_fix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time

FIX_COLS = ["fvg_bullish", "fvg_bearish", "ob_bullish", "ob_bearish", "choch_dir", "bos_dir"]


def count_block(tag, df, est_fn, cfg):
    def col_or_false(name):
        if name in df.columns:
            return df[name].fillna(False).astype(bool)
        return pd.Series([False] * len(df), index=df.index)

    def col_or_zero(name):
        if name in df.columns:
            return df[name].fillna(0).astype(int)
        return pd.Series([0] * len(df), index=df.index)

    fvg = int(col_or_false("fvg_bullish").sum() + col_or_false("fvg_bearish").sum())
    ob = int(col_or_false("ob_bullish").sum() + col_or_false("ob_bearish").sum())
    ch = int((col_or_zero("choch_dir") != 0).sum())
    sigs, ph = run_sequence(df, est_fn, cfg)
    print(f"  [{tag}] FVG={fvg}  OB={ob}  CHOCH={ch}  SENALES={len(sigs)}  fases={ph}")
    return fvg, ob, ch, len(sigs)


def main() -> None:
    symbol, htf, ltf = "EURUSD", "H4", "M15"
    fr = load_frames(symbol, (htf, ltf, "D1"))          # build_features actual
    ltf_df = fr[ltf].tail(6000).reset_index(drop=True)
    htf_df = fr[htf]

    def est_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    cfg = SequenceConfig(counter_trend=True, tp_mode="fixed2r", require_displacement=True)

    print(f"(EURUSD {ltf} ultimas 6000 velas, sesgo {htf} real)")
    print("=== DESPUES del fix (columnas expuestas) ===")
    count_block("DESPUES", ltf_df, est_fn, cfg)

    old = ltf_df.drop(columns=[c for c in FIX_COLS if c in ltf_df.columns])
    print("=== ANTES del fix (mismas velas, SIN las 6 columnas) ===")
    count_block("ANTES", old, est_fn, cfg)


if __name__ == "__main__":
    main()
