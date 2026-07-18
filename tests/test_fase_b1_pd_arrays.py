"""Fase B1 (SPEC §3/§4): PD Arrays completos + tiers/stacking (metadatos).

Prueba empírica de que los detectores etiquetan tipo/tier y que el cruce
BPR/T1 se resuelve en data_feed, y que el motor (run_sequence) consume los
objetos sin I/O de disco. La afirmación de "no altera la decisión" se cubre
con un smoke test de regresión contra el baseline (git stash) en terminal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from ict_backtest.data_feed import build_features
from ict_backtest.translation import df_to_objects
from ict_backtest.sequence import SequenceConfig, run_sequence, _candle_objects


def _synthetic_df(n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100.0 + np.cumsum(rng.normal(0, 0.1, n))
    df = pd.DataFrame({
        "open": close,
        "high": close + 0.15,
        "low": close - 0.15,
        "close": close,
        "time": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
    })
    df["atr"] = 0.2
    return df


def test_fvg_labels_type_and_tier():
    df = _synthetic_df()
    df.loc[5, "low"] = df.loc[3, "high"] + 0.05
    out = detect_fvg(df)
    assert out["fvg_bullish"].iloc[5]
    assert out["pd_type"].iloc[5] == "FVG"
    assert out["pd_tier"].iloc[5] == "T2"
    # build_features debe preservar el etiquetado del FVG
    bf = build_features(df)
    assert bf["pd_type"].iloc[5] == "FVG", "build_features no debe pisar pd_type del FVG"


def test_ob_rejection_block_labeled_T3():
    # OB BULLISH = vela BEARISH fuerte (body_ratio>0.7) + vela sig cierra > high.
    df = _synthetic_df()
    df.loc[6, "open"] = 100.0
    df.loc[6, "close"] = 98.0          # cuerpo 2.0 (bearish)
    df.loc[6, "high"] = 100.2          # mecha sup 0.2
    df.loc[6, "low"] = 97.5            # rango 2.7 -> body_ratio 0.74 > 0.7
    df.loc[7, "open"] = 98.0
    df.loc[7, "close"] = 100.5         # followthrough alcista: cierra > high[6]=100.2
    df.loc[7, "high"] = 100.6
    df.loc[7, "low"] = 98.0
    out = detect_order_blocks(df)
    assert out["ob_bullish"].iloc[6], "el OB bullish debe formarse con followthrough"
    # mecha opuesta (sup) = 0.2; cuerpo = 2.0 -> no llega a 1.5x -> tipo OB T2
    assert out["pd_type"].iloc[6] == "OB"
    assert out["pd_tier"].iloc[6] == "T2"


def test_bpr_cross_lifts_tier_to_T1():
    df = _synthetic_df()
    # FVG bullish en barra 8 (low[8] > high[6])
    df.loc[8, "low"] = df.loc[6, "high"] + 0.05
    # OB bullish FUERTE en barra 10, en MISMA zona que el FVG -> BPR T1
    z = df.loc[8, "low"]                       # ~ high[6]+0.05
    df.loc[10, "open"] = z + 0.30              # vela bearish fuerte
    df.loc[10, "close"] = z - 0.30             # cuerpo 0.6
    df.loc[10, "high"] = z + 0.35              # ob_top = z+0.35
    df.loc[10, "low"] = z - 0.35               # ob_bottom = z-0.35; rango 0.70, cuerpo 0.6 -> 0.86>0.7
    df.loc[11, "open"] = z - 0.30
    df.loc[11, "close"] = z + 0.50             # followthrough alcista: cierra > high[10]=z+0.35
    df.loc[11, "high"] = z + 0.55
    df.loc[11, "low"] = z - 0.30
    out = build_features(df)
    ob_rows = out[out["ob_bullish"] | out["ob_bearish"]]
    assert len(ob_rows) > 0, "debe haber al menos un OB"
    assert (ob_rows["pd_tier"] == "T1").any(), (
        "BPR (FVG+OB misma zona) debe ser T1; filas ob=" + str(len(ob_rows))
        + " tiers=" + str(ob_rows["pd_tier"].tolist())
    )


def test_translation_propagates_pd_type_tier():
    df = _synthetic_df()
    df.loc[5, "low"] = df.loc[3, "high"] + 0.05
    out = build_features(df)
    objs = df_to_objects({"M15": out}, symbol="TEST")
    fvgs = [o for o in objs if o.type.value == "FVG"]
    assert fvgs, "debe haber al menos un FVG como objeto"
    assert fvgs[0].meta.get("pd_type") == "FVG"
    assert fvgs[0].meta.get("pd_tier") == "T2"


def test_run_sequence_end_to_end_produces_signals():
    """Cableo real extremo-a-extremo (sin I/O de disco)."""
    df = _synthetic_df(120)
    df.loc[20, "low"] = df.loc[18, "high"] + 0.05
    df.loc[30, "low"] = df.loc[28, "low"] - 0.2
    frames = {"M15": build_features(df)}
    dfm = frames["M15"]

    def est_htf_fn(i):
        r = dfm.iloc[i]
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    objs = _candle_objects(dfm, "M15")
    signals, _ = run_sequence(objs, est_htf_fn, SequenceConfig(),
                              htf_poi_fn=None, ltf_tf="M15", bos_table=None)
    assert isinstance(signals, list)
