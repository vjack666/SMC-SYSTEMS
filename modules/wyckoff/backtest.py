from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules.wyckoff.config import WyckoffConfig
from modules.wyckoff.detector import detect_wyckoff


def backtest_wyckoff(
    data_dir: Path,
    symbol: str,
    timeframe: str = "M15",
    config: WyckoffConfig | None = None,
) -> dict[str, float | int]:
    if config is None:
        config = WyckoffConfig()

    path = data_dir / f"{symbol}_{timeframe}.parquet"
    frame = pd.read_parquet(path)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)

    from modules.indicators import add_atr
    frame["atr"] = add_atr(frame, 14)

    data = detect_wyckoff(frame, config)
    total = int(len(data))

    return {
        "total_bars": total,
        "selling_climax": int(data["wyckoff_sc"].sum()),
        "automatic_rally": int(data["wyckoff_ar"].sum()),
        "secondary_test": int(data["wyckoff_st"].sum()),
        "spring": int(data["wyckoff_spring"].sum()),
        "sign_of_strength": int(data["wyckoff_sos"].sum()),
        "last_point_support": int(data["wyckoff_lps"].sum()),
        "accumulation_bars": int(data["wyckoff_accumulation"].sum()),
        "accumulation_share": float(data["wyckoff_accumulation"].mean()),
    }
