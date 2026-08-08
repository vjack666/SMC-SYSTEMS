# MDS — Killzones: London Open + New York AM/PM (SPEC §15, libros 01/18)

**Clasificación:** OBLIGATORIO · **Fase:** B2 (paralelo) · **Estado:** ✅ HECHO (rescatado a `engine/killzone.py`, commit dd8f7ef)
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §15 · **Roadmap maestro:** §9 (Killzone)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.
**Arquitectura:** módulo PERMANENTE en `engine/killzone.py`; `ict_backtest/` solo lo CONSUME (nunca al revés).

---

## 1. Título + Clasificación

Software Design Doc — **Killzones (London Open / New York AM / New York PM)**.
Obligatorio · Fase B2 · Estado: rescate de `ict_backtest/rules.py` a `engine/killzone.py`.

Este módulo no toma decisiones de trade por sí solo: es un **filtro temporal** que decide
si una vela cae dentro de una ventana intraday ICT. La ventana es geometría pura del tiempo
de mercado (cuándo operan los bancos), NO un indicador. No usa EMA/RSI/ATR/MACD/Bollinger.

## 2. Propósito

Determinar, a partir del **timestamp de una vela ya cerrada**, en qué ventana horaria ICT cae:
`London Open`, `New York AM`, `New York PM` (y las ventanas de soporte `Asia`, `London Close`).
El backtest y el motor de señales usan esto para habilitar/deshabilitar setups (Silver Bullet
solo en NY AM/LO; Turtle Soup sin restricción de KZ pero sí trazabilidad). Es la única forma
de comparar una vela contra las bandas ICT de forma **backtest-safe** (usa el reloj de la vela,
no el de la PC).

## 3. Por qué importa (geometría de mercado, sin indicadores)

ICT define las killzones como las franjas horarias en que la liquidez institucional se mueve.
Es pura **geometría del calendario de sesiones**: el rango de horas en que ciertos barridos
de liquidez y estructuras tienen validez. No hay ningún indicador técnico de por medio — solo
la posición de la vela en el eje temporal convertida a UTC canónico. Esto garantiza que el
motor en vivo y el backtest evalúen exactamente las mismas ventanas (sin deriva de reloj).

## 4. Entradas (datos geométricos + VOLUMEN como único extra permitido)

- **Timestamp de vela** `ts` (ya cerrada): `datetime`, puede venir naive o tz-aware.
  - Si `broker_tz` se pasa → se asume `ts` en hora del **servidor (broker)** y se convierte a UTC.
  - Si `broker_tz` es `None` → se asume `ts` ya en **UTC canónico** (ruta legacy de `canonical.py`).
- **Zona del broker** `broker_tz`: `ZoneInfo | str` (config `SMC_BROKER_TZ`, default `America/New_York`).
  Convertida vía `ZoneInfo` (DST automático). **NUNCA offset fijo.**
- **No usa OHLC ni swings ni volumen para decidir la ventana** — la killzone es función solo del
  tiempo. El volumen y el OHLC entran en los setups que *consumen* la killzone (ver §10 y SDD C2/C3).

Bandas canónicas (fiel a `ict_backtest/rules.py`):

```
KILLZONES_UTC  (ts ya en UTC, ruta legacy):
    Asia         (0.0, 3.0)
    London Open  (7.0, 10.0)
    New York AM  (12.5, 15.0)   # ~10-11 ET
    New York PM  (15.0, 17.5)
    London Close (15.5, 17.5)

KILLZONES_ET   (horario local mentorship ICT, convertido a UTC POR DIA vía
                ZoneInfo('America/New_York') -> DST automático, NUNCA offset fijo):
    London Open  ((2,0),  (5,0))    # 02:00-05:00 ET  (London 07:00-10:00 UK)
    New York AM  ((10,0), (12,0))   # 10:00-12:00 ET  (Silver Bullet)
    New York PM  ((14,0), (17,0))   # 14:00-17:00 ET  (NY PM session)
```

## 5. Lógica (geometría pura, cero indicadores)

Patrón de tiempo, sin ningún indicador:

1. **Conversión de zona (principio DEC-009i / Ruben):** si `broker_tz` presente, `server_to_utc(ts, broker_tz)`
   convierte la hora del servidor a UTC usando `ZoneInfo` (DST automático). Nunca offset fijo.
2. **Evaluación por banda:** se compara la hora decimal UTC `h = ts.hour + ts.minute/60.0` contra las
   bandas canónicas. Devuelve el nombre de la primera ventana que contiene `h` (`ini <= h < fin`), o `''`.
3. **Ruta ET:** si vino de broker_tz, las bandas `KILLZONES_ET` se convierten a UTC *por el día de la vela*
   (`_et_band_to_utc` ancla al día UTC y aplica DST vigente) y se evalúa el rango UTC resultante.
4. **Backtest-safe:** el cálculo usa exclusivamente el `ts` de la vela; el reloj de la PC no interviene.

Firma propuesta (rescatada a `engine/killzone.py`, fiel a `ict_backtest/rules.py`):

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Bandas UTC canónico (ruta legacy, ts ya en UTC). NO son offsets fijos: rango ya convertido.
KILLZONES_UTC: dict[str, tuple[float, float]] = {
    "Asia": (0.0, 3.0),
    "London Open": (7.0, 10.0),
    "New York AM": (12.5, 15.0),
    "New York PM": (15.0, 17.5),
    "London Close": (15.5, 17.5),
}

# Bandas en ET fijo del mentorship -> UTC por dia (DST automático, sin offset fijo).
KILLZONES_ET: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "London Open": ((2, 0), (5, 0)),
    "New York AM": ((10, 0), (12, 0)),
    "New York PM": ((14, 0), (17, 0)),
}

def server_to_utc(ts: datetime, broker_tz) -> datetime:
    """Hora del SERVIDOR (broker) -> UTC canónico vía ZoneInfo (DST automático)."""
    if isinstance(broker_tz, str):
        broker_tz = ZoneInfo(broker_tz)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=broker_tz)
    return ts.astimezone(timezone.utc)

def _et_band_to_utc(et_h: int, et_m: int, day_utc: datetime) -> datetime:
    ny = ZoneInfo("America/New_York")
    et_local = datetime(day_utc.year, day_utc.month, day_utc.day, et_h, et_m, tzinfo=ny)
    return et_local.astimezone(timezone.utc)

def killzone_en(ts: datetime, broker_tz: ZoneInfo | str | None = None) -> str:
    """Killzone activa para el timestamp de vela. Devuelve
    'London Open' | 'New York AM' | 'New York PM' | '' (más 'Asia'/'London Close')."""
    if broker_tz is not None:
        utc_ts = server_to_utc(ts, broker_tz)
        for nombre, ((h0, m0), (h1, m1)) in KILLZONES_ET.items():
            ini = _et_band_to_utc(h0, m0, utc_ts)
            fin = _et_band_to_utc(h1, m1, utc_ts)
            if ini <= utc_ts < fin:
                return nombre
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    h = ts.hour + ts.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""
```

## 6. Salidas (bool confirmado + metadata)

`killzone_en(ts, broker_tz) -> str`. Valores posibles: `'London Open'`, `'New York AM'`,
`'New York PM'`, `'Asia'`, `'London Close'`, `''` (fuera de ventana). La salida es un *label*;
los setups la consumen como filtro booleano (`in_killzone(kz, ("London Open","New York AM"))`).

## 7. Integración: rescatarse a `engine/` y consumirse desde `ict_backtest` (nunca al revés)

- **Origen hoy:** `ict_backtest/rules.py` (funciones `killzone_en`, `server_to_utc`, `_et_band_to_utc`, `KILLZONES_UTC`, `KILLZONES_ET`).
- **Destino PERMANENTE:** `engine/killzone.py`. El motor (única fuente de decisión) importa de aquí.
- **`ict_backtest/` es DESECHABLE:** solo demuestra la tesis y *consume* `engine.killzone.killzone_en`.
- **Ley Fundamental:** `engine/` **NUNCA** importa `ict_backtest/`. La flecha de dependencia es
  `ict_backtest/ → engine/`, nunca al revés.
- Los setups `engine/silver_bullet.py` y `engine/turtle_soup.py` llamarán `engine.killzone.killzone_en`.

## 8. Anti-look-ahead (solo velas con `time <= t`)

- El filtro opera sobre el `ts` de la vela evaluada. En backtest se pasa el timestamp de la vela
  **ya cerrada**; jamás el reloj de la PC ni velas futuras.
- La conversión `server_to_utc`/`_et_band_to_utc` ancla al día de la vela, sin mirar adelante.
- Las bandas son estáticas por definición ICT; no se recalculan con datos posteriores a `t`.

## 9. Verificación (pytest con datos sintéticos)

Pruebas con timestamps sintéticos (sin datos de mercado reales):

- `ts` broker 08:30 ET (server NY) → `killzone_en(ts, "America/New_York") == "New York AM"`.
- Verano (DST) no se desfasa: `ZoneInfo` cubre DST; comparar 08:30 ET julio vs enero → mismo label.
- Broker en otra zona (p.ej. server Cyprus `Europe/Nicosia`) → convierte correcto a UTC y cae en su ventana.
- `ts` en UTC 13:00 → ruta legacy (`broker_tz=None`) → `"New York AM"` (12.5–15.0).
- `ts` UTC 18:00 → `""` (fuera de todas las bandas canónicas).
- Test de regresión: `diag_etapas.py` con datos chicos. PF bloqueado hasta Fase G (R4).

## 10. Notas de volumen (cómo el volumen ayuda sin ser indicador)

La killzone **no necesita volumen** para decidir la ventana: es geometría temporal pura. El tick
volume solo se usa *aguas abajo*, en los setups que consumen la killzone, para confirmar que el
empuje/retorno dentro de la ventana tuvo participación real (vela de sweep con volumen superior al
promedio local ⇒ barrido genuino, no ruido). El volumen es dato de mercado crudo, no un indicador
derivado (no EMA de volumen, no OBV, no indicadores). En `killzone.py` el volumen queda fuera; en
`engine/silver_bullet.py` y `engine/turtle_soup.py` se documenta su uso confirmatorio.

## Trazabilidad

SPEC §15 (Killzone) · libro 01/18 (3 ventanas) · ROADMAP §9 (Killzone) · DEC-009i (principio TZ
servidor→conversión, bug KZ-2) · `ict_backtest/rules.py` (fuente real) · `app_observador/core/timezone.py`
(patrón UTC canónico reusado) · SPEC §17 (SB usa NY AM/PM) · SPEC §18 (Turtle Soup).
