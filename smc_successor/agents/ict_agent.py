from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from smc_successor.agents.base import AnalysisResult


class ICTAgent:
    name: str = "ICT"

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        row = context.iloc[index]
        events: list[dict[str, Any]] = []
        evidence: dict[str, Any] = {}
        invalidation: list[str] = []
        start = max(0, index - self.lookback)
        window = context.iloc[start : index + 1]

        trend = self._detect_trend(window)
        evidence["market_structure"] = trend

        bos = self._detect_bos(window, trend)
        if bos:
            events.append({"type": "BOS", "direction": trend, "detail": bos})
            evidence["bos"] = bos

        choch = self._detect_choch(window, trend)
        if choch:
            events.append({"type": "CHOCH", "direction": choch})
            evidence["choch"] = choch
            invalidation.append(f"CHOCH against {trend} trend — structure shift possible")

        sweep = self._detect_sweep(window)
        if sweep:
            events.append({"type": "LIQUIDITY_SWEEP", "side": sweep})
            evidence["liquidity_sweep"] = sweep

        fvg = self._detect_fvg(window)
        if fvg:
            events.append({"type": "FVG", "detail": fvg})
            evidence["fvg"] = fvg

        ob = self._detect_ob(window)
        if ob:
            events.append({"type": "ORDER_BLOCK", "detail": ob})
            evidence["order_block"] = ob

        premium_discount = self._detect_zone(row)
        evidence["zone"] = premium_discount

        displacement = self._detect_displacement(window)
        if displacement:
            events.append({"type": "DISPLACEMENT", "direction": displacement})
            evidence["displacement"] = displacement

        mtf = self._detect_mtf_alignment(context, index)
        evidence["mtf_alignment"] = mtf
        if mtf == "ALIGNED":
            events.append({"type": "MTF_ALIGNMENT", "detail": "HTF and LTF agree"})

        confidence, bias = self._compute_confidence(events, trend, premium_discount)

        return AnalysisResult(
            agent_name="ICT",
            bias=bias,
            confidence=confidence,
            detected_events=events,
            evidence=evidence,
            invalidation_conditions=invalidation,
        )

    def _detect_trend(self, window: pd.DataFrame) -> str:
        labels = window["swing_label"].dropna().unique()
        has_hh = any("HH" in str(l) for l in labels)
        has_ll = any("LL" in str(l) for l in labels)
        if has_hh and not has_ll:
            return "BULLISH"
        if has_ll and not has_hh:
            return "BEARISH"
        last = window["macro_direction"].iloc[-1] if "macro_direction" in window.columns else "RANGING"
        return str(last) if str(last) in ("BULLISH", "BEARISH") else "RANGING"

    def _detect_bos(self, window: pd.DataFrame, trend: str) -> str | None:
        bos = window["bos_direction"].iloc[-3:].max() if len(window) >= 3 else window["bos_direction"].max()
        if trend == "BULLISH" and bos > 0:
            return "bullish_break"
        if trend == "BEARISH" and bos < 0:
            return "bearish_break"
        return None

    def _detect_choch(self, window: pd.DataFrame, trend: str) -> str | None:
        if "choch_signal" not in window.columns:
            return None
        recent = window["choch_signal"].iloc[-5:].dropna().unique() if len(window) >= 5 else window["choch_signal"].dropna().unique()
        if trend == "BULLISH" and any("BEARISH" in str(c) for c in recent):
            return "BEARISH"
        if trend == "BEARISH" and any("BULLISH" in str(c) for c in recent):
            return "BULLISH"
        return None

    def _detect_sweep(self, window: pd.DataFrame) -> str | None:
        if "liquidity_sweep_up" in window.columns and window["liquidity_sweep_up"].iloc[-1]:
            return "buy_side"
        if "liquidity_sweep_down" in window.columns and window["liquidity_sweep_down"].iloc[-1]:
            return "sell_side"
        recent_up = window["recent_sweep_up"].iloc[-1] if "recent_sweep_up" in window.columns else False
        recent_down = window["recent_sweep_down"].iloc[-1] if "recent_sweep_down" in window.columns else False
        if isinstance(recent_up, (bool, np.bool_)) and recent_up:
            return "buy_side_swept"
        if isinstance(recent_down, (bool, np.bool_)) and recent_down:
            return "sell_side_swept"
        return None

    def _detect_fvg(self, window: pd.DataFrame) -> dict[str, Any] | None:
        last = window.iloc[-1]
        bullish = bool(last.get("fvg_bullish", False))
        bearish = bool(last.get("fvg_bearish", False))
        if not bullish and not bearish:
            if "fvg_fill_status" in window.columns:
                status = str(last.get("fvg_fill_status", "none"))
                if status != "none":
                    return {"status": status, "direction": "bullish" if "bullish" in status else "bearish"}
            return None
        size = float(last.get("fvg_size", 0.0))
        atr = float(last.get("atr", 1.0))
        quality = min(size / atr, 1.0) if atr > 1e-9 else 0.0
        direction = "bullish" if bullish else "bearish"
        return {"direction": direction, "size_points": size, "quality": round(quality, 4)}

    def _detect_ob(self, window: pd.DataFrame) -> dict[str, Any] | None:
        last = window.iloc[-1]
        bullish = bool(last.get("ob_bullish", False))
        bearish = bool(last.get("ob_bearish", False))
        if not bullish and not bearish:
            return None
        distance = float(last.get("ob_distance", 0.0))
        atr = float(last.get("atr", 1.0))
        proximity = distance / atr if atr > 1e-9 else 99.0
        return {
            "direction": "bullish" if bullish else "bearish",
            "distance_atr": round(proximity, 2),
        }

    def _detect_zone(self, row: pd.Series) -> str:
        zone = row.get("premium_discount_zone", "NONE")
        return str(zone) if str(zone) != "NONE" else "UNKNOWN"

    def _detect_displacement(self, window: pd.DataFrame) -> str | None:
        if len(window) < 3:
            return None
        last = window.iloc[-1]
        bullish = bool(last.get("displacement_bullish", False))
        bearish = bool(last.get("displacement_bearish", False))
        if bullish:
            return "BULLISH"
        if bearish:
            return "BEARISH"
        return None

    def _detect_mtf_alignment(self, context: pd.DataFrame, index: int) -> str:
        row = context.iloc[index]
        macro = str(row.get("macro_direction", "RANGING"))
        d1 = str(row.get("d1_direction", "RANGING"))
        if macro == d1 and macro in ("BULLISH", "BEARISH"):
            return "ALIGNED"
        if macro in ("BULLISH", "BEARISH") and d1 in ("BULLISH", "BEARISH"):
            return "PARTIAL"
        return "CONFLICTING"

    def _compute_confidence(self, events: list[dict[str, Any]], trend: str, zone: str) -> tuple[float, str]:
        score = 0.0
        max_score = 0.0
        weights = {"BOS": 1.0, "CHOCH": 2.0, "LIQUIDITY_SWEEP": 2.0, "FVG": 2.0, "ORDER_BLOCK": 2.0, "DISPLACEMENT": 2.0, "MTF_ALIGNMENT": 3.0}

        for e in events:
            w = weights.get(e["type"], 1.0)
            max_score += w
            score += w

        if max_score == 0.0:
            return 0.0, "NEUTRAL"

        raw = score / max_score
        zone_bonus = 0.05 if "OTE" in zone else 0.0
        trend_bonus = 0.05 if trend in ("BULLISH", "BEARISH") else -0.05
        confidence = min(max(raw + zone_bonus + trend_bonus, 0.0), 0.95)

        if confidence >= 0.5:
            bias = "BULLISH" if trend != "BEARISH" else "NEUTRAL"
        else:
            bias = "NEUTRAL"

        return round(confidence, 4), bias
