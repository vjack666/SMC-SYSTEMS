"""ict_backtest/poi_anchor_motor.py — Brecha B (Opción 2): ancla POI HTF SIN tocar run_sequence.

Principio Brecha D: el ancla se ANOTA, NO filtra. `compute_htf_anchored` es una
funcion PURA que, dada una senal ya generada por `run_sequence`, consulta el
indice HTF (HtfPdIndex, ya construido en canonical.py cuando enable_pd_index=True)
y devuelve si habia un POI del HTF padre en la MISMA direccion al momento de la
entrada (anti look-ahead: zones_at usa el mapa LTF->HTF ya alineado closed-only).

NO modifica el conteo de senales: si no hay ancla, devuelve False y la senal
sigue saliendo. Si no hay indice HTF (modo historico), devuelve None.

Esta es la alternativa conservadora a tocar run_sequence: el motor interno
queda 100% intacto; el ancla se calcula en post-proceso, en canonical.py.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest.htf_pd_index import HtfPdIndex


def compute_htf_anchored(
    sig_dir: int,
    entry_at: int,
    htf_pd_index: HtfPdIndex | None,
    ltf_map: dict[str, pd.DataFrame] | None,
) -> bool | None:
    """¿La senal tiene respaldo de POI HTF padre en su direccion?

    Consulta `htf_pd_index.zones_at(entry_at, tf, ltf_map)` para cada TF HTF
    (D1/H4/H1) y devuelve True si ALGUNA zona vigente va en `sig_dir`.

    - `htf_pd_index is None` (modo historico, enable_pd_index=False): None.
    - sin zona en la direccion: False (la senal NO se descarta).
    """
    if htf_pd_index is None or ltf_map is None:
        return None
    for tf in htf_pd_index.timeframes:
        zones = htf_pd_index.zones_at(entry_at, tf, ltf_map)
        for z in zones:
            if z.direction == sig_dir:
                return True
    return False
