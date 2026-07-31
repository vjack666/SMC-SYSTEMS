"""ict_backtest/structure_mtf_align.py — Fase 4: alineacion temporal multi-TF.

Clasifica onsets BOS/CHOCH del timeframe de ejecucion (LTF, p.ej. M5)
contra onsets detectados de forma INDEPENDIENTE en D1/H4/H1.

Regla de clasificacion (ICT, match temporal — NO precio/rango):

  HTF  = existe onset del mismo tipo y direccion en D1 o H4
         dentro de la ventana de tolerancia del TF superior.
  ITF  = existe en H1 (y no en D1/H4) dentro de su tolerancia.
  LTF  = solo aparece en el frame de ejecucion (sin eco superior).

Por que NO usar membership de high/low ni rango 20/50:
  - Agregar H4/H1 a la grilla M5 "traga" casi todos los niveles → CHOCH LTF=0.
  - Clasificar por rango local M5 empuja casi todo a LTF → HTF≈0.
  La capa temporal es el RELOJ de origen del onset, no la geometria del precio.

Contrato:
  - El motor `detect_market_structure` permanece TF-agnostico.
  - Este modulo solo lee onsets (bos_dir/choch_dir != 0) y tiempos.
  - Anti look-ahead: el match superior usa time_htf <= time_ltf + tol
    y time_htf >= time_ltf - tol (ventana simetrica acotada; el onset HTF
    tipicamente cierra antes o en la misma ventana que el eco LTF).

Tolerancias por defecto (anchas a proposito; calibrables):
  D1: ±1 day, H4: ±4 hours, H1: ±1 hour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


# Tolerancias por defecto (pandas Timedelta strings).
DEFAULT_TOLERANCES: dict[str, str] = {
    "D1": "1D",
    "H4": "4h",
    "H1": "1h",
}

HTF_TFS: tuple[str, ...] = ("D1", "H4")
ITF_TFS: tuple[str, ...] = ("H1",)


@dataclass(frozen=True)
class StructureOnset:
    """Un onset de estructura en un timeframe concreto."""

    time: pd.Timestamp
    event: str  # "BOS" | "CHOCH"
    direction: int  # +1 | -1
    level: float
    tf: str
    bar_index: int = -1


@dataclass
class AlignConfig:
    """Configuracion de alineacion temporal."""

    tolerances: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TOLERANCES))
    ltf: str = "M5"
    htf_tfs: tuple[str, ...] = HTF_TFS
    itf_tfs: tuple[str, ...] = ITF_TFS


def extract_onsets(ms: pd.DataFrame, tf: str) -> list[StructureOnset]:
    """Extrae onsets BOS/CHOCH de un DataFrame anotado por detect_market_structure.

    Onset = fila donde bos_dir != 0 o choch_dir != 0 (mutuamente excluyentes
    en el motor canonico). Si hay columna structure_label, se prioriza.
    """
    if ms is None or len(ms) == 0:
        return []

    d = ms
    times = pd.to_datetime(d["time"] if "time" in d.columns else d.index, utc=True, errors="coerce")
    bos = d["bos_dir"].to_numpy() if "bos_dir" in d.columns else np.zeros(len(d))
    choch = d["choch_dir"].to_numpy() if "choch_dir" in d.columns else np.zeros(len(d))
    bos_lvl = d["bos_level"].to_numpy() if "bos_level" in d.columns else np.full(len(d), np.nan)
    choch_lvl = (
        d["choch_level"].to_numpy() if "choch_level" in d.columns else np.full(len(d), np.nan)
    )
    labels = (
        d["structure_label"].astype(str).to_numpy()
        if "structure_label" in d.columns
        else None
    )

    out: list[StructureOnset] = []
    for i in range(len(d)):
        t = times.iloc[i] if hasattr(times, "iloc") else times[i]
        if pd.isna(t):
            continue
        bd = int(bos[i]) if not (isinstance(bos[i], float) and np.isnan(bos[i])) else 0
        cd = int(choch[i]) if not (isinstance(choch[i], float) and np.isnan(choch[i])) else 0

        if labels is not None and labels[i] in ("BOS", "CHOCH"):
            event = labels[i]
            direction = bd if event == "BOS" else cd
            if direction == 0:
                direction = bd or cd
            level = float(bos_lvl[i]) if event == "BOS" else float(choch_lvl[i])
            if direction == 0:
                continue
            out.append(
                StructureOnset(
                    time=pd.Timestamp(t),
                    event=event,
                    direction=int(direction),
                    level=level if np.isfinite(level) else float("nan"),
                    tf=tf,
                    bar_index=int(i),
                )
            )
            continue

        if bd != 0:
            lvl = float(bos_lvl[i]) if np.isfinite(bos_lvl[i]) else float("nan")
            out.append(
                StructureOnset(
                    time=pd.Timestamp(t),
                    event="BOS",
                    direction=bd,
                    level=lvl,
                    tf=tf,
                    bar_index=int(i),
                )
            )
        elif cd != 0:
            lvl = float(choch_lvl[i]) if np.isfinite(choch_lvl[i]) else float("nan")
            out.append(
                StructureOnset(
                    time=pd.Timestamp(t),
                    event="CHOCH",
                    direction=cd,
                    level=lvl,
                    tf=tf,
                    bar_index=int(i),
                )
            )
    return out


def _tol_delta(tolerances: dict[str, str], tf: str) -> pd.Timedelta:
    raw = tolerances.get(tf, "1h")
    return pd.Timedelta(raw)


def _has_match(
    onset: StructureOnset,
    candidates: Sequence[StructureOnset],
    tol: pd.Timedelta,
) -> bool:
    """True si algun candidate comparte event+direction y cae en [t-tol, t+tol]."""
    if not candidates:
        return False
    t0 = onset.time - tol
    t1 = onset.time + tol
    for c in candidates:
        if c.event != onset.event:
            continue
        if c.direction != onset.direction:
            continue
        if t0 <= c.time <= t1:
            return True
    return False


def classify_onset_tf_level(
    onset: StructureOnset,
    onsets_by_tf: dict[str, list[StructureOnset]],
    config: AlignConfig | None = None,
) -> str:
    """Clasifica un onset LTF como HTF / ITF / LTF por alineacion temporal.

    Prioridad: HTF (D1|H4) > ITF (H1) > LTF.
    """
    cfg = config or AlignConfig()

    for tf in cfg.htf_tfs:
        cand = onsets_by_tf.get(tf, [])
        tol = _tol_delta(cfg.tolerances, tf)
        if _has_match(onset, cand, tol):
            return "HTF"

    for tf in cfg.itf_tfs:
        cand = onsets_by_tf.get(tf, [])
        tol = _tol_delta(cfg.tolerances, tf)
        if _has_match(onset, cand, tol):
            return "ITF"

    return "LTF"


def classify_ltf_onsets(
    ltf_onsets: Sequence[StructureOnset],
    onsets_by_tf: dict[str, list[StructureOnset]],
    config: AlignConfig | None = None,
) -> list[dict[str, Any]]:
    """Clasifica una lista de onsets LTF. Devuelve dicts listos para JSON/CSV."""
    cfg = config or AlignConfig()
    rows: list[dict[str, Any]] = []
    for o in ltf_onsets:
        level = classify_onset_tf_level(o, onsets_by_tf, cfg)
        rows.append(
            {
                "time": o.time.isoformat(),
                "event": o.event,
                "direction": o.direction,
                "level": o.level,
                "tf": o.tf,
                "bar_index": o.bar_index,
                "tf_level": level,
            }
        )
    return rows


def build_onsets_by_tf(
    ms_by_tf: dict[str, pd.DataFrame],
    tfs: Iterable[str] | None = None,
) -> dict[str, list[StructureOnset]]:
    """Corre extract_onsets sobre cada TF presente en ms_by_tf."""
    order = list(tfs) if tfs is not None else list(ms_by_tf.keys())
    out: dict[str, list[StructureOnset]] = {}
    for tf in order:
        df = ms_by_tf.get(tf)
        if df is None:
            out[tf] = []
            continue
        out[tf] = extract_onsets(df, tf)
    return out


def summarize_by_tf_level(classified: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Agrega conteos BOS/CHOCH por tf_level. Particion exhaustiva."""
    bos = {"HTF": 0, "ITF": 0, "LTF": 0}
    choch = {"HTF": 0, "ITF": 0, "LTF": 0}
    for row in classified:
        bucket = bos if row["event"] == "BOS" else choch
        lvl = row.get("tf_level", "LTF")
        if lvl not in bucket:
            lvl = "LTF"
        bucket[lvl] += 1
    bos_total = sum(bos.values())
    choch_total = sum(choch.values())
    return {
        "bos": {"total": bos_total, "by_tf": bos},
        "choch": {"total": choch_total, "by_tf": choch},
        "partition_ok": (
            bos_total == bos["HTF"] + bos["ITF"] + bos["LTF"]
            and choch_total == choch["HTF"] + choch["ITF"] + choch["LTF"]
        ),
    }


def align_structure_mtf(
    ms_by_tf: dict[str, pd.DataFrame],
    *,
    ltf: str = "M5",
    config: AlignConfig | None = None,
) -> dict[str, Any]:
    """Pipeline end-to-end: extrae onsets, clasifica LTF, resume.

    ``ms_by_tf`` debe contener DataFrames YA anotados por
    ``detect_market_structure`` (columnas bos_dir/choch_dir/time).

    Devuelve::

        {
          "ltf": "M5",
          "events": [...],          # cada onset LTF con tf_level
          "summary": {...},         # conteos BOS/CHOCH by_tf
          "onsets_counts": {tf: n}, # onsets nativos por TF
        }
    """
    cfg = config or AlignConfig(ltf=ltf)
    if config is None:
        cfg = AlignConfig(ltf=ltf)
    else:
        cfg = config

    tfs = list(dict.fromkeys([*(cfg.htf_tfs), *(cfg.itf_tfs), ltf]))
    onsets_by_tf = build_onsets_by_tf(ms_by_tf, tfs=tfs)
    ltf_onsets = onsets_by_tf.get(ltf, [])
    classified = classify_ltf_onsets(ltf_onsets, onsets_by_tf, cfg)
    summary = summarize_by_tf_level(classified)

    return {
        "ltf": ltf,
        "events": classified,
        "summary": summary,
        "onsets_counts": {tf: len(v) for tf, v in onsets_by_tf.items()},
    }
