"""RED -> Brecha B (Opción 2): anclar POI HTF SIN tocar run_sequence.

Principio Brecha D: el ancla se ANOTA en ICTSignal, NO filtra señales.
El conteo de señales debe ser IDÉNTICO con/sin POI HTF padre.

Este test es UNITARIO y AISLADO: mock de HtfPdIndex.zones_at, sin datos reales.
"""
import unittest
from unittest.mock import MagicMock

import pandas as pd

from ict_backtest.htf_pd_index import HtfPdZone
from ict_backtest.poi_anchor_motor import compute_htf_anchored


def _make_ltf_map(n: int) -> dict:
    """ltf_map dummy de n filas (las columnas act_* no importan: las mockeamos)."""
    return {"H4": pd.DataFrame(index=range(n))}


def _sig_dir() -> int:
    return 1  # long


class TestComputeHtfAnchored(unittest.TestCase):
    def test_anchored_when_htf_poi_present(self):
        """Si el HTF tiene POI en la dirección de la señal -> anclada True."""
        idx = MagicMock()
        idx.timeframes = ["H4"]
        # zones_at devuelve una zona bullish (direction=1) en la vela entry
        idx.zones_at.return_value = [
            HtfPdZone(tf="H4", pd_type="FVG", pd_tier="T2",
                      direction=1, zone_high=1.1, zone_low=1.0)
        ]
        ltf_map = _make_ltf_map(10)
        result = compute_htf_anchored(
            sig_dir=_sig_dir(), entry_at=5, htf_pd_index=idx, ltf_map=ltf_map
        )
        self.assertTrue(result)
        # verifica que consultó exactamente la vela entry y el tf H4
        idx.zones_at.assert_called_with(5, "H4", ltf_map)

    def test_not_anchored_when_no_htf_poi(self):
        """Si el HTF NO tiene POI en la dirección -> anclada False (señal SIGUE saliendo)."""
        idx = MagicMock()
        idx.zones_at.return_value = []  # sin POI HTF padre
        ltf_map = _make_ltf_map(10)
        result = compute_htf_anchored(
            sig_dir=_sig_dir(), entry_at=5,
            htf_pd_index=idx, ltf_map=ltf_map
        )
        self.assertFalse(result)

    def test_none_when_no_index(self):
        """Sin htf_pd_index (modo histórico) -> None, comportamiento intacto."""
        result = compute_htf_anchored(
            sig_dir=_sig_dir(), entry_at=5,
            htf_pd_index=None, ltf_map=None
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
