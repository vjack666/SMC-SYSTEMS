"""Muestra eventos BOS/CHOCH/MSS con el bias HTF en el momento exacto.

Ayuda a separar dos hipótesis:
1) bug de reindex en D1/H4/H1/M15
2) eventos que ocurren contra el bias HTF dominante
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd

from engine.bias.narrative import compute_htf_bias_series
from engine.bos.structure import StructureConfig, detect_market_structure
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = df["open"].resample(rule, label="left", closed="left").first()
    h = df["high"].resample(rule, label="left", closed="left").max()
    l = df["low"].resample(rule, label="left", closed="left").min()
    c = df["close"].resample(rule, label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


def run(symbol: str = "EURUSD", max_bars: int = 30000) -> dict[str, Any]:
    validated = validate_m15_parquet(symbol)
    m15_df = validated.df.sort_index().iloc[:max_bars]
    h4_df = _resample(m15_df, "4h")
    h1_df = _resample(m15_df, "1h")
    d1_df = _resample(m15_df, "1d")

    bias_index = compute_htf_bias_series(d1_df, h4_df, h1_df, m15_df, swing_lookback=5)

    tf_frames = {
        "D1": d1_df,
        "H4": h4_df,
        "H1": h1_df,
        "M15": m15_df,
    }

    summary: dict[str, Any] = {"symbol": symbol.upper(), "max_bars": max_bars, "timeframes": {}}

    for tf, frame in tf_frames.items():
        ms = detect_market_structure(frame, StructureConfig(swing_lookback=5, confirm_bars=2, k=5))
        d = ms.frame
        bias_tf = bias_index.reindex(frame.index).fillna({"direction": "NEUTRAL", "aligned": False})
        sample = []
        for i in range(len(d)):
            if d["bos_dir"].iat[i] != 0:
                sample.append({
                    "type": "BOS",
                    "direction": "bullish" if d["bos_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_tf["direction"].iat[i],
                    "bias_aligned": bool(bias_tf["aligned"].iat[i]),
                    "timestamp": d.index[i],
                })
            if d["choch_dir"].iat[i] != 0:
                sample.append({
                    "type": "CHOCH",
                    "direction": "bullish" if d["choch_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_tf["direction"].iat[i],
                    "bias_aligned": bool(bias_tf["aligned"].iat[i]),
                    "timestamp": d.index[i],
                })
            if d["mss_dir"].iat[i] != 0:
                sample.append({
                    "type": "MSS",
                    "direction": "bullish" if d["mss_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_tf["direction"].iat[i],
                    "bias_aligned": bool(bias_tf["aligned"].iat[i]),
                    "timestamp": d.index[i],
                })

        df_sample = pd.DataFrame(sample)
        aligned = (df_sample["bias_direction"] == df_sample["direction"].replace({"bullish": "BULLISH", "bearish": "BEARISH"})) & df_sample["bias_aligned"]
        summary["timeframes"][tf] = {
            "events": len(df_sample),
            "aligned_true": int(aligned.sum()),
            "aligned_false": int((~aligned).sum()),
            "bias_direction_counts": df_sample["bias_direction"].value_counts().to_dict(),
            "event_direction_counts": df_sample["direction"].value_counts().to_dict(),
            "sample": df_sample.head(20).to_dict(orient="records"),
        }
    return summary


def main() -> int:
    symbol = os.environ.get("SMCS_EFFECTIVENESS_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_EFFECTIVENESS_MAX_BARS", 30000))
    summary = run(symbol, max_bars)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
