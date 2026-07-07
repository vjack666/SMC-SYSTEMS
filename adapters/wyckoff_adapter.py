from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from agents.wyckoff_agent import WyckoffAgent
from indicators import add_stochastic


class WyckoffAdapter:
    name = "wyckoff"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        s = parameters.get("scenario", "bullish_exhaustion")
        lookback = int(parameters.get("lookback", 40))
        agent = WyckoffAgent(lookback=lookback)
        frame = self._build_synthetic_frame(120, s)
        result = agent.analyze(frame, len(frame) - 1)
        ev = result.evidence

        return {
            "module": self.name,
            "event_names": [],
            "status": "ok",
            "agent_bias": result.bias,
            "agent_confidence": result.confidence,
            "phase": str(ev.get("phase", "UNKNOWN")),
            "stoch_exhaustion_type": str((ev.get("stoch_exhaustion") or {}).get("type", "")),
            "stoch_divergence": bool((ev.get("stoch_exhaustion") or {}).get("divergence", False)),
            "volume_confirmed": bool((ev.get("stoch_exhaustion") or {}).get("volume_confirmed", False)),
            "events_found": len(result.detected_events),
        }

    def _build_synthetic_frame(self, n_bars: int, scenario: str) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        prices = np.linspace(1.10, 1.12, n_bars) + rng.normal(0.0, 0.001, n_bars)
        frame = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=n_bars, freq="15min", tz="UTC"),
            "open": prices,
            "high": prices + abs(rng.normal(0.0, 0.002, n_bars)),
            "low": prices - abs(rng.normal(0.0, 0.002, n_bars)),
            "close": prices,
            "tick_volume": rng.integers(100, 10000, n_bars),
        })

        stoch = add_stochastic(frame)
        frame["stoch_k"] = stoch["stoch_k"]
        frame["stoch_d"] = stoch["stoch_d"]

        k = frame["stoch_k"].values.copy()
        d = frame["stoch_d"].values.copy()
        idx = len(k) - 2
        vol = frame["tick_volume"].values.copy()

        if scenario == "bullish_exhaustion":
            k[idx] = 15.0; d[idx] = 15.0
            k[idx + 1] = 25.0; d[idx + 1] = 25.0
            vol[idx + 1] = int(max(vol) * 2)
        elif scenario == "bearish_exhaustion":
            k[idx] = 85.0; d[idx] = 85.0
            k[idx + 1] = 75.0; d[idx + 1] = 75.0
            vol[idx + 1] = int(max(vol) * 2)
        elif scenario == "bullish_divergence":
            k[idx] = 15.0; d[idx] = 15.0
            k[idx + 1] = 25.0; d[idx + 1] = 25.0
            vol[idx + 1] = int(max(vol) * 2)
            frame.loc[frame.index[-1], "low"] = float(frame["low"].iloc[-2]) * 0.98
        elif scenario == "bearish_divergence":
            k[idx] = 85.0; d[idx] = 85.0
            k[idx + 1] = 75.0; d[idx + 1] = 75.0
            vol[idx + 1] = int(max(vol) * 2)
            frame.loc[frame.index[-1], "high"] = float(frame["high"].iloc[-2]) * 1.02
        elif scenario == "no_exhaustion":
            k[idx] = 50.0; d[idx] = 50.0
            k[idx + 1] = 52.0; d[idx + 1] = 52.0
            vol[idx + 1] = int(np.mean(vol))

        frame["stoch_k"] = k
        frame["stoch_d"] = d
        frame["tick_volume"] = vol

        atr = (frame["high"] - frame["low"]).rolling(14).mean().bfill()
        frame["atr"] = atr
        frame["macro_direction"] = "BULLISH" if "bull" in scenario else "BEARISH"
        return frame
