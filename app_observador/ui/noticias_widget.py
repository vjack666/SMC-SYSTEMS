"""Noticias rojas del dia + resumen de estructura del mercado (datos reales).

El resumen de estructura se genera desde result['estructura'] (lo que devuelve
el motor con analyze_timeframe real: BOS, barrido de liquidez, OTE, Wyckoff).
Se actualiza solo en cada ciclo (cuando el mercado cambia de verdad).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QFrame


def resumen_estructura(estructura: dict) -> str:
    """Texto en criollo desde los datos reales de cada temporalidad."""
    if not estructura:
        return "Sin datos de estructura (MT5 no disponible)."

    def linea(tf: str) -> str:
        d = estructura.get(tf, {})
        if not d:
            return f"{tf}: sin datos"
        trend = {"" : "indefinido", "BULLISH": "alcista", "BEARISH": "bajista",
                 "RANGING": "en rango"}.get(d.get("trend", ""), d.get("trend", ""))
        bos_dir = d.get("bos_dir", 0)
        bos_status = d.get("bos_status", "")
        if bos_dir == 1 and bos_status == "active":
            bos = "BOS alcista (rompio estructura arriba)"
        elif bos_dir == -1 and bos_status == "active":
            bos = "BOS bajista (rompio estructura abajo)"
        elif bos_dir == 1:
            bos = "intenta BOS alcista (aun no confirma)"
        elif bos_dir == -1:
            bos = "intenta BOS bajista (aun no confirma)"
        else:
            bos = "estructura intacta"
        partes = [f"{tf}: {trend}, {bos}"]
        if d.get("sweep_up"):
            partes.append("barrio liquidez arriba (sweep buy)")
        if d.get("sweep_down"):
            partes.append("barrio liquidez abajo (sweep sell)")
        return "; ".join(partes) + "."

    wyk = estructura.get("WYCKOFF_M15", {})
    wyk_txt = ""
    if wyk:
        fase = wyk.get("phase_es", "")
        sesgo = wyk.get("bias", "")
        if fase or sesgo:
            wyk_txt = f"\nWyckoff M15: {fase} ({sesgo})".strip()
    return "\n".join([linea("D1"), linea("H4"), linea("M15")]) + wyk_txt


class NoticiasWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title = QLabel("NOTICIAS ROJAS HOY")
        self.title.setStyleSheet("color: #aaa; font-weight: bold;")
        layout.addWidget(self.title)

        self.fuente = QLabel("")
        self.fuente.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.fuente)

        self.list = QListWidget()
        self.list.setStyleSheet("background-color: #1e1e1e; color: #eee;")
        layout.addWidget(self.list, 2)

        # Separador + resumen de estructura
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        self.struct_title = QLabel("ESTRUCTURA DEL MERCADO")
        self.struct_title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.struct_title)

        self.struct_lbl = QLabel("calculando...")
        self.struct_lbl.setStyleSheet("color: #ddd; font-size: 12px;")
        self.struct_lbl.setWordWrap(True)
        layout.addWidget(self.struct_lbl, 1)

    def update_state(self, events: list[dict], fuente: str = "", estructura: dict | None = None) -> None:
        self.list.clear()
        self.fuente.setText(f"Fuente: {fuente}")
        if not events:
            self.list.addItem("Sin noticias rojas en ventana")
        else:
            for e in events:
                txt = f"{e.get('currency','')} {e.get('event','')} {e.get('time_utc','')} UTC"
                self.list.addItem(txt)
        if estructura is not None:
            self.struct_lbl.setText(resumen_estructura(estructura))
