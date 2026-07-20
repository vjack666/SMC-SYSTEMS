"""Demo sintético Brecha E (Opción 2) — SIN datos reales.

Objetivo: demostrar que `ict_backtest.po3_motor.compute_po3_complete` calcula
correctamente el estado PO3/AMD al momento de la entrada y que, al aplicarlo en
POST-PROCESO sobre las señales ya generadas por run_sequence, el CONTEo de
señales queda IDÉNTICO (principio Brecha D: anota, NO filtra).

No lee data/raw (radio de explosión mínimo, demo pre-datos-reales). Simula el
loop de post-proceso que el agente principal hará en canonical.evaluate_signals:
toma N señales crudas y les PEGA la anotación `po3_complete` sin descartar
ninguna.

Cómo se enchufa luego en canonical.evaluate_signals (documentado también en
po3_motor.py):
    structure_data = <estructura por TF, velas CERRADAS <= entry_at>
    po3_complete = compute_po3_complete(structure_data,
                                        config=Po3MotorConfig(bias=..., htf=..., ...))
    ICTSignal(..., po3_complete=po3_complete)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ict_backtest.po3_motor import Po3MotorConfig, compute_po3_complete


def _complete_bullish_po3() -> dict:
    return {
        "H4": {"trend": "BULLISH", "sweep_up": False, "sweep_down": False},
        "M15": {
            "trend": "BULLISH", "sweep_up": False, "sweep_down": True,
            "bos_dir": 1, "bos_status": "active", "choch_status": "-",
            "fvg_state": "FVG", "ob_dir": "-",
        },
    }


def _incomplete_judas_po3() -> dict:
    return {
        "H4": {"trend": "BULLISH", "sweep_up": False, "sweep_down": False},
        "M15": {
            "trend": "BULLISH", "sweep_up": False, "sweep_down": True,
            "bos_dir": 0, "bos_status": "no", "choch_status": "-",
            "fvg_state": "-", "ob_dir": "-",
        },
    }


def _simulate_postprocess(raw_signals: list[dict], structure_fn) -> list[dict]:
    """Replica el loop de post-proceso (anota, NO filtra) que hará el principal.

    Recibe señales crudas de run_sequence y les pega `po3_complete` usando
    compute_po3_complete. NO descarta ninguna señal (mismo len de entrada).
    """
    out = []
    for s in raw_signals:
        cfg = Po3MotorConfig(bias="BULLISH", exec_tf="M15", htf="H4")
        s = dict(s)
        s["po3_complete"] = compute_po3_complete(structure_fn(s), config=cfg)
        out.append(s)
    return out


if __name__ == "__main__":
    # 1) Función pura: los tres veredictos del contrato.
    cfg = Po3MotorConfig(bias="BULLISH")
    assert compute_po3_complete(_complete_bullish_po3(), config=cfg) is True
    assert compute_po3_complete(_incomplete_judas_po3(), config=cfg) is False
    assert compute_po3_complete(None) is None
    assert compute_po3_complete({}) is None
    print("[1] compute_po3_complete: True / False / None OK")

    # 2) Post-proceso sobre un lote de señales crudas: conteo IDÉNTICO.
    #    Señales 0,2,4 tienen PO3 completo; 1,3 incompleto. Ninguna se borra.
    raw = [{"id": i, "entry_at": i} for i in range(5)]
    structures = [
        _complete_bullish_po3(),   # 0 -> True
        _incomplete_judas_po3(),   # 1 -> False
        _complete_bullish_po3(),   # 2 -> True
        _incomplete_judas_po3(),   # 3 -> False
        _complete_bullish_po3(),   # 4 -> True
    ]

    annotated = _simulate_postprocess(raw, lambda s: structures[s["id"]])

    # Brecha D: el conteo NO cambia.
    assert len(annotated) == len(raw), "BRECHA D VIOLADA: cambió el conteo de señales"
    flags = [a["po3_complete"] for a in annotated]
    assert flags == [True, False, True, False, True], f"anotación incorrecta: {flags}"
    print(f"[2] conteo idéntico ({len(annotated)} señales) + anotación correcta: {flags}")

    # 3) Modo histórico (sin datos de estructura): None para todas, conteo intacto.
    raw_h = [{"id": i, "entry_at": i} for i in range(3)]
    annotated_h = _simulate_postprocess(raw_h, lambda s: None)
    assert len(annotated_h) == len(raw_h)
    assert all(a["po3_complete"] is None for a in annotated_h)
    print(f"[3] modo histórico (sin datos): {[a['po3_complete'] for a in annotated_h]} "
          "OK — comportamiento intacto")

    print("\nOK: Brecha E anota sin filtrar (conteo idéntico, veredicto PO3 correcto).")
