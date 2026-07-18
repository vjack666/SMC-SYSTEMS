"""Fase C (C0) — Plumbing HTF: indice temporal de PD Arrays del marco superior.

Este módulo es SOLO PERCEPCIÓN. No crea zonas nuevas: lee los detectores
FVG/OB ya existentes en los frames HTF y los organiza en un mapa temporal para
que el evaluador de autoridad (zone_authority.py, C2) pueda consultar, dada una
vela del LTF, qué PD arrays del HTF están VIGENTES (no invalidados/llenados).

CIERRE DEL ROOT CAUSE (ver ETAPA_4_FASE_C_PLAN.md §3): el hook htf_poi_fn ya
existía en run_sequence, pero est_htf_fn nunca traía FVG/OB del HTF. Aquí
construimos exactamente esa información que faltaba ("el cable que no llegaba").

CONSTRUCCIÓN O(n), NO O(n²): el mapa LTF->HTF se resuelve UNA sola vez
por TF HTF con closed_merge_asof (anti look-ahead, R6.1/G1). `zones_at` solo
hace lookup O(1) sobre el mapa ya alineado. Esto evita el cuello que tendría
consultar closed_row_at_time por cada una de las ~112k velas M15.

Contrato de no invasión de C (§1 del plan): este módulo NO decide dirección,
entry, SL ni TP; NO crea zonas; NO toca R7. Solo indexa lo que los detectores
ya marcaron.

Convención de tiers (libro 21 §2 / Fase B1):
    T1 = BPR (FVG + OB en misma zona, máxima autoridad)  -> resuelto en C2
    T2 = FVG / OB / PROPULSION
    T3 = REJECTION_BLOCK
Orden de autoridad: T1 > T2 > T3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class HtfPdZone:
    """Un PD array vigente del HTF, ya detectado por los detectores existentes.

    Es SOLO lectura de lo que el detector marcó: C no inventa ninguno.
    """

    tf: str          # marco superior de origen ("D1", "H4", "H1")
    pd_type: str     # FVG / OB / BPR / REJECTION_BLOCK / MITIGATION_BLOCK / BREAKER
    pd_tier: str     # T1 / T2 / T3 (sin BPR, el HTF crudo es T2/T3)
    direction: int   # +1 bullish, -1 bearish
    zone_high: float
    zone_low: float


def _detect_pd_arrays(frame: pd.DataFrame) -> pd.DataFrame:
    """Aplica FVG + OB al frame HTF y devuelve columnas de PD array + zonas activas.

    Reusa los detectores ya canónicos (Fase B1: pd_type/pd_tier). Además calcula,
    por barra HTF, la zona ACTIVA vigente por dirección (forward-filled hasta
    invalidación), porque los flags fvg_*/ob_* solo valen en la barra de creación.
    Así zones_at() lee el estado "vivo" correcto en cualquier vela LTF.
    """
    from detectors.fvg import detect_fvg
    from detectors.ob import detect_order_blocks

    d = detect_fvg(frame)
    d = detect_order_blocks(d)
    n = len(d)

    cur = {"bull_fvg": None, "bull_ob": None, "bear_fvg": None, "bear_ob": None}

    out = {
        "act_bull_type": [None] * n, "act_bull_tier": [None] * n,
        "act_bull_high": [float("nan")] * n, "act_bull_low": [float("nan")] * n,
        "act_bull_on": [False] * n,
        "act_bear_type": [None] * n, "act_bear_tier": [None] * n,
        "act_bear_high": [float("nan")] * n, "act_bear_low": [float("nan")] * n,
        "act_bear_on": [False] * n,
    }

    for i in range(n):
        r = d.iloc[i]
        if bool(r.get("fvg_bullish", False)):
            cur["bull_fvg"] = ("FVG", "T2", float(r["high"]), float(r["low"]))
        if bool(r.get("fvg_bearish", False)):
            cur["bear_fvg"] = ("FVG", "T2", float(r["high"]), float(r["low"]))
        if bool(r.get("ob_bullish", False)):
            cur["bull_ob"] = (str(r.get("pd_type", "OB")), str(r.get("pd_tier", "T2")),
                              float(r["ob_top"]), float(r["ob_bottom"]))
        if bool(r.get("ob_bearish", False)):
            cur["bear_ob"] = (str(r.get("pd_type", "OB")), str(r.get("pd_tier", "T2")),
                              float(r["ob_top"]), float(r["ob_bottom"]))
        fs = str(r.get("fvg_fill_status", ""))
        if fs not in ("bullish_unfilled", "just_created"):
            cur["bull_fvg"] = None
        if fs not in ("bearish_unfilled", "just_created"):
            cur["bear_fvg"] = None
        if str(r.get("ob_status", "")) == "invalidated":
            cur["bull_ob"] = None
            cur["bear_ob"] = None
        for side, on_key, fvg_key, ob_key in (
            ("bull", "act_bull_on", "bull_fvg", "bull_ob"),
            ("bear", "act_bear_on", "bear_fvg", "bear_ob"),
        ):
            zone = cur[ob_key] if cur[ob_key] is not None else cur[fvg_key]
            if zone is not None:
                out[f"act_{side}_type"][i] = zone[0]
                out[f"act_{side}_tier"][i] = zone[1]
                out[f"act_{side}_high"][i] = zone[2]
                out[f"act_{side}_low"][i] = zone[3]
                out[on_key][i] = True

    for k, v in out.items():
        d[k] = v
    return d


class HtfPdIndex:
    """Indice temporal de PD arrays HTF vigentes por vela del LTF.

    Construye UNA sola vez, por TF HTF, un merge asof CERRADO (anti look-ahead)
    que alinea las zonas activas del HTF al LTF. `zones_at` es lookup O(1).
    """

    # Columnas de zona activa que _detect_pd_arrays calcula por barra HTF.
    _ACT_COLS = [
        "act_bull_on", "act_bull_type", "act_bull_tier",
        "act_bull_high", "act_bull_low",
        "act_bear_on", "act_bear_type", "act_bear_tier",
        "act_bear_high", "act_bear_low",
    ]

    def __init__(self, htf_frames: dict[str, pd.DataFrame]):
        # Precalcula los detectores una sola vez por frame HTF (fuera del loop).
        self._detected: dict[str, pd.DataFrame] = {}
        for tf, df in htf_frames.items():
            if df is None or len(df) == 0:
                continue
            self._detected[tf] = _detect_pd_arrays(df)

    def build_ltf_map(self, ltf_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Resuelve el mapa LTF->HTF O(n) por TF HTF (merge asof cerrado).

        Devuelve {tf_htf: DataFrame alineado al LTF con las columnas act_*}.
        Se llama UNA vez fuera del loop del motor (evita O(n^2)).

        CERRADO-ONLY ANTI LOOK-AHEAD: el 'time' del HTF es el CIERRE de la
        vela. Un merge_asof backward sobre 'time' entre LTF y HTF entrega,
        para cada vela LTF, la ULTIMA barra HTF que ya cerró (htf_close <=
        ltf_time). Nunca lee una barra HTF que cierra DESPUES de la vela LTF
        (eso seria look-ahead cross-timeframe, R6.1/G1).

        Nota: NO usamos closed_merge_asof de _util porque este resta
        `duration` al join (asume time=OPEN); aqui time=CIERRE, asi que el
        merge directo es el closed-only correcto. Normalizamos el dtype de
        'time' (us/ms/ns) en ambos extremos porque merge_asof exige llaves
        del mismo tipo.
        """
        ltf_t = pd.to_datetime(ltf_df["time"], utc=True, errors="coerce").astype("datetime64[us, UTC]")
        ltf_sorted = ltf_df.copy()
        ltf_sorted["time"] = ltf_t
        ltf_sorted = ltf_sorted.sort_values("time").reset_index(drop=True)
        maps: dict[str, pd.DataFrame] = {}
        for tf, det in self._detected.items():
            det_t = pd.to_datetime(det["time"], utc=True, errors="coerce").astype("datetime64[us, UTC]")
            htf_sorted = det.copy()
            htf_sorted["time"] = det_t
            # Conservar time en el subset para poder ordenar/hacer merge asof.
            htf_sorted = htf_sorted[self._ACT_COLS + ["time"]].sort_values("time").reset_index(drop=True)
            merged = pd.merge_asof(
                ltf_sorted[["time"]], htf_sorted, on="time", direction="backward"
            )
            merged["time"] = ltf_t.values
            maps[tf] = merged[self._ACT_COLS].reset_index(drop=True)
        return maps

    def zones_at(self, ltf_i: int, htf_tf: str,
                 ltf_map: dict[str, pd.DataFrame] | None = None) -> list[HtfPdZone]:
        """PD arrays vigentes del HTF `htf_tf` en la vela LTF de índice `ltf_i`.

        O(1): lee la fila ya alineada en `ltf_map[htf_tf].iloc[ltf_i]`
        (construido por build_ltf_map). Si no se pasa mapa, cae a lookup por
        'time' (más lento, solo para tests unitarios).
        """
        det = self._detected.get(htf_tf)
        if det is None:
            return []
        if ltf_map is not None and htf_tf in ltf_map:
            row = ltf_map[htf_tf].iloc[ltf_i]
        else:
            # Modo test: requiere que se pasara el time en lugar de índice.
            raise ValueError(
                "zones_at en modo test requiere ltf_map; pasa (ltf_i, htf_tf, ltf_map)"
            )
        return self._row_zones(row, htf_tf)

    @staticmethod
    def _row_zones(row: pd.Series, tf: str) -> list[HtfPdZone]:
        out: list[HtfPdZone] = []
        if bool(row.get("act_bull_on", False)):
            out.append(HtfPdZone(
                tf=tf, pd_type=str(row["act_bull_type"]), pd_tier=str(row["act_bull_tier"]),
                direction=1, zone_high=float(row["act_bull_high"]),
                zone_low=float(row["act_bull_low"]),
            ))
        if bool(row.get("act_bear_on", False)):
            out.append(HtfPdZone(
                tf=tf, pd_type=str(row["act_bear_type"]), pd_tier=str(row["act_bear_tier"]),
                direction=-1, zone_high=float(row["act_bear_high"]),
                zone_low=float(row["act_bear_low"]),
            ))
        return out

    @property
    def timeframes(self) -> list[str]:
        return list(self._detected.keys())
