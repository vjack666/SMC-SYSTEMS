"""Cronologia del semaforo del dia (lee la caja negra, no recalcula).

Muestra los cambios de color del semaforo en orden cronologico: cada chip es
un ciclo (hora + color). Asi ves si el mercado se esta calentando o enfriando.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame

from app_observador.core.blackbox import BLACKBOX_DIR

_COLOR_BG = {
    "VERDE": "#1f9d55",
    "AMARILLO": "#c9a227",
    "ROJO": "#c0392b",
    "DESCCONOCIDO": "#555",
}


def _ciclos_hoy() -> list[dict]:
    """Lee eventos ciclo_completo de hoy desde la caja negra."""
    out: list[dict] = []
    log = BLACKBOX_DIR / "app.log"
    if not log.exists():
        return out
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        for ln in log.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            o = json.loads(ln)
            if o.get("event") != "ciclo_completo":
                continue
            ts = o.get("ts", "")
            if not ts.startswith(hoy):
                continue
            out.append({
                "ts": ts,
                "color": (o.get("data") or {}).get("color", "DESCCONOCIDO"),
                "bias": (o.get("data") or {}).get("bias", ""),
            })
    except Exception:
        return out
    return out


class CronoWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setSpacing(4)
        self.title = QLabel("SEMÁFORO HOY:")
        self.title.setStyleSheet("color:#aaa; font-size:11px; font-weight:bold;")
        layout.addWidget(self.title)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(3)
        layout.addLayout(self.chips)
        layout.addStretch()
        self.setMaximumHeight(34)

    def update_state(self) -> None:
        # limpia chips viejos
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        ciclos = _ciclos_hoy()
        if not ciclos:
            vacio = QLabel("sin ciclos hoy")
            vacio.setStyleSheet("color:#777; font-size:11px;")
            self.chips.addWidget(vacio)
            return
        for c in ciclos[-12:]:  # ultimos 12 ciclos
            chip = QLabel(f" {c['ts'][11:16]} ")
            bg = _COLOR_BG.get(c["color"], "#555")
            chip.setStyleSheet(
                f"background:{bg}; color:#fff; border-radius:4px; "
                f"font-size:10px; padding:2px 4px;")
            chip.setToolTip(f"{c['ts']} | {c['color']} | {c['bias']}")
            self.chips.addWidget(chip)
