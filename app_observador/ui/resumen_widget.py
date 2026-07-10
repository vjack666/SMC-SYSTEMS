"""Pestaña Principal: SETUP ARMADO + checklists INTRADIA / SCALPING.

Layout de 2 columnas:
  - Izquierda: SETUP ARMADO DEL DIA (texto: sesgo + estructura + Wyckoff + ICT).
  - Derecha: dos paneles (INTRADIA, SCALPING) con checklist numerado de
    "que falta para terminar de armar la estrategia", derivado de los datos
    REALES del motor (trend, bos_dir, sweep, votos, killzone activa).

Fuentes de regla:
  - docs/WYCKOFF_RULEBOOK.md -> fase Wyckoff
  - docs/ict/*.md -> modelos ICT (Turtle Soup, Silver Bullet, PO3, liquidez)
  - graphify-out/graph.json -> detector real de cada fase
No inventa: cada check refleja un dato del motor o la hora/killzone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QListWidget,
)

from app_observador.ui.noticias_widget import resumen_estructura

ROOT = Path(__file__).resolve().parents[3]
GRAPH_JSON = ROOT / "graphify-out" / "graph.json"
RULEBOOK = ROOT / "docs" / "WYCKOFF_RULEBOOK.md"
ICT_DIR = ROOT / "docs" / "ict"

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

# Bandas de killzone (UTC) segun docs/ict/01_KILLZONES.md (aprox, horario estandar).
# London 07-10 UTC, NY AM 12:30-15:00 UTC, NY PM 17:00-20:00 UTC.
KILLZONES_UTC = {
    "London Open": (7, 10),
    "New York AM": (12, 15),
    "New York PM": (17, 20),
}


def _cargar_grafo() -> dict | None:
    if not GRAPH_JSON.exists():
        return None
    try:
        return json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


_GRAFO = _cargar_grafo()


def killzone_activa_ahora() -> str:
    """Devuelve el nombre de la killzone activa ahora (UTC) o '' si ninguna.

    Aproximacion de las bandas documentadas en docs/ict/01_KILLZONES.md.
    """
    ahora = datetime.now(timezone.utc)
    h = ahora.hour + ahora.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""


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
    if not RULEBOOK.exists():
        return ""
    secc = WYCKOFF_SECCION.get(fase)
    if not secc:
        return ""
    return f"  [{secc} de WYCKOFF_RULEBOOK.md]"


def _cita_ict(nombre: str) -> str:
    if not (ICT_DIR / nombre).exists():
        return ""
    return f"  [docs/ict/{nombre}]"


def _dir_setup(bias: str, votes: dict | None, m15: dict) -> str:
    v = votes or {}
    if v.get("LONG", 0) > v.get("SHORT", 0):
        return "LONG"
    if v.get("SHORT", 0) > v.get("LONG", 0):
        return "SHORT"
    bd = int(m15.get("bos_dir", 0) or 0)
    if bd > 0:
        return "LONG"
    if bd < 0:
        return "SHORT"
    return "NEUTRAL"


def modelo_ict(estructura: dict, bias: str, votes: dict | None) -> tuple[str, str, int]:
    """Elige el modelo ICT mas coherente por puntuacion sobre los datos reales.

    Devuelve (nombre, libro_md, score). Modelos evaluados (detectables hoy):
      - Turtle Soup   : reversión contra tendencia (sweep + MSS/CHoCH opuesto a D1)
      - Silver Bullet : intradía killzone (sweep + FVG en M15)
      - PO3           : continuación a favor (sesgo alineado + manipulación/sweep)
      - Unicorn       : FVG + Order Block juntos en M15 (necesita ob_dir/fvg_state)
    Cada modelo suma puntos segun features del motor; gana el de mayor score.
    Empate -> el primero en esta lista (orden de especificidad).
    """
    d1 = estructura.get("D1", {})
    h4 = estructura.get("H4", {})
    m15 = estructura.get("M15", {})
    dir_setup = _dir_setup(bias, votes, m15)
    tendencia_d1 = d1.get("trend", "RANGING")
    sweep_m15 = bool(m15.get("sweep_up")) or bool(m15.get("sweep_down"))
    sweep_menor = sweep_m15 or bool(h4.get("sweep_up")) or bool(h4.get("sweep_down"))
    fvg_m15 = str(m15.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    ob_m15 = str(m15.get("ob_dir", "-")) not in ("-", "none", "nan", "")
    choch_m15 = str(m15.get("choch_status", "-")).lower() not in ("-", "none", "nan", "")
    bos_m15 = int(m15.get("bos_dir", 0) or 0) != 0
    kz = killzone_activa_ahora()

    # --- Turtle Soup (contra tendencia) ---
    s_ts = 0
    if dir_setup == "LONG" and tendencia_d1 == "BEARISH":
        s_ts += 3
    elif dir_setup == "SHORT" and tendencia_d1 == "BULLISH":
        s_ts += 3
    if sweep_menor:
        s_ts += 2
    if choch_m15 or bos_m15:
        s_ts += 1

    # --- Silver Bullet (intradía killzone, sweep + FVG) ---
    s_sb = 0
    if kz in ("London Open", "New York AM", "New York PM"):
        s_sb += 2
    if sweep_m15:
        s_sb += 2
    if fvg_m15:
        s_sb += 2
    if dir_setup != "NEUTRAL":
        s_sb += 1

    # --- PO3 (continuación a favor) ---
    s_po3 = 0
    if (dir_setup == "LONG" and tendencia_d1 == "BULLISH") or \
       (dir_setup == "SHORT" and tendencia_d1 == "BEARISH"):
        s_po3 += 3
    if sweep_menor:
        s_po3 += 1
    if tendencia_d1 == "RANGING":
        s_po3 += 1  # en rango, PO3 busca la ruptura del rango

    # --- Unicorn (FVG + OB juntos en M15) ---
    s_uni = 0
    if fvg_m15 and ob_m15:
        s_uni += 4
    if choch_m15:
        s_uni += 1
    if dir_setup != "NEUTRAL":
        s_uni += 1

    candidatos = [
        ("Unicorn (FVG + OB)", "07_SILVER_BULLET.md", s_uni),  # Unicorn usa mismo libro base de entrada
        ("Silver Bullet", "07_SILVER_BULLET.md", s_sb),
        ("Turtle Soup", "06_TURTLE_SOUP.md", s_ts),
        ("Power of Three (PO3)", "08_POWER_OF_THREE.md", s_po3),
    ]
    # ordenar por score desc, luego por orden de especificidad (Unicorn primero)
    orden = {"Unicorn (FVG + OB)": 0, "Silver Bullet": 1, "Turtle Soup": 2, "Power of Three (PO3)": 3}
    mejor = max(candidatos, key=lambda c: (c[2], -orden[c[0]]))
    return mejor


def modo_ict(estructura: dict, bias: str, votes: dict | None) -> list[str]:
    """Bloque MODO INTRADIA / SCALPING: modelo ICT mas coherente + a-favor/contra."""
    lineas: list[str] = []
    d1 = estructura.get("D1", {})
    m15 = estructura.get("M15", {})
    h4 = estructura.get("H4", {})
    dir_setup = _dir_setup(bias, votes, m15)
    tendencia_d1 = d1.get("trend", "RANGING")

    nombre, libro, score = modelo_ict(estructura, bias, votes)
    lineas.append("MODO INTRADIA / SCALPING (ICT)")
    lineas.append(f"  Direccion del setup: {dir_setup}   |   Tendencia D1: {tendencia_d1}")
    lineas.append(f"  MODELO MAS COHERENTE: {nombre}  (score {score})")
    cita = _cita_ict(libro)
    if cita:
        lineas.append(cita)

    if dir_setup == "LONG" and tendencia_d1 == "BEARISH":
        lineas.append("  CONTRA TENDENCIA: setup long vs D1 bajista (reversion).")
        lineas.append("  Esperar sweep de SSL + MSS alcista en M15 antes de entrar.")
    elif dir_setup == "SHORT" and tendencia_d1 == "BULLISH":
        lineas.append("  CONTRA TENDENCIA: setup short vs D1 alcista (reversion).")
        lineas.append("  Esperar sweep de BSL + MSS bajista en M15 antes de entrar.")
    elif dir_setup != "NEUTRAL" and (
        (dir_setup == "LONG" and tendencia_d1 == "BULLISH")
        or (dir_setup == "SHORT" and tendencia_d1 == "BEARISH")
    ):
        lineas.append("  A FAVOR (continuation): setup y D1 alineados.")
    elif tendencia_d1 == "RANGING":
        lineas.append("  NEUTRAL: D1 en rango -> esperar sweep + CHOCH en M15 para definir.")
    else:
        lineas.append("  NEUTRAL: sin direccion de setup hoy (votos/empatados, sin BOS M15).")

    sweep_up = bool(m15.get("sweep_up")) or bool(h4.get("sweep_up"))
    sweep_down = bool(m15.get("sweep_down")) or bool(h4.get("sweep_down"))
    if dir_setup != "NEUTRAL":
        if (sweep_up and dir_setup == "SHORT") or (sweep_down and dir_setup == "LONG"):
            lineas.append("  Liquidez barrida en TF menor -> entrada alineada al modelo.")
            lineas += _cita_ict("05_LIQUIDEZ.md").splitlines() or ["  [docs/ict/05_LIQUIDEZ.md]"]
        else:
            lineas.append("  Aun sin barrido de liquidez confirmado en TF menor -> esperar sweep.")
            lineas += _cita_ict("05_LIQUIDEZ.md").splitlines() or ["  [docs/ict/05_LIQUIDEZ.md]"]

    lineas.append("  TP sugerido = liquidez opuesta (BSL si long / SSL si short, ver mapa ICT).")
    lineas.append("  Regla Stellar: RR >= 1:2 (TP estructural).")
    return lineas


def resumen_setup(estructura: dict, bias: str = "", votes: dict | None = None,
                 extra: dict | None = None) -> str:
    """Texto detallado del setup: sesgo + estructura + Wyckoff + ICT + armado."""
    if not estructura:
        return "Sin datos de estructura (MT5 no disponible)."

    lineas: list[str] = []

    # 1) Sesgo direccional (votos L/S)
    v = votes or {"LONG": 0, "SHORT": 0}
    lineas.append("SESGO DIRECCIONAL")
    lineas.append(f"  Veredicto: {bias}   (votos L:{v.get('LONG', 0)} / S:{v.get('SHORT', 0)})")

    # 2) Estructura por TF
    lineas.append("")
    lineas.append("ESTRUCTURA D1 / H4 / M15")
    lineas.append(resumen_estructura(estructura))

    # 3) Fase Wyckoff M15
    wyk = estructura.get("WYCKOFF_M15") or {}
    if not wyk:
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

    # 4) Modo intradia / scalping
    lineas.append("")
    lineas += modo_ict(estructura, bias, votes)

    # 5) Setup armado
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


# ---------------------------------------------------------------------------
# Checklists INTRADIA / SCALPING
# ---------------------------------------------------------------------------

def _sweep_dir(estructura: dict, tfs: tuple[str, ...]) -> str:
    """Devuelve 'up'/'down'/'none' segun sweeps en los TF indicados."""
    up = any(estructura.get(tf, {}).get("sweep_up") for tf in tfs)
    down = any(estructura.get(tf, {}).get("sweep_down") for tf in tfs)
    if up and down:
        return "both"
    return "up" if up else "down" if down else "none"


def _bos_m15(estructura: dict) -> str:
    m15 = estructura.get("M15", {})
    bd = int(m15.get("bos_dir", 0) or 0)
    st = m15.get("bos_status", "")
    if bd == 1 and st == "active":
        return "alcista"
    if bd == -1 and st == "active":
        return "bajista"
    if bd != 0:
        return "intentando"
    return "no"


def checklist_intradia(estructura: dict, bias: str, votes: dict | None) -> list[str]:
    """Checklist INTRADIA (H1/H4/M15, modelo PO3 / Turtle Soup). Items numerados."""
    items: list[str] = []
    d1 = estructura.get("D1", {})
    h4 = estructura.get("H4", {})
    m15 = estructura.get("M15", {})
    dir_setup = _dir_setup(bias, votes, m15)
    kz = killzone_activa_ahora()

    # 1. Sesgo del dia
    if "NEUTRAL" in bias or not bias:
        items.append("✗ Falta: definir SESGO DEL DIA (L/S) desde H4/D1.")
    else:
        items.append(f"✓ Sesgo del dia: {bias}.")

    # 2. Contexto D1/H4
    if d1.get("trend") in ("", "RANGING") and h4.get("trend") in ("", "RANGING"):
        items.append("✗ Falta: contexto D1/H4 definido (en rango -> sin marea).")
    else:
        items.append(f"✓ Contexto: D1 {d1.get('trend','?')} / H4 {h4.get('trend','?')}.")

    # 3. Killzone intradia activa
    if kz in ("London Open", "New York AM", "New York PM"):
        items.append(f"✓ Killzone intradia activa: {kz} (UTC).")
    else:
        items.append("✗ Fuera de killzone intradia (London/NY) -> esperar ventana.")

    # 4. Sweep de liquidez en H4/M15
    sw = _sweep_dir(estructura, ("H4", "M15"))
    if sw == "none":
        items.append("✗ Falta: barrido de liquidez (sweep SSL/BSL) en H4/M15.")
    else:
        items.append(f"✓ Liquidez barrida ({sw}) en H4/M15.")

    # 5. BOS/CHoCH en M15
    bos = _bos_m15(estructura)
    if bos == "no":
        items.append("✗ Falta: BOS/CHoCH en M15 (estructura intacta).")
    else:
        items.append(f"✓ M15 con BOS {bos}.")

    # 6. Direccion alineada al sesgo
    if dir_setup == "NEUTRAL":
        items.append("✗ Falta: direccion del setup (votos/L-S o BOS M15).")
    else:
        items.append(f"✓ Direccion setup: {dir_setup}.")

    # 7. TP en liquidez opuesta (ver mapa)
    items.append("○ TP en liquidez opuesta (BSL/SSL del mapa ICT).")

    # 8. RR >= 1:2
    items.append("○ RR >= 1:2 (regla Stellar).")
    return items


def checklist_scalping(estructura: dict, bias: str, votes: dict | None) -> list[str]:
    """Checklist SCALPING (M1/M5, modelo Silver Bullet). Items numerados."""
    items: list[str] = []
    m15 = estructura.get("M15", {})
    dir_setup = _dir_setup(bias, votes, m15)
    kz = killzone_activa_ahora()

    # 1. Ventana Silver Bullet (NY AM 10-11 ET ~ 14-15 UTC; usamos banda NY AM)
    if kz == "New York AM":
        items.append("✓ Ventana Silver Bullet activa (NY AM).")
    else:
        items.append("✗ Fuera de ventana Silver Bullet (NY AM 10-11 ET) -> esperar.")

    # 2. Sesgo filtrado
    if "NEUTRAL" in bias or not bias:
        items.append("✗ Falta: sesgo del dia para filtrar solo setups a favor.")
    else:
        items.append(f"✓ Sesgo filtra setups: {bias}.")

    # 3. Sweep en M15 (la materia prima del Silver Bullet en M1/M5)
    sw = _sweep_dir(estructura, ("M15",))
    if sw == "none":
        items.append("✗ Falta: sweep de SSL/BSL en M15 (previo al FVG M1/M5).")
    else:
        items.append(f"✓ Sweep M15 ({sw}) presente.")

    # 4. FVG en M1/M5 (datos reales del motor, si existen los parquet)
    m5 = estructura.get("M5", {}) or {}
    m1 = estructura.get("M1", {}) or {}
    fvg_m5 = str(m5.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    fvg_m1 = str(m1.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    if not m5 and not m1:
        items.append("○ Buscar FVG en M1/M5 tras el sweep (sin datos M1/M5 en cache).")
    elif fvg_m5 or fvg_m1:
        donde = "M5" if fvg_m5 else "M1"
        items.append(f"✓ FVG en {donde} presente tras sweep (Silver Bullet listo).")
    else:
        items.append("✗ Sin FVG en M1/M5 aun (esperar tras el sweep).")

    # 5. Direccion coincide con sesgo
    if dir_setup == "NEUTRAL":
        items.append("✗ Falta: direccion del setup para el scalp.")
    else:
        items.append(f"✓ Direccion scalp: {dir_setup}.")

    # 6. SL ajustado al FVG/sweep (OB real si existe)
    ob_m5 = str(m5.get("ob_dir", "-")) not in ("-", "none", "nan", "")
    if ob_m5:
        items.append(f"✓ OB en M5 ({m5.get('ob_dir')}) -> SL sobre/fallo del OB.")
    else:
        items.append("○ SL bajo FVG alcista / sobre FVG bajista (o en SSL/BSL).")

    # 7. RR 1:2 rapido
    items.append("○ RR >= 1:2, salida en liquidez opuesta (rapido).")
    return items


class ResumenWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setSpacing(10)

        # --- Columna izquierda: SETUP ARMADO ---
        left = QVBoxLayout()
        self.title = QLabel("SETUP ARMADO DEL DÍA")
        self.title.setStyleSheet("color: #7fb3ff; font-weight: bold; font-size: 13px;")
        left.addWidget(self.title)
        self.lbl = QLabel("calculando...")
        self.lbl.setStyleSheet("color: #ddd; font-size: 12px;")
        self.lbl.setWordWrap(True)
        left.addWidget(self.lbl, 1)
        left_w = QWidget()
        left_w.setLayout(left)
        root.addWidget(left_w, 1)

        # --- Columna derecha: INTRADIA + SCALPING (checklists) ---
        right = QVBoxLayout()
        right.setSpacing(8)

        self.g_intra = QGroupBox("INTRADÍA  (H1/H4/M15 — PO3 / Turtle Soup)")
        gi_layout = QVBoxLayout(self.g_intra)
        self.list_intra = QListWidget()
        self.list_intra.setStyleSheet("background-color: #1e1e1e; color: #eee; font-size: 12px;")
        gi_layout.addWidget(self.list_intra)
        right.addWidget(self.g_intra, 1)

        self.g_scalp = QGroupBox("SCALPING  (M1/M5 — Silver Bullet)")
        gs_layout = QVBoxLayout(self.g_scalp)
        self.list_scalp = QListWidget()
        self.list_scalp.setStyleSheet("background-color: #1e1e1e; color: #eee; font-size: 12px;")
        gs_layout.addWidget(self.list_scalp)
        right.addWidget(self.g_scalp, 1)

        right_w = QWidget()
        right_w.setLayout(right)
        root.addWidget(right_w, 1)

    def update_state(self, estructura: dict | None = None, bias: str = "",
                     votes: dict | None = None, extra: dict | None = None) -> None:
        if estructura is None:
            self.lbl.setText("Sin datos de estructura (MT5 no disponible).")
            self.list_intra.clear()
            self.list_scalp.clear()
            return
        self.lbl.setText(resumen_setup(estructura, bias or "", votes, extra))
        self.list_intra.clear()
        for it in checklist_intradia(estructura, bias or "", votes):
            self.list_intra.addItem(it)
        self.list_scalp.clear()
        for it in checklist_scalping(estructura, bias or "", votes):
            self.list_scalp.addItem(it)
