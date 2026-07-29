"""FASE NUCLEO — Motor de decisión por Pipeline (jerarquía, no votación).

Cada temporalidad cumple UNA responsabilidad dentro de una jerarquía ICT:

    Stage 1  BiasEngine      (D1)   -> macro
    Stage 2  ContextEngine   (H4)   -> confirma bias macro
    Stage 3  IntradayEngine  (H1)   -> contexto operativo del día
    Stage 4  POIEngine       (M15)  -> zona OTE/OB/FVG + invalidación
    Stage 5  TriggerEngine   (M5)   -> [EN CONSTRUCCIÓN] Two-pass futuro
    Stage 6  RiskEngine             -> riesgo día / R:R
    Stage 7  ExecutionPlan          -> plan entry/SL/TP + handoff CSV

`run_pipeline` junta los stages en `context_alignment`, que ES la fuente de verdad
del veredicto. NO hay "votos": el sesgo se deriva de la ALINEACIÓN de capas.

El campo `votes` se mantiene SOLO como LEGADO derivado para no romper la UI que hoy
lo lee (resumen_widget). No es fuente de verdad: se calcula desde context_alignment.
Cuando la UI migre a context_alignment, se elimina.

Funciones PURAS: cada stage recibe SOLO su TF (o None) y devuelve dict.
Reutiliza `analyze_timeframe` (ya genérico) de rutina_eurusd; no duplica detectores.
"""
from __future__ import annotations

from typing import Any


def _side_from_trend(trend: str) -> str:
    """Mapea tendencia a lado operativo."""
    return {"BULLISH": "LONG", "BEARISH": "SHORT", "RANGING": "NEUTRAL"}.get(trend, "NEUTRAL")


def _ok(trend: str) -> bool:
    return trend in ("BULLISH", "BEARISH")


# ---------------------------------------------------------------------------
# Stage 1 — Bias macro (D1)
# ---------------------------------------------------------------------------
def bias_engine(d1: dict) -> dict:
    """Sesgo macro: hacia dónde quiere ir el precio a largo plazo."""
    trend = d1.get("trend", "RANGING")
    return {
        "side": _side_from_trend(trend),
        "ok": _ok(trend),
        "trend": trend,
        "note": f"D1 {trend}",
    }


# ---------------------------------------------------------------------------
# Stage 2 — Context (H4): confirma el bias macro
# ---------------------------------------------------------------------------
def context_engine(h4: dict, macro_side: str) -> dict:
    """El H4 confirma (o no) el sesgo macro. No vota: valida coherencia."""
    trend = h4.get("trend", "RANGING")
    side = _side_from_trend(trend)
    aligned = _ok(trend) and (side == macro_side)
    return {
        "side": side,
        "aligned": aligned,
        "trend": trend,
        "note": f"H4 {trend}" + ("" if aligned else " (no confirma macro)"),
    }


# ---------------------------------------------------------------------------
# Stage 3 — Intraday (H1): contexto operativo del día  [SUB-FASE H1]
# ---------------------------------------------------------------------------
def intraday_engine(h1: dict) -> dict:
    """Contexto operativo intradía. La tesis marca H1 como HTF intradía principal."""
    trend = h1.get("trend", "RANGING")
    return {
        "side": _side_from_trend(trend),
        "ok": _ok(trend),
        "trend": trend,
        "note": f"H1 {trend}",
    }


# ---------------------------------------------------------------------------
# Stage 4 — POI (M15): zona de interés
# ---------------------------------------------------------------------------
def _side_from_dir(v: Any) -> str | None:
    """Normaliza indicadores de dirección (ob_dir str / bos_dir int) a LONG/SHORT."""
    if v in ("bullish", "LONG", "long", 1):
        return "LONG"
    if v in ("bearish", "SHORT", "short", -1):
        return "SHORT"
    return None


def poi_engine(
    m15: dict,
    d1: dict | None = None,
    h4: dict | None = None,
    h1: dict | None = None,
    bias_side: str | None = None,
) -> dict:
    """Zona de interés M15 rankeada según libro 21 (PD Array anclado + stacking).

    POI = BONUS de calidad (cap 20), NUNCA filtro duro. `valid` se mantiene
    EXACTAMENTE igual: (has_ob or has_fvg) and has_ote. Los campos nuevos
    (tier/anchored/stacked/displacement/quality_bonus/tier_note) son diagnóstico
    y bonus; jamás anulan la señal. Función pura, sin I/O ni estado.

    Premium/Discount: donde cae el POI respecto al rango del D1 (dealing range).
    Reusa zone_high/zone_low del D1 (sin carga nueva). Sin D1 -> PD PENDING honesto.
    """
    has_ob = m15.get("ob_dir", "-") not in ("-", None)
    has_fvg = m15.get("fvg_state", "-") not in ("-", None)
    ote = m15.get("ote_long", (0.0, 0.0)) or m15.get("ote_short", (0.0, 0.0))
    has_ote = bool(ote) and any(float(x) != 0.0 for x in ote)
    valid = bool(has_ob or has_fvg) and has_ote

    # Premium/Discount del POI vs rango D1
    premium_discount = "PENDING"
    pd_aligned = False
    mid_m15 = None
    plo = m15.get("zone_low")
    phi = m15.get("zone_high")
    if plo not in (None, 0, 0.0) and phi not in (None, 0, 0.0):
        mid_m15 = (float(plo) + float(phi)) / 2.0
    if d1 is not None:
        lo = d1.get("zone_low")
        hi = d1.get("zone_high")
        if lo not in (None, 0, 0.0) and hi not in (None, 0, 0.0) and mid_m15 is not None:
            mid = (float(lo) + float(hi)) / 2.0
            premium_discount = "DISCOUNT" if mid_m15 < mid else "PREMIUM"
            # alineado si POI en DISCOUNT (lado "comprable" del rango D1)
            pd_aligned = (premium_discount == "DISCOUNT")

    # --- Ranking libro 21 ---------------------------------------------------
    # side_poi: dirección del PD Array (OB M15 -> BOS M15 -> bias_side de fallback)
    side_poi = _side_from_dir(m15.get("ob_dir")) \
        or _side_from_dir(m15.get("bos_dir")) \
        or (bias_side if bias_side in ("LONG", "SHORT") else None)

    # cond_zona: PD Array en la zona correcta del rango D1 (PENDING si sin D1)
    cond_zona = None
    if premium_discount != "PENDING" and side_poi is not None:
        cond_zona = (premium_discount == "DISCOUNT" and side_poi == "LONG") \
            or (premium_discount == "PREMIUM" and side_poi == "SHORT")

    cond_sesgo = bias_side in ("LONG", "SHORT") and side_poi == bias_side

    displacement = (
        m15.get("bos_status") == "active"
        and _side_from_dir(m15.get("bos_dir")) == side_poi
        and side_poi is not None
    )

    anchored = bool(
        h4 is not None
        and h4.get("bos_status") == "active"
        and _side_from_dir(h4.get("bos_dir")) == side_poi
        and side_poi is not None
    )

    stacked = False
    if h1 is not None and mid_m15 is not None and side_poi is not None:
        h1_lo = h1.get("zone_low")
        h1_hi = h1.get("zone_high")
        h1_side = _side_from_dir(h1.get("bos_dir")) or _side_from_trend(h1.get("trend", ""))
        if h1_lo not in (None, 0, 0.0) and h1_hi not in (None, 0, 0.0):
            lo_h1, hi_h1 = float(h1_lo), float(h1_hi)
            if lo_h1 > hi_h1:
                lo_h1, hi_h1 = hi_h1, lo_h1
            in_zone = lo_h1 <= mid_m15 <= hi_h1
            stacked = bool(in_zone and h1_side == side_poi)

    # Tier
    if not valid:
        tier = "PENDING"
    elif cond_zona is False:
        tier = "SKIP"  # wrong-side: diagnóstico, NO anula valid
    elif has_ob and has_fvg and displacement:
        tier = "T1"  # BPR proxy
    elif (has_ob ^ has_fvg) and displacement:
        tier = "T2"
    elif has_ob or has_fvg:
        tier = "T3"
    else:
        tier = "PENDING"

    # Stacking eleva el tier
    if stacked and tier == "T2":
        tier = "T1"
    elif stacked and tier == "T3":
        tier = "T2"

    # Quality bonus (cap 20). SKIP/PENDING => 0 (wrong-side/incompleto no bonifica).
    bonus = 0
    if valid and tier in ("T1", "T2", "T3"):
        bonus += {"T1": 10, "T2": 7, "T3": 4}[tier]
        if cond_zona and cond_sesgo:
            bonus += 5  # absorbe el pd_bonus suelto anterior
        if anchored:
            bonus += 5
    quality_bonus = min(bonus, 20)

    tier_note = (
        f"{tier}"
        + (" apilado" if stacked else "")
        + (" anclado" if anchored else "")
        + (" wrong-side" if tier == "SKIP" else "")
    )

    return {
        "valid": valid,
        "has_ob": bool(has_ob),
        "has_fvg": bool(has_fvg),
        "has_ote": has_ote,
        "premium_discount": premium_discount,
        "pd_aligned": pd_aligned,
        "tier": tier,
        "anchored": anchored,
        "stacked": stacked,
        "displacement": bool(displacement),
        "quality_bonus": quality_bonus,
        "tier_note": tier_note,
        "invalidation": m15.get("zone_high") if m15.get("ob_dir") == "SHORT" else m15.get("zone_low"),
        "target": m15.get("zone_low") if m15.get("ob_dir") == "SHORT" else m15.get("zone_high"),
        "note": f"OB={has_ob} FVG={has_fvg} OTE={has_ote} PD={premium_discount} tier={tier}",
    }


# ---------------------------------------------------------------------------
# Stage 5 — Trigger (M5): Two-pass real. El Trigger NO piensa: reporta ambos
# lados (long/short) con sus checks (sweep/bos/fvg). El VerdictBuilder elige
# segun el contexto. Flujo ICT: Sweep -> Displacement(BOS) -> FVG (el FVG ya
# implica displacement en el detector existente, no se anade detector nuevo).
# ---------------------------------------------------------------------------
# Buffer de pullback: fracción del ATR M5 alrededor de la entry_zone (§5A).
PULLBACK_BUFFER_ATR = 0.10


def _entry_zone(m5: dict, poi: dict | None, side: str):
    """Zona de retroceso (entry_zone) para UN lado. Prioridad: OB M5 > POI M15.

    Devuelve (lo, hi) ordenado o None si no hay zona computable (§5A pseudocódigo).
    """
    ob_dir = _side_from_dir(m5.get("ob_dir"))
    ob_top = m5.get("ob_top")
    ob_bottom = m5.get("ob_bottom")
    if ob_dir == side and ob_top not in (None, 0, 0.0) and ob_bottom not in (None, 0, 0.0):
        lo, hi = float(ob_bottom), float(ob_top)
        return (lo, hi) if lo <= hi else (hi, lo)
    if poi is not None and poi.get("valid"):
        inv = poi.get("invalidation")
        tgt = poi.get("target")
        if inv not in (None, 0, 0.0) and tgt not in (None, 0, 0.0):
            lo, hi = float(inv), float(tgt)
            return (lo, hi) if lo <= hi else (hi, lo)
    return None


def _eval_side(m5: dict, side: str, poi: dict | None = None,
               session: dict | None = None) -> dict:
    """Valida el Two-pass + máquina de estados para UN lado (§5A).

    Devuelve checks (sweep/bos/fvg/pullback/reaction) + valid + machine_state
    + entry_zone. valid=True SOLO en TRIGGER_READY.
    """
    if side == "LONG":
        sweep = bool(m5.get("sweep_up"))
        bos = m5.get("bos_dir", 0) == 1 and m5.get("bos_status") == "active"
        fvg = m5.get("fvg_state", "-") not in ("-", None, "")
    else:  # SHORT
        sweep = bool(m5.get("sweep_down"))
        bos = m5.get("bos_dir", 0) == -1 and m5.get("bos_status") == "active"
        fvg = m5.get("fvg_state", "-") not in ("-", None, "")

    structure = sweep and bos and fvg
    checks = {"sweep": sweep, "bos": bos, "fvg": fvg,
              "pullback": None, "reaction": None}

    # Estado por defecto
    machine_state = "PENDING"
    entry_zone = None
    valid = False

    if not structure:
        machine_state = "PENDING"
        missing = [k for k in ("sweep", "bos", "fvg") if not checks[k]]
        reason = f"Esperando {'/'.join(missing)}"
        return {"valid": valid, "checks": checks, "reason": reason,
                "side": side, "machine_state": machine_state,
                "entry_zone": entry_zone}

    entry_zone = _entry_zone(m5, poi, side)
    if entry_zone is None:
        # Estructura OK pero sin zona: EN CONSTRUCCIÓN.
        machine_state = "STRUCTURE_READY"
        checks["pullback"] = None
        return {"valid": valid, "checks": checks,
                "reason": "Estructura lista, sin zona calculable (en construcción)",
                "side": side, "machine_state": machine_state,
                "entry_zone": entry_zone}

    lo, hi = entry_zone
    px = m5.get("close")
    atr = m5.get("atr")
    try:
        atr_f = float(atr)
        if atr_f != atr_f:  # NaN
            atr_f = 0.0
    except (TypeError, ValueError):
        atr_f = 0.0
    buf = PULLBACK_BUFFER_ATR * atr_f

    if px is None:
        pullback = False
    else:
        px = float(px)
        pullback = (lo - buf) <= px <= (hi + buf)
    checks["pullback"] = pullback

    if not pullback:
        machine_state = "WAITING_PULLBACK"
        checks["reaction"] = False
        return {"valid": valid, "checks": checks,
                "reason": "Estructura lista, precio fuera de zona (WAITING_PULLBACK)",
                "side": side, "machine_state": machine_state,
                "entry_zone": entry_zone}

    # En zona: evaluar reacción (heurística v1: close del lado correcto + BOS activo)
    side_ok = (px >= lo) if side == "LONG" else (px <= hi)
    reaction = bool(side_ok and m5.get("bos_status") == "active")
    checks["reaction"] = reaction

    if not reaction:
        machine_state = "WAITING_PULLBACK"
        return {"valid": valid, "checks": checks,
                "reason": "En zona, sin reacción (WAITING_PULLBACK)",
                "side": side, "machine_state": machine_state,
                "entry_zone": entry_zone}

    # Reacción OK: gate de sesión decide TRIGGER_READY vs OFF_SESSION vs espera.
    sess_state = session.get("state") if session else "UNKNOWN"
    if sess_state == "UNKNOWN":
        machine_state = "WAITING_PULLBACK"
        reason = "Setup listo, sin reloj (session UNKNOWN)"
    elif session and session.get("in_killzone"):
        machine_state = "TRIGGER_READY"
        valid = True
        reason = "Sweep + BOS + FVG + pullback + reacción en killzone"
    else:
        machine_state = "TRIGGER_READY_OFF_SESSION"
        reason = "Setup listo, fuera de killzone"

    return {"valid": valid, "checks": checks, "reason": reason,
            "side": side, "machine_state": machine_state,
            "entry_zone": entry_zone}


def _session_gate(now_utc) -> dict:
    """Gate de sesión killzone puro (§5A). now_utc=None -> UNKNOWN."""
    if now_utc is None:
        return {"in_killzone": None, "name": "", "state": "UNKNOWN"}
    from .timezone import killzone_en
    name = killzone_en(now_utc)
    return {"in_killzone": bool(name), "name": name,
            "state": "OPEN" if name else "CLOSED"}


def trigger_engine(m5: dict | None = None, poi: dict | None = None,
                   now_utc=None) -> dict:
    """Trigger de entrada (M5) con máquina de estados + gate de sesión (§5A).

    Reporta AMBOS lados; no recibe bias (el VerdictBuilder elige). Función PURA:
    el reloj entra por now_utc (sin datetime.now() interno).

    Sin M5 (None) -> PENDING honesto en los dos lados (no inventa señal).
    """
    session = _session_gate(now_utc)
    session_check = None if session["state"] == "UNKNOWN" else session["in_killzone"]

    if m5 is None:
        pending = {
            "valid": False, "state": "PENDING",
            "note": "M5 trigger PENDING (sin datos M5)",
            "checks": {"sweep": False, "bos": False, "fvg": False,
                       "pullback": None, "reaction": None},
            "machine_state": "PENDING", "entry_zone": None,
        }
        return {
            "side": None, "valid": False, "state": "PENDING",
            "note": "M5 trigger PENDING (sin datos M5)",
            "checks": {"sweep": False, "bos": False, "fvg": False,
                       "pullback": False, "reaction": False,
                       "session": session_check},
            "session": session,
            "long": {**pending, "side": "LONG"},
            "short": {**pending, "side": "SHORT"},
        }

    long = _eval_side(m5, "LONG", poi, session)
    short = _eval_side(m5, "SHORT", poi, session)

    def _or_none(a, b):
        if a is None and b is None:
            return None
        return bool(a) or bool(b)

    valid = long["valid"] or short["valid"]
    return {
        "side": None, "valid": valid,  # el lado lo resuelve el VerdictBuilder
        "state": "PENDING",
        "note": "trigger reporta ambos lados; VerdictBuilder elige",
        "checks": {
            "sweep": long["checks"]["sweep"] or short["checks"]["sweep"],
            "bos": long["checks"]["bos"] or short["checks"]["bos"],
            "fvg": long["checks"]["fvg"] or short["checks"]["fvg"],
            "pullback": _or_none(long["checks"]["pullback"], short["checks"]["pullback"]),
            "reaction": _or_none(long["checks"]["reaction"], short["checks"]["reaction"]),
            "session": session_check,
        },
        "session": session,
        "long": long,
        "short": short,
    }


# ---------------------------------------------------------------------------
# Stage 4b — SMT (Smart Money Technique): par correlacionado (EURUSD vs GBPUSD)
# en el MISMO TF (H1). La senal vive en el DESENCUENTRO: si EURUSD hace sweep
# y GBPUSD NO, el que se queda atras delata la trampa. El SMT NO piensa:
# reporta divergencia de AMBOS lados; el VerdictBuilder lo usa como filtro.
# Reusa analyze_timeframe en ambos pares (cero detectores nuevos).
# ---------------------------------------------------------------------------
def _eval_smt_side(a: dict, b: dict, side: str) -> dict:
    """SMT para UN lado. a=EURUSD, b=par correlacionado, mismo TF.

    La senal vive en el DESENCUENTRO (cruzado):
    - EURUSD barre ARRIBA (sweep_up) y GBPUSD NO -> trampa de COMPRA ->
      diverge SHORT (el sesgo alcista de EURUSD es falso).
    - EURUSD barre ABAJO (sweep_down) y GBPUSD NO -> trampa de VENTA ->
      diverge LONG (el sesgo bajista de EURUSD es falso).
    """
    eur_up = bool(a.get("sweep_up"))
    eur_down = bool(a.get("sweep_down"))
    b_up = bool(b.get("sweep_up"))
    b_down = bool(b.get("sweep_down"))
    if side == "SHORT":
        diverge = eur_up and not b_up  # EURUSD caza BSL solo -> trampa alcista
        note = "EURUSD sweep_up sin GBPUSD -> divergencia SHORT (trampa)" if diverge \
            else "EURUSD/GBPUSD alineados arriba"
    else:  # LONG
        diverge = eur_down and not b_down  # EURUSD caza SSL solo -> trampa bajista
        note = "EURUSD sweep_down sin GBPUSD -> divergencia LONG (trampa)" if diverge \
            else "EURUSD/GBPUSD alineados abajo"
    return {"diverge": diverge, "side": side, "note": note}


def smt_engine(a: dict | None = None, b: dict | None = None) -> dict:
    """SMT entre dos pares correlacionados en el mismo TF (H1).

    Sin segundo par (b=None) -> PENDING honesto (no inventa correlacion).
    """
    if a is None or b is None:
        pending = {"diverge": False, "side": "LONG",
                   "note": "SMT PENDING (sin segundo par)"}
        return {
            "diverge": False, "state": "PENDING",
            "note": "SMT PENDING (sin segundo par correlacionado)",
            "long": {**pending, "side": "LONG"},
            "short": {**pending, "side": "SHORT"},
        }
    long = _eval_smt_side(a, b, "LONG")
    short = _eval_smt_side(a, b, "SHORT")
    return {
        "diverge": long["diverge"] or short["diverge"],
        "state": "DIVERGE" if (long["diverge"] or short["diverge"]) else "ALIGNED",
        "note": long["note"] if long["diverge"] else (short["note"] if short["diverge"] else "pares alineados"),
        "long": long,
        "short": short,
    }
# ---------------------------------------------------------------------------
# Stage extra — Régimen de mercado (volatilidad por RANGO PURO, SIN ATR)
# ---------------------------------------------------------------------------
# Ruben, Fase 1 (ATR -> RANGO): la volatilidad del sistema se lee de
# ict_backtest._util.avg_candle_range (rango high-low promedio), NUNCA de ATR.
# regime_engine es PURO: recibe el rango reciente y el histórico ya calculados
# por el motor (engine.run_cycle) y clasifica. Sin datos -> PENDING honesto.
REGIME_HIGH_RATIO = 1.5   # rango reciente >= 1.5x histórico -> HIGH_VOL
REGIME_LOW_RATIO = 0.6    # rango reciente <= 0.6x histórico -> LOW_VOL


def regime_engine(recent: float | None = None, hist: float | None = None) -> dict:
    """Clasifica el régimen de volatilidad por rango puro (SIN ATR).

    recent = rango promedio de las velas recientes (avg_candle_range corto).
    hist   = rango promedio histórico (avg_candle_range largo, línea base).
    ratio = recent / hist. Sin datos válidos -> PENDING (no inventa régimen).
    """
    try:
        r = float(recent)
        h = float(hist)
    except (TypeError, ValueError):
        return {"state": "PENDING", "ratio": None,
                "note": "régimen PENDING (sin rango calculado)"}
    if r != r or h != h or h <= 0.0:  # NaN o histórico nulo
        return {"state": "PENDING", "ratio": None,
                "note": "régimen PENDING (rango histórico nulo)"}
    ratio = r / h
    if ratio >= REGIME_HIGH_RATIO:
        state, note = "HIGH_VOL", "volatilidad alta (rango expandido)"
    elif ratio <= REGIME_LOW_RATIO:
        state, note = "LOW_VOL", "volatilidad baja (rango comprimido)"
    else:
        state, note = "NORMAL", "volatilidad normal"
    return {"state": state, "ratio": round(ratio, 3), "note": note}


def _confidence(macro_ok, ctx_aligned, intraday_ok, poi_valid, trigger_valid) -> int:
    """Confianza por ALINEACIÓN de capas, no por conteo de votos."""
    score = 0
    if macro_ok:
        score += 25
    if ctx_aligned:
        score += 25
    if intraday_ok:
        score += 20
    if poi_valid:
        score += 20
    if trigger_valid:
        score += 10
    return score


def run_pipeline(d1: dict, h4: dict, h1: dict, m15: dict, m5: dict | None = None,
                 smt_a: dict | None = None, smt_b: dict | None = None,
                 regime_range: tuple | None = None) -> dict:
    """Ejecuta el pipeline jerárquico y devuelve el veredicto.

    Salida:
      context_alignment: fuente de verdad (macro/intraday/poi/trigger/confidence/stages)
      bias:              lado dominante derivado de macro+intraday
      votes:             LEGADO derivado (no fuente de verdad) para no romper UI
      reasons:           explicación por etapa
    """
    macro = bias_engine(d1)
    ctx = context_engine(h4, macro["side"])
    intraday = intraday_engine(h1)

    # Sesgo derivado de capas altas (igual que luego se asigna a `bias`).
    # Se calcula ANTES de poi_engine para pasarle bias_side (cálculo puro, sin
    # dependencia circular: no usa nada del poi).
    if macro["side"] == intraday["side"] and macro["side"] != "NEUTRAL":
        derived_bias = macro["side"]
    elif macro["side"] == "NEUTRAL" and intraday["side"] != "NEUTRAL":
        derived_bias = intraday["side"]
    else:
        derived_bias = "NEUTRAL (esperar)"

    bias_side = derived_bias if derived_bias in ("LONG", "SHORT") else None
    poi = poi_engine(m15, d1, h4=h4, h1=h1, bias_side=bias_side)
    from .timezone import utc_now
    trig = trigger_engine(m5, poi=poi, now_utc=utc_now())
    smt = smt_engine(smt_a, smt_b)

    # Régimen de mercado (volatilidad por RANGO PURO, sin ATR). El motor pasa
    # (recent, hist) ya calculados con avg_candle_range; sin datos -> PENDING.
    if regime_range is not None:
        regime = regime_engine(regime_range[0], regime_range[1])
    else:
        regime = regime_engine(None, None)

    # VerdictBuilder: elige el lado del trigger segun el sesgo derivado.
    # NO opera en contra del macro (si el lado ganador no valida, PENDING).
    # El Trigger no recibio bias; solo reporto ambos lados.
    chosen = None
    if derived_bias in ("LONG", "SHORT"):
        cand = trig["long"] if derived_bias == "LONG" else trig["short"]
        if cand["valid"]:
            chosen = cand
    trigger_valid = chosen is not None
    trigger_state = "VALID" if trigger_valid else "PENDING"
    trigger_side = chosen["side"] if chosen else None

    # machine_state fino del lado elegido por el sesgo (para trigger_machine).
    if derived_bias in ("LONG", "SHORT"):
        _cand_side = trig["long"] if derived_bias == "LONG" else trig["short"]
        trigger_machine = _cand_side.get("machine_state", "PENDING")
    else:
        trigger_machine = "PENDING"

    # Sesgo dominante final (igual logica que arriba, para el campo `bias`).
    bias = derived_bias

    # VerdictBuilder SMT: el SMT es FILTRO de trampa, no opera solo.
    # Si SMT diverge en contra del sesgo derivado -> resta confianza (alerta).
    # Si alineado -> bonus de alineacion inter-par. Si PENDING -> neutral.
    smt_penalty = 0
    if smt["diverge"] and derived_bias in ("LONG", "SHORT"):
        # diverge SHORT cuando sesgo LONG = trampa de compra; y viceversa
        trap_side = "SHORT" if derived_bias == "LONG" else "LONG"
        if smt[trap_side.lower()]["diverge"]:
            smt_penalty = -10
    smt_bonus = 5 if smt["state"] == "ALIGNED" else 0
    smt_conf = max(0, smt_bonus + smt_penalty)

    # VerdictBuilder Premium/Discount: el bonus de alineación PD ahora está
    # ABSORBIDO dentro de poi["quality_bonus"] (libro 21). No se suma pd_bonus
    # suelto para evitar doble conteo.
    confidence = _confidence(
        macro["ok"], ctx["aligned"], intraday["ok"], poi["valid"], trigger_valid
    ) + smt_conf + poi.get("quality_bonus", 0)

    # Setup quality: calidad combinada del setup (0-100) a partir de POI +
    # BOS/CHOCH/sweep reales del LTF, SIN reloj ni look-ahead.
    # Componentes: POI tier (max 30), anchored H4 (+10), BOS distance (<8b +25,
    # <=16b +10), sweep en contra del sesgo (+15), proximidad precio a POI
    # (retrace <= fib 0.618 +10, <= 0.786 +5).
    setup_quality_pct = 0
    if bias in ("LONG", "SHORT") and poi.get("valid"):
        # 1) POI tier (peso mayor: el POI es el gatillo físico)
        setup_quality_pct += {"T1": 30, "T2": 20, "T3": 10}.get(poi.get("tier", "PENDING"), 0)
        # 2) HTF anchor
        if poi.get("anchored"):
            setup_quality_pct += 10
        # 3) BOS distance (evento estructural reciente en dirección del sesgo)
        _bdir = m15.get("bos_dir", 0)
        _bdist = int(m15.get("bos_distance_bars", 0) or 0)
        _bias_side_dir = 1 if bias == "LONG" else (-1 if bias == "SHORT" else 0)
        if _bias_side_dir != 0 and _bdir == _bias_side_dir and _bdist > 0:
            if _bdist <= 8:
                setup_quality_pct += 25
            elif _bdist <= 16:
                setup_quality_pct += 10
        # 4) Sweep en dirección opuesta al sesgo = liquidez tomada = favorable
        _sweep_opposite = ((bias == "LONG" and bool(m15.get("sweep_down")))
                         or (bias == "SHORT" and bool(m15.get("sweep_up"))))
        if _sweep_opposite:
            setup_quality_pct += 15
        # 5) Proximidad precio actual al OTE (cuán dentro de la pierna está)
        # Aproximación: usa retrace del último swing_formado hacia precio.
        # Fase 1 simple: usar bos_distance como proxy (menor distance = más cerca).
        if _bdist > 0 and _bdist <= 6:
            setup_quality_pct += 10
        elif _bdist > 0 and _bdist <= 12:
            setup_quality_pct += 5
    setup_quality_pct = max(0, min(100, setup_quality_pct))

    # Stage M5: checks REALES (no stub). Muestra el lado elegido si valido.
    if chosen is not None:
        c = chosen["checks"]
        m5_stage = (f"{'✔' if c['sweep'] else '□'} sweep "
                    f"{'✔' if c['bos'] else '□'} bos "
                    f"{'✔' if c['fvg'] else '□'} fvg ({chosen['side']})")
    else:
        m5_stage = "□ sweep / □ bos / □ fvg (PENDING)"
    stages = {
        "D1": "✔" if macro["ok"] else "□",
        "H4": "✔" if ctx["aligned"] else "□",
        "H1": "✔" if intraday["ok"] else "□",
        "M15_POI": (f"✔ {poi['tier']} {poi.get('tier_note', '').strip()}".strip()
                    if poi["valid"] else "□ sin POI"),
        "SMT": "✔" if smt["state"] == "ALIGNED" else ("□ diverge" if smt["state"] == "DIVERGE" else "□ PENDING"),
        "M5_TRIGGER": m5_stage,
    }

    context_alignment = {
        "macro": macro["side"],
        "intraday": intraday["side"],
        "poi": "VALID" if poi["valid"] else "INVALID",
        "poi_tier": poi.get("tier", "PENDING"),
        "poi_anchored": poi.get("anchored", False),
        "poi_stacked": poi.get("stacked", False),
        "poi_quality_bonus": poi.get("quality_bonus", 0),
        "premium_discount": poi.get("premium_discount", "PENDING"),
        "bos_signal": str(m15.get("bos_signal", "NONE")),
        "bos_distance_bars": int(m15.get("bos_distance_bars", 0) or 0),
        "sweep_up_bars": int(m15.get("sweep_up_bars", 0) or 0),
        "sweep_down_bars": int(m15.get("sweep_down_bars", 0) or 0),
        "range_pips": float(m15.get("range_pips", 0.0) or 0.0),
        "trigger": trigger_state,
        "trigger_machine": trigger_machine,
        "smt": smt["state"],
        "smt_note": smt.get("note", ""),
        "regime": regime["state"],
        "regime_note": regime["note"],
        "confidence": confidence,
        "setup_quality_pct": int(setup_quality_pct),
        "exec_m5_score": int(m15.get("exec_m5_score", 0) or 0),
        "exec_m5_matches": m15.get("exec_m5_matches", []),
        "exec_position_size_multiplier": {
            0: 1.0,
            1: 0.5,
            2: 1.0,
        }.get(int(m15.get("exec_m5_score", 0) or 0), 1.25),
        "stages": stages,
    }

    # trigger rico para el dashboard (dict completo, no solo el string del estado)
    trigger_out = {
        "side": trigger_side,
        "valid": trigger_valid,
        "state": trigger_state,
        "note": chosen["reason"] if chosen else "trigger PENDING (esperando confirmacion M5)",
        "long": trig["long"],
        "short": trig["short"],
    }

    # votes LEGADO: refleja la alineación de capas, NO es democracia.
    # Se elimina cuando la UI migre a context_alignment.
    n_long = sum(1 for s in (macro["side"], ctx["side"], intraday["side"]) if s == "LONG")
    n_short = sum(1 for s in (macro["side"], ctx["side"], intraday["side"]) if s == "SHORT")
    votes = {"LONG": n_long, "SHORT": n_short}

    reasons = [
        macro["note"],
        ctx["note"],
        intraday["note"],
        f"POI M15: {poi['note']}",
        f"Premium/Discount: {poi.get('premium_discount', 'PENDING')}",
        f"Trigger M5: {trigger_out['note']}",
        f"SMT: {smt['note']}",
        f"Confianza: {confidence}%",
    ]

    return {
        "bias": bias,
        "context_alignment": context_alignment,
        "votes": votes,  # LEGADO
        "reasons": reasons,
        "invalidation": poi.get("invalidation"),
        "target": poi.get("target"),
        "poi": poi,
        "trigger": trigger_out,
        "smt": smt,
    }
