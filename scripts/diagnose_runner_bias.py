"""Debug: muestra bias HTF exacto en cada evento BOS/CHOCH/MSS del runner."""
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


def run(symbol: str = "EURUSD", max_bars: int = 5000) -> dict[str, Any]:
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

    summary = {}
    for tf, frame in tf_frames.items():
        ms = detect_market_structure(frame, StructureConfig(swing_lookback=5, confirm_bars=2, k=5))
        d = ms.frame
        n = len(d)

        bias_aligned = bias_index.reindex(frame.index).fillna({"aligned": False})["aligned"].to_numpy()
        bias_direction = bias_index.reindex(frame.index).fillna({"direction": "NEUTRAL"})["direction"].astype(object).to_numpy()

        events = []
        for i in range(n):
            if d["bos_dir"].iat[i] != 0:
                events.append({
                    "type": "BOS",
                    "dir": "bullish" if d["bos_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_direction[i],
                    "bias_aligned": bool(bias_aligned[i]),
                })
            if d["choch_dir"].iat[i] != 0:
                events.append({
                    "type": "CHOCH",
                    "dir": "bullish" if d["choch_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_direction[i],
                    "bias_aligned": bool(bias_aligned[i]),
                })
            if d["mss_dir"].iat[i] != 0:
                events.append({
                    "type": "MSS",
                    "dir": "bullish" if d["mss_dir"].iat[i] == 1 else "bearish",
                    "bias_direction": bias_direction[i],
                    "bias_aligned": bool(bias_aligned[i]),
                })

        df_ev = pd.DataFrame(events)
        aligned = (df_ev["bias_direction"] == df_ev["dir"].replace({"bullish": "BULLISH", "bearish": "BEARISH"})) & df_ev["bias_aligned"]
        summary[tf] = {
            "events": len(df_ev),
            "aligned_true": int(aligned.sum()),
            "aligned_false": int((~aligned).sum()),
            "bias_direction_counts": df_ev["bias_direction"].value_counts().to_dict(),
            "event_dir_counts": df_ev["dir"].value_counts().to_dict(),
            "first_20": df_ev.head(20).to_dict(orient="records"),
        }
    return summary


def main() -> int:
    symbol = os.environ.get("SMCS_EFFECTIVENESS_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_EFFECTIVENESS_MAX_BARS", 5000))
    print(run(symbol, max_bars))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
