# MDS — Killzones London + NY PM (SPEC §15, libros 01/18)

**Clasificación:** OBLIGATORIO · **Fase:** B2 (paralelo) · **Estado:** ❌ (NY AM ✅, L/NY PM faltan)
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §15 · **Roadmap maestro:** §9 (Killzone)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Helper `in_killzone(ts)` que cubra las 3 ventanas ICT: London Open, NY AM, NY PM. Hoy solo
NY AM cableada (libro 17 / `rules.py`).

## ⚠️ REGLA DURA DE ZONA HORARIA (PRINCIPIO DE ARQUITECTURA — 2026-07-20)

**La hora la da el SERVIDOR (donde está instalado MT5/Hermes = broker time). Se CONVIERTE.**

1. El parquet de MT5 trae `time` en **HORA DEL SERVIDOR** (broker time, donde corre la
   instalación). NO es ET por definición, NO es UTC por definición.
2. Para evaluar ventanas ICT (que se definen en **ET**) se debe **CONVERTIR** server_time →
   ET (o → UTC canónico del proyecto) usando la **zona real del servidor** vía `ZoneInfo`
   (DST automático). NUNCA offset fijo hardcodeado.
3. La zona del servidor es **CONFIGURACIÓN** (p.ej. `SMC_BROKER_TZ="America/New_York"` o la
   que reporte MT5), NO hardcode. Igual filosofía que `SMC_TZ` del operador.
4. El cálculo interno del proyecto es **UTC** (ya lo hace `app_observador/core/timezone.py`
   para el reloj de la PC). El `ts` de vela debe pasar por el MISMO patrón:
   `server_tz → UTC → comparar bandas canónicas`.
5. **Anti-look-ahead:** en backtest se usa SOLO el `time` de la vela (ya cerrada),
   convertido. NUNCA el reloj de la PC.

### BUG ACTUAL DETECTADO (KZ-2, 2026-07-20) — debe morir con este MDS

- `detectors/killzones.py:11-14` asume el `time` "YA está en hora broker" y NO lo convierte;
  usa offset FIJO ("NY=-4, LDN=0, TOKYO=+9 en verano") → ignora DST y zonas reales.
- `ict_backtest/rules.py:killzone_en` asume el `ts` "ya viene en UTC" y lo evalúa crudo.
- `docs/ict/01_KILLZONES.md §4` marcaba KZ-1 "resuelto" pero en la práctica siguen 3 relojes.
→ Este MDS EXIGE unificar en un solo helper de conversión y evaluar SIEMPRE en UTC canónico.

## 1. Dependencias

- `app_observador/core/timezone.py` (patrón UTC canónico + `ZoneInfo`, ya existe, reusar).
- Config de zona del broker (`SMC_BROKER_TZ`; default `America/New_York` con warning si falta).

## 2. Módulo (a crear/extender)

- Nuevo helper en `ict_backtest/rules.py` (o `timezone.py`): `server_to_utc(ts, broker_tz)`.
- `killzone_en(ts, broker_tz=None)` convierte primero y luego evalúa bandas UTC canónicas.
- `detectors/killzones.py` reescrito: usa `server_to_utc`, elimina offset fijo.

## 3. Firma propuesta

```python
from datetime import timezone
from zoneinfo import ZoneInfo
from app_observador.core.timezone import operator_tz  # patrón existente

def server_to_utc(ts: datetime, broker_tz: ZoneInfo) -> datetime:
    """Convierte hora del SERVIDOR (broker) a UTC canónico del proyecto."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=broker_tz)   # asumir broker_tz si llega naive
    return ts.astimezone(timezone.utc)

def killzone_en(ts: datetime, broker_tz: ZoneInfo | None = None) -> str:
    """Killzone activa para el timestamp de vela (UTC canónico). Backtest-safe.

    REGLA: si broker_tz se pasa, PRIMERO server_to_utc (nunca evaluar sobre hora broker cruda).
    """
    if broker_tz is not None:
        ts = server_to_utc(ts, broker_tz)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    h = ts.hour + ts.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""
```

Bandas canónicas (UTC, según `01_KILLZONES.md §4` ya convertidas):
- London Open: 07:00–10:00 UTC · NY AM: 12:30–15:00 UTC · NY PM: 17:00–20:00 UTC.

## 4. Reglas duras

- El setup solo es válido dentro de la killzone asignada (SPEC §15 POST).
- **NUNCA** evaluar killzone sobre hora broker/servidor cruda sin `server_to_utc` previo.
- **NUNCA** usar offset fijo hardcodeado (DST lo rompe).
- Zona del broker = config (`SMC_BROKER_TZ`), no hardcode.
- En backtest: solo `time` de vela ya cerrada (anti look-ahead R4).

## 5. Criterios de aceptación

- Tests unitarios con timestamp broker 08:30 ET (server NY) → convierte a UTC y cae en NY AM.
- Test con DST (verano) NO se desfasa (ZoneInfo cubre DST automático).
- Test con broker en OTRA zona (p.ej. server Cyprus) convierte correcto a UTC.
- `detectors/killzones.py` sin offset fijo; `killzone_en` con `broker_tz` obliga conversión.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §10 (SB usa NY AM/PM) · §15 (Killzone) · libro 01/18 · ROADMAP §9 (Killzone) ·
libro 18 §0 #8 (3 ventanas) · `app_observador/core/timezone.py` (patrón UTC) ·
DEC-009i (principio TZ servidor→conversión, bug KZ-2).
