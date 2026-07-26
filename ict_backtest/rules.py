"""ict_backtest/rules.py — Reglas ICT rescatadas del dashboard observador.

Estas reglas SON las mismas que usa app_observador/ui/resumen_widget.py
(checklist_intradia / checklist_scalping). Se rescatan AQUI como funciones
PURAS para que el backtest use EXACTAMENTE la misma logica que el observador
en vivo (sin desincronizacion entre "lo que ves" y "lo que se prueba").

Diferencia clave vs el dashboard:
  - El dashboard usa killzone_activa_ahora() (reloj de la PC).
  - AQUI la killzone se calcula del TIMESTAMP de la vela (backtest historico).
  - Todo es puro: recibe `estructura: dict` (por TF) y devuelve checklist + puntuacion.

Modelos cubiertos (docs/ict/*.md):
  - INTRADIA  : PO3 / Turtle Soup  (H1/H4/M15)
  - SCALPING  : Silver Bullet      (M1/M5, sweep en M15)
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from signals.po3 import evaluate_po3

# DEPRECATED (deuda ROJA #5): tabla de bandas UTC FIJAS todo el año. Era un
# offset fijo disfrazado (London 7-10 UTC solo vale en invierno EST; en verano
# EDT London real es 06-09 UTC). killzone_en YA NO la usa: se conserva SOLO
# porque scripts de diagnóstico (deep_diagnostic/forensic_audit) y el dashboard
# la importan para imprimir referencias. NO usar en lógica de edge.
KILLZONES_UTC: dict[str, tuple[float, float]] = {
    "Asia": (0.0, 3.0),
    "London Open": (7.0, 10.0),
    "New York AM": (12.5, 15.0),   # ~10-11 ET
    "New York PM": (15.0, 17.5),
    "London Close": (15.5, 17.5),
}

# FUENTE ÚNICA de killzones del edge (tesis §15): las 3 ventanas OBLIGATORIAS
# (London Open / NY AM / NY PM) definidas en ET FIJO (horario local del
# mentorship ICT). Se convierten a UTC POR DIA usando
# ZoneInfo('America/New_York') -> DST automático. NUNCA offset fijo.
# Clave -> ((h_ini, m_ini), (h_fin, m_fin)) en ET local.
KILLZONES_ET: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "London Open": ((2, 0), (5, 0)),    # 02:00-05:00 ET  (London 07:00-10:00 UK)
    "New York AM": ((10, 0), (12, 0)),  # 10:00-12:00 ET  (Silver Bullet)
    "New York PM": ((14, 0), (17, 0)),  # 14:00-17:00 ET  (NY PM session)
}

# Etiqueta corta usada por detectors/killzones.py (pintar banda de fondo).
_KZ_ET_TO_SHORT = {
    "London Open": "LDN_OPEN",
    "New York AM": "NY_AM",
    "New York PM": "NY_PM",
}


def server_to_utc(ts: datetime, broker_tz) -> datetime:
    """Convierte hora del SERVIDOR (broker MT5) a UTC canónico del proyecto.

    PRINCIPIO DE RUBEN (DEC-009i): la hora la da el servidor (broker time); se
    CONVIERTE via ZoneInfo (DST automático) a UTC. NUNCA offset fijo hardcodeado.
    - Si `ts` es naive, se asume que está en `broker_tz`.
    - Si `ts` es tz-aware, se reconvertiza a UTC desde su zona.
    `broker_tz` es ZoneInfo | str (nombre IANA).
    """
    if isinstance(broker_tz, str):
        broker_tz = ZoneInfo(broker_tz)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=broker_tz)
    return ts.astimezone(timezone.utc)


def _et_band_to_utc(et_h: int, et_m: int, day_utc: datetime) -> datetime:
    """Convierte una hora ET fija del DIA de `day_utc` a su instante UTC real.

    Se ancla al dia UTC de la vela y se aplica el DST vigente ese dia via
    ZoneInfo('America/New_York'). Así la ventana UTC correcta se calcula sin
    offset fijo.
    """
    ny = ZoneInfo("America/New_York")
    # Construir el instante ET del dia de la vela (localize naive a NY).
    et_local = datetime(day_utc.year, day_utc.month, day_utc.day, et_h, et_m,
                        tzinfo=ny)
    return et_local.astimezone(timezone.utc)


def killzone_windows_utc(day_utc: datetime) -> dict[str, tuple[datetime, datetime]]:
    """Tabla de PRIMERA CLASE de las 3 killzones (tesis §15) para un día dado.

    Devuelve {'London Open'|'New York AM'|'New York PM': (ini_utc, fin_utc)}
    con las ventanas ET fijas de KILLZONES_ET convertidas al UTC REAL de ese
    día vía ZoneInfo('America/New_York') -> DST automático, sin offset fijo.
    Es la ÚNICA fuente que consume killzone_en (con o sin broker_tz).
    """
    return {
        nombre: (_et_band_to_utc(h0, m0, day_utc), _et_band_to_utc(h1, m1, day_utc))
        for nombre, ((h0, m0), (h1, m1)) in KILLZONES_ET.items()
    }


def _killzone_en_utc(utc_ts: datetime) -> str:
    """Killzone activa evaluando la tabla de ventanas UTC del día (DST-aware)."""
    for nombre, (ini, fin) in killzone_windows_utc(utc_ts).items():
        if ini <= utc_ts < fin:
            return nombre
    return ""


def killzone_en(ts: datetime, broker_tz: ZoneInfo | str | None = None) -> str:
    """Killzone activa para un timestamp de vela. Backtest-safe.

    REESCRITURA DE RAÍZ (deuda ROJA #5, tesis §15). CAUSA RAÍZ del bug: había
    DOS caminos. Con broker_tz se evaluaba ET->UTC por día (correcto); sin
    broker_tz (el camino del EDGE, canonical.evaluate_signals) se evaluaba
    contra KILLZONES_UTC, bandas UTC FIJAS todo el año — un offset fijo
    disfrazado que en verano (EDT) perdía London (real 06-09 UTC) y NY PM
    (real 18-21 UTC). Ahora AMBOS caminos usan la MISMA tabla de ventanas
    killzone_windows_utc (ET->UTC por día vía ZoneInfo, DST automático).

    REGLA DE ZONA HORARIA (MDS_KILLZONES / DEC-009i):
    - broker_tz dado: PRIMERO server_to_utc (nunca evaluar hora broker cruda).
    - broker_tz None: se asume que `ts` YA viene en UTC canónico (convención
      del proyecto; ruta de canonical.py). Naive => UTC.

    Devuelve 'London Open' | 'New York AM' | 'New York PM' | ''.
    """
    if broker_tz is not None:
        utc_ts = server_to_utc(ts, broker_tz)
    else:
        utc_ts = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
        utc_ts = utc_ts.astimezone(timezone.utc)
    return _killzone_en_utc(utc_ts)


def _dir_setup(bias: str, votes: dict | None, m15: dict, counter_trend: bool = False) -> str:
    """Direccion del setup.

    A-favor (counter_trend=False): la direccion sigue al BOS/votos del exec TF
    (que coincide con la marea del HTF).
    Contratendencia (counter_trend=True): el setup opera la REVERSION, por lo
    que la direccion es el BOS/choch del exec TF TAL CUAL (ese break YA es el
    movimiento contrario a la marea del HTF). No se invierte nada.
    """
    v = votes or {}
    if v.get("LONG", 0) > v.get("SHORT", 0):
        raw = "LONG"
    elif v.get("SHORT", 0) > v.get("LONG", 0):
        raw = "SHORT"
    else:
        bd = int(m15.get("bos_dir", 0) or 0)
        raw = "LONG" if bd > 0 else "SHORT" if bd < 0 else "NEUTRAL"
    if counter_trend:
        # En contratendencia el setup opera la REVERSION: direccion OPUESTA al sesgo HTF.
        want = -1 if bias == "BULLISH" else 1 if bias == "BEARISH" else 0
        return "LONG" if want == 1 else "SHORT" if want == -1 else "NEUTRAL"
    return raw


def _sweep_dir(estructura: dict, tfs: tuple[str, ...]) -> str:
    up = any(estructura.get(tf, {}).get("sweep_up") for tf in tfs)
    down = any(estructura.get(tf, {}).get("sweep_down") for tf in tfs)
    if up and down:
        return "both"
    return "up" if up else "down" if down else "none"


def _bos_exec(estructura: dict, exec_tf: str = "M15") -> str:
    m15 = estructura.get(exec_tf, {})
    bd = int(m15.get("bos_dir", 0) or 0)
    st = m15.get("bos_status", "")
    if bd == 1 and st == "active":
        return "alcista"
    if bd == -1 and st == "active":
        return "bajista"
    if bd != 0:
        return "intentando"
    return "no"


def checklist_intradia(estructura: dict, bias: str, votes: dict | None,
                       ts: datetime | None = None, exec_tf: str = "M15",
                       htf: str = "H4", counter_trend: bool = False) -> list[str]:
    """Checklist INTRADIA (PO3/Turtle Soup). Items numerados.

    ts: timestamp de la vela para killzone historica (si None, fuera de KZ).
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest de opcion A).
    htf: TF de contexto alto para el sweep (H4 por defecto).
    counter_trend: si True, el setup opera CONTRA la marea del HTF.
    """
    items: list[str] = []
    d1 = estructura.get("D1", {})
    h4 = estructura.get(htf, {})
    m15 = estructura.get(exec_tf, {})
    label = "CONTRA-tendencia" if counter_trend else "a-favor"
    dir_setup = _dir_setup(bias, votes, m15, counter_trend)
    kz = killzone_en(ts) if ts is not None else ""

    # 1. Sesgo del dia
    if "NEUTRAL" in (bias or "") or not bias:
        items.append("FALTA: definir SESGO DEL DIA (L/S) desde H4/D1.")
    else:
        items.append(f"OK: Sesgo del dia: {bias} (setup {label}).")

    # 2. Contexto D1/H4 (en contratendencia, el HTF debe tener tendencia clara A OPONERSE)
    if counter_trend:
        if bias in ("BULLISH", "BEARISH"):
            items.append(f"OK: Contratendencia lista sobre {bias} en {htf}.")
        else:
            items.append(f"FALTA: contratendencia requiere HTF con tendencia ({bias}).")
    else:
        if d1.get("trend") in ("", "RANGING") and h4.get("trend") in ("", "RANGING"):
            items.append("FALTA: contexto D1/H4 definido (en rango -> sin marea).")
        else:
            items.append(f"OK: Contexto D1 {d1.get('trend','?')} / {htf} {h4.get('trend','?')}.")

    # 3. Killzone intradia
    if kz in ("London Open", "New York AM", "New York PM"):
        items.append(f"OK: Killzone intradia activa: {kz} (UTC).")
    else:
        items.append("FALTA: killzone intradia (London/NY) -> esperar ventana.")

    # 4. Sweep HTF/exec (en contratendencia, el sweep es de la liquidez OPUESTA al sesgo)
    sw = _sweep_dir(estructura, (htf, exec_tf))
    if sw == "none":
        items.append(f"FALTA: barrido de liquidez (sweep SSL/BSL) en {htf}/{exec_tf}.")
    else:
        items.append(f"OK: Liquidez barrida ({sw}) en {htf}/{exec_tf}.")

    # 5. BOS/CHOCH exec
    bos = _bos_exec(estructura, exec_tf)
    if counter_trend:
        # En contratendencia el disparo es un BOS en direccion OPUESTA al sesgo HTF.
        exec_row = estructura.get(exec_tf, {})
        bos_dir = int(exec_row.get("bos_dir", 0) or 0)
        choch = str(exec_row.get("choch_signal", "NONE"))
        # direccion objetivo: opuesta al sesgo
        want = -1 if bias == "BULLISH" else 1 if bias == "BEARISH" else 0
        ok = (bos_dir == want) or (want == 1 and choch == "CHOCH_BULLISH") or (want == -1 and choch == "CHOCH_BEARISH")
        if want != 0 and ok:
            nombre = "CHOCH/LONG" if want == 1 else "CHOCH/SHORT"
            items.append(f"OK: reversión {nombre} en {exec_tf} (contra {bias}).")
        else:
            items.append(f"FALTA: reversión en {exec_tf} contra {bias} (BOS={bos_dir}, CHOCH={choch}).")
    else:
        if bos == "no":
            items.append(f"FALTA: BOS/CHOCH en {exec_tf} (estructura intacta).")
        else:
            items.append(f"OK: {exec_tf} con BOS {bos}.")

    # 6. Direccion alineada
    if dir_setup == "NEUTRAL":
        items.append("FALTA: direccion del setup (votos/L-S o BOS M15).")
    else:
        items.append(f"OK: Direccion setup: {dir_setup}.")

    # 7-8. TP en liquidez opuesta + RR>=1:2 (regla de ejecucion, ver engine)
    items.append("PENDIENTE: TP en liquidez opuesta (BSL/SSL del mapa ICT).")
    items.append("PENDIENTE: RR >= 1:2 (regla Stellar).")
    return items


def checklist_scalping(estructura: dict, bias: str, votes: dict | None,
                       ts: datetime | None = None, exec_tf: str = "M15") -> list[str]:
    """Checklist SCALPING (M1/M5, Silver Bullet). Items numerados.

    ts: timestamp de la vela para ventana NY AM historica.
    exec_tf: TF de ejecucion cargado (M5/M15/M1). Lo pasa el engine de forma
    explicita (no se adivina) para evitar desincronizacion con el backtest.
    """
    items: list[str] = []
    # exec TF lo pasa el engine de forma explicita (no se adivina):
    # evita la desincronizacion que silenciaba Silver Bullet (ver AUDIT_BUG_SILVER_TF.md).
    m15 = estructura.get(exec_tf, {}) if exec_tf else {}
    dir_setup = _dir_setup(bias, votes, m15)
    kz = killzone_en(ts) if ts is not None else ""

    # 1. Ventana Silver Bullet (NY AM)
    if kz == "New York AM":
        items.append("OK: Ventana Silver Bullet activa (NY AM).")
    else:
        items.append("FALTA: ventana Silver Bullet (NY AM 10-11 ET) -> esperar.")

    # 2. Sesgo filtrado
    if "NEUTRAL" in (bias or "") or not bias:
        items.append("FALTA: sesgo del dia para filtrar solo setups a favor.")
    else:
        items.append(f"OK: Sesgo filtra setups: {bias}.")

    # 3. Sweep en el TF de ejecucion (exec_tf, explicito).
    sw = _sweep_dir(estructura, (exec_tf,)) if exec_tf else "none"
    if sw == "none":
        items.append("FALTA: sweep de SSL/BSL en el TF de ejecucion (previo al FVG M1/M5).")
    else:
        items.append(f"OK: Sweep {exec_tf} ({sw}) presente.")

    # 4. FVG M1/M5
    m5 = estructura.get("M5", {}) or {}
    m1 = estructura.get("M1", {}) or {}
    fvg_m5 = str(m5.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    fvg_m1 = str(m1.get("fvg_state", "-")).lower() not in ("-", "none", "nan", "")
    if not m5 and not m1:
        items.append("PENDIENTE: buscar FVG en M1/M5 tras el sweep (sin datos M1/M5).")
    elif fvg_m5 or fvg_m1:
        donde = "M5" if fvg_m5 else "M1"
        items.append(f"OK: FVG en {donde} presente tras sweep (Silver Bullet listo).")
    else:
        items.append("FALTA: sin FVG en M1/M5 aun (esperar tras el sweep).")

    # 5. Direccion coincide
    if dir_setup == "NEUTRAL":
        items.append("FALTA: direccion del setup para el scalp.")
    else:
        items.append(f"OK: Direccion scalp: {dir_setup}.")

    # 6. SL en FVG/OB
    ob_m5 = str(m5.get("ob_dir", "-")) not in ("-", "none", "nan", "")
    if ob_m5:
        items.append(f"OK: OB en M5 ({m5.get('ob_dir')}) -> SL sobre/fallo del OB.")
    else:
        items.append("PENDIENTE: SL bajo FVG alcista / sobre FVG bajista (o SSL/BSL).")

    # 7. RR 1:2
    items.append("PENDIENTE: RR >= 1:2, salida en liquidez opuesta (rapido).")
    return items


def evaluate(model: str, estructura: dict, bias: str, votes: dict | None,
             ts: datetime | None = None, exec_tf: str = "M15",
             htf: str = "H4", counter_trend: bool = False) -> dict[str, Any]:
    """Evalua un modelo ICT y devuelve checklist + puntuacion.

    model: "intradia" | "scalping" | "po3"
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest opcion A).
    counter_trend: si True, setup opera contra la marea del HTF.
    Devuelve {"model":..., "checks":[...], "passed":int, "total":int,
              "ready":bool, "direction":"LONG"|"SHORT"|"NEUTRAL"}
    Para model="po3" tambien incluye "phases", "complete", "incomplete_reason".
    """
    if model == "intradia":
        checks = checklist_intradia(estructura, bias, votes, ts, exec_tf, htf, counter_trend)
    elif model == "scalping":
        checks = checklist_scalping(estructura, bias, votes, ts, exec_tf)
    elif model == "po3":
        return evaluate_po3("po3", estructura, bias, votes, ts, exec_tf, htf, counter_trend)
    else:
        raise ValueError(f"modelo desconocido: {model}")

    passed = sum(1 for c in checks if c.startswith("OK:"))
    total = len(checks)
    # "ready" = todos los OK (los PENDIENTE son de ejecucion, no bloquean senal)
    blocked = [c for c in checks if c.startswith("FALTA:")]
    dir_setup = _dir_setup(bias, votes, estructura.get(exec_tf, {}), counter_trend)
    return {
        "model": model,
        "checks": checks,
        "passed": passed,
        "total": total,
        "ready": len(blocked) == 0,
        "direction": dir_setup,
    }


if __name__ == "__main__":
    # Smoke test (sin pytest).
    est = {
        "D1": {"trend": "BULLISH"}, "H4": {"trend": "BULLISH"},
        "M15": {"bos_dir": 1, "bos_status": "active", "sweep_up": True},
        "M5": {"fvg_state": "bullish", "ob_dir": "bullish"},
    }
    from datetime import datetime, timezone
    ts = datetime(2026, 7, 10, 13, 30, tzinfo=timezone.utc)  # NY AM
    r = evaluate("scalping", est, "BULLISH", {"LONG": 3, "SHORT": 1}, ts)
    print("SCALPING:", r["ready"], r["direction"], f"({r['passed']}/{r['total']})")
    for c in r["checks"]:
        print("  -", c)
