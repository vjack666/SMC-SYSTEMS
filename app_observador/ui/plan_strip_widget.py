"""Decision-first strip: one compact semáforo + plan numbers.

Space-saving: single color chip (not a second big SemaforoWidget).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame

from app_observador.ui.theme import BG_PANEL, BORDER, TEXT, TEXT_DIM, TEXT_MUTED, ACCENT, GREEN, YELLOW, RED, RED_SOFT, GREEN_SOFT
from app_observador.ui.format_helpers import format_canonical, canonical_is_ready


_COLOR_MAP = {
    "VERDE": GREEN,
    "AMARILLO": YELLOW,
    "ROJO": RED,
}


def _fmt(x) -> str:
    try:
        return f"{float(x):.5f}"
    except Exception:
        return "—"


class PlanStripWidget(QWidget):
    """Compact always-visible strip: chip + side + levels + action."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("planStrip")
        self.setStyleSheet(
            f"#planStrip {{ background: {BG_PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; }}"
        )
        self.setMaximumHeight(72)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(10)

        # Compact semáforo chip (ONLY place color is shown large)
        self.chip = QLabel("—")
        self.chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip.setFixedSize(88, 36)
        self.chip.setStyleSheet(
            "background: #444; color: white; font-size: 12px; font-weight: 800; "
            "border-radius: 6px;"
        )
        self.chip.setToolTip("Semáforo FundedNext")
        root.addWidget(self.chip)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color: {BORDER};")
        root.addWidget(div)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        row_top = QHBoxLayout()
        row_top.setSpacing(12)
        self.side_lbl = QLabel("Esperando…")
        self.side_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 800;")
        row_top.addWidget(self.side_lbl)
        self.entry_lbl = QLabel("E —")
        self.sl_lbl = QLabel("SL —")
        self.tp_lbl = QLabel("TP —")
        self.rr_lbl = QLabel("R:R —")
        for w in (self.entry_lbl, self.sl_lbl, self.tp_lbl, self.rr_lbl):
            w.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; "
                f"font-family: Consolas, 'Cascadia Mono', monospace;"
            )
            row_top.addWidget(w)
        row_top.addStretch()
        mid.addLayout(row_top)

        self.hint_lbl = QLabel("Semáforo + plan (una sola franja)")
        self.hint_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        self.hint_lbl.setWordWrap(True)
        mid.addWidget(self.hint_lbl)
        root.addLayout(mid, 1)

        self.action_lbl = QLabel("—")
        self.action_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.action_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: 700;")
        self.action_lbl.setMaximumWidth(160)
        self.action_lbl.setWordWrap(True)
        root.addWidget(self.action_lbl)

    def update_state(self, result: dict | None) -> None:
        if not result:
            self.chip.setText("—")
            self.chip.setStyleSheet(
                "background: #444; color: white; font-size: 12px; font-weight: 800; border-radius: 6px;"
            )
            self.chip.setToolTip("Sin datos")
            self.side_lbl.setText("Esperando…")
            self.entry_lbl.setText("E —")
            self.sl_lbl.setText("SL —")
            self.tp_lbl.setText("TP —")
            self.rr_lbl.setText("R:R —")
            self.hint_lbl.setText("Actualizá el ciclo")
            self.action_lbl.setText("—")
            return

        color = (result.get("semaforo") or {}).get("color", "DESCCONOCIDO")
        reasons = (result.get("semaforo") or {}).get("reasons") or []
        bg = _COLOR_MAP.get(color, "#555")
        label = color if color in _COLOR_MAP else "N/D"
        self.chip.setText(label)
        self.chip.setStyleSheet(
            f"background: {bg}; color: white; font-size: 12px; font-weight: 800; border-radius: 6px;"
        )
        tip = f"Semáforo: {label}"
        if reasons:
            tip += "\n" + "\n".join(str(r) for r in reasons[:4])
        self.chip.setToolTip(tip)

        raw_can = result.get("canonical")
        can = raw_can if isinstance(raw_can, dict) else None
        verd = result.get("veredicto") or {}

        if can and can.get("entry") is not None:
            side = str(can.get("side") or "—")
            entry, sl, tp = can.get("entry"), can.get("sl"), can.get("tp")
            rr = float(can.get("rr") or 0.0)
            self.side_lbl.setText(side)
            self.side_lbl.setStyleSheet(
                f"color: {'#9fd3a0' if side == 'LONG' else '#ff8a80'}; "
                f"font-size: 14px; font-weight: 800;"
            )
            self.entry_lbl.setText(f"E {_fmt(entry)}")
            self.sl_lbl.setText(f"SL {_fmt(sl)}")
            self.tp_lbl.setText(f"TP {_fmt(tp)}")
            rr_color = GREEN if rr >= 2.0 else (YELLOW if rr >= 1.0 else RED)
            self.rr_lbl.setText(f"R:R 1:{rr:.2f}")
            self.rr_lbl.setStyleSheet(
                f"color: {rr_color}; font-size: 12px; font-weight: 700; "
                f"font-family: Consolas, 'Cascadia Mono', monospace;"
            )
            reason0 = str(reasons[0])[:90] if reasons else ""
            # FASE D: umbral Stellar (RR >= 1:2 = rr >= 2.0). Bajo 2.0 = riesgo.
            if rr >= 2.0:
                self.setStyleSheet(f"QFrame#planStrip {{ border: none; }}")
                self.hint_lbl.setText(
                    f"sequence · {can.get('time', '')}" + (f" · {reason0}" if reason0 else "")
                )
            else:
                self.setStyleSheet(
                    f"QFrame#planStrip {{ border: 2px solid {RED}; "
                    f"background: {RED_SOFT}; }}"
                )
                self.hint_lbl.setText(
                    f"⚠ RR 1:{rr:.2f} < 1:2 (Stellar): riesgo alto" + (f" · {reason0}" if reason0 else "")
                )
            if color == "VERDE" and rr >= 2.0:
                self.action_lbl.setText("LIMIT listo")
            elif color == "ROJO":
                self.action_lbl.setText("No operar")
            elif rr < 2.0:
                self.action_lbl.setText("Revisar RR")
            else:
                self.action_lbl.setText("Esperar / demo")
            return

        # FASE 5 (UI): canonical NO es dict → mostrar los otros 2 estados honestos.
        # "EN CONSTRUCCIÓN" (str) = el canonical tardó/se colgó → chip gris.
        # None = corrió limpio pero no hay señal → "sin plan vigente".
        can_text, can_color = format_canonical(raw_can)
        bias = str(result.get("bias") or verd.get("bias") or "—")
        self.side_lbl.setText(can_text if raw_can == "EN CONSTRUCCIÓN" else bias[:28])
        self.side_lbl.setStyleSheet(f"color: {can_color}; font-size: 14px; font-weight: 800;")
        inv, tgt = verd.get("invalidation"), verd.get("target")
        self.entry_lbl.setText("E —")
        self.sl_lbl.setText(f"SL {_fmt(inv)}" if inv is not None else "SL —")
        self.tp_lbl.setText(f"TP {_fmt(tgt)}" if tgt is not None else "TP —")
        self.rr_lbl.setText("R:R —")
        self.rr_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        if raw_can == "EN CONSTRUCCIÓN":
            self.hint_lbl.setText("⏳ calculando plan… (canonical en construcción)")
            self.action_lbl.setText("Calculando…")
        else:
            reason0 = str(reasons[0])[:100] if reasons else can_text
            self.hint_lbl.setText(reason0)
            self.action_lbl.setText("Sin plan")
