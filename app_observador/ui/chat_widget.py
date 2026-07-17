"""Pestaña CHAT — conversá con Hermes o el modelo que elijas.

El contexto de la app (ficha + ciclo + noticias) se inyecta SOLO, sin que el
usuario tenga que generar ni adjuntar nada a mano.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QCheckBox, QTextBrowser, QMessageBox,
)

from app_observador.core.chat_client import (
    chat_completion,
    list_chat_models,
    resolve_chat_config,
    status_line,
)
from app_observador.core.chat_context import build_chat_context
from app_observador.ui.theme import btn_ghost


class _ChatInput(QPlainTextEdit):
    """Enter = send; Ctrl+Enter (or Shift+Enter) = newline."""

    submit = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = event.modifiers()
            # Ctrl+Enter or Shift+Enter → newline without send
            if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                super().keyPressEvent(event)
                return
            # Plain Enter → send
            self.submit.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _ChatWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        messages: list[dict[str, str]],
        model_id: str,
        provider_tag: str = "hermes",
    ) -> None:
        super().__init__()
        self._messages = messages
        self._model_id = model_id
        self._provider_tag = provider_tag

    def run(self) -> None:
        try:
            text = chat_completion(
                self._messages,
                model_id=self._model_id,
                provider_tag=self._provider_tag,
            )
            self.finished.emit(text)
        except Exception as e:
            self.failed.emit(str(e))


class ChatWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._history: list[dict[str, str]] = []  # user/assistant only
        self._scanner_provider = None  # callable -> str (optional legacy)
        self._context_provider = None  # callable -> str full app context
        self._worker: _ChatWorker | None = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        title = QLabel("CHAT CON EL MODELO")
        title.setStyleSheet("color: #c9a3ff; font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        top = QHBoxLayout()
        top.addWidget(QLabel("Modelo:"))
        self.combo = QComboBox()
        for label, model_id, _sys, prov in list_chat_models():
            self.combo.addItem(label, (model_id, _sys, prov))
        self.combo.setMinimumWidth(280)
        top.addWidget(self.combo)

        self.chk_scanner = QCheckBox("Incluir contexto de la app")
        self.chk_scanner.setChecked(True)
        self.chk_scanner.setToolTip(
            "Siempre ON por defecto: manda ficha + ciclo del motor + noticias "
            "sin que tengas que generar nada en Escáner."
        )
        top.addWidget(self.chk_scanner)

        self.btn_clear = QPushButton("Limpiar chat")
        self.btn_clear.setStyleSheet(btn_ghost())
        self.btn_clear.clicked.connect(self._clear)
        top.addWidget(self.btn_clear)
        top.addStretch()
        root.addLayout(top)

        self.key_status = QLabel("")
        self.key_status.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        root.addWidget(self.key_status)
        self._refresh_key_status()

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setPlaceholderText("La conversación aparece acá…")
        root.addWidget(self.view, 1)

        self.input = _ChatInput()
        self.input.setPlaceholderText(
            "Escribí acá…  Enter = enviar  ·  Ctrl+Enter = nueva línea"
        )
        self.input.setMaximumHeight(100)
        self.input.submit.connect(self._on_send)
        root.addWidget(self.input)

        hint = QLabel("Enter envía · Ctrl+Enter (o Shift+Enter) baja de línea")
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        root.addWidget(hint)

    def set_scanner_provider(self, fn) -> None:
        """fn() -> str with latest scanner report text (may be empty)."""
        self._scanner_provider = fn

    def set_context_provider(self, fn) -> None:
        """fn() -> str full auto context (ficha + structure + news). Preferred."""
        self._context_provider = fn

    def _refresh_key_status(self) -> None:
        try:
            self.key_status.setText(status_line())
        except Exception as e:
            self.key_status.setText(f"Status error: {e}")

    def _selected(self) -> tuple[str, str, str, str]:
        data = self.combo.currentData()
        label = self.combo.currentText()
        if not data:
            return label, "tencent/hy3:free", "", "hermes"
        if len(data) == 3:
            model_id, system, prov = data
        else:
            model_id, system = data[0], data[1]
            prov = "hermes"
        return label, model_id, system, prov

    def _append_view(self, who: str, text: str) -> None:
        color = {
            "vos": "#7fb3ff",
            "modelo": "#9fd3a0",
            "sistema": "#888",
        }.get(who, "#e6e6e6")
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        self.view.append(
            f"<p style='margin:6px 0;'><b style='color:{color};'>{who.upper()}</b><br>"
            f"<span style='color:#e6e6e6;'>{safe}</span></p>"
        )

    def _clear(self) -> None:
        self._history.clear()
        self.view.clear()
        self._append_view("sistema", "Chat limpio. Elegí modelo y mandá un mensaje.")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.input.setEnabled(not busy)
        if busy:
            self.key_status.setText("Pensando… (Enter bloqueado hasta la respuesta)")
        else:
            self._refresh_key_status()

    def _on_send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self._busy or (self._worker and self._worker.isRunning()):
            return

        self._refresh_key_status()
        label, model_id, system, prov = self._selected()
        if resolve_chat_config(model_id, provider_tag=prov) is None:
            QMessageBox.warning(
                self,
                "Chat",
                "Sin credenciales para el modelo seleccionado.\n\n"
                "Hermes (Nous):\n"
                "  · Abrí Hermes Agent o corré `hermes auth` (OAuth Nous).\n"
                "  · Config leída de %LOCALAPPDATA%\\hermes\\config.yaml\n\n"
                "Fallback xAI:\n"
                "  · XAI_API_KEY en .env del proyecto",
            )
            return

        self.input.clear()
        self._append_view("vos", text)
        self._history.append({"role": "user", "content": text})

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        # Always inject live app context when enabled (default ON) — never nag the user.
        if self.chk_scanner.isChecked():
            ctx = ""
            try:
                if self._context_provider:
                    ctx = (self._context_provider() or "").strip()
                elif self._scanner_provider:
                    # Legacy: only scanner text → wrap with builder for news/instructions
                    card = (self._scanner_provider() or "").strip()
                    ctx = build_chat_context(None, scanner_text=card)
            except Exception as e:
                ctx = (
                    "Contexto de la app no disponible por error interno: "
                    f"{e}. Respondé igual sin inventar Entry/SL/TP."
                )
            if ctx:
                messages.append({"role": "system", "content": ctx})

        # Keep more turns so "repasalo" has continuity without losing thread
        messages.extend(self._history[-20:])

        # Nudge depth on follow-ups that ask to re-read
        low = text.lower()
        if any(
            k in low
            for k in (
                "repasa",
                "repaso",
                "profund",
                "detall",
                "explica",
                "por qué",
                "porque",
            )
        ):
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "El usuario pide PROFUNDIDAD. No repitas el resumen previo. "
                        "Subí de nivel: lógica ICT con estos niveles, invalidación, "
                        "escenarios A/B, pips risk/reward, decisión operativa ahora. "
                        "Calidad de modelo completo (Claude/GPT/Grok)."
                    ),
                }
            )

        self._set_busy(True)
        self._worker = _ChatWorker(messages, model_id, provider_tag=prov)
        self._worker.finished.connect(self._on_reply)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_reply(self, text: str) -> None:
        self._set_busy(False)
        self._history.append({"role": "assistant", "content": text})
        self._append_view("modelo", text)
        self.input.setFocus()

    def _on_fail(self, err: str) -> None:
        self._set_busy(False)
        # Drop last user turn on hard fail so they can retry cleanly
        if self._history and self._history[-1].get("role") == "user":
            self._history.pop()
        self._append_view("sistema", f"Error: {err}")
        QMessageBox.warning(self, "Chat", err)
        self.input.setFocus()
