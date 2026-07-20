"""ict_backtest/dealing_range_motor.py — Brecha C (Opción 2): dealing range SIN tocar run_sequence.

Tesis (libro 21 §0/§2, libro 08 PO3): un POI / entrada valida debe caer en la
ZONA CORRECTA del dealing range del swing HTF. EQ = 50% fib del swing HTF.
discount (< EQ) favorece long; premium (> EQ) favorece short; EQ central es
ambiguo. La capa `ict_backtest/dealing_range.py` YA existe (la usa el MEDIDOR
Fase 5), pero el MOTOR canonico no la anota por senal. Esta Brecha C cierra eso.

Principio Brecha D: la zona se ANOTA en ICTSignal, NO filtra. El conteo de
senales debe ser IDENTICO con/sin esta capa. Si no hay swing HTF disponible
(modo historico), `compute_zone_class` devuelve None y la senal sigue saliendo.

Alternativa conservadora a tocar run_sequence: el motor interno queda 100%
intacto; la clase de zona se calcula en POST-PROCESO, en canonical.py.

----------------------------------------------------------------------------
ENCHUFE (lo hace el agente principal en el merge, NO este modulo):
----------------------------------------------------------------------------
En `ict_backtest/canonical.py`, dentro de `evaluate_signals`, TRAS el bucle de
`run_sequence` (no tocar sequence.py), en el mismo punto donde ya se calcula
`htf_anchored`, agregar:

    from ict_backtest.dealing_range_motor import compute_zone_class

    # swing HTF vigente al momento de la entrada (sin look-ahead: usamos el
    # candle HTF cerrado que contiene entry_at, igual que est_htf_fn).
    htf_ms = ms.get(htf, ltf_df)            # market structure HTF ya calculado
    htf_row = closed_row_at_time(htf_ms, ltf_df.iloc[entry_at]["time"],
                                 tf_duration(htf))
    zone_class = compute_zone_class(
        sig_dir=direction,
        entry=entry,
        swing_high_htf=float(htf_row["swing_high"]) if htf_row is not None else None,
        swing_low_htf=float(htf_row["swing_low"]) if htf_row is not None else None,
    )

y setear en el ICTSignal:

    zone_class=zone_class,

(fieldo `ICTSignal.zone_class: str | None = None` lo agrega el principal en el
merge en engine.py; no se edita aqui). Con swing_high/low = None (modo
historico) compute_zone_class devuelve None y el comportamiento previo queda
intacto: cero cambios en el conteo de senales.
"""
from __future__ import annotations

from typing import Any

from ict_backtest.dealing_range import classify_zone


def compute_zone_class(
    sig_dir: int,
    entry: float,
    swing_high_htf: float | None,
    swing_low_htf: float | None,
) -> str | None:
    """Clasifica la ZONA de la entrada dentro del dealing range del swing HTF.

    Funcion PURA y testeable. Dada una senal ya generada por `run_sequence`,
    toma el precio de entrada y el swing HTF padre (swing_high/swing_low del
    candle HTF vigente al momento de la entrada, anti look-ahead) y devuelve
    en que zona cae la entrada: 'PREMIUM' | 'DISCOUNT' | 'EQ'.

    `sig_dir` (+1 long, -1 short) se acepta por simetria con Brecha B y para
    futuros helpers direccionales, pero la clase de zona es POSICIONAL (entry
    vs EQ); no altera el resultado de la clasificacion.

    - `swing_high_htf` o `swing_low_htf` es None (modo historico, sin swing HTF
      disponible): devuelve None -> comportamiento historico intacto, la senal
      NO se descarta (principio Brecha D).
    - Delega en `dealing_range.classify_zone`, pasando entry como punto
      (zone_high == zone_low == entry) para que el midpoint sea el propio precio.

    NO modifica el conteo de senales: es pura anotacion.
    """
    if swing_high_htf is None or swing_low_htf is None:
        return None
    try:
        return classify_zone(
            zone_high=entry,
            zone_low=entry,
            swing_high=float(swing_high_htf),
            swing_low=float(swing_low_htf),
        )
    except (ValueError, TypeError):
        # swing invalido (high <= low, o no numericos) -> no anotamos, intacto.
        return None
