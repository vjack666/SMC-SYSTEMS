"""DIAGNOSTICO POR ETAPAS (solo lectura, NO modifica produccion).

Objetivo: localizar el primer punto donde el flujo de senales pasa de
"hay datos" a "0". No mide PF, solo cuenta en cada etapa.

Cadena (emulando run_sequence_backtest de produccion):
  load LTF+HTF (recortado)
      -> detect_market_structure en AMBOS (produccion hace esto)
      -> build_features (columnas LTF que lee sequence/rules)
      -> translation/df_to_objects
      -> run_sequence (lee trend del HTF; si RANGING, descarta)
      -> raw signals
      -> post-filter
      -> trades

Usa un LTF chico (~1500 velas) para iterar en SEGUNDOS.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
import pandas as pd
from ict_backtest.data_feed import build_features
from ict_backtest.market_structure import detect_market_structure, StructureConfig
from ict_backtest.translation import df_to_objects
from ict_backtest.sequence import run_sequence, SequenceConfig
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.engine import calc_structural_sl, STRUCT_SL_MAX_RANGE
from ict_backtest.rules import killzone_en

SYMBOL, HTF, LTF = "AUDUSD", "H4", "M15"
N = 1500  # velas LTF para iterar rapido
CFG = StructureConfig(swing_lookback=5, confirm_bars=2)

def t0(): return time.time()

# Carga DIRECTA del parquet y recorte ANTES de features (itera en segundos).
ltf_raw = pd.read_parquet(f"data/raw/{SYMBOL}_{LTF}.parquet")
htf_raw = pd.read_parquet(f"data/raw/{SYMBOL}_{HTF}.parquet")
print(f"[load] raw LTF={len(ltf_raw)} HTF={len(htf_raw)}  ({time.time()-t0():.1f}s)")
ltf = ltf_raw.iloc[:N].reset_index(drop=True).copy()
htf = htf_raw.iloc[: max(1, N // 4)].reset_index(drop=True).copy()

# --- PRODUCCION aplica detect_market_structure a CADA tf ---
ltf_ms = detect_market_structure(ltf, CFG)
htf_ms = detect_market_structure(htf, CFG)
print(f"[ms] LTF trend!=RANGING: {int((ltf_ms['trend']!='RANGING').sum())}  "
      f"HTF trend!=RANGING: {int((htf_ms['trend']!='RANGING').sum())}")
print(f"[ms] HTF trend counts: {htf_ms['trend'].value_counts().to_dict()}")

# --- ETAPA 1: columnas de estructura tras build_features (sobre ltf_ms que ya
#     trae trend/bos_dir/choch_dir del canonico) ---
bf = build_features(ltf_ms.copy())
print(f"[1 build_features] bos_dir!={0}: {int((bf['bos_dir']!=0).sum())}  "
      f"choch_dir!={0}: {int((bf['choch_dir']!=0).sum())}  "
      f"fvg_bullish: {int(bf['fvg_bullish'].fillna(False).sum())}  "
      f"ob_bullish: {int(bf['ob_bullish'].fillna(False).sum())}  "
      f"liq_sweep_up: {int(bf['liquidity_sweep_up'].fillna(False).sum())}")

# --- ETAPA 2: objetos BOS/CHOCH/FVG/OB ---
objs = df_to_objects({LTF: bf, HTF: htf_ms}, symbol=SYMBOL)
from ict_backtest.translation import ObjectType
def count(t): return sum(1 for o in objs if o.type.value == t)
print(f"[2 objects] BOS={count('BOS')} CHOCH={count('CHOCH')} "
      f"FVG={count('FVG')} OB={count('OB')} SWEEP={count('SWEEP')} total={len(objs)}")

# --- ETAPA 3: run_sequence (raw signals). est_htf lee trend del HTF canonico. ---
def _est(ltf_df, htf_df):
    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(HTF))
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return fn

raw, phases = run_sequence(bf, _est(bf, htf_ms),
                      SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                                     require_displacement=False, bos_gap=10),
                      ltf_tf=LTF)
print(f"[3 run_sequence] raw signals = {len(raw)}")
print(f"[3 run_sequence] phases alcanzadas = {phases}")

# --- ETAPA 4: post-filter estilo test ---
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
print(f"[4 post-filter] senales que pasan = {len(out)}")
print("DIAGNOSTICO LISTO")
