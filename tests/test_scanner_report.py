"""Unit tests for observador scanner report (no MT5, no UI)."""
from __future__ import annotations

from app_observador.core.scanner_report import build_scanner_report


def test_build_scanner_report_empty():
    text = build_scanner_report(None)
    assert "ESCÁNER" in text
    assert "Sin datos" in text


def test_build_scanner_report_short_plan():
    result = {
        "bias": "SHORT",
        "semaforo": {"color": "AMARILLO", "reasons": ["R:R bajo"]},
        "veredicto": {
            "bias": "SHORT",
            "votes": {"LONG": 1, "SHORT": 3},
            "zone_note": "Zona de venta (OTE M15): 1.14633 - 1.14658",
            "invalidation": 1.14747,
            "target": 1.14603,
        },
        "estructura": {
            "D1": {"trend": "BEARISH", "sweep_up": False, "sweep_down": False},
            "H4": {"trend": "RANGING", "fvg_state": "bullish_unfilled", "ob_dir": "bullish"},
            "M15": {
                "trend": "BULLISH",
                "bos_dir": -1,
                "bos_status": "active",
                "bos_level": 1.14672,
                "sweep_up": True,
                "sweep_down": False,
                "ote_long": [1.14692, 1.14716],
                "ote_short": [1.14633, 1.14658],
                "ob_dir": "bullish",
                "fvg_state": "bearish_unfilled",
                "choch_status": "active",
            },
        },
        "wyckoff": {"M15": {"phase_es": "MARKDOWN (bajada)", "bias": "BEARISH"}},
        "errores": [],
    }
    text = build_scanner_report(result, symbol="EURUSD")
    assert "SHORT" in text
    assert "1.14645" in text or "1.1464" in text
    assert "1.14747" in text
    assert "1.14603" in text
    assert "R:R" in text
    assert "NO abre órdenes" in text
    assert "Silver Bullet" in text or "Turtle" in text or "PO3" in text or "Unicorn" in text
