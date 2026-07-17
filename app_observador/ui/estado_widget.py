"""Estado operativo: loop (siempre ON), vigilante (toggle), cuenta MT5.

Design (cognitive-first):
  - Recognition over recall: big ON/OFF, color = state
  - One control per job: vigilante is a button, not a passive label
  - Loop is default-on infrastructure (auto-ensure), not a toy switch
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
)

from app_observador.config import SYMBOL
from app_observador.core.mt5_status import account_snapshot
from app_observador.core.process_control import (
    LOOP_SCRIPT,
    VIGILANTE_SCRIPT,
    ensure_loop_running,
    is_script_running,
    probe_scripts,
    start_script,
    stop_script,
)
from app_observador.core.blackbox import log_event, log_error
from app_observador.ui.theme import GREEN, GREEN_SOFT, RED, RED_SOFT, TEXT_DIM, BORDER, BG_RAISED


def _btn_on_style() -> str:
    return (
        f"QPushButton {{ background-color: {GREEN_SOFT}; color: #e8ffe8; "
        f"font-weight: 700; border: 1px solid {GREEN}; border-radius: 6px; "
        f"padding: 6px 12px; min-height: 28px; }}"
        f"QPushButton:hover {{ background-color: #2a6b3c; }}"
        f"QPushButton:disabled {{ color: #888; background: #222; border-color: #333; }}"
    )


def _btn_off_style() -> str:
    return (
        f"QPushButton {{ background-color: {RED_SOFT}; color: #ffe8e8; "
        f"font-weight: 700; border: 1px solid {RED}; border-radius: 6px; "
        f"padding: 6px 12px; min-height: 28px; }}"
        f"QPushButton:hover {{ background-color: #7a3535; }}"
        f"QPushButton:disabled {{ color: #888; background: #222; border-color: #333; }}"
    )


def _btn_idle_style() -> str:
    return (
        f"QPushButton {{ background-color: {BG_RAISED}; color: #e6e6e6; "
        f"font-weight: 700; border: 1px solid {BORDER}; border-radius: 6px; "
        f"padding: 6px 12px; min-height: 28px; }}"
        f"QPushButton:hover {{ background-color: #252a34; }}"
    )


class EstadoWidget(QWidget):
    """Panel ESTADO with functional process controls."""

    status_changed = Signal()  # optional hook for main window

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.title = QLabel("ESTADO")
        self.title.setStyleSheet(f"color: {TEXT_DIM}; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.title)

        # --- Loop (always on by default) ---
        loop_row = QHBoxLayout()
        loop_row.setSpacing(8)
        self.loop_lbl = QLabel("Loop observador")
        self.loop_lbl.setStyleSheet("color: #ccc; font-size: 12px;")
        loop_row.addWidget(self.loop_lbl, 1)
        self.btn_loop = QPushButton("Loop · —")
        self.btn_loop.setToolTip(
            "Loop de análisis 24/7 (actualiza datos / ficha / semáforo).\n"
            "Por defecto siempre ON. Si se apagó, este botón lo re-enciende."
        )
        self.btn_loop.clicked.connect(self._on_loop_click)
        loop_row.addWidget(self.btn_loop)
        layout.addLayout(loop_row)

        # --- Vigilante toggle ---
        vig_row = QHBoxLayout()
        vig_row.setSpacing(8)
        self.vig_lbl = QLabel("Vigilante de riesgo")
        self.vig_lbl.setStyleSheet("color: #ccc; font-size: 12px;")
        vig_row.addWidget(self.vig_lbl, 1)
        self.btn_vig = QPushButton("Vigilante · —")
        self.btn_vig.setToolTip(
            "Kill-switch: SOLO CIERRA posiciones si la pérdida flotante toca 2%/4%.\n"
            "NUNCA abre órdenes. Click = activar / desactivar."
        )
        self.btn_vig.clicked.connect(self._on_vig_click)
        vig_row.addWidget(self.btn_vig)
        layout.addLayout(vig_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(line)

        self.acct_lbl = QLabel("Cuenta: —")
        self.risk_lbl = QLabel("Riesgo día: —")
        self.hint = QLabel("Loop se mantiene ON · Vigilante es opt-in con botón")
        self.hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        self.hint.setWordWrap(True)
        for w in (self.acct_lbl, self.risk_lbl):
            w.setStyleSheet("color: #ccc; font-size: 11px;")
            layout.addWidget(w)
        layout.addWidget(self.hint)
        layout.addStretch()

        # Refresh process state without full engine cycle (slow CIM scan is cached)
        self._poll = QTimer(self)
        self._poll.setInterval(15_000)
        self._poll.timeout.connect(self.update_state)
        self._poll.start()

        # First paint + ensure loop (deferred so first paint is instant)
        QTimer.singleShot(50, self.update_state)
        QTimer.singleShot(600, self._bootstrap)

    def _bootstrap(self) -> None:
        """On open: loop always on; paint buttons."""
        try:
            res = ensure_loop_running()
            log_event(
                "estado",
                "ensure_loop",
                data={"ok": res.ok, "msg": res.message, "running": res.running},
            )
        except Exception as e:
            log_error("estado", "ensure_loop", e)
        self.update_state()

    def update_state(self) -> None:
        if self._busy:
            return
        # One batched probe (cache) instead of 2× PowerShell
        st = probe_scripts([LOOP_SCRIPT, VIGILANTE_SCRIPT])
        loop_on = bool(st.get(LOOP_SCRIPT))
        vig_on = bool(st.get(VIGILANTE_SCRIPT))

        # Loop: always preferred ON — if off, button invites re-enable
        if loop_on:
            self.btn_loop.setText("Loop · ON")
            self.btn_loop.setStyleSheet(_btn_on_style())
            self.btn_loop.setEnabled(False)  # already on; no accidental stop
            self.loop_lbl.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 600;")
        else:
            self.btn_loop.setText("Encender loop")
            self.btn_loop.setStyleSheet(_btn_idle_style())
            self.btn_loop.setEnabled(True)
            self.loop_lbl.setStyleSheet("color: #c9a227; font-size: 12px; font-weight: 600;")

        # Vigilante: real toggle
        if vig_on:
            self.btn_vig.setText("Vigilante · ON  (click OFF)")
            self.btn_vig.setStyleSheet(_btn_on_style())
            self.vig_lbl.setStyleSheet(f"color: {GREEN}; font-size: 12px; font-weight: 600;")
        else:
            self.btn_vig.setText("Vigilante · OFF  (click ON)")
            self.btn_vig.setStyleSheet(_btn_off_style())
            self.vig_lbl.setStyleSheet("color: #888; font-size: 12px;")

        snap = account_snapshot()
        if snap["conectado"]:
            self.acct_lbl.setText(
                f"Cuenta {snap['login']} | {SYMBOL} | bal {snap['balance']:.2f}"
            )
            self.acct_lbl.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
            riesgo = snap["riesgo_dia_pct"] or 0.0
            color = "#c0392b" if riesgo >= 2.0 else ("#c9a227" if riesgo >= 1.0 else GREEN)
            self.risk_lbl.setText(f"Riesgo día: {riesgo:.2f}% (DLL 4%)")
            self.risk_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        else:
            self.acct_lbl.setText("Cuenta MT5: DESCONECTADA (abrí el terminal)")
            self.acct_lbl.setStyleSheet("color: #888; font-size: 12px;")
            self.risk_lbl.setText("Riesgo día: —")
            self.risk_lbl.setStyleSheet("color: #888; font-size: 12px;")

    def _on_loop_click(self) -> None:
        """Only used when loop is OFF — turn it back on."""
        if self._busy:
            return
        self._busy = True
        self.btn_loop.setEnabled(False)
        self.btn_loop.setText("Encendiendo…")
        try:
            res = ensure_loop_running()
            log_event("estado", "loop_start", data={"ok": res.ok, "msg": res.message})
            if not res.ok:
                QMessageBox.warning(self, "Loop observador", res.message)
        except Exception as e:
            log_error("estado", "loop_start", e)
            QMessageBox.warning(self, "Loop observador", str(e))
        finally:
            self._busy = False
            self.update_state()
            self.status_changed.emit()

    def _on_vig_click(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_vig.setEnabled(False)
        was_on = is_script_running(VIGILANTE_SCRIPT)
        self.btn_vig.setText("Apagando…" if was_on else "Encendiendo…")
        try:
            if was_on:
                res = stop_script(VIGILANTE_SCRIPT)
                log_event("estado", "vigilante_stop", data={"ok": res.ok, "msg": res.message})
            else:
                # Confirm before enabling kill-switch that closes positions
                box = QMessageBox(self)
                box.setWindowTitle("Activar vigilante de riesgo")
                box.setIcon(QMessageBox.Icon.Warning)
                box.setText(
                    "El vigilante SOLO CIERRA posiciones (nunca abre).\n\n"
                    "Si la pérdida flotante del día toca ~2% (suave) / 4% (duro),\n"
                    "cierra TODAS las posiciones abiertas en MT5.\n\n"
                    "¿Activarlo ahora?"
                )
                box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if box.exec() != QMessageBox.StandardButton.Yes:
                    self._busy = False
                    self.btn_vig.setEnabled(True)
                    self.update_state()
                    return
                res = start_script(VIGILANTE_SCRIPT)
                log_event("estado", "vigilante_start", data={"ok": res.ok, "msg": res.message})
            if not res.ok:
                QMessageBox.warning(self, "Vigilante de riesgo", res.message)
        except Exception as e:
            log_error("estado", "vigilante_toggle", e)
            QMessageBox.warning(self, "Vigilante de riesgo", str(e))
        finally:
            self._busy = False
            self.btn_vig.setEnabled(True)
            self.update_state()
            self.status_changed.emit()
