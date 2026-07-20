"""RED -> Brecha C (Opción 2): clasificar zona (dealing range) SIN tocar run_sequence.

Principio Brecha D: la zona se ANOTA en ICTSignal, NO filtra señales.
El conteo de señales debe ser IDÉNTICO con/sin swing HTF padre.

Este test es UNITARIO y AISLADO: solo ejercita `compute_zone_class` (una funcion
PURA). No lee data/raw (radio de explosion minimo, pre-datos-reales).
"""
import unittest

from ict_backtest.dealing_range_motor import compute_zone_class


# Swing HTF de referencia para los casos (un rango limpio 1.0000 - 1.0200,
# EQ en 1.0100). long quiere discount (< EQ); short quiere premium (> EQ).
_SWING_HIGH = 1.0200
_SWING_LOW = 1.0000
_EQUITY = 1.0100


class TestComputeZoneClass(unittest.TestCase):
    def test_long_entry_in_discount(self):
        """Long con entrada en discount (< EQ) -> 'DISCOUNT'."""
        result = compute_zone_class(
            sig_dir=1, entry=1.0050,
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
        self.assertEqual(result, "DISCOUNT")

    def test_long_entry_in_premium(self):
        """Long con entrada en premium (> EQ) -> 'PREMIUM' (se anota, no filtra)."""
        result = compute_zone_class(
            sig_dir=1, entry=1.0150,
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
        self.assertEqual(result, "PREMIUM")

    def test_short_entry_in_premium(self):
        """Short con entrada en premium (> EQ) -> 'PREMIUM'."""
        result = compute_zone_class(
            sig_dir=-1, entry=1.0150,
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
        self.assertEqual(result, "PREMIUM")

    def test_short_entry_in_discount(self):
        """Short con entrada en discount (< EQ) -> 'DISCOUNT' (se anota, no filtra)."""
        result = compute_zone_class(
            sig_dir=-1, entry=1.0050,
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
        self.assertEqual(result, "DISCOUNT")

    def test_entry_at_eq_is_ambiguous(self):
        """Entrada justo en EQ (banda ambigua) -> 'EQ'."""
        result = compute_zone_class(
            sig_dir=1, entry=_EQUITY,
            swing_high_htf=_SWING_HIGH, swing_low_htf=_SWING_LOW,
        )
        self.assertEqual(result, "EQ")

    def test_none_when_no_swing(self):
        """Sin swing HTF (modo historico, swing=None) -> None, intacto."""
        result = compute_zone_class(
            sig_dir=1, entry=1.0050,
            swing_high_htf=None, swing_low_htf=None,
        )
        self.assertIsNone(result)

    def test_none_when_partial_swing(self):
        """Swing incompleto (solo uno None) -> None, intacto (no rompe)."""
        result = compute_zone_class(
            sig_dir=1, entry=1.0050,
            swing_high_htf=_SWING_HIGH, swing_low_htf=None,
        )
        self.assertIsNone(result)

    def test_none_when_invalid_swing(self):
        """Swing invalido (high <= low) -> None en lugar de explotar."""
        result = compute_zone_class(
            sig_dir=1, entry=1.0050,
            swing_high_htf=1.0000, swing_low_htf=1.0000,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
