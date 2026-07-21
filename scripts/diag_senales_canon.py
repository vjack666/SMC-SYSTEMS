"""Diagnostico: por que generate_sequence_signals da 0 senales con EURUSD canonico.

Imprime: n velas LTF, columnas de estructura (bos_dir/choch_dir nonzeros),
n objetos BOS/CHOCH/FVG/OB, n senales raw de generate_sequence_signals,
y desglose de _post_filter-style para ver por donde se pierden.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd
from ict_backtest.data_feed import load_frames, build_features
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.engine import calc_structural_sl, _tp_liquidity, STRUCT_SL_MAX_RANGE
from ict_backtest.rules import killzone_en

SYMBOL, HTF, LTF = "AUDUSD", "H4", "M15"

fr = load_frames(SYMBOL, (HTF, LTF), start=pd.Timestamp("2024-01-01", tz="UTC"))
ltf_raw = fr[LTF].copy()
htf = fr.get(HTF, ltf_raw).copy()
# Recorte chico para diagnostico rapido (el full EURUSD M15 es muy pesado aqui)
ltf = ltf_raw.iloc[:3000].reset_index(drop=True).copy()
print(f"LTF velas (recorte): {len(ltf)}  HTF velas: {len(htf)}")

# build_features (camino produccion)
bf = build_features(ltf)
print("build_features cols:", [c for c in ["bos_dir","choch_dir","bos_direction","choch_signal","fvg_bullish","ob_bullish","liquidity_sweep_up"] if c in bf.columns])
print("bos_dir nonzeros:", int((bf["bos_dir"] != 0).sum()))
print("choch_dir nonzeros:", int((bf["choch_dir"] != 0).sum()))
print("fvg_bullish True:", int(bf["fvg_bullish"].fillna(False).sum()))
print("ob_bullish True:", int(bf["ob_bullish"].fillna(False).sum()))
print("liquidity_sweep_up True:", int(bf["liquidity_sweep_up"].fillna(False).sum()))

def _est(ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return fn

raw, _ = run_sequence(bf, _est(bf, htf),
                      SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                                     require_displacement=False, bos_gap=10),
                      ltf_tf=LTF)
print(f"\nraw senales: {len(raw)}")
if raw:
    print("primeras 3:", [(s.get('direction'), s.get('entry_at'), s.get('sweep_at')) for s in raw[:3]])

# post-filter estilo test
out = []
for s in raw:
    direction = s["direction"]
    entry_at = s["entry_at"]
    entry_row = bf.iloc[entry_at]
    atr = float(entry_row.get("atr", 0.0) or 0.0)
    if not (atr > 0):
        continue
    kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
    if kz not in ("London Open", "New York AM", "New York PM"):
        continue
    sweep_row = bf.iloc[s["sweep_at"]]
    sl = calc_structural_sl(sweep_row, direction, atr)
    if sl is None:
        continue
    risk = abs(s["entry"] - sl)
    if risk <= 0 or risk > STRUCT_SL_MAX_RANGE * atr:
        continue
    out.append(entry_at)
print(f"post-filter senales: {len(out)}")
