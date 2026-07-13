# Decision: Zona horaria del sistema (Ecuador hoy → servidor en el futuro)

**Fecha:** 2026-07-13 · **Estándar:** ADR-021 / RFC-001 · **Roadmap:** R2

## Problema

SMC-SYSTEMS corre hoy en Ecuador (GMT-5, sin DST) pero en el futuro correrá
en un servidor (VPS/AWS), probablemente en UTC o cualquier huso. El libro
`docs/ict/01_KILLZONES.md` documentaba el hueco **KZ-1**: tres relojes distintos
(ET / broker-local / UTC) causaban desalineación entre UI y backtest.

Riesgo concreto: si el código asume "hora local del sistema" o hardcodea
Ecuador, al moverse al servidor las killzones se calculan con 5h de diferencia
y el observador marca "killzone activa" a la hora equivocada.

## Investigación (fuentes)

- Práctica estándar de servidores (FMSoup, r/linuxadmin): **trabajar siempre
  en UTC internamente; convertir a la zona del usuario solo para mostrar**.
- Python 3.9+ trae `zoneinfo` en stdlib (PEP 615) con la IANA tz DB oficial.
  No requiere `pytz`. En Windows puede necesitar `pip install tzdata` si el
  SO no trae la DB (verificado en este entorno: funciona sin tzdata extra).
- El binario ya usaba `datetime.now(timezone.utc)` en `rules.py`,
  `resumen_widget.py` y `mt5_status.py` → la base UTC ya estaba bien.

## Decisión

1. **Cálculo interno SIEMPRE UTC** (ya así; se mantiene). Determinístico en
   cualquier servidor porque UTC es absoluto.
2. **Zona del operador = CONFIGURACIÓN**, no hardcode. Ecuador =
   `America/Guayaquil` (GMT-5, sin DST). Se lee de env `SMC_TZ`; default
   Ecuador. Mismo binario corre en cualquier huso cambiando solo esa env.
3. **Mostrar** la hora convertida a la zona del operador solo en UI, con
   `zoneinfo`. El cálculo no cambia.
4. **Defensa**: `utc_now()` devuelve tz-aware; `datetime.now()` naive falla
   temprano en vez de calcular mal silenciosamente.

## Implementación

- `app_observador/core/timezone.py`: helper único
  (`utc_now`, `to_operator_time`, `operator_clock_str`, `operator_offset_hours`,
  `killzone_activa_ahora`, `killzone_bandas_operador`). Zona por `SMC_TZ`.
- `resumen_widget.py`: usa `killzone_activa_ahora()` del helper; muestra
  bandas en UTC y en zona operador.
- `mt5_status.py`: reloj también en zona operador además de UTC.
- `detectors/killzones.py` (mapa de velas): queda como está (trabaja en la
  zona de la vela/broker por diseño de LuxAlgo). Se documenta como capa
  distinta; unificar visualmente es KZ-2 (fuera de R2).

## Por qué no pytz

`zoneinfo` es stdlib desde 3.9, usa IANA oficial, cero dependencias. pytz está
en mantenimiento; migrar a él sería un paso atrás.

## Verificación

- `America/Guayaquil`: UTC 12:00 → 07:00 (-05) sin DST. ✅
- Tests en `tests/test_timezone.py`: conversion, bandas, override por env.
