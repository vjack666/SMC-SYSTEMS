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

from datetime import datetime, timezone
from typing import Any

# Bandas killzone en UTC (aprox docs/ict/01_KILLZONES.md).
# Clave -> (hora_ini, hora_fin) en horas decimales UTC.
KILLZONES_UTC: dict[str, tuple[float, float]] = {
    "Asia": (0.0, 3.0),
    "London Open": (7.0, 10.0),
    "New York AM": (12.5, 15.0),   # ~10-11 ET
    "New York PM": (15.0, 17.5),
    "London Close": (15.5, 17.5),
}


def killzone_en(ts: datetime) -> str:
    """Killzone activa para un timestamp de vela (UTC). Backtest-safe."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    h = ts.hour + ts.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""


def _dir_setup(bias: str, votes: dict | None, m15: dict) -> str:
    """Direccion del setup: votos L/S o BOS M15."""
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
                       htf: str = "H4") -> list[str]:
    """Checklist INTRADIA (PO3/Turtle Soup). Items numerados.

    ts: timestamp de la vela para killzone historica (si None, fuera de KZ).
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest de opcion A).
    htf: TF de contexto alto para el sweep (H4 por defecto).
    """
    items: list[str] = []
    d1 = estructura.get("D1", {})
    h4 = estructura.get(htf, {})
    m15 = estructura.get(exec_tf, {})
    dir_setup = _dir_setup(bias, votes, m15)
    kz = killzone_en(ts) if ts is not None else ""

    # 1. Sesgo del dia
    if "NEUTRAL" in (bias or "") or not bias:
        items.append("FALTA: definir SESGO DEL DIA (L/S) desde H4/D1.")
    else:
        items.append(f"OK: Sesgo del dia: {bias}.")

    # 2. Contexto D1/H4
    if d1.get("trend") in ("", "RANGING") and h4.get("trend") in ("", "RANGING"):
        items.append("FALTA: contexto D1/H4 definido (en rango -> sin marea).")
    else:
        items.append(f"OK: Contexto D1 {d1.get('trend','?')} / {htf} {h4.get('trend','?')}.")

    # 3. Killzone intradia
    if kz in ("London Open", "New York AM", "New York PM"):
        items.append(f"OK: Killzone intradia activa: {kz} (UTC).")
    else:
        items.append("FALTA: killzone intradia (London/NY) -> esperar ventana.")

    # 4. Sweep HTF/exec
    sw = _sweep_dir(estructura, (htf, exec_tf))
    if sw == "none":
        items.append(f"FALTA: barrido de liquidez (sweep SSL/BSL) en {htf}/{exec_tf}.")
    else:
        items.append(f"OK: Liquidez barrida ({sw}) en {htf}/{exec_tf}.")

    # 5. BOS/CHOCH exec
    bos = _bos_exec(estructura, exec_tf)
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
                       ts: datetime | None = None) -> list[str]:
    """Checklist SCALPING (M1/M5, Silver Bullet). Items numerados.

    ts: timestamp de la vela para ventana NY AM historica.
    """
    items: list[str] = []
    m15 = estructura.get("M15", {})
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

    # 3. Sweep M15
    sw = _sweep_dir(estructura, ("M15",))
    if sw == "none":
        items.append("FALTA: sweep de SSL/BSL en M15 (previo al FVG M1/M5).")
    else:
        items.append(f"OK: Sweep M15 ({sw}) presente.")

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
             htf: str = "H4") -> dict[str, Any]:
    """Evalua un modelo ICT y devuelve checklist + puntuacion.

    model: "intradia" | "scalping"
    exec_tf: TF de ejecucion (M15 en vivo; H4 en backtest opcion A).
    Devuelve {"model":..., "checks":[...], "passed":int, "total":int,
              "ready":bool, "direction":"LONG"|"SHORT"|"NEUTRAL"}
    """
    if model == "intradia":
        checks = checklist_intradia(estructura, bias, votes, ts, exec_tf, htf)
    elif model == "scalping":
        checks = checklist_scalping(estructura, bias, votes, ts)
    else:
        raise ValueError(f"modelo desconocido: {model}")

    passed = sum(1 for c in checks if c.startswith("OK:"))
    total = len(checks)
    # "ready" = todos los OK (los PENDIENTE son de ejecucion, no bloquean senal)
    blocked = [c for c in checks if c.startswith("FALTA:")]
    dir_setup = _dir_setup(bias, votes, estructura.get(exec_tf, {}))
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
