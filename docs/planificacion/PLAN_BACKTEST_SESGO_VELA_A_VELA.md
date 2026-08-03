# Plan de trabajo — Backtest del sesgo (bias) D1/H4/H1, vela a vela sobre parquet M15

| Campo | Valor |
|-------|-------|
| **Estado** | Plan propuesto (sin código) |
| **Fecha** | 2026-08-03 |
| **Autor** | Sesión de planificación SMC-SYSTEMS |
| **Dependencias** | `docs/plan/PLAN_BACKTEST_PROFESIONAL.md` (R6), `docs/ict/13_BACKTEST_PROFESIONAL/`, `engine/bias/` (capa 1 del motor), `tests/test_engine_bias.py`, `docs/METRICS_CANON.md` |
| **Carpeta de trabajo** | `docs/planificacion/` (nueva) |

---

## 1. Objetivo

Construir un **backtest del sesgo** (bias) multi-temporalidad que:

- Toma el **parquet M15** como única fuente de datos.
- Recorre las velas M15 **una a una, en orden cronológico estricto** (como miraría el chart un humano).
- Deja que **cada temporalidad haga lo suyo** (D1 sesgo, H4 estructura/zona, H1 contexto, M15 ejecución) **solo cuando tiene suficientes velas cerradas** para hacerlo.
- Respeta el reloj: en cada instante solo existe el pasado conocido. Nunca el futuro.

**No se escribe código en este documento.** Solo instrucciones de trabajo, tablas y criterios de terminación (done) por fase.

---

## 2. Concepto central: el reloj lo marca M15

El corazón del backtest es un **reloj de velas**. La vela M15 es el "latido": cada vez que cierra una vela M15, el tiempo avanza un paso. Los temporalidades superiores **son perezosos**: no se recalculan en cada M15, sino **solo cuando cierra una vela propia** (cada 4 M15 cierra un H1, cada 16 un H4, cada 96 un D1).

Regla de oro (contrato del libro 13, §0 #1–#2):

> **La vela HTF que está en formación NO existe para el backtest.** Solo se usa una vela de D1/H4/H1 si ya cerró en el instante actual del reloj.

En la práctica, por cada vela M15 en el índice `i` con su timestamp `t`:

1. ¿Cerró una vela H1 en este instante? (el reloj cruzó el límite de la hora) → **recalcular la parte de H1**.
2. ¿Cerró una vela H4? (cruzó el límite de 4 horas) → **recalcular la parte de H4**.
3. ¿Cerró una vela D1? (cruzó el límite del día) → **recalcular el sesgo (bias)**.
4. Con las vistas vigentes de D1/H4/H1 (todas cerradas) + la M15 actual ya cerrada → **evaluar el setup de ejecución**.
5. Si hay señal → el fill ocurre en el **open de la M15 siguiente** (`i+1`), nunca en el close de la señal (contrato #3).

Detectar el "cierre de TF" sin ambigüedades de zona horaria: se usa el propio timestamp de cada vela M15, agrupando por tramos. Una vela H1 es el grupo de M15 cuyo `floor(t / 1h)` es el mismo; idem `floor(t / 4h)` para H4 y `floor(t / 1d)` para D1. Un TF "cerró una vela ahora" cuando el grupo de la vela M15 actual es **distinto** al de la vela M15 anterior. Ese mecanismo es determinista y no depende de conversiones de zona horaria manuales.

---

## 3. Cuántas velas M15 necesita cada temporalidad (tabla central)

Esta es la tabla que pide el enunciado: la traducción exacta de velas M15 → velas superiores, y el mínimo de velas **propias cerradas** que cada TF necesita para poder hacer su parte.

### 3.1 Agregación: velas M15 por vela superior

| TF superior | Velas M15 por vela | Cálculo |
|-------------|-------------------:|---------|
| H1  | 4  | 60 min ÷ 15 |
| H4  | 16 | 240 min ÷ 15 |
| D1  | 96 | 1440 min ÷ 15 |

(Si en el futuro el LTF de ejecución fuera M5, la tabla cambia a H1=12, H4=48, D1=288. Ver §8, decisión abierta.)

### 3.2 Warm-up: mínimo de velas CERRADAS por TF para hacer su parte

Cada TF necesita un mínimo de velas **de su propia temporalidad** ya cerradas para producir resultados confiables. Se define como **parámetro configurable** (no un número mágico en código):

| TF | Mínimo sugerido (velas propias) | Justificación | Equivale a (M15) |
|----|-------------------------------:|---------------|-----------------:|
| D1 | 20  | Sesgo por tramos: con `swing_lookback=5` y votación de últimos 4 tramos hacen falta ~4–6 swings confirmados ≈ 15–20 velas D1 | 1.920 |
| H4 | 60  | Estructura BOS/CHOCH + POI anclado con memoria estable (~10 días) | 960 |
| H1 | 100 | Contexto ITF / dealing range del día (~4 días) | 400 |

**Regla de activación:** el backtest **no genera operaciones** hasta que **todos los TF activos completaron su warm-up** (primera vela M15 tal que: velas D1 cerradas ≥ 20, H4 ≥ 60 y H1 ≥ 100). Antes de ese punto, el sesgo reporta "no disponible" (mismo comportamiento que `HtfBias` con votos insuficientes → `NEUTRAL` / sin voto). El backtest debe **registrar la fecha y hora** en que el sesgo queda disponible, para auditar cuánta muestra se pierde por warm-up.

Los valores de la tabla son **punto de partida**, no verdad revelada: la Fase 1 (reloj) debe medir cuántas velas de cada TF hacen falta para que el sesgo estabilice (primera vez que `aligned != NEUTRAL` con 3 TF) y ajustar si hace falta.

---

## 4. Qué hace cada temporalidad ("su parte")

| TF | Responsabilidad | Fuente de verdad |
|----|-----------------|------------------|
| **D1** | Sesgo / narrativa HTF: `compute_htf_bias` (polaridad de swings por tramos, `aligned`) — la capa 1 del motor | `engine/bias/narrative.py` (ya construida, 12/12 tests) |
| **H4** | Estructura (BOS/CHOCH) + zona premium/discount + POI anclado HTF (la brecha C06 del libro 21) | Tesis 18/21 — a cablear en el motor |
| **H1** | Contexto intermedio: zona ITF, dealing range del día | Tesis 18 (capa ITF) — a cablear |
| **M15** | Ejecución: secuencia sweep → displacement → BOS → retorno, killzone, entry/SL/TP | Libro 15/16 — motor vela a vela |

**Regla de actualización (lazy update):** cada capa se recalcula **exclusivamente** en el cierre de su propia vela (D1 al cerrar D1, H4 al cerrar H4, H1 al cerrar H1). Entre cierres, la vista vigente es la última calculada — que es exactamente lo que ve un humano cuando cambia de temporalidad en el chart.

---

## 5. El bucle vela a vela (instrucciones paso a paso)

Instrucción general: el bucle principal recorre el parquet M15 de la primera a la última vela, una sola pasada, **sin mirar nunca velas futuras ni HTF a medio formar**.

1. **Cargar** el parquet M15 (única fuente), ordenado por timestamp. Validar: sin huecos raros, sin duplicados, zona horaria documentada (la que usa MT5 para el símbolo).
2. **Iterar** `i` desde `0` hasta `N-1` (N = total de velas M15). En cada paso:
   - `t` = timestamp de la vela M15 `i`.
   - Comparar el grupo (bucket) de `t` con el de la vela anterior para cada TF superior.
   - **Si cerró H1**: materializar la vela H1 (agregando las M15 de ese bucket) y re-ejecutar la parte de H1.
   - **Si cerró H4**: idem para H4.
   - **Si cerró D1**: idem para D1 → re-computar `compute_htf_bias` sobre la vista D1 agregada → **actualizar el sesgo vigente**.
   - Con el sesgo vigente (cerrado) + vistas H4/H1 (cerradas) + la M15 `i` (cerrada): evaluar el setup de ejecución (sección 4). Si el setup dispara y el warm-up está completo → **señal**.
3. **Fill**: señal generada en el close de la M15 `i` → entrada al **open de la M15 `i+1`** (salvo que el bucle haya terminado: descartar la última vela como señal por falta de siguiente open).
4. **Gestión del trade abierto**: en cada M15 posterior, verificar SL estructural / TP (RR configurado) / max hold (mínimo 40 velas M15 según libro 15) vela a vela, hasta que cierre.
5. **Métricas**: al terminar la pasada, calcular PF/WR/R/DD/Sharpe **con costos** (ver §7) y volcar a `docs/METRICS_CANON.md` si hay veredicto.

**Anti-look-ahead (no negociable, aprendido de la auditoría):**
- Los swings de cada TF se confirman con **ventana no centrada** (solo miran hacia atrás) y se difunden con `shift + ffill` (patrón ya canónico en `ict_backtest/market_structure.py`).
- La vela M15 **abierta** no decide nada: solo la cerrada.
- Test de regresión obligatorio en el **límite exacto** (una H4 que se forma a las 08:00 no debe devolverse hasta que su M15 de las 08:00 haya cerrado) — mismo espíritu que `test_row_at_time_exact_boundary_closed`.

---

## 6. Fases de construcción con criterios de terminación (done)

| Fase | Qué hacer | Criterio done |
|------|-----------|---------------|
| **F0 · Datos y contrato** | Validar parquet M15 disponible (2.02 años, 2024-07→2026-07). Documentar TZ. Fijar en configuración: tabla de agregación (4/16/96) y warm-ups (§3.2) | Parquet validado; tabla y warm-ups documentados en config; sin huecos ni duplicados |
| **F1 · El reloj (corazón)** | Implementar el bucle vela a vela con detección de cierre de H1/H4/D1 y materialización por agregación de M15 cerradas. **Sin lógica de trading todavía** | Test sintético: un H1 = 4 M15, un H4 = 16, un D1 = 96 (buckets exactos). Test "HTF en formación invisible". Cero look-ahead (tests de regresión verdes) |
| **F2 · Sesgo (motor)** | Conectar la capa `engine/bias` al reloj: en cada cierre de D1, re-computar el sesgo con las vistas D1/H4/H1 agregadas. Definir la regla "el sesgo rige hasta el próximo cierre de D1" | Test sintético: transición de sesgo en el límite del día; el sesgo vigente no cambia entre cierres de D1; `aligned` correcto con 3 TF |
| **F3 · Ejecución M15** | Evaluar el setup en cada M15 cerrada (sweep→displace→BOS→retorno + killzone) con el sesgo vigente y las zonas H4/H1. Fill next-open, SL estructural, RR, max hold | Señales con fill en open de `i+1`; N ≥ umbral mínimo para concluir; test sintético determinista |
| **F4 · Costos** | Cablear spread + comisión + slippage explícitos (misma estructura de costos que `ict_backtest`) | Métricas de producción SIEMPRE con costos (contrato #4); test de que los costos no inflan el pnl (regresión existente) |
| **F5 · Validación** | Test sintético determinista (como `test_engine_bias`). Corrida real sobre EURUSD (u otro con M15 disponible). Comparar señales de sesgo con `ict_backtest` (misma ventana) para detectar divergencias de reloj. Walk-forward multi-fold OOS | Sintético verde; divergencias de reloj = 0 (o documentadas); veredicto honesto volcado a `METRICS_CANON.md` |

---

## 7. Reglas no negociables (heredadas del libro 13 §0)

1. El reloj es el LTF (M15); no se usa OHLC futuro de ninguna temporalidad.
2. Los TF superiores se usan solo si `close_time_HTF <= now` (closed-only).
3. Señal en close de M15 → fill en open de `i+1`.
4. Toda métrica de producción se reporta **con costos**.
5. Edge se declara solo con OOS multi-fold + N suficiente (gates de `METRICS_CANON`).
6. **Misma función de decisión en vivo y en backtest** (sin copias divergentes): el motor (`engine/bias` y futuras capas) es la única fuente de la lógica; el backtest solo orquesta el reloj y las vistas.
7. **Motor ≠ backtest**: `engine/` nunca importa `ict_backtest/`; el backtest del sesgo puede importar `engine/` (es su consumidor), nunca al revés.
8. No commit/push sin OK expreso de Ruben (regla del repo), y con `docs/plan/CRONOGRAMA_Y_ROADMAP.md` + `ROADMAP_BIBLIOTECA_Y_APLICACION.md` al día en el mismo commit.

---

## 8. Límites y decisiones abiertas

- **M15 vs M5 (ambigüedad del pedido):** **DECIDIDO el 2026-08-03 → M15 como LTF de ejecución** (intradía, libro 15/18). Queda descartado M5 como base; si en el futuro se quisiera, la tabla de agregación pasaría a H1=12, H4=48, D1=288 y el warm-up se re-traduciría.
- **Símbolos:** XAUUSD no tiene M15 en `data/raw/` (bloqueo R5/A6 conocido) → excluido hasta bajar datos con MT5 FundedNext en vivo. EURUSD/GBPUSD/USDCHF/USDCAD tienen M15 (2.02 años).
- **Muestra:** 2.02 años → N acotada; el gate `N ≥ 200/fold` de walk-forward puede no alcanzarse en todos los símbolos. Reportar N junto a cada métrica.
- **Warm-up:** los valores de §3.2 son estimaciones; la F1 debe medirlos empíricamente antes de fijarlos en config.
- **POI anclado (C06, libro 21):** el plan asume que H4 aporta el POI anclado a narrativa HTF (la brecha B que el motor R6 tenía desactivada). Si no se implementa, este backtest mediría de nuevo la versión "FVG/OB sin ancla" ya rechazada — documentar explícitamente qué se está midiendo.

---

## 9. Próximos pasos

1. Ruben revisa este plan y decide la pregunta de §8 (M15 vs M5).
2. Aprobado → arrancar F0 (validar parquet M15 y fijar config).
3. F1 (el reloj) es la primera pieza de código, con sus tests sintéticos, **sin lógica de trading** — es la pieza que se puede verificar de forma aislada antes que nada.
