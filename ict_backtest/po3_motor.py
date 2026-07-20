"""ict_backtest/po3_motor.py — Brecha E (Opción 2): PO3/AMD completo SIN tocar run_sequence.

Copia del patrón de Brecha B (ict_backtest/poi_anchor_motor.py): el motor
canónico (run_sequence) queda 100% intacto y el veredicto PO3 se calcula en
POST-PROCESO, como una ANOTACIÓN por señal (principio Brecha D: anota, NO
filtra). El conteo de señales es IDÉNTICO con o sin esta capa.

`compute_po3_complete` es una función PURA y testeable que, dada la
`structure_data` (estructura por TF ya construida con velas CERRADAS al
momento de la entrada) y un `config`, delega en `signals.po3.build_po3_state`
y devuelve si el ciclo PO3/AMD (A/M/D + alineación a-favor) estaba COMPLETO:

  - True   -> ciclo PO3 completo en la dirección del setup.
  - False  -> ciclo presente pero incompleto/judas (falta D, o desalineado).
  - None   -> sin datos de estructura (modo histórico): comportamiento intacto,
              la señal NO se toca.

NO altera el conteo de señales ni entry/SL/TP: es metadato de percepción,
igual que htf_anchored.

--------------------------------------------------------------------------------
CÓMO ENCHUFARLO EN canonical.evaluate_signals (lo hace el agente principal):
--------------------------------------------------------------------------------
En el loop post-run_sequence (alrededor de canonical.py líneas 170-188, donde
se construye ICTSignal), PARA CADA señal `s`:

  1) Armar `structure_data` con velas CERRADAS <= entry_at, en la forma que
     consume `signals.po3.build_po3_state`:
        {tf: {"trend", "sweep_up", "sweep_down", "bos_dir", "bos_status",
              "choch_status", "fvg_state", "ob_dir", "session_range",
              "session_open"}}
     (reusar est_htf_fn y los ms[ltf]/ms[htf] ya calculados; slice hasta
      entry_at para anti look-ahead).
  2) Llamar:
        po3_complete = compute_po3_complete(
            structure_data,
            config=Po3MotorConfig(bias=<bias htf>, votes=<votos ltf>,
                                  exec_tf=ltf, htf=htf),
        )
  3) Pasar `po3_complete=po3_complete` al constructor ICTSignal (el campo
     `po3_complete: bool | None = None` lo agrega el principal en engine.py).

El `score_plan` de plan_driver.py YA suma +0.5 cuando `po3_complete` es True
(Brecha E, líneas 147-149), así que el medidor de alineación se beneficia sin
tocar la generación de señales.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from signals.po3 import build_po3_state


@dataclass
class Po3MotorConfig:
    """Contexto que necesita compute_po3_complete para delegar en build_po3_state.

    El llamador (canonical.evaluate_signals) lo popula con el sesgo HTF ya
    calculado, los votos L/S del LTF y los timeframes de ejecución/contexto.
    """

    bias: str = ""               # sesgo HTF: "BULLISH" | "BEARISH" | "NEUTRAL" | ""
    votes: dict | None = None    # votos L/S del motor (opcional)
    exec_tf: str = "M15"         # timeframe de ejecución
    htf: str = "H4"              # timeframe de contexto


def compute_po3_complete(
    structure_data: dict | None,
    config: Po3MotorConfig | None = None,
) -> bool | None:
    """¿El ciclo PO3/AMD estaba COMPLETO al momento de la entrada?

    Función PURA: no accede a disco ni a bar_index, no muta nada. Solo lee
    `structure_data` (dict por TF, velas CERRADAS) y delega en
    `signals.po3.build_po3_state`.

    Parámetros
    ----------
    structure_data : dict por TF en la forma que consume build_po3_state.
        Si es None o vacío -> None (modo histórico, sin datos: intacto).
    config : Po3MotorConfig con bias/votes/exec_tf/htf. Si None, usa defaults.

    Devuelve
    --------
    bool | None :
        True  -> PO3 completo (A/M/D + alineación a-favor) en la dirección.
        False -> ciclo presente pero incompleto/judas (falta D o desalineado).
        None  -> sin datos de estructura (comportamiento histórico intacto).
    """
    if not structure_data:
        # Sin datos de estructura: no podemos opinar. El comportamiento
        # histórico queda intacto (la señal no se anota ni se descarta).
        return None

    cfg = config if config is not None else Po3MotorConfig()
    state = build_po3_state(
        structure_data,
        bias=cfg.bias,
        votes=cfg.votes,
        exec_tf=cfg.exec_tf,
        htf=cfg.htf,
    )
    # complete ya es A and M and D and aligned (ver signals/po3.py).
    return bool(state.complete)
