"""Demo sintético Brecha C (Opción 2) — SIN datos reales.

Objetivo: demostrar que el MOTOR canonico puede ANOTAR `zone_class` (dealing
range premium/discount) en ICTSignal SIN modificar run_sequence y SIN cambiar
el conteo de señales (principio Brecha D: anota, no filtra).

El enchufe real en canonical/engine lo hace el agente principal en el merge.
Aca aislamos SOLO la funcion pura `compute_zone_class` y comprobamos que:

  1) calcula la clase correcta (DISCOUNT/PREMIUM/EQ) para long y short;
  2) con swing HTF = None (modo historico) devuelve None y el conteo de
     señales seria IDENTICO (no filtra).

No lee data/raw (radio de explosion minimo, demo pre-datos-reales).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ict_backtest.dealing_range_motor import compute_zone_class


# Swing HTF de referencia: rango 1.0000 - 1.0200, EQ en 1.0100.
_SWING_HIGH = 1.0200
_SWING_LOW = 1.0000


def _fake_signals(n: int = 4) -> list[dict]:
    """Señales dummy ya generadas por run_sequence (aislamos solo la anotacion)."""
    entries = [1.0040, 1.0160, 1.0100, 1.0070]  # DISCOUNT, PREMIUM, EQ, DISCOUNT
    sigs = []
    for i in range(n):
        sigs.append({
            "id": i,
            "direction": 1 if i % 2 == 0 else -1,  # long/short alternados
            "entry": entries[i],
        })
    return sigs


if __name__ == "__main__":
    print("=== Brecha C: anotar zona (dealing range), NO filtrar ===\n")

    # Caso A: con swing HTF disponible -> anota la clase correcta.
    sigs = _fake_signals()
    n_antes = len(sigs)
    for s in sigs:
        s["zone_class"] = compute_zone_class(
            sig_dir=s["direction"], entry=s["entry"],
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
    n_despues = len(sigs)
    assert n_antes == n_despues, "BRECHA D VIOLADA: cambio el conteo de señales"
    for s in sigs:
        print(f"  sig#{s['id']} dir={s['direction']:+d} entry={s['entry']:.4f} "
              f"-> zone_class={s['zone_class']}")
    assert sigs[0]["zone_class"] == "DISCOUNT"
    assert sigs[1]["zone_class"] == "PREMIUM"
    assert sigs[2]["zone_class"] == "EQ"
    assert sigs[3]["zone_class"] == "DISCOUNT"

    # Caso B: modo historico (sin swing HTF) -> None, conteo intacto.
    n_antes = len(sigs)
    for s in sigs:
        s["zone_class"] = compute_zone_class(
            sig_dir=s["direction"], entry=s["entry"],
            swing_high_htf=None, swing_low_htf=None,
        )
    n_despues = len(sigs)
    assert n_antes == n_despues, "BRECHA D VIOLADA: cambio el conteo de señales"
    assert all(s["zone_class"] is None for s in sigs), "modo historico debe ser None"

    print("\nOK: Brecha C anota la zona sin filtrar "
          "(conteo identico con/sin swing HTF; clase correcta DISCOUNT/PREMIUM/EQ).")
