"""ict_backtest/sequence.py — Capa 2: motor EVENT-SEQUENCE (memoria de eventos).

Arregla la raiz del problema que viste: el mini-check del dashboard evaluaba
sweep + BOS + displacement en la MISMA vela ("todo de golpe"). En ICT real los
eventos ocurren EN SECUENCIA y el mercado se revela en cascada (D1 -> H4 -> M15):

  1. SWEEP    : el precio barre una liquidez (BSL/SSL) en HTF o LTF.
  2. DISPLACE  : en las proximas N velas hay una vela de displacement fuerte
                en la direccion del setup (la "falla" de la que habla ICT).
  3. BOS/CHOCH : luego el precio rompe estructura (BOS continuacion o CHOCH giro)
                en esa direccion.
  4. ENTRY     : aparece un FVG/OB en la direccion -> se genera la senal.

Cada evento se recuerda vela a vela en SequenceState (memoria). Si pasa
max_gap velas sin avanzar, la secuencia se reinicia (no acumula ruido).

Esto es la "memoria" que pediste, antes de meter ML (Capa 3): el estado de
que eventos ya pasaron y hace cuantas velas.

============================================================================
R9 PASO 3 — Refactor de tipo de dato (SIN cambiar reglas ICT).
============================================================================
El motor AHORA consume MarketObject[] en lugar de columnas sueltas del
DataFrame. Cada vela del LTF se envuelve en UN MarketObject(type=CANDLE) que
carga en su `meta` TODOS los campos ICT de esa vela (bos_dir, choch_dir,
fvg_*, ob_*, sweep_*, displacement_*, high/low/open/close/atr/bos_level/time).
Las funciones internas (_has_sweep, _has_bos, _latest_fvg_zone, etc.) leen
exclusivamente de MarketObject — NUNCA de ltf_df.iloc[i][col].

La conversion inicial (DataFrame -> MarketObject[]) vive en `_candle_objects`,
que NO toca translation.py (capa de compatibilidad intacta). `run_sequence`
acepta DataFrame O lista de objetos (compatibilidad de firma).

Equivalencia: el round-trip df -> objetos -> senales es IDENTICO al legado
(ver tests/test_r9_object_adapter.py). Ninguna regla ICT cambia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ict_backtest._util import closed_row_at_time
from ict_backtest.htf_pd_index import HtfPdZone
from ict_backtest.market_object import MarketObject, ObjectState, ObjectType, Role
from ict_backtest.multitf_context import MultiTFContext, extract_htf_layer
from ict_backtest.plan_fsm import PlanEvent, PlanVerdict
from ict_backtest.zone_authority import evaluate_zone_authority
from ict_backtest.poi_filter import poi_present


PHASE = ("IDLE", "SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE")

# Campos ICT de la vela que sequence necesita. Se cargan en MarketObject.meta.
_CANDLE_FIELDS = (
    "bos_dir", "choch_dir", "fvg_bullish", "fvg_bearish", "ob_direction",
    "ob_bullish", "ob_bearish", "liquidity_sweep_up", "liquidity_sweep_down",
    "displacement_bullish", "displacement_bearish", "high", "low", "open",
    "close", "atr", "bos_level", "time", "fvg_zone_low", "fvg_zone_high",
)


@dataclass
class SequenceConfig:
    sweep_lookback: int = 8        # el sweep debe verse en las ultimas N velas
    displace_gap: int = 6          # ventana para el displacement tras el sweep
    # R10 (Propuesta A): ventana de confirmacion BOS.
    #   bos_gap: int  -> fijo (solo para debugging/scripts).
    #   bos_gap: None -> DINAMICO: confirmation_window() deriva N de la FUERZA
    #                del quiebre via tabla empirica del backtest (sin ATR/indicadores).
    # Por defecto running en modo dinamico; si se pasa int, se mantiene compat.
    bos_gap: int | None = None
    require_displacement: bool = True
    counter_trend: bool = False
    tp_mode: str = "fixed2r"


@dataclass
class SequenceState:
    """Memoria de la secuencia en curso para UN simbolo/direccion."""
    phase: str = "IDLE"
    direction: int = 0
    sweep_idx: int = -1
    displace_idx: int = -1
    bos_idx: int = -1
    bos_level: float = float("nan")
    zone_high: float = float("nan")
    zone_low: float = float("nan")
    zone_pd_type: str = "NONE"   # Fase B1 (SPEC §4): metadato de la zona congelada
    zone_pd_tier: str = "NONE"   # (no altera la decisión de entry; info para POI/stacking)
    zone_authority: Any = None     # Fase C (C2/C3): ZoneAuthority anotada (peso de confianza)
    htf_aligned: bool = True       # A1 (Brecha A1): ¿la cascada D1->H4->H1 permite la dir?
    htf_reason: str = "ok"         # A1: motivo del filtro top-down (observabilidad)
    poi_present: Any = None        # Brecha A (Fase C): ¿hay POI HTF anclado en dir? (bonus, no gate)
    history: list = field(default_factory=list)

    def reset(self):
        self.phase = "IDLE"
        self.direction = 0
        self.sweep_idx = -1
        self.displace_idx = -1
        self.bos_idx = -1
        self.bos_level = float("nan")
        self.zone_high = float("nan")
        self.zone_low = float("nan")
        self.zone_pd_type = "NONE"
        self.zone_pd_tier = "NONE"
        self.zone_authority = None
        self.htf_aligned = True
        self.htf_reason = "ok"
        self.poi_present = None

    def note(self, tag: str, i: int, extra: str = ""):
        self.history.append((tag, i, extra))


# ---------------------------------------------------------------------------
# R9 Paso 3: constructor de objetos (NO toca translation.py)
# ---------------------------------------------------------------------------

def _candle_objects(ltf_df: pd.DataFrame, ltf_tf: str) -> list[MarketObject]:
    """Envuelve cada vela del LTF en UN MarketObject(type=CANDLE).

    Carga en `meta` TODOS los campos ICT de la vela para que sequence los
    lea sin tocar el DataFrame. El `bar_index` ancla al indice de la vela
    (igual que ltf_df.iloc[i]), garantizando equivalencia 1:1 con el legado.
    """
    objs: list[MarketObject] = []
    for i, row in ltf_df.iterrows():
        meta: dict[str, Any] = {}
        for col in _CANDLE_FIELDS:
            meta[col] = row.get(col, np.nan)
        objs.append(MarketObject(
            type=ObjectType.CANDLE, origin_tf=ltf_tf, role=Role.REFINEMENT,
            direction=0, symbol="", state=__import__("ict_backtest.market_object",
                fromlist=["ObjectState"]).ObjectState.ACTIVE,
            bar_index=int(i), bar_time=row.get("time"), meta=meta,
        ))
    return objs


# ---------------------------------------------------------------------------
# Funciones internas — leen MarketObject (NO columnas del DataFrame)
# ---------------------------------------------------------------------------

def _has_sweep(obj: MarketObject, est_htf: dict, direction: int) -> bool:
    """Sweep de la liquidez OPUESTA a la direccion del setup (stop-hunt).

    Long busca sweep DOWN (barre SSL); Short busca sweep UP (barre BSL).
    Se acepta en LTF o HTF.
    """
    if direction == 1:
        return bool(obj.meta.get("liquidity_sweep_down", False)) or bool(est_htf.get("sweep_down", False))
    if direction == -1:
        return bool(obj.meta.get("liquidity_sweep_up", False)) or bool(est_htf.get("sweep_up", False))
    return False


def _has_displacement(obj: MarketObject, direction: int, est_htf: dict | None = None) -> bool:
    """Displacement de impulso fuerte en la direccion del setup.

    Igual que el sweep, se acepta en LTF O HTF (la vela del sweep puede ser
    HTF). Antes solo miraba la vela LTF exacta, lo que silenciaba setups de
    ruptura rapida (Silver Bullet) donde la entrada M5 es pequena sobre el FVG.
    Ver AUDIT_BUG_SILVER_TF.md (hallazgo IA externa: asimetria de diseno).
    """
    if direction == 1:
        if bool(obj.meta.get("displacement_bullish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bullish", False))
    if direction == -1:
        if bool(obj.meta.get("displacement_bearish", False)):
            return True
        return bool((est_htf or {}).get("displacement_bearish", False))
    return False


def _has_choch(obj: MarketObject, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """CHOCH en la direccion del giro (aviso de cambio de caracter, libro 02 §3.1).

    En contratendencia el CHOCH debe ir OPUESTO al HTF (es el paso 2 de la
    secuencia canonica BOS->CHOCH->BOS). En a-favor no se exige (el BOS de
    continuacion basta).
    """
    choch_dir = int(obj.meta.get("choch_dir", 0) or 0)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        return False  # a-favor: el CHOCH no es requisito (ver _has_bos)
    return choch_dir == want


def _has_bos(obj: MarketObject, est_htf: dict, direction: int, counter_trend: bool) -> bool:
    """BOS/CHOCH en la direccion del setup.

    A-favor (counter_trend=False): el BOS del LTF debe ir en la direccion del
    sesgo HTF. Contratendencia: el BOS/CHOCH debe ir en direccion OPUESTA al HTF.
    """
    _bd = obj.meta.get("bos_dir", 0)
    bos_dir = 0 if (_bd is None or (isinstance(_bd, float) and (_bd != _bd))) else int(_bd)
    _cd = obj.meta.get("choch_dir", 0)
    choch_dir = 0 if (_cd is None or (isinstance(_cd, float) and (_cd != _cd))) else int(_cd)
    htf_trend = str(est_htf.get("trend", "RANGING"))
    if counter_trend:
        want = -1 if htf_trend == "BULLISH" else 1 if htf_trend == "BEARISH" else direction
    else:
        want = direction
    return (bos_dir == want) or (choch_dir == want)


def _htf_has_poi(est_htf: dict, target: int) -> bool:
    """¿El HTF tiene un POI (FVG/OB) en la direccion del setup?

    Ontologia (MARKET_OBJECT_MODEL.md): el POI institucional SOLO existe en
    HTF (D1/H4/H1). La zona de entrada del LTF (FVG/OB) solo cuenta si
    hay un POI de HTF que la respalde. Sin esto, un FVG M15 suelto se
    usa como entrada (error conceptual que la tesis 18 corrige).

    `est_htf` puede traer las columnas de detectores del HTF; si no las trae,
    se asume que NO hay POI (comportamiento conservador).
    """
    if target == 1:
        return bool(est_htf.get("fvg_bullish", False)) or bool(est_htf.get("ob_bullish", False))
    if target == -1:
        return bool(est_htf.get("fvg_bearish", False)) or bool(est_htf.get("ob_bearish", False))
    return False


def _latest_fvg_zone(obj: MarketObject, direction: int) -> tuple[float, float] | None:
    """Cuadro del FVG mas reciente en la direccion del setup.

    Devuelve (zone_high, zone_low) del GAP, no de la vela del impulse.
    Prioriza fvg_zone_high/fvg_zone_low si estan en meta; si falta,
    no inventa proxy por high/low de la vela porque dibuja el impulso,
    no el hueco. Fallback seguro = None.
    """
    meta = obj.meta or {}
    if direction == 1 and bool(meta.get("fvg_bullish", False)):
        z_high = meta.get("fvg_zone_high")
        z_low = meta.get("fvg_zone_low")
        if z_high is not None and z_low is not None:
            return (float(z_high), float(z_low))
        return None
    if direction == -1 and bool(meta.get("fvg_bearish", False)):
        z_high = meta.get("fvg_zone_high")
        z_low = meta.get("fvg_zone_low")
        if z_high is not None and z_low is not None:
            return (float(z_high), float(z_low))
        return None
    return None


def _latest_ob_zone(obj: MarketObject, direction: int) -> tuple[float, float] | None:
    """Cuerpo del order block (vela de displacement previa) como cuadro.

    La columna del dataframe es 'ob_direction' (values 'bullish'/'bearish'),
    NO 'ob_dir'. Se corrige el nombre y el case para que el OB se use de
    verdad como zona de entrada.
    """
    ob_dir = str(obj.meta.get("ob_direction", "-")).lower()
    if direction == 1 and ob_dir == "bullish":
        o, c = float(obj.meta.get("open")), float(obj.meta.get("close"))
        return (max(o, c), min(o, c))
    if direction == -1 and ob_dir == "bearish":
        o, c = float(obj.meta.get("open")), float(obj.meta.get("close"))
        return (max(o, c), min(o, c))
    return None


def _touches_zone(obj: MarketObject, zone_high: float, zone_low: float) -> bool:
    """La vela toca/retorna al cuadro (mitigation). Confirma entrada."""
    low, high = float(obj.meta.get("low")), float(obj.meta.get("high"))
    return (low <= zone_high) and (high >= zone_low) and (zone_low < zone_high)


def _direction_from_bias(bias: str, counter_trend: bool) -> int:
    if bias == "BULLISH":
        return -1 if counter_trend else 1
    if bias == "BEARISH":
        return 1 if counter_trend else -1
    return 0


def confirmation_window(bos_obj: MarketObject, ctx_objs: list[MarketObject],
                         ctx_len: int, bos_table: dict | None) -> int:
    """R10 (Propuesta A): ventana de confirmacion BOS DINAMICA, SIN INDICADORES.

    Deriva N de la FUERZA del quiebre usando MATEMATICA PURA del gráfico:
        r = rango_bos / rango_promedio_contexto
    donde rango = high - low (ningún indicador). Luego mapea `r` a un bucket
    entero y lo busca en `bos_table` (tabla empirica P(mitigacion en N velas |
    fuerza r), pre-calculada del backtest). Si no hay tabla, fallback 40.

    Esto reemplaza el "numero magico" por "lo que el mercado hizo antes en
    situaciones iguales" (Principio 1: decision del estado, no constante).
    """
    if bos_table is None:
        return 40  # fallback deterministico (default canonico previo a R10)

    def _rango(o: MarketObject) -> float:
        return float(o.meta.get("high", 0.0)) - float(o.meta.get("low", 0.0))

    rango_bos = _rango(bos_obj)
    if ctx_len > 0 and rango_bos <= 0:
        return 40
    # rango promedio del contexto (promedio simple de high-low, NO ATR).
    if ctx_len > 0:
        suma = sum(_rango(o) for o in ctx_objs[:ctx_len])
        rango_ctx = suma / ctx_len
    else:
        rango_ctx = rango_bos
    if rango_ctx <= 0:
        return 40
    r = rango_bos / rango_ctx
    # bucket: 1 (debil) .. 5+ (muy fuerte). BOS fuerte => bucket alto.
    bucket = max(1, min(5, int(round(r))))
    return int(bos_table.get(bucket, 40))


def _effective_bos_gap(cfg: SequenceConfig, i: int, obj, est_htf,
                       objs, bos_table) -> int:
    """Ventana efectiva: fija si bos_gap es int, dinamica si es None.

    R10: el contexto es la ventana de velas previas (memoria del humano) para
    medir el rango promedio del mercado sin indicadores.
    """
    if cfg.bos_gap is None:
        lo = max(0, i - 50)
        ctx = objs[lo:i] if i > lo else objs[lo:i + 1]
        return confirmation_window(obj, ctx, len(ctx), bos_table)
    return cfg.bos_gap


def run_sequence(ltf_df_or_objs: Any, est_htf_fn, cfg: SequenceConfig,
                 htf_poi_fn=None, ltf_tf: str = "M15", bos_table: dict | None = None,
                 htf_pd_index=None, ltf_map: dict | None = None,
                 htf: str | None = None,
                 est_htf_ctx_fn=None,
                 itf_df: pd.DataFrame | None = None,
                 itf_tf: str | None = None):
    """Recorre el LTF y devuelve lista de dicts de senal.

    R9 Paso 3: acepta DataFrame O lista de MarketObject (type=CANDLE). En
    ambos casos itera sobre MarketObject[]; NUNCA lee columnas del DataFrame
    dentro del loop. Equivalencia 100% con el legado (mismo bar_index).

    est_htf_fn(i) -> dict con trend/sweep_up/sweep_down del HTF en la vela i.
        En Fase C (C1) tambien puede traer 'pd_zones': lista de PD arrays
        HTF vigentes (HtfPdZone) a la vela i.
        (Legacy: mantenido para llamadores existentes y tests aislados.)
    htf / est_htf_ctx_fn (Fase 1, lectura multitemporal): si est_htf_ctx_fn
        se pasa, run_sequence lo llama por barra y obtiene un MultiTFContext
        con el snapshot closed-only de TODA la cadena D1..M1. Luego aplica
        extract_htf_layer(context, htf) para seguir decidiendo con el MISMO
        HTF que usaba antes (Opción A): comportamiento 100% idéntico al
        baseline de 1 nivel. Los otros 5 TF viajan disponibles en el
        contexto pero aún no influyen en la lógica. Sin est_htf_ctx_fn, el
        comportamiento es exactamente el de antes (est_htf_fn legacy).
    htf_poi_fn(i, target) -> bool OPCIONAL: si se pasa, la zona de entrada del
        LTF (FVG/OB) SOLO se memoriza cuando el HTF tiene un POI en esa
        direccion (fidelidad ICT, tesis 18). Si es None (default), el
        comportamiento es el historico (no rompe llamadores existentes).
    bos_table -> dict bucket->ventana (R10 Propuesta A). Si cfg.bos_gap is None,
        la ventana de confirmacion BOS se deriva de la FUERZA del quiebre via
        esta tabla empirica (sin indicadores). Si bos_gap es int, se ignora.
    htf_pd_index -> HtfPdIndex OPCIONAL (Fase C, C1/C2). Si se pasa, cada
        zona LTF trazada se ANOTA con su ZoneAuthority (peso de confianza de
        zona, NO gate duro). El conteo de senales NO cambia: C solo aporta
        informacion contextual (Contrato de no invasion de C).
    Cada senal: {time, direction, entry, phase_log, zone_authority}.
    """
    # Conversion inicial: DataFrame -> MarketObject[] (si no vino ya como objetos).
    if isinstance(ltf_df_or_objs, pd.DataFrame):
        objs = _candle_objects(ltf_df_or_objs, ltf_tf)
    else:
        objs = list(ltf_df_or_objs)

    # --- Capa ITF (3 capas ICT: HTF bias -> ITF zona -> exec entry) ---
    # Si se provee itf_df, la deteccion de FVG/OB se hace sobre el ITF
    # (zona de entrada), mientras que sweep/displace/BOS y _touches_zone
    # siguen en el LTF/exec. Modo permisivo: si ITF no tiene zona,
    # fallback a LTF (backward compatible).
    itf_objs: list[MarketObject] | None = None
    ltf_to_itf: dict[int, int] | None = None
    if itf_df is not None and itf_tf is not None:
        itf_objs = _candle_objects(itf_df, itf_tf)
        # Pre-computar mapping LTF_idx -> ITF_idx (O(n), una sola pasada).
        # Usa closed_row_at_time para alinear por tiempo con anti look-ahead.
        from ict_backtest._util import closed_row_at_time, tf_duration
        _itf_dur = tf_duration(itf_tf)
        ltf_to_itf = {}
        _itf_times = pd.to_datetime(itf_df["time"], utc=True, errors="coerce")
        for _i in range(len(objs)):
            _t = objs[_i].meta.get("time")
            if _t is None:
                ltf_to_itf[_i] = 0
                continue
            _tt = pd.to_datetime(_t, utc=True, errors="coerce")
            _cutoff = _tt - pd.Timedelta(_itf_dur)
            _matches = _itf_times[_itf_times <= _cutoff]
            if len(_matches) > 0:
                ltf_to_itf[_i] = int(_matches.index[-1])
            else:
                ltf_to_itf[_i] = 0

    state = SequenceState()
    signals: list[dict] = []
    n = len(objs)
    phase_seen = {"SWEEP": 0, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}
    # Contexto de "memoria del humano": las 50 velas previas para medir el
    # rango promedio (matematica pura high-low, sin indicadores).
    CTX_WINDOW = 50

    for i in range(n):
        obj = objs[i]
        # Fase 1 (lectura multitemporal): si se pasó est_htf_ctx_fn, run_sequence
        # recibe el MultiTFContext completo y lo reduce al MISMO HTF de antes
        # (Opción A) vía extract_htf_layer. Sin esto, usa est_htf_fn legacy
        # (comportamiento idéntico al histórico).
        if est_htf_ctx_fn is not None:
            _ctx = est_htf_ctx_fn(i)
            est_htf = extract_htf_layer(_ctx, htf) if htf is not None else {}
        else:
            _ctx = None
            est_htf = est_htf_fn(i)
        htf_trend = str(est_htf.get("trend", "RANGING"))
        bias = htf_trend if htf_trend in ("BULLISH", "BEARISH") else "RANGING"
        if bias == "RANGING":
            state.reset()
            continue

        # Direccion objetivo segun sesgo (a-favor o contratendencia)
        target = _direction_from_bias(bias, cfg.counter_trend)
        if target == 0:
            state.reset()
            continue

        # BRECHA A1 (Opción B, filtro suave): la dirección objetivo debe
        # alinearse con la cascada top-down D1->H4->H1 del MultiTFContext
        # completo. Solo se aplica cuando el llamador pasó est_htf_ctx_fn
        # (modo multitemporal). Si es None (legacy sin contexto) el
        # comportamiento histórico queda INTACTO. El POI anclado NO es veto
        # (require_pd=False): según auditoría destruye edge; se usa como
        # bonus/anotación, no como gate duro.
        if est_htf_ctx_fn is not None and _ctx is not None:
            from ict_backtest.v2.context_mtf import top_down_allows_trade
            _ok, _reason = top_down_allows_trade(
                _ctx, target, counter_trend=cfg.counter_trend, require_pd=False,
            )
            if not _ok:
                # Veta la dirección que choca con la cascada y reinicia la
                # secuencia (no cambia la lógica interna del SETUP).
                state.htf_aligned = False
                state.htf_reason = _reason
                state.reset()
                continue

        # Si la secuencia en curso es de distinta direccion, reinicia
        if state.phase != "IDLE" and state.direction != target:
            state.reset()

        # Memoria de zona: recordar la ULTIMA vela con FVG/OB entre el sweep y
        # el BOS (el FVG/OB NO esta en la vela del BOS). Se congela en BOS_DONE
        # para que el cuadro no se mueva mientras se espera el retorno.
        if state.phase in ("SWEEP_DONE", "DISPLACE_DONE"):
            # Fidelidad ICT (tesis 18): la zona LTF (FVG/OB) solo se traza como
            # cuadro de entrada si el HTF tiene un POI en esa direccion. Sin
            # guarda (htf_poi_fn=None) el comportamiento es el historico.
            # BRECHA A (Fase C): poi_present anota si hay POI HTF anclado
            # en la direccion del setup (bonus de autoridad de zona, NO gate
            # duro: segun auditoria Fase E el veto destruye edge). Se calcula
            # SIEMPRE (con indice presente) via poi_filter.poi_present, y se
            # congela en state para propagarse a la senal en BOS_DONE.
            if htf_poi_fn is not None and htf_pd_index is not None and ltf_map is not None:
                state.poi_present = poi_present(htf_pd_index, ltf_map, i, target)
            else:
                state.poi_present = None
            # Hook historico: poi_ok decide si se memoriza la zona LTF. Con
            # htf_poi_fn=None es no-op (comportamiento historico intacto).
            poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))
            if poi_ok:
                # Capa ITF: si hay ITF y mapping, la zona viene del ITF.
                # Modo permisivo: si ITF no tiene FVG/OB, fallback a LTF.
                _zone_src = obj  # default: LTF
                if itf_objs is not None and ltf_to_itf is not None:
                    _itf_idx = ltf_to_itf.get(i, 0)
                    if 0 <= _itf_idx < len(itf_objs):
                        _itf_obj = itf_objs[_itf_idx]
                        _itf_fvg = _latest_fvg_zone(_itf_obj, target)
                        _itf_ob = _latest_ob_zone(_itf_obj, target)
                        if _itf_fvg is not None or _itf_ob is not None:
                            _zone_src = _itf_obj  # ITF tiene zona -> usar ITF
                _fvg = _latest_fvg_zone(_zone_src, target)
                _ob = _latest_ob_zone(_zone_src, target)
                _zone_obj = None
                if _fvg is not None:
                    state.zone_high, state.zone_low = _fvg
                    state.zone_pd_type = str(_zone_src.meta.get("pd_type", "FVG"))
                    state.zone_pd_tier = str(_zone_src.meta.get("pd_tier", "T2"))
                    _zone_tf = itf_tf if (itf_tf and _zone_src is not obj) else ltf_tf
                    _zone_obj = HtfPdZone(tf=_zone_tf, pd_type=state.zone_pd_type,
                                          pd_tier=state.zone_pd_tier,
                                          direction=target,
                                          zone_high=state.zone_high,
                                          zone_low=state.zone_low)
                elif _ob is not None:
                    state.zone_high, state.zone_low = _ob
                    state.zone_pd_type = str(_zone_src.meta.get("pd_type", "OB"))
                    state.zone_pd_tier = str(_zone_src.meta.get("pd_tier", "T2"))
                    _zone_tf = itf_tf if (itf_tf and _zone_src is not obj) else ltf_tf
                    _zone_obj = HtfPdZone(tf=_zone_tf, pd_type=state.zone_pd_type,
                                          pd_tier=state.zone_pd_tier,
                                          direction=target,
                                          zone_high=state.zone_high,
                                          zone_low=state.zone_low)
                # Fase C (C2/C3): anota la AUTORIDAD de la zona (peso de
                # confianza) SIN alterar la decision de R7. Lookup O(1) sobre
                # ltf_map (precalculado una vez en canonical.py / build_ltf_map).
                # CONTRATO: sin indice HTF, zone_authority queda None (el
                # comportamiento historico no se toca; C no anota nada).
                if htf_pd_index is not None and ltf_map is not None:
                    _pd_zones = []
                    for _tf in htf_pd_index.timeframes:
                        _pd_zones.extend(htf_pd_index.zones_at(i, _tf, ltf_map))
                    state.zone_authority = evaluate_zone_authority(_zone_obj, _pd_zones)
                else:
                    state.zone_authority = None

        if state.phase == "IDLE":
            if _has_sweep(obj, est_htf, target):
                state.phase = "SWEEP_DONE"
                state.direction = target
                state.sweep_idx = i
                state.note("SWEEP", i)
                phase_seen["SWEEP"] += 1
        elif state.phase == "SWEEP_DONE":
            if i - state.sweep_idx > cfg.displace_gap:
                state.reset()
                continue
            if (not cfg.require_displacement) or _has_displacement(obj, target, est_htf):
                state.phase = "DISPLACE_DONE"
                state.displace_idx = i
                state.note("DISPLACE", i)
                phase_seen["DISPLACE"] += 1
        elif state.phase == "DISPLACE_DONE":
            if i - state.displace_idx > _effective_bos_gap(cfg, i, obj, est_htf, objs, bos_table):
                state.reset()
                continue
            if _has_bos(obj, est_htf, target, cfg.counter_trend):
                # Secuencia canonica BOS->CHOCH->BOS (libro 02 §3.1): en
                # contratendencia exigir CHOCH (giro) ANTES del BOS de confirmacion.
                if cfg.counter_trend and not _has_choch(obj, est_htf, target, cfg.counter_trend):
                    continue
                state.phase = "BOS_DONE"
                state.bos_idx = i
                try:
                    state.bos_level = float(obj.meta.get("bos_level", np.nan))
                except (TypeError, ValueError):
                    state.bos_level = float("nan")
                # TRAZAR EL CUADRO: usar la zona cacheada (FVG/OB del tramo
                # sweep->displacement, memoria arriba), NO la vela del BOS donde
                # el imbalance ya no esta. El trader marca ese cuadro y ESPERA
                # el retorno (mitigation). Fallback: nivel del BOS +- 0.5 * rango
                # promedio (meta["atr"] ya es avg_candle_range, fuente unica de
                # volatilidad; migrado de ATR a rango puro, Fase 1).
                if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
                    _atr = obj.meta.get("atr", np.nan)
                    try:
                        atr = float(_atr) if _atr is not None else float("nan")
                    except (TypeError, ValueError):
                        atr = float("nan")
                    if np.isfinite(atr) and np.isfinite(state.bos_level):
                        state.zone_high = state.bos_level + 0.5 * atr
                        state.zone_low = state.bos_level - 0.5 * atr
                state.note("BOS", i)
                phase_seen["BOS"] += 1
        elif state.phase == "BOS_DONE":
            if i - state.bos_idx > _effective_bos_gap(cfg, i, obj, est_htf, objs, bos_table):
                state.reset()
                continue
            # ENTRADA = el precio RETORNA al cuadro trazado (mitigation), no FVG instantaneo.
            if _touches_zone(obj, state.zone_high, state.zone_low):
                # SENAL: la secuencia completa ocurrio en orden y el precio
                # volvio al cuadro (igual que el trader que espera el toque).
                zone_auth = getattr(state, "zone_authority", None)
                _poi_present = getattr(state, "poi_present", None)
                signals.append({
                    "time": str(obj.meta.get("time")),
                    "direction": target,
                    "entry": float(obj.meta.get("close")),
                    "bos_level": state.bos_level,
                    "sweep_at": state.sweep_idx,
                    "displace_at": state.displace_idx,
                    "bos_at": state.bos_idx,
                    "entry_at": i,
                    "zone_authority": zone_auth,
                    "poi_present": _poi_present,
                    "htf_aligned": state.htf_aligned,
                    "htf_reason": state.htf_reason,
                    "zone_pd_type": state.zone_pd_type,
                })
                state.note("ENTRY", i)
                phase_seen["ENTRY"] += 1
                state.reset()  # una secuencia por senal
    return signals, phase_seen


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ict_backtest.data_feed import load_frames
    from ict_backtest.market_structure import detect_market_structure

    fr = load_frames("XAUUSD", ("D1", "H4"))
    h4 = detect_market_structure(fr["H4"])
    d1 = detect_market_structure(fr["D1"])

    def est_htf_fn(i):
        t = h4.iloc[i]["time"]
        d1row = closed_row_at_time(d1, t, "1D")
        return {"trend": str(d1row.get("trend", "RANGING")),
                "sweep_up": bool(d1row.get("liquidity_sweep_up", False)),
                "sweep_down": bool(d1row.get("liquidity_sweep_down", False))}

    sigs, phases = run_sequence(h4, est_htf_fn, SequenceConfig(), ltf_tf="H4")
    print(f"Senales secuencia (D1->H4): {len(sigs)}")
    print(f"Fases alcanzadas: {phases}")
    if sigs:
        print("primera:", sigs[0])
