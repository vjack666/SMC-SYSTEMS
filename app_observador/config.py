"""Configuración de la app del observador.

Ruta única de verdad para rutas, símbolo, TFs y umbrales. No importa nada del bot
heredado. Solo usa rutas reales del proyecto.
"""
from __future__ import annotations

from pathlib import Path

# Raíz del proyecto (app_observador/ está dentro de SMC-SYSTEMS)
# config.py está en SMC-SYSTEMS/app_observador/config.py -> subimos 2 niveles
ROOT = Path(__file__).resolve().parent.parent

SYMBOL = "EURUSD"
# TFs obligatorios del analisis top-down (contexto + veredicto + mapa)
TIMEFRAMES = ["D1", "H4", "M15"]
# TFs de scalping (M1/M5) — OPCIONALES: entran a la estructura/cache para el
# check de scalping, pero solo existen para EURUSD en data/raw. Si faltan no
# abortan el ciclo (el check de scalping queda en "sin datos M1/M5").
TIMEFRAMES_SCALPING = ["M1", "M5"]
# TFs que generan mapa PNG (solo los 3 de contexto, no M1/M5)
TIMEFRAMES_MAPA = ["D1", "H4", "M15"]

# Carpeta de datos crudos (parquet MT5) — ya existe, la lee el loop
DATA_RAW = ROOT / "data" / "raw"

# Donde la app guarda los mapas PNG y el black-box
APP_DIR = ROOT / "app_observador"
MAPS_DIR = ROOT / "docs" / "diario"
BLACKBOX_DIR = ROOT / "data" / "blackbox"

# Retención de datos (regla de Ruben): 3 meses = 90 días
RETENTION_DAYS = 90

# Refresco de la UI (igual que el loop: cada 5 min)
REFRESH_SECONDS = 300

# Ventana de noticias que la app resalta (rojas)
NEWS_HIGH_IMPACT_ONLY = True


def ensure_dirs() -> None:
    """Crea las carpetas de salida si no existen."""
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    BLACKBOX_DIR.mkdir(parents=True, exist_ok=True)
