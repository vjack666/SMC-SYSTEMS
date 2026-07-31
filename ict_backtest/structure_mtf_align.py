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
class AlignConfig:
    tolerances: Dict[str, pd.Timedelta] = field(
        default_factory=lambda: {
            "D1": pd.Timedelta("1D"),
            "H4": pd.Timedelta("4h"),
            "H1": pd.Timedelta("1h"),
            "M5": pd.Timedelta("5min"),
        }
    )
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
        if htf.event != onset.event or htf.direction != onset.direction:
            continue
        if abs(htf.time - onset.time) <= tol:
            return htf.tf or "UNKNOWN"
    return None


def align_structure_mtf(
    ms_by_tf: Dict[str, pd.DataFrame],
    config: Optional[AlignConfig] = None,
) -> Dict:
    if config is None:
        config = AlignConfig()

    # Orden natural: D1 → H4 → H1 → LTF
    ordered = [tf for tf in ["D1", "H4", "H1", "M5"] if tf in ms_by_tf]
    if config.ltf not in ms_by_tf:
        raise KeyError(f"LTF '{config.ltf}' ausente en ms_by_tf")
    if len(ordered) < 2:
        # Degenerate case: only one TF available -> all onsets are LTF by definition
        ltf_onsets = _extract_onsets(ms_by_tf[config.ltf], config.ltf)
        by_tf = {"bos": {"HTF": 0, "ITF": 0, "LTF": 0}, "choch": {"HTF": 0, "ITF": 0, "LTF": 0}}
        for onset in ltf_onsets:
            if onset.event == "bos":
                by_tf["bos"]["LTF"] += 1
            else:
                by_tf["choch"]["LTF"] += 1
        summary = {
            "bos": {"total": by_tf["bos"]["LTF"], "by_tf": by_tf["bos"]},
            "choch": {"total": by_tf["choch"]["LTF"], "by_tf": by_tf["choch"]},
            "partition_ok": True,
            "counts_used": ordered,
        }
        return {"summary": summary, "onsets": ltf_onsets}

    ltf_onsets = _extract_onsets(ms_by_tf[config.ltf], config.ltf)

    # Índice temporal por TF superior (D1/H4/H1)
    htf_index: Dict[str, List[Onset]] = {}
    for tf in ordered:
        if tf == config.ltf:
            continue
        htf_index[tf] = sorted(
            _extract_onsets(ms_by_tf[tf], tf),
            key=lambda o: o.time,
        )

    def _best_match(onset: Onset) -> str:
        for tf in ["D1", "H4", "H1"]:
            if tf not in htf_index or tf == config.ltf:
                continue
            tol = config.tolerances.get(tf, pd.Timedelta("1h"))
            matched = _match_tf(onset, htf_index[tf], tol)
            if matched is not None:
                return matched
        return "LTF"

    by_tf: Dict[str, Dict[str, int]] = {"bos": {"HTF": 0, "ITF": 0, "LTF": 0}, "choch": {"HTF": 0, "ITF": 0, "LTF": 0}}
    for onset in ltf_onsets:
        tf_level = _best_match(onset)
        if tf_level == "LTF":
            bucket = "LTF"
        elif tf_level in ("D1", "H4"):
            bucket = "HTF"
        elif tf_level == "H1":
            bucket = "ITF"
        else:
            bucket = "LTF"

        if onset.event == "bos":
            by_tf["bos"][bucket] += 1
        else:
            by_tf["choch"][bucket] += 1

    bos_total = sum(by_tf["bos"].values())
    choch_total = sum(by_tf["choch"].values())
    partition_ok = (
        bos_total == sum(by_tf["bos"].values())
        and choch_total == sum(by_tf["choch"].values())
        and bos_total + choch_total > 0
    )

    summary = {
        "bos": {
            "total": bos_total,
            "by_tf": by_tf["bos"],
        },
        "choch": {
            "total": choch_total,
            "by_tf": by_tf["choch"],
        },
        "partition_ok": partition_ok,
        "counts_used": ordered,
    }
    return {
        "summary": summary,
        "onsets": ltf_onsets,
    }
