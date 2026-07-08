from __future__ import annotations

import pandas as pd


CHOCH_BULLISH = "CHOCH_BULLISH"
CHOCH_BEARISH = "CHOCH_BEARISH"


def detect_choch(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["choch_signal"] = "NONE"

    data["last_swing_high"] = data["high"].rolling(20, min_periods=5).max().shift(1)
    data["last_swing_low"] = data["low"].rolling(20, min_periods=5).min().shift(1)

    bearish_context = data["close"].rolling(20).mean() < data["close"].rolling(50).mean()
    bullish_context = data["close"].rolling(20).mean() > data["close"].rolling(50).mean()

    bullish_break = data["close"] > data["last_swing_high"]
    bearish_break = data["close"] < data["last_swing_low"]

    data.loc[bearish_context & bullish_break, "choch_signal"] = CHOCH_BULLISH
    data.loc[bullish_context & bearish_break, "choch_signal"] = CHOCH_BEARISH

    # --- Item E: invalidacion + envejecimiento ---
    data["choch_status"], data["choch_age"] = _track_choch_validity(
        data, max_age=20, swing_lookback=20
    )
    return data


def _track_choch_validity(
    data: pd.DataFrame, max_age: int, swing_lookback: int = 20
) -> tuple[pd.Series, pd.Series]:
    n = len(data)
    status = pd.Series(["none"] * n, index=data.index, dtype=object)
    age = pd.Series([0] * n, index=data.index, dtype=int)
    last_dir = "NONE"
    last_idx = -1
    active = False
    close = data["close"].to_numpy()
    swing_high = data["last_swing_high"].to_numpy() if "last_swing_high" in data else data["high"].rolling(swing_lookback, min_periods=5).max().shift(1).to_numpy()
    swing_low = data["last_swing_low"].to_numpy() if "last_swing_low" in data else data["low"].rolling(swing_lookback, min_periods=5).min().shift(1).to_numpy()
    sig = data["choch_signal"].to_numpy()
    for i in range(1, n):
        s = sig[i]
        if s != "NONE":
            last_dir, last_idx, active = s, i, True
        if active:
            age.iloc[i] = i - last_idx
            failed = (
                (last_dir == CHOCH_BULLISH and close[i] < swing_low[i])
                or (last_dir == CHOCH_BEARISH and close[i] > swing_high[i])
            )
            if failed:
                status.iloc[i], active = "invalidated", False
            elif age.iloc[i] > max_age:
                status.iloc[i], active = "aged", False
            else:
                status.iloc[i] = "active"
    return status, age
