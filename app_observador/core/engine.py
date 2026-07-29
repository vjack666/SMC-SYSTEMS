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
import gc
import json
import os
import sys
import time

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

# Slow-stage timing budget for run_cycle() watchdog.
# Non-canonical stages: 20s budget. Canonical stage: 600s budget.
_STAGE_THRESHOLD_S = {
    "stage1_load_analyze": 20.0,
    "stage2_wyckoff": 20.0,
    "stage3_canonical": 600.0,
    "stage_total": 20.0,
}
# Rolling window size for recent completed-cycle durations.
_RESOURCE_WINDOW_SIZE = 5
# Thread-safe-ish list for recent totals. run_cycle() appends 1 entry per call.
_RECENT_CYCLE_TIMES: list[float] = []

# §5C: presupuesto de tiempo estricto para el paso 6 (canonical R7). El plan
# canónico es enriquecimiento best-effort; si no llega dentro de este tiempo,
# canonical queda 'EN CONSTRUCCIÓN' (honesto) y el cache YA está escrito.
CANONICAL_TIMEOUT_S = 12

# Executor persistente para canonical plan (NO se crea/destruye por ciclo).
# Evita leak de threads (shutdown con wait=False dejaba pools huérfanos).
_CANONICAL_POOL: ThreadPoolExecutor | None = None


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
    global _CANONICAL_POOL
    if _CANONICAL_POOL is None:
        _CANONICAL_POOL = ThreadPoolExecutor(max_workers=1)
    fut = _CANONICAL_POOL.submit(_canonical_plan, symbol)
    try:
        return ("OK", fut.result(timeout=timeout_s))
    except FutureTimeoutError:
        return ("TIMEOUT", None)
    except Exception as e:  # noqa: BLE001
        return ("ERROR", e)
    # NOTA: No hacemos shutdown(). El executor es persistente y se reusa
    # entre ciclos. Si timeout, el thread queda huérfano pero es 1 thread
    # que el SO recolecta cuando termine su I/O.


def _import_script(name: str) -> ModuleType:
    """Importa un script de scripts/ dinámicamente (los scripts se insertan su
    propio parent en sys.path, así que detectors/fase_wyckoff quedan accesibles)."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module(name)


def run_cycle(force_fetch: bool = False, symbol: str | None = None) -> dict:
    """Corre un ciclo de análisis completo y devuelve el estado para la UI.

    symbol: si se pasa, usa ese activo; si no, usa config.SYMBOL.
    """
    target = symbol or SYMBOL
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
        "symbol": target,
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
    _t0 = time.perf_counter()
    tfs_data: dict[str, tuple] = {}
    for tf in TIMEFRAMES:
        try:
            df = rut._load(target, tf)
            info = rut.analyze_timeframe(df, tf)
            tfs_data[tf] = (df, info)
            log_event("engine", "tf_analizado", symbol=target, tf=tf,
                      data={"trend": info.get("trend"), "bos_dir": info.get("bos_dir")})
        except Exception as e:
            log_error("engine", "tf_fallo", e, symbol=target, tf=tf)
            result["errores"].append(f"{tf}: {e}")
            result["bias"] = "SIN DATOS MT5"
            return result  # sin datos no hay análisis

    d1, h4, h1, m15 = (
        tfs_data["D1"][1], tfs_data["H4"][1],
        tfs_data["H1"][1], tfs_data["M15"][1],
    )

    # Cachear DataFrames+infos para reuso (canonical plan, mapas on-demand)
    try:
        from app_observador.core.data_cache import store_tfs_data
        store_tfs_data(target, tfs_data)
    except Exception:
        pass

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
        log_error("engine", "regime_fallo", e, symbol=target, tf="M15")
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
        log_error("engine", "stoch_m15_fallo", e, symbol=target)
    ca = verdict.get("context_alignment", {})
    log_event("engine", "veredicto_core", symbol=target,
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
            "bos_signal": str(info.get("bos_signal", "NONE")),
            "bos_distance_bars": int(info.get("bos_distance_bars", 0) or 0),
            "bos_status": str(info.get("bos_status", "")),
            "bos_level": float(info.get("bos_level", 0.0) or 0.0),
            "bos_age": int(info.get("bos_age", 0) or 0),
            "bos_bars": int(info.get("bos_bars", 0) or 0),
            "sweep_up": bool(info.get("sweep_up", False)),
            "sweep_up_bars": int(info.get("sweep_up_bars", 0) or 0),
            "sweep_down": bool(info.get("sweep_down", False)),
            "sweep_down_bars": int(info.get("sweep_down_bars", 0) or 0),
            "ote_long": [float(x) for x in info.get("ote_long", (0.0, 0.0))],
            "ote_short": [float(x) for x in info.get("ote_short", (0.0, 0.0))],
            "choch_dir": int(info.get("choch_dir", 0) or 0),
            "choch_level": float(info.get("choch_level", 0.0) or 0.0),
            "choch_status": str(info.get("choch_status", "-") or "-"),
            "choch_age": int(info.get("choch_age", 0) or 0),
            "choch_bars": int(info.get("choch_bars", 0) or 0),
            "choch_origin_time": str(info.get("choch_origin_time", "-") or "-"),
            "choch_confirm_time": str(info.get("choch_confirm_time", "-") or "-"),
            "fvg_state": str(info.get("fvg_state", "-") or "-"),
            "fvg_type": str(info.get("fvg_type", "") or ""),
            "fvg_size": float(info.get("fvg_size", 0.0) or 0.0),
            "fvg_low": float(info.get("fvg_low", 0.0) or 0.0),
            "fvg_high": float(info.get("fvg_high", 0.0) or 0.0),
            "fvg_age": int(info.get("fvg_age", 0) or 0),
            # datos reales ya calculados por analyze_timeframe (para puntuar modelos ICT)
            "ob_dir": str(info.get("ob_dir", "-") or "-"),
            "ob_high": float(info.get("ob_high", 0.0) or 0.0),
            "ob_low": float(info.get("ob_low", 0.0) or 0.0),
            "ob_active": bool(info.get("ob_active", False)),
            "ob_age": int(info.get("ob_age", 0) or 0),
            "range_pips": float(info.get("range_pips", 0.0) or 0.0),
        }
    result["estructura"]["WYCKOFF_M15"] = result["wyckoff"].get("M15", {})

    # ESCRITURA INMEDIATA (pass 1): el cache YA tiene el veredicto core honesto
    # ANTES de cargar M5/SMT (lentos) o el canonical. El dashboard no espera.
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write_pass1", e, symbol=target)

    # --- PASS 2: ENRIQUECIMIENTO (M5 + SMT, best-effort) --------------------
    # FASE M5 TWOPASS: cargar M5 APARTE (no toca TIMEFRAMES ni la estructura UI).
    # Si no hay M5 -> m5=None -> trigger_engine PENDING honesto (sin inventar).
    # NOTA: el resultado se cachea para evitar el loop scalping duplicado abajo.
    from app_observador.core.data_cache import store_analyzed as _cache_info
    m5_info = None
    _m5_loaded = False
    try:
        df_m5 = rut._load(SYMBOL, "M5")
        m5_info = rut.analyze_timeframe(df_m5, "M5")
        _cache_info(SYMBOL, "M5", m5_info)
        _m5_loaded = True
    except Exception as e:
        log_error("engine", "m5_fallo_twopass", e, symbol=target, tf="M5")
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
            log_event("engine", "veredicto_enriquecido", symbol=target,
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
                log_error("engine", "cache_write_pass2", e, symbol=target)
        except Exception as e:
            # El enriquecimiento es best-effort: si falla, conservamos el core.
            log_error("engine", "veredicto_enriquecido_fallo", e, symbol=target)
            result["errores"].append(f"enriquecimiento: {e}")

    # 1c) TFs de scalping (M1/M5) — OPCIONALES: no abortan si faltan.
    #     Solo EURUSD tiene esos parquet en data/raw; para otros simbolos el
    #     check de scalping quedara en "sin datos M1/M5".
    #     M5 se salta si ya se cargó en PASS 2 (evita analyze_timeframe duplicado).
    for tf in TIMEFRAMES_SCALPING:
        if tf == "M5" and _m5_loaded and m5_info is not None:
            result["estructura"][tf] = {
                "trend": m5_info.get("trend", ""),
                "bos_dir": int(m5_info.get("bos_dir", 0)),
                "bos_status": str(m5_info.get("bos_status", "")),
                "bos_level": float(m5_info.get("bos_level", 0.0) or 0.0),
                "sweep_up": bool(m5_info.get("sweep_up", False)),
                "sweep_down": bool(m5_info.get("sweep_down", False)),
                "ote_long": [float(x) for x in m5_info.get("ote_long", (0.0, 0.0))],
                "ote_short": [float(x) for x in m5_info.get("ote_short", (0.0, 0.0))],
                "ob_dir": str(m5_info.get("ob_dir", "-") or "-"),
                "fvg_state": str(m5_info.get("fvg_state", "-") or "-"),
                "choch_status": str(m5_info.get("choch_status", "-") or "-"),
            }
            continue
        try:
            df = rut._load(SYMBOL, tf)
            info = rut.analyze_timeframe(df, tf)
            # Cachear info para reuso
            try:
                _cache_info(SYMBOL, tf, info)
            except Exception:
                pass
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
            log_event("engine", "tf_scalping_analizado", symbol=target, tf=tf)
        except Exception as e:
            # sin datos M1/M5 -> no es error fatal, el check lo refleja
            result["estructura"][tf] = {}
            log_event("engine", "tf_scalping_sin_datos", symbol=target, tf=tf,
                      data={"error": str(e)[:120]})

    stage1_s = round(time.perf_counter() - _t0, 3)

    # 2) Noticias rojas reales (usa cache del dia; si no hay cache, baja RSS)
    try:
        relevant, fuente = news.load_events(no_fetch=not force_fetch)
        result["noticias"] = relevant
        result["fuente_noticias"] = fuente
        log_event("engine", "noticias", symbol=target,
                  data={"count": len(relevant), "fuente": fuente})
    except Exception as e:
        log_error("engine", "noticias_fallo", e, symbol=target)
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
        log_event("engine", "semaforo", symbol=target, data={"color": color})
    except Exception as e:
        log_error("engine", "semaforo_fallo", e, symbol=target)
        result["errores"].append(f"semaforo: {e}")

    # 4) Mapas ICT — ya NO se regeneran automáticamente en cada ciclo.
    #     Se generan SOLO bajo demanda (botón "Regenerar mapa" en la pestaña Mapa).
    #     Los paths a PNGs existentes se resuelven al vuelo en mapa_widget.
    result["mapas"] = {tf: str(MAPS_DIR / f"{target}_{tf}.png") for tf in TIMEFRAMES_MAPA}
    log_event("engine", "mapas_skip_auto", symbol=target,
              data={"note": "maps deferred to on-demand"})

    # 5) Fase Wyckoff M15 real
    _t1 = time.perf_counter()
    try:
        fase = wyk.fase_actual(target, "M15")
        result["wyckoff"]["M15"] = fase
        log_event("engine", "wyckoff", symbol=target, tf="M15",
                  data={"fase": fase.get("phase_es"), "sesgo": fase.get("bias")})
    except Exception as e:
        log_error("engine", "wyckoff_fallo", e, symbol=target)
        result["errores"].append(f"wyckoff: {e}")

    stage2_s = round(time.perf_counter() - _t1, 3)

    # Cache del ultimo ciclo (la app lo lee en <1s al abrir).
    # SE ESCRIBE ANTES del paso 6 (canonico R7) a proposito: si el plan canonico
    # tarda o se cuelga, el dashboard YA tiene el veredicto honesto (votes reales)
    # y no se queda mudo. Fase C: el veredicto aqui ya NO esta reescrito por canonical.
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write", e, symbol=target)

    # 6) Motor canónico R7 (sequence) → plan Entry/SL/TP compartido con Lab/LIMIT.
    # §5C: el canonical es enriquecimiento best-effort ACOTADO EN TIEMPO. Primero
    # marcamos 'EN CONSTRUCCIÓN' y re-escribimos cache (garantía sí-o-sí de no-silencio);
    # luego intentamos el plan con un presupuesto estricto (_canonical_plan_bounded).
    # Si tarda/falla, el cache YA tiene el veredicto honesto y canonical honesto.
    result["canonical"] = "EN CONSTRUCCIÓN"
    try:
        _write_cache_atomic(result)
    except Exception as e:
        log_error("engine", "cache_write", e, symbol=target)

    _t2 = time.perf_counter()
    status, payload = _canonical_plan_bounded(target, CANONICAL_TIMEOUT_S)
    stage3_s = round(time.perf_counter() - _t2, 3)

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
        log_event("engine", "canonical_plan", symbol=target,
                  data={"side": payload["side"], "entry": payload["entry"],
                        "sl": payload["sl"], "tp": payload["tp"], "rr": payload["rr"]})
        # Re-escribir cache con canonical ya poblado (el veredicto sigue honesto)
        try:
            _write_cache_atomic(result)
        except Exception as e:
            log_error("engine", "cache_write", e, symbol=target)
    elif status == "OK":
        result["canonical"] = None
        log_event("engine", "canonical_plan_empty", symbol=target)
    elif status == "TIMEOUT":
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append("canonical: timeout")
        log_error("engine", "canonical_timeout",
                  TimeoutError(f"canonical excedió {CANONICAL_TIMEOUT_S}s"),
                  symbol=target)
    else:  # status == "ERROR"
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append(f"canonical: {payload}")
        log_error("engine", "canonical_plan_fallo", payload, symbol=target)

    total_s = round(stage1_s + stage2_s + stage3_s, 3)
    warnings: list[str] = []
    budgets = {
        "stage1_load_analyze": stage1_s,
        "stage2_wyckoff": stage2_s,
        "stage3_canonical": stage3_s,
        "stage_total": total_s,
    }
    for name, value in budgets.items():
        threshold = _STAGE_THRESHOLD_S.get(name, 20.0)
        if value > threshold:
            msg = f"{name}={value:.1f}s > {threshold:.0f}s"
            warnings.append(msg)
            log_event("engine", "cycle_timing", symbol=target,
                      data={"stage": name, "s": value, "threshold_s": threshold})
    result["resource_timing"] = {
        "stage1_s": stage1_s,
        "stage2_s": stage2_s,
        "stage3_s": stage3_s,
        "total_s": total_s,
        "warnings": warnings,
    }
    try:
        _RECENT_CYCLE_TIMES.append(total_s)
        if len(_RECENT_CYCLE_TIMES) > _RESOURCE_WINDOW_SIZE:
            del _RECENT_CYCLE_TIMES[0]
    except Exception:
        pass

    # Liberar memoria cíclica cada ciclo. Los DataFrames viejos que ya no
    # referencia nadie se recolectan, evitando que RAM crezca indefinidamente.
    gc.collect()

    if not result["errores"]:
        log_event("engine", "ciclo_completo", level="INFO", symbol=target,
                  data={"color": result["semaforo"]["color"], "bias": bias})
    return result


def _canonical_plan(symbol: str) -> dict | None:
    """R7: last sequence signal H4→M15 (or D1→H4 fallback) as live plan.

    Primero intenta usar los DataFrames cacheados por run_cycle (evita recargar
    parquets de disco). Si no hay cache, cae a load_frames tradicional.
    """
    from ict_backtest.canonical import latest_plan
    from ict_backtest.data_feed import load_frames

    def _cap(df, max_rows=2500):
        """Cap rows to keep latency bounded."""
        if len(df) > max_rows:
            return df.iloc[-max_rows:].reset_index(drop=True)
        return df.reset_index(drop=True)

    # Prefer H4→M15 (intraday exec). Fall back to D1→H4 if M15 missing.
    for htf, ltf in (("H4", "M15"), ("D1", "H4")):
        try:
            # Intentar usar cache primero
            from app_observador.core.data_cache import get_tfs_entry
            _df_htf = get_tfs_entry(symbol, htf)
            _df_ltf = get_tfs_entry(symbol, ltf)
            _df_d1 = get_tfs_entry(symbol, "D1")
            if _df_htf is not None and _df_ltf is not None:
                frames = {
                    htf: _cap(_df_htf[0]),
                    ltf: _cap(_df_ltf[0]),
                    "D1": _cap(_df_d1[0]) if _df_d1 is not None else load_frames(symbol, ("D1",))["D1"],
                }
                plan = latest_plan(symbol, htf=htf, ltf=ltf, frames=frames, max_age_bars=64)
                if plan:
                    return plan
                continue  # cache no tenía plan activo -> probar fallback
            # Cache miss → cargar desde disco
            frames = load_frames(symbol, (htf, ltf, "D1"))
            capped = {tf: _cap(df) for tf, df in frames.items()}
            plan = latest_plan(symbol, htf=htf, ltf=ltf, frames=capped, max_age_bars=64)
            if plan:
                return plan
        except Exception:
            continue
    return None


def regenerate_maps(result: dict | None = None) -> dict[str, str]:
    """Regenera los 4 PNGs (D1/H4/H1/M15) bajo demanda.

    Devuelve dict {tf: path_str}. Usa el último result del ciclo para
    los DataFrames cacheados. Si no hay data disponible, devuelve paths vacíos.
    """
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    try:
        from app_observador.core.data_cache import get_tfs_data
        tfs_data = get_tfs_data()
        if not tfs_data:
            log_error("engine", "mapas_sin_cache", Exception("no cached data"), symbol=SYMBOL)
            return {tf: "" for tf in TIMEFRAMES_MAPA}
        mapa = _import_script("mapa_precio")
        for tf in TIMEFRAMES_MAPA:
            if tf not in tfs_data:
                continue
            df, info = tfs_data[tf]
            path = mapa.save_tf_png(SYMBOL, tf, df, info, MAPS_DIR)
            paths[tf] = str(path)
        log_event("engine", "mapas_generados_manual", symbol=SYMBOL, data={"paths": paths})
    except Exception as e:
        log_error("engine", "mapas_manual_fallo", e, symbol=SYMBOL)
    return paths


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
