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

from app_observador.config import (
    DATA_RAW, MAPS_DIR, ROOT, SYMBOL, TIMEFRAMES, TIMEFRAMES_MAPA, TIMEFRAMES_SCALPING
)
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
            # datos reales ya calculados por analyze_timeframe (para puntuar modelos ICT)
            "ob_dir": str(info.get("ob_dir", "-") or "-"),
            "fvg_state": str(info.get("fvg_state", "-") or "-"),
            "choch_status": str(info.get("choch_status", "-") or "-"),
        }
    result["estructura"]["WYCKOFF_M15"] = result["wyckoff"].get("M15", {})

    # 1c) TFs de scalping (M1/M5) — OPCIONALES: no abortan si faltan.
    #     Solo EURUSD tiene esos parquet en data/raw; para otros simbolos el
    #     check de scalping quedara en "sin datos M1/M5".
    for tf in TIMEFRAMES_SCALPING:
        try:
            df = rut._load(SYMBOL, tf)
            info = rut.analyze_timeframe(df, tf)
            result["estructura"][tf] = {
                "trend": info.get("trend", ""),
                "bos_dir": int(info.get("bos_dir", 0)),
                "bos_status": str(info.get("bos_status", "")),
                "bos_level": float(info.get("bos_level", 0.0) or 0.0),
                "sweep_up": bool(info.get("sweep_up", False)),
                "sweep_down": bool(info.get("sweep_down", False)),
                "ote_long": [float(x) for x in info.get("ote_long", (0.0, 0.0))],
                "ote_short": [float(x) for x in info.get("ote_short", (0.0, 0.0))],
                "ob_dir": str(info.get("ob_dir", "-") or "-"),
                "fvg_state": str(info.get("fvg_state", "-") or "-"),
                "choch_status": str(info.get("choch_status", "-") or "-"),
            }
            log_event("engine", "tf_scalping_analizado", symbol=SYMBOL, tf=tf)
        except Exception as e:
            # sin datos M1/M5 -> no es error fatal, el check lo refleja
            result["estructura"][tf] = {}
            log_event("engine", "tf_scalping_sin_datos", symbol=SYMBOL, tf=tf,
                      data={"error": str(e)[:120]})

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
        # Calcula el plan de trade real para decidir VERDE/AMARILLO con R:R.
        trade_plan = None
        try:
            rut_plan = _import_script("rutina_eurusd")
            trade_plan = rut_plan.compute_trade_plan(verdict, m15)
        except Exception:
            trade_plan = None
        color, reasons = sem.evaluate(bias, result["noticias"], trade_plan)
        result["semaforo"] = {"color": color, "reasons": reasons}
        log_event("engine", "semaforo", symbol=SYMBOL, data={"color": color})
    except Exception as e:
        log_error("engine", "semaforo_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"semaforo: {e}")

    # 4) Regenerar mapas ICT (usando los df/info reales de los 3 TF de contexto)
    try:
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        for tf in TIMEFRAMES_MAPA:
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

    # 6) Motor canónico R7 (sequence) → plan Entry/SL/TP compartido con Lab/LIMIT
    try:
        plan = _canonical_plan(SYMBOL)
        if plan:
            result["canonical"] = plan
            # Overlay veredicto invalidation/target from structural plan when present
            verd = result.get("veredicto") or {}
            verd = dict(verd)
            verd["invalidation"] = plan["sl"]
            verd["target"] = plan["tp"]
            verd["canonical_entry"] = plan["entry"]
            verd["canonical_side"] = plan["side"]
            verd["canonical_rr"] = plan["rr"]
            verd["engine"] = plan["engine"]
            # Align votes lightly with sequence side for Lab direction
            if plan["side"] == "LONG":
                verd["votes"] = {"LONG": max(int((verd.get("votes") or {}).get("LONG", 0)), 2),
                                 "SHORT": int((verd.get("votes") or {}).get("SHORT", 0))}
            else:
                verd["votes"] = {"LONG": int((verd.get("votes") or {}).get("LONG", 0)),
                                 "SHORT": max(int((verd.get("votes") or {}).get("SHORT", 0)), 2)}
            result["veredicto"] = verd
            log_event("engine", "canonical_plan", symbol=SYMBOL,
                      data={"side": plan["side"], "entry": plan["entry"],
                            "sl": plan["sl"], "tp": plan["tp"], "rr": plan["rr"]})
        else:
            result["canonical"] = None
            log_event("engine", "canonical_plan_empty", symbol=SYMBOL)
    except Exception as e:
        result["canonical"] = None
        log_error("engine", "canonical_plan_fallo", e, symbol=SYMBOL)
        result["errores"].append(f"canonical: {e}")

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


def _canonical_plan(symbol: str) -> dict | None:
    """Plan en vivo desde el MOTOR (engine/), no del backtest (Ley).

    El motor es la lectura top-down del trader humano (D1->H4->H1->M15) hecha
    codigo y es permanente; el backtest es desechable y solo lo demuestra. El
    observador en vivo lee del motor, nunca del backtest.
    """
    from engine.data_feed import load_frames
    from engine.plan import build_context_stack, top_down_allows_trade
    from engine.htf_narrative import build_htf_narrative

    # Preferir H4->M15 (exec intradia). Fallback a D1->H4 si M15 falta.
    for htf, ltf in (("H4", "M15"), ("D1", "H4")):
        try:
            frames = load_frames(symbol, tuple(dict.fromkeys([htf, ltf, "D1"])))
            # Cap bars for latency: keep last ~2k LTF rows
            capped = {}
            for tf, df in frames.items():
                if len(df) > 2500:
                    capped[tf] = df.iloc[-2500:].reset_index(drop=True)
                else:
                    capped[tf] = df.reset_index(drop=True)
            ltf_df = capped.get(ltf)
            if ltf_df is None or len(ltf_df) == 0:
                continue
            t = ltf_df.iloc[-1]["time"]
            # Lectura del humano: narrativa HTF + gate top-down
            htf_frames = {tf: df for tf, df in capped.items() if tf in ("D1", "H4", "H1")}
            narr = build_htf_narrative(capped.get(htf, ltf_df), htf_frames=htf_frames)
            stack = build_context_stack(capped, t, tfs=(htf, ltf, "D1") if htf == "H4" else (htf, ltf))
            direction = 1 if narr.get("bias") == "BULLISH" else (-1 if narr.get("bias") == "BEARISH" else 0)
            if direction == 0:
                return None
            ok, reason = top_down_allows_trade(stack, direction)
            if not ok:
                return None
            poi = narr.get("poi") or {}
            plan = {
                "engine": "engine.plan (top_down)",
                "symbol": symbol,
                "side": "LONG" if direction == 1 else "SHORT",
                "direction": direction,
                "bias": narr.get("bias"),
                "zone": narr.get("zone"),
                "poi_kind": poi.get("kind"),
                "anchored": poi.get("anchored"),
                "liquidity_target": (narr.get("liquidity_target") or {}).get("side"),
                "time": str(t),
                "model": "top_down_htf_narrative",
            }
            return plan
        except Exception:
            continue
    return None


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
