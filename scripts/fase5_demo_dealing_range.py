"""Fase 5 Brecha C — Demo sintetica: dealing range premium/discount.

Muestra que una zona se clasifica segun el swing HTF y si favorece la
direccion del setup. NO toca produccion.
Correr: python scripts/fase5_demo_dealing_range.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.dealing_range import classify_zone, zone_ok_for_direction


def main():
    print("=== Demo Brecha C: dealing range (sintetico) ===\n")
    swing_high, swing_low = 1.1100, 1.1000
    eq = (swing_high + swing_low) / 2
    print(f"Swing HTF: {swing_low} - {swing_high} | EQ = {eq:.4f}\n")

    casos = [
        ("Zona discount (long ok)", 1.1030, 1.1020, 1),
        ("Zona premium (short ok)", 1.1080, 1.1070, -1),
        ("Zona EQ (ambigua)", 1.1052, 1.1048, 1),
        ("Zona premium pero long (wrong-side)", 1.1080, 1.1070, 1),
    ]
    for nombre, zh, zl, direccion in casos:
        cls = classify_zone(zh, zl, swing_high, swing_low)
        ok = zone_ok_for_direction(cls, direccion)
        print(f"  {nombre:38} {cls:9} dir={direccion:+d} -> "
              f"{'OK' if ok else 'no-bonifica'}")

    print("\nRegla: discount favorece long; premium favorece short; EQ ambiguo.")
    print("Es BONUS (marca la zona), no filtro duro: no descarta la senal.")


if __name__ == "__main__":
    main()
