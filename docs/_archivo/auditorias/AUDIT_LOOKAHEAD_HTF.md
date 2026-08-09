# Auditoría: Look-ahead cross-timeframe en join H4→M5 (hallazgo IA externa)

**Fecha:** 2026-07-13
**Severidad:** CRÍTICA (el bug más caro: infla artificialmente TODOS los modelos)
**Fuente:** IA externa revisó el repo en commit b641a83 (no el resumen).
**Verificado por mí en código real:** SÍ (ver "Evidencia").

## Mecanismo
`ict_backtest/_util.py::row_at_time` hace join asof `times <= tt` (la vela LTF
actual). Para una vela M5 de las 09:03, selecciona la barra H4 `time=08:00` que
en MT5 **abre** 08:00 y **cierra** 12:00. El `trend`/`bos_status`/`choch_status`
de esa fila H4 se calculó sobre el `close` de las 12:00 — 3h en el futuro
respecto de la vela M5 de las 09:03. El sesgo H4 que usa cada vela M5 puede
estar construido con precio que aún no existía. Look-ahead cross-timeframe real.

El fix intra-timeframe (shift en `bos.py::_swing_points`) NO cubría el join
entre TF: no hay `shift(1)` al pasar de H4 a M5.

## Evidencia (medida, no especulación)
Sobre EURUSD M5 (50k velas) vs H4: **48694/50000 = 97.4%** de las velas M5 usan
una barra H4 que AÚN NO HA CERRADO al momento de la vela M5. No es caso borde:
es el comportamiento por defecto del 97% del tiempo.

## Parche (APLICADO 2026-07-13, autorizado por Ruben — sin commit, regla de hierro)
1. `ict_backtest/_util.py::row_at_time(df, t, freq=None)`: si `freq` dado,
   el asof usa `upper = tt - freq` (exige barra ya cerrada: `time+freq <= tt`).
2. `ict_backtest/engine.py::_build_estructura`: mapa `TF_FREQ` y pasa
   `freq=TF_FREQ[tf]` para todo TF != LTF. El LTF actual usa match exacto
   (`freq=None`), no asof.

## Fix residual (IA externa, 2026-07-13 — SEGUNDO PASO)
Mi primer parche solo descontaba `freq` en la rama `prior` (asof), pero la
rama `exact` (`times == tt`) comparaba contra `tt` sin ajuste. Resultado:
una vela LTF en el **limite exacto de apertura del HTF** (ej M5 08:00:00 ==
open H4 08:00) devolvia la vela HTF SIN cerrar (close futuro) — mismo bug.
**Reproducido con datos sinteticos** (close=3 en vez de 2). La IA lo detectó
probando el propio parche; NO era teoria.

Fix: `cutoff = tt - pd.Timedelta(freq)` se aplica TAMBIEN al match exacto.
Test de regresion agregado: `test_row_at_time_exact_boundary_closed`
(suite 8/8 passed).

**Cuantificacion del residual en dataset real (EURUSD M5, 50k velas):**
1042/50000 = **2.08%** de velas M5 caen exactamente en limite H4
(hora multiplo de 4, minuto 0). Se concentra en 00/04/08/12/16/20 UTC, que
toca London Open (07-10) y NY AM (12:5-15:0) — las killzones operativas.
No es marginal, pero es menor al 97.4% original. v2.7 (corrida anterior)
TAMBIEN tenia este 2.08% con fuga residual.

## Impacto final
- v2/v2.5/v2.6: contaminados por look-ahead masivo (97.4%) -> INVALIDADOS.
- v2.7: correccion parcial (97.4% arreglado, pero 2.08% residual en limites).
- **v2.8 (pendiente): corrida DEFINITIVA** con fix residual aplicado + test.
  Solo sus numeros son "limpios confirmados" para decidir Optuna.

## Prioridad de trabajo (IA externa, acordada)
1. look-ahead HTF (este) → 2. exec_tf explícito → 3. displacement en vela de
sweep no de entrada → 4. fix test H1 → 5. re-correr R4.
