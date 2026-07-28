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
import os
import sys

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from types import ModuleType

from app_observador.config import (
    DATA_RAW, MAPS_DIR, ROOT, SYMBOL, SYMBOL_PAIR, TIMEFRAMES, TIMEFRAMES_MAPA, TIMEFRAMES_SCALPING
)
from app_observador.core import pipeline as decision_pipeline
from app_observador.core.blackbox import BLACKBOX_DIR, log_event, log_error

CACHE_PATH = BLACKBOX_DIR / "last_cycle.json"
_SCRIPTS = ROOT / "scripts"

# §5C: presupuesto de tiempo estricto para el paso 6 (canonical R7). El plan
# canónico es enriquecimiento best-effort; si no llega dentro de este tiempo,
# canonical queda 'EN CONSTRUCCIÓN' (honesto) y el cache YA está escrito.
CANONICAL_TIMEOUT_S = 12


def _write_cache_atomic(result: dict) -> None:
    """Escribe CACHE_PATH de forma atómica (tmp + os.replace).

    Un lector nunca ve JSON a medias: se escribe a un .json.tmp y se renombra
    con os.replace (atómico en el mismo filesystem).
    """
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, ensure_ascii=False, default=str),
        encoding="utf-8")
    os.replace(tmp, CACHE_PATH)


def _canonical_plan_bounded(symbol: str, timeout_s: float) -> tuple:
    """Envuelve _canonical_plan en un worker acotado por timeout.

    Devuelve una tupla de estado honesto:
      ('OK', payload)   -> _canonical_plan corrió (payload = dict o None)
      ('TIMEOUT', None) -> excedió timeout_s (thread queda huérfano, aceptable)
      ('ERROR', exc)    -> _canonical_plan lanzó excepción

    _canonical_plan NO se modifica: mantiene el import de ict_backtest adentro,
    preservando la separación backtest≠dashboard.
    """
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_canonical_plan, symbol)
    try:
        return ("OK", fut.result(timeout=timeout_s))
    except FutureTimeoutError:
        return ("TIMEOUT", None)
    except Exception as e:  # noqa: BLE001
        return ("ERROR", e)
    finally:
        # No esperar al thread: si _canonical_plan se colgó en I/O nativo,
        # queda huérfano pero run_cycle ya retorna con el cache escrito.
        # (No usamos `with` porque su __exit__ hace shutdown(wait=True).)
        ex.shutdown(wait=False)


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
    tfs_data: dict[str, tuple] = {}
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

    d1, h4, h1, m15 = (
        tfs_data["D1"][1], tfs_data["H4"][1],
        tfs_data["H1"][1], tfs_data["M15"][1],
    )
    # ========================================================================
    # §5D TWO-PASS: separar el veredicto CORE (rápido) del ENRIQUECIMIENTO (lento).
    # PASS 1 (core): pipeline SIN M5/SMT → veredicto honesto (trigger PENDING si
    #   falta M5) y ESCRITURA INMEDIATA del cache. El dashboard ve sesgo+POI+trigger
    #   en minutos, sin esperar a que M5/SMT (analyze_timeframe lento) carguen.
    # PASS 2 (enriquecimiento): cargar M5/SMT APARTE y re-llamar el pipeline con
    #   m5=m5_info/smt_b=smt_b_info → veredicto enriquecido y RE-ESCRITURA del cache.
    # Si M5/SMT fallan, el veredicto final = el core (nunca vacío, nunca inventado).
    # ========================================================================

    # --- PASS 1: veredicto CORE (sin M5/SMT) --------------------------------
    # FASE NUCLEO: pipeline jerarquico (no votacion). H1 = Stage 3 (IntradayEngine).
    # Aquí m5=None y smt=None a propósito → trigger/SMT quedan PENDING honestos.
    # Régimen de mercado (RANGO PURO, sin ATR): rango reciente vs histórico M15
    # vía avg_candle_range (FUENTE ÚNICA de volatilidad, Fase 1 ATR->RANGO).
    regime_range = None
    try:
        from ict_backtest._util import avg_candle_range
        df_m15 = tfs_data["M15"][0]
        if df_m15 is not None and len(df_m15) >= 20:
            recent = float(avg_candle_range(df_m15, window=10).iloc[-1])
            hist = float(avg_candle_range(df_m15, window=50).iloc[-1])
            regime_range = (recent, hist)
    except Exception as e:
        log_error("engine", "regime_fallo", e, symbol=SYMBOL, tf="M15")
        result["errores"].append(f"regime: {e}")
    verdict = decision_pipeline.run_pipeline(
        d1, h4, h1, m15, m5=None, smt_a=None, smt_b=None, regime_range=regime_range)
    bias = verdict.get("bias", "NEUTRAL (esperar)")
    result["bias"] = bias
    result["veredicto"] = verdict

    # Exponer el estocástico M15 en el cache para que el semáforo de la
    # pestaña "Auto" lo consuma SIN recalcular (single source of truth).
    try:
        from indicators.indicators import add_stochastic

        df_m15 = tfs_data["M15"][0]
        if df_m15 is not None and len(df_m15) >= 3:
            st = df_m15 if {"stoch_k", "stoch_d"}.issubset(df_m15.columns) else add_stochastic(df_m15)
            sk = st["stoch_k"].to_numpy()
            sd = st["stoch_d"].to_numpy()
            n = len(sk)
            j = n - 1
            while j > 0 and (pd.isna(sk[j]) or pd.isna(sd[j])):
                j -= 1
            if j >= 1:
                ki, di = float(sk[j]), float(sd[j])
                kp, dp = float(sk[j - 1]), float(sd[j - 1])
                bull = (kp <= dp) and (ki > di)
                bear = (kp >= dp) and (ki < di)
                result["stoch_m15"] = {
                    "k": ki,
                    "d": di,
                    "extreme": (ki < 20.0 and di < 20.0) or (ki > 80.0 and di > 80.0),
                    "cross": bull or bear,
                    "confirm": (bull or bear) and abs(ki - di) >= 1.0,
                }
    except Exception as e:
        log_error("engine", "stoch_m15_fallo", e, symbol=SYMBOL)
    ca = verdict.get("context_alignment", {})
    log_event("engine", "veredicto_core", symbol=SYMBOL,
              data={"bias": bias,
                    "macro": ca.get("macro"),
                    "intraday": ca.get("intraday"),
                    "poi": ca.get("poi"),
                    "trigger": ca.get("trigger"),
                    "confidence": ca.get("confidence")})

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

    # ESCRITURA INMEDIATA (pass 1): el cache YA tiene el veredicto core honesto
    # ANTES de cargar M5/SMT (lentos) o el canonical. El dashboard no espera.
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write_pass1", e, symbol=SYMBOL)

    # --- PASS 2: ENRIQUECIMIENTO (M5 + SMT, best-effort) --------------------
    # FASE M5 TWOPASS: cargar M5 APARTE (no toca TIMEFRAMES ni la estructura UI).
    # Si no hay M5 -> m5=None -> trigger_engine PENDING honesto (sin inventar).
    m5_info = None
    try:
        df_m5 = rut._load(SYMBOL, "M5")
        m5_info = rut.analyze_timeframe(df_m5, "M5")
    except Exception as e:
        log_error("engine", "m5_fallo_twopass", e, symbol=SYMBOL, tf="M5")
        result["errores"].append(f"M5: {e}")
    # FASE SMT: cargar el par correlacionado (SYMBOL_PAIR) en H1 APARTE.
    # SMT lee EURUSD vs GBPUSD en el MISMO TF (H1). Si no hay segundo par ->
    # smt=None -> smt_engine PENDING honesto (no inventa correlacion).
    smt_b_info = None
    try:
        sym_pair = SYMBOL_PAIR
        df_pair = rut._load(sym_pair, "H1")
        smt_b_info = rut.analyze_timeframe(df_pair, "H1")
    except Exception as e:
        log_error("engine", "smt_fallo", e, symbol=SYMBOL_PAIR, tf="H1")
        result["errores"].append(f"SMT({SYMBOL_PAIR} H1): {e}")

    # Re-llamar el pipeline con M5/SMT solo si cargó ALGO (evita trabajo redundante).
    # SMT necesita H1 de AMBOS pares -> smt_a = h1 (EURUSD), smt_b = smt_b_info (par).
    if m5_info is not None or smt_b_info is not None:
        try:
            verdict = decision_pipeline.run_pipeline(
                d1, h4, h1, m15, m5=m5_info, smt_a=h1, smt_b=smt_b_info,
                regime_range=regime_range)
            bias = verdict.get("bias", bias)
            result["bias"] = bias
            result["veredicto"] = verdict
            ca = verdict.get("context_alignment", {})
            log_event("engine", "veredicto_enriquecido", symbol=SYMBOL,
                      data={"bias": bias,
                            "macro": ca.get("macro"),
                            "intraday": ca.get("intraday"),
                            "poi": ca.get("poi"),
                            "trigger": ca.get("trigger"),
                            "confidence": ca.get("confidence")})
            # RE-ESCRITURA (pass 2): cache con veredicto enriquecido (M5/SMT).
            try:
                _write_cache_atomic(result)
            except Exception as e:
                log_error("engine", "cache_write_pass2", e, symbol=SYMBOL)
        except Exception as e:
            # El enriquecimiento es best-effort: si falla, conservamos el core.
            log_error("engine", "veredicto_enriquecido_fallo", e, symbol=SYMBOL)
            result["errores"].append(f"enriquecimiento: {e}")

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

    # Cache del ultimo ciclo (la app lo lee en <1s al abrir).
    # SE ESCRIBE ANTES del paso 6 (canonico R7) a proposito: si el plan canonico
    # tarda o se cuelga, el dashboard YA tiene el veredicto honesto (votes reales)
    # y no se queda mudo. Fase C: el veredicto aqui ya NO esta reescrito por canonical.
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write", e, symbol=SYMBOL)

    # 6) Motor canónico R7 (sequence) → plan Entry/SL/TP compartido con Lab/LIMIT.
    # §5C: el canonical es enriquecimiento best-effort ACOTADO EN TIEMPO. Primero
    # marcamos 'EN CONSTRUCCIÓN' y re-escribimos cache (garantía sí-o-sí de no-silencio);
    # luego intentamos el plan con un presupuesto estricto (_canonical_plan_bounded).
    # Si tarda/falla, el cache YA tiene el veredicto honesto y canonical honesto.
    result["canonical"] = "EN CONSTRUCCIÓN"
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write", e, symbol=SYMBOL)

    status, payload = _canonical_plan_bounded(SYMBOL, CANONICAL_TIMEOUT_S)
    if status == "OK" and payload:
        result["canonical"] = payload
        # Overlay veredicto invalidation/target from structural plan when present
        verd = dict(result.get("veredicto") or {})
        verd["invalidation"] = payload["sl"]
        verd["target"] = payload["tp"]
        verd["canonical_entry"] = payload["entry"]
        verd["canonical_side"] = payload["side"]
        verd["canonical_rr"] = payload["rr"]
        verd["engine"] = payload["engine"]
        # NOTE (Fase C, 2026-07-22): los votos del veredicto NO se reescriben con el
        # plan canónico. El consenso D1/H4/M15 es la fuente de verdad del sesgo operativo
        # (tesis: alineamiento top-down). El plan canónico R7 es UNA señal más y vive en
        # result["canonical"] (chip propio en plan_strip). No se inventa consenso.
        result["veredicto"] = verd
        log_event("engine", "canonical_plan", symbol=SYMBOL,
                  data={"side": payload["side"], "entry": payload["entry"],
                        "sl": payload["sl"], "tp": payload["tp"], "rr": payload["rr"]})
        # Re-escribir cache con canonical ya poblado (el veredicto sigue honesto)
        try:
            _write_cache_atomic(result)
        except Exception as e:
            log_error("engine", "cache_write", e, symbol=SYMBOL)
    elif status == "OK":
        result["canonical"] = None
        log_event("engine", "canonical_plan_empty", symbol=SYMBOL)
    elif status == "TIMEOUT":
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append("canonical: timeout")
        log_error("engine", "canonical_timeout",
                  TimeoutError(f"canonical excedió {CANONICAL_TIMEOUT_S}s"),
                  symbol=SYMBOL)
    else:  # status == "ERROR"
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append(f"canonical: {payload}")
        log_error("engine", "canonical_plan_fallo", payload, symbol=SYMBOL)

    if not result["errores"]:
        log_event("engine", "ciclo_completo", level="INFO", symbol=SYMBOL,
                  data={"color": result["semaforo"]["color"], "bias": bias})
    return result


def _canonical_plan(symbol: str) -> dict | None:
    """R7: last sequence signal H4→M15 (or D1→H4 fallback) as live plan."""
    from ict_backtest.canonical import latest_plan
    from ict_backtest.data_feed import load_frames

    # Prefer H4→M15 (intraday exec). Fall back to D1→H4 if M15 missing.
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
            plan = latest_plan(symbol, htf=htf, ltf=ltf, frames=capped, max_age_bars=64)
            if plan:
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
