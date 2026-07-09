"""Motor de la app del observador.

Orquesta los scripts REALES de la rutina (sin duplicar lógica):
  - rutina_eurusd.analyze_timeframe / build_verdict  -> sesgo + veredicto
  - news_report.load_events                            -> noticias rojas
  - semaforo_fundednext.evaluate                       -> color del semáforo
  - mapa_precio.save_tf_png                            -> regenera mapas ICT
  - fase_wyckoff_m15.fase_actual                       -> fase Wyckoff M15

NO inventa datos. Si falta el parquet MT5, reporta 'sin datos' y lo escribe en la
caja negra. Cada paso queda registrado en blackbox para análisis de errores.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

from app_observador.config import DATA_RAW, MAPS_DIR, ROOT, SYMBOL, TIMEFRAMES
from app_observador.core.blackbox import BLACKBOX_DIR, log_event, log_error

CACHE_PATH = BLACKBOX_DIR / "last_cycle.json"
_SCRIPTS = ROOT / "scripts"


def _import_script(name: str) -> ModuleType:
    """Importa un script de scripts/ dinámicamente (los scripts se insertan su
    propio parent en sys.path, así que detectors/fase_wyckoff quedan accesibles)."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module(name)


def run_cycle(force_fetch: bool = False) -> dict:
    """Corre un ciclo de análisis completo y devuelve el estado para la UI.

    Devuelve un dict con: semaforo (color, reasons), bias, veredicto,
    noticias, mapas (paths), fases_wyckoff, errores.
    """
    result: dict = {
        "semaforo": {"color": "DESCCONOCIDO", "reasons": []},
        "bias": "SIN DATOS",
        "veredicto": {},
        "noticias": [],
        "fuente_noticias": "",
        "mapas": {},
        "wyckoff": {},
        "estructura": {},
        "errores": [],
    }

    try:
        rut = _import_script("rutina_eurusd")
        news = _import_script("news_report")
        sem = _import_script("semaforo_fundednext")
        mapa = _import_script("mapa_precio")
        wyk = _import_script("fase_wyckoff_m15")
    except Exception as e:
        log_error("engine", "import_scripts", e)
        result["errores"].append(f"import: {e}")
        return result

    # 1) Cargar y analizar cada temporalidad con datos REALES
    tfs_data: dict[str, object] = {}
    for tf in TIMEFRAMES:
        try:
            df = rut._load(SYMBOL, tf)
            info = rut.analyze_timeframe(df, tf)
            tfs_data[tf] = (df, info)
            log_event("engine", "tf_analizado", symbol=SYMBOL, tf=tf,
                      data={"trend": info.get("trend"), "bos_dir": info.get("bos_dir")})
        except Exception as e:
            log_error("engine", "tf_fallo", e, symbol=SYMBOL, tf=tf)
            result["errores"].append(f"{tf}: {e}")
            result["bias"] = "SIN DATOS MT5"
            return result  # sin datos no hay análisis

    d1, h4, m15 = tfs_data["D1"][1], tfs_data["H4"][1], tfs_data["M15"][1]
    verdict = rut.build_verdict(d1, h4, m15)
    bias = verdict.get("bias", "NEUTRAL (esperar)")
    result["bias"] = bias
    result["veredicto"] = verdict
    log_event("engine", "veredicto", symbol=SYMBOL, data={"bias": bias, "votes": verdict.get("votes")})

    # 1b) Estructura del mercado (datos reales de analyze_timeframe) para la UI
    for tf in TIMEFRAMES:
        info = tfs_data[tf][1]
        result["estructura"][tf] = {
            "trend": info.get("trend", ""),
            "bos_dir": int(info.get("bos_dir", 0)),
            "bos_status": str(info.get("bos_status", "")),
            "bos_level": float(info.get("bos_level", 0.0) or 0.0),
            "sweep_up": bool(info.get("sweep_up", False)),
            "sweep_down": bool(info.get("sweep_down", False)),
            "ote_long": [float(x) for x in info.get("ote_long", (0.0, 0.0))],
            "ote_short": [float(x) for x in info.get("ote_short", (0.0, 0.0))],
        }
    result["estructura"]["WYCKOFF_M15"] = result["wyckoff"].get("M15", {})

    # 2) Noticias rojas reales (usa cache del dia; si no hay cache, baja RSS)
    try:
        relevant, fuente = news.load_events(no_fetch=not force_fetch)
        result["noticias"] = relevant
        result["fuente_noticias"] = fuente
        log_event("engine", "noticias", symbol=SYMBOL,
                  data={"count": len(relevant), "fuente": fuente})
    except Exception as e:
        log_error("engine", "noticias_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"noticias: {e}")

    # 3) Semáforo FundedNext real
    try:
        color, reasons = sem.evaluate(bias, result["noticias"])
        result["semaforo"] = {"color": color, "reasons": reasons}
        log_event("engine", "semaforo", symbol=SYMBOL, data={"color": color})
    except Exception as e:
        log_error("engine", "semaforo_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"semaforo: {e}")

    # 4) Regenerar mapas ICT (usando los df/info reales)
    try:
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        for tf in TIMEFRAMES:
            df, info = tfs_data[tf]
            path = mapa.save_tf_png(SYMBOL, tf, df, info, MAPS_DIR)
            result["mapas"][tf] = str(path)
        log_event("engine", "mapas_generados", symbol=SYMBOL,
                  data={"paths": result["mapas"]})
    except Exception as e:
        log_error("engine", "mapas_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"mapas: {e}")

    # 5) Fase Wyckoff M15 real
    try:
        fase = wyk.fase_actual(SYMBOL, "M15")
        result["wyckoff"]["M15"] = fase
        log_event("engine", "wyckoff", symbol=SYMBOL, tf="M15",
                  data={"fase": fase.get("phase_es"), "sesgo": fase.get("bias")})
    except Exception as e:
        log_error("engine", "wyckoff_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"wyckoff: {e}")

    if not result["errores"]:
        log_event("engine", "ciclo_completo", level="INFO", symbol=SYMBOL,
                  data={"color": result["semaforo"]["color"], "bias": bias})

    # Cache del ultimo ciclo (la app lo lee en <1s al abrir)
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8")
    except Exception as e:
        log_error("engine", "cache_write", e, symbol=SYMBOL)
    return result


def load_cached() -> dict | None:
    """Lee el ultimo ciclo cacheado (None si no existe). Para abrir la app rapido."""
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


if __name__ == "__main__":
    out = run_cycle()
    print("SEMAFORO:", out["semaforo"]["color"])
    print("BIAS:", out["bias"])
    print("NOTICIAS:", len(out["noticias"]), "(", out["fuente_noticias"], ")")
    print("MAPAS:", out["mapas"])
    print("WYCKOFF M15:", out["wyckoff"].get("M15", {}).get("fase"))
    if out["errores"]:
        print("ERRORES:", out["errores"])
