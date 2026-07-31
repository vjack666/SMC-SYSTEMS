"""ict_backtest/structure_mtf_align.py — Alineación temporal multi-TF de onsets BOS/CHOCH.

Contrato:
- Clasifica onsets del LTF por eco temporal en D1/H4/H1.
- NO modifica market_structure.py.
- NO usa membership de precio ni rangos locales.
- Criterio: mismo event + direction en TF superior dentro de tolerancia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd


@dataclass(frozen=True)
class LeadLag:
    lead: pd.Timedelta
    lag: pd.Timedelta


@dataclass(frozen=True)
class AlignConfig:
    tolerances: Dict[str, pd.Timedelta] = field(
        default_factory=lambda: {
            "D1": pd.Timedelta("1D"),
            "H4": pd.Timedelta("4h"),
            "H1": pd.Timedelta("1h"),
            "M5": pd.Timedelta("5min"),
        }
    )
    lead_lag: Dict[str, LeadLag] = field(
        default_factory=lambda: {
            "D1": LeadLag(lead=pd.Timedelta("2D"), lag=pd.Timedelta("1D")),
            "H4": LeadLag(lead=pd.Timedelta("8h"), lag=pd.Timedelta("4h")),
            "H1": LeadLag(lead=pd.Timedelta("2h"), lag=pd.Timedelta("1h")),
            "M5": LeadLag(lead=pd.Timedelta("5min"), lag=pd.Timedelta("5min")),
        }
    )
    soft_match_events: Tuple[str, ...] = ("choch", "bos")
    ltf: str = "M5"


@dataclass(frozen=True)
class Onset:
    time: pd.Timestamp
    event: str
    direction: int
    level: Optional[float] = None
    tf: Optional[str] = None


def _extract_onsets(ms: pd.DataFrame, tf: str) -> List[Onset]:
    onsets: List[Onset] = []
    for _, row in ms.iterrows():
        if pd.isna(row.get("time")):
            continue
        if row.get("bos_dir", 0) != 0:
            onsets.append(
                Onset(
                    time=pd.Timestamp(row["time"]),
                    event="bos",
                    direction=int(row["bos_dir"]),
                    level=float(row["bos_level"]) if pd.notna(row.get("bos_level")) else None,
                    tf=tf,
                )
            )
        if row.get("choch_dir", 0) != 0:
            onsets.append(
                Onset(
                    time=pd.Timestamp(row["time"]),
                    event="choch",
                    direction=int(row["choch_dir"]),
                    level=float(row["choch_level"]) if pd.notna(row.get("choch_level")) else None,
                    tf=tf,
                )
            )
    return onsets


def _match_tf(
    onset: Onset,
    htf_onsets: Sequence[Onset],
    tol: pd.Timedelta,
) -> Optional[str]:
    for htf in htf_onsets:
        if htf.direction != onset.direction:
            continue
        if htf.event != onset.event:
            continue
        if abs(htf.time - onset.time) <= tol:
            return htf.tf or "UNKNOWN"
    return None


def _soft_match_tf(
    onset: Onset,
    htf_onsets: Sequence[Onset],
    lead_lag: LeadLag,
    allowed_events: Tuple[str, ...],
) -> Optional[str]:
    for htf in htf_onsets:
        if htf.direction != onset.direction:
            continue
        if htf.event not in allowed_events:
            continue
        delta = onset.time - htf.time
        if -lead_lag.lead <= delta <= lead_lag.lag:
            return htf.tf or "UNKNOWN"
    return None


def align_structure_mtf(
    ms_by_tf: Dict[str, pd.DataFrame],
    config: Optional[AlignConfig] = None,
) -> Dict:
    if config is None:
        config = AlignConfig()

    ordered = [tf for tf in ["D1", "H4", "H1", "M5"] if tf in ms_by_tf]
    if config.ltf not in ms_by_tf:
        raise KeyError(f"LTF '{config.ltf}' ausente en ms_by_tf")

    onsets_by_tf = {tf: _extract_onsets(ms_by_tf[tf], tf) for tf in ordered}
    onsets_counts = {
        tf: {
            "bos": int(sum(1 for o in onsets_by_tf[tf] if o.event == "bos")),
            "choch": int(sum(1 for o in onsets_by_tf[tf] if o.event == "choch")),
        }
        for tf in ordered
    }

    if len(ordered) < 2:
        ltf_onsets = onsets_by_tf[config.ltf]
        by_tf = {"bos": {"HTF": 0, "ITF": 0, "LTF": 0}, "choch": {"HTF": 0, "ITF": 0, "LTF": 0}}
        for onset in ltf_onsets:
            by_tf[onset.event]["LTF"] += 1
        summary = {
            "bos": {"total": by_tf["bos"]["LTF"], "by_tf": by_tf["bos"]},
            "choch": {"total": by_tf["choch"]["LTF"], "by_tf": by_tf["choch"]},
            "partition_ok": True,
            "counts_used": ordered,
            "onsets_counts": onsets_counts,
        }
        return {"summary": summary, "onsets": ltf_onsets}

    ltf_onsets = onsets_by_tf[config.ltf]
    htf_index: Dict[str, List[Onset]] = {tf: sorted(onsets_by_tf[tf], key=lambda o: o.time) for tf in ordered if tf != config.ltf}

    by_tf: Dict[str, Dict[str, int]] = {"bos": {"HTF": 0, "ITF": 0, "LTF": 0}, "choch": {"HTF": 0, "ITF": 0, "LTF": 0}}
    for onset in ltf_onsets:
        tf_level = "LTF"
        for tf in ["D1", "H4", "H1"]:
            if tf not in htf_index or tf == config.ltf:
                continue
            tol = config.tolerances.get(tf, pd.Timedelta("1h"))
            matched = _match_tf(onset, htf_index[tf], tol)
            if matched is not None:
                tf_level = matched
                break

        if tf_level == "LTF" and onset.event == "choch":
            for tf in ["D1", "H4", "H1"]:
                if tf not in htf_index or tf == config.ltf:
                    continue
                ll = config.lead_lag.get(tf, LeadLag(lead=pd.Timedelta("2h"), lag=pd.Timedelta("1h")))
                matched = _soft_match_tf(onset, htf_index[tf], ll, config.soft_match_events)
                if matched is not None:
                    tf_level = matched
                    break

        if tf_level == "LTF":
            bucket = "LTF"
        elif tf_level in ("D1", "H4"):
            bucket = "HTF"
        elif tf_level == "H1":
            bucket = "ITF"
        else:
            bucket = "LTF"

        by_tf[onset.event][bucket] += 1

    bos_total = sum(by_tf["bos"].values())
    choch_total = sum(by_tf["choch"].values())
    partition_ok = bos_total == sum(by_tf["bos"].values()) and choch_total == sum(by_tf["choch"].values()) and bos_total + choch_total > 0

    summary = {
        "bos": {"total": bos_total, "by_tf": by_tf["bos"]},
        "choch": {"total": choch_total, "by_tf": by_tf["choch"]},
        "partition_ok": partition_ok,
        "counts_used": ordered,
        "onsets_counts": onsets_counts,
    }
    return {"summary": summary, "onsets": ltf_onsets}
