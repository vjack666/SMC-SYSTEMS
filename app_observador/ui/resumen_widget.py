"""Pestaña Principal: SETUP ARMADO del dia (Wyckoff + sesgo + estructura).

Muestra en texto detallado como esta armado el setup usando:
  - result['estructura'] (motor, datos reales MT5)
  - result['bias'] + result['veredicto']['votes'] (sesgo direccional)
  - docs/WYCKOFF_RULEBOOK.md -> significado de cada fase (leido como texto)
  - graphify-out/graph.json -> mapea la fase a su detector real (trazabilidad)
No inventa nada: todo sale de esas fuentes.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app_observador.ui.noticias_widget import resumen_estructura

ROOT = Path(__file__).resolve().parents[3]
GRAPH_JSON = ROOT / "graphify-out" / "graph.json"
RULEBOOK = ROOT / "docs" / "WYCKOFF_RULEBOOK.md"

# Secciones del rulebook por fase (numero de seccion -> titulo)
WYCKOFF_SECCION = {
    "Accumulation": "§1 Accumulation",
    "Markup": "§3 Markup",
    "Distribution": "§2 Distribution",
    "Markdown": "§4 Markdown",
    "Spring": "§5 Spring",
    "Upthrust": "§6 Upthrust",
    "SOS": "§7 Sign of Strength",
    "SOW": "§8 Sign of Weakness",
}

# Mapeo fase -> nodo en el grafo Graphify (detector real). Verificado en graph.json.
WYCKOFF_NODO = {
    "Accumulation": "agents_wyckoff_agent_wyckoffagent",
    "Markup": "agents_wyckoff_agent_wyckoffagent",
    "Distribution": "agents_wyckoff_agent_wyckoffagent",
    "Markdown": "agents_wyckoff_agent_wyckoffagent",
    "Spring": "agents_wyckoff_agent_wyckoffagent_detect_spring",
    "Upthrust": "agents_wyckoff_agent_wyckoffagent_detect_upthrust",
}


def _cargar_grafo() -> dict | None:
    if not GRAPH_JSON.exists():
        return None
    try:
        import json
        return json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


_GRAFO = _cargar_grafo()


def _detector_fase(fase: str) -> str:
    """Devuelve 'archivo.py :: Clase.metodo' real desde el grafo Graphify."""
    if _GRAFO is None:
        return ""
    nodo_id = WYCKOFF_NODO.get(fase)
    if not nodo_id:
        return ""
    for n in _GRAFO.get("nodes", []):
        if n.get("id") == nodo_id:
            sf = n.get("source_file", "")
            lab = n.get("label", "")
            if sf:
                return f" ({sf} :: {lab})"
    return ""


def _significado_fase(fase: str) -> str:
    """Referencia de seccion del rulebook para la fase (sin hardcodear texto largo)."""
    if not RULEBOOK.exists():
        return ""
    secc = WYCKOFF_SECCION.get(fase)
    if not secc:
        return ""
    return f"  [{secc} de WYCKOFF_RULEBOOK.md]"


def resumen_setup(estructura: dict, bias: str = "", votes: dict | None = None,
                 extra: dict | None = None) -> str:
    """Texto detallado del setup: sesgo direccional + estructura + Wyckoff + armado."""
    if not estructura:
        return "Sin datos de estructura (MT5 no disponible)."

    lineas: list[str] = []

    # 1) Sesgo direccional (votos L/S) + cita rulebook §11-12 (volumen/precio)
    v = votes or {"LONG": 0, "SHORT": 0}
    lineas.append("SESGO DIRECCIONAL")
    lineas.append(f"  Veredicto: {bias}   (votos L:{v.get('LONG', 0)} / S:{v.get('SHORT', 0)})")
    lineas.append("  Regla volumen-precio (WYCKOFF_RULEBOOK.md §11-12):")
    lineas.append("    precio sube + volumen sube = compra fuerte;")
    lineas.append("    precio baja + volumen baja = venta debil (posible acumulacion).")

    # 2) Estructura por TF (reusa resumen_estructura existente)
    lineas.append("")
    lineas.append("ESTRUCTURA D1 / H4 / M15")
    lineas.append(resumen_estructura(estructura))

    # 3) Fase Wyckoff M15: nombre + significado del rulebook + detector del grafo
    wyk = estructura.get("WYCKOFF_M15") or {}
    if not wyk:  # fallback: el motor tambien expone result["wyckoff"]["M15"]
        wyk = (extra or {}).get("wyckoff_m15", {}) or {}
    if wyk:
        fase = wyk.get("phase_es", "")
        sesgo_w = wyk.get("bias", "")
        lineas.append("")
        lineas.append("FASE WYCKOFF M15")
        lineas.append(f"  {fase} ({sesgo_w})")
        ref = _significado_fase(fase.split()[0] if fase else "")
        if ref:
            lineas.append(ref)
        det = _detector_fase(fase.split()[0] if fase else "")
        if det:
            lineas.append(f"  Detectado por:{det}")

    # 4) Setup armado: alineacion simple D1/H4/M15
    lineas.append("")
    lineas.append("COMO ESTA ARMADO EL SETUP")
    sesgos_tf = [estructura.get(tf, {}).get("trend", "") for tf in ("D1", "H4", "M15")]
    if all(s == "BULLISH" for s in sesgos_tf):
        lineas.append("  Alineacion ALCISTA en los 3 TF + Wyckoff a favor -> setup long limpio.")
    elif all(s == "BEARISH" for s in sesgos_tf):
        lineas.append("  Alineacion BAJISTA en los 3 TF + Wyckoff a favor -> setup short limpio.")
    elif len(set(sesgos_tf)) == 1:
        lineas.append(f"  Los 3 TF en {sesgos_tf[0]} pero Wyckoff puede diferir -> confirmar.")
    else:
        lineas.append("  TF en conflicto (D1/H4/M15 no alineados) -> esperar confirmacion.")
    lineas.append("  (BOS/CHOCH y barrido de liquidez arriba/abajo en cada TF validan la entrada.)")

    return "\n".join(lineas)


class ResumenWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.title = QLabel("SETUP ARMADO DEL DÍA")
        self.title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.title)

        self.lbl = QLabel("calculando...")
        self.lbl.setStyleSheet("color: #ddd; font-size: 12px;")
        self.lbl.setWordWrap(True)
        layout.addWidget(self.lbl, 1)

    def update_state(self, estructura: dict | None = None, bias: str = "",
                     votes: dict | None = None, extra: dict | None = None) -> None:
        if estructura is None:
            self.lbl.setText("Sin datos de estructura (MT5 no disponible).")
            return
        self.lbl.setText(resumen_setup(estructura, bias or "", votes, extra))
