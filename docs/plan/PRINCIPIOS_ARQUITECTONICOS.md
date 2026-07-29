# PRINCIPIOS ARQUITECTÓNICOS — SMC SYSTEMS

**Estado:** VIGENTE desde 2026-07-15. Autoridad: Ruben (radiólogo / dueño del proyecto).
Scribe: Hermes. **Jerarquía:** por ENCIMA de R7. R7 es refactor puro congelado;
estos principios NO se aplican dentro de R7, gobiernan R10/R11 en adelante.

Objective: SMC SYSTEMS debe ser un **motor de interpretación del mercado**, no un
bot de reglas fijas. El mercado describe significado; el algoritmo se adapta a él.

---

## PRINCIPIO 1 — Interpretación, nunca constante arbitraria

> Toda decisión del sistema debe derivarse del estado e interpretación del mercado,
> nunca de constantes arbitrarias (número de velas, lookback fijo, distancia fija,
> tiempo fijo o parámetros equivalentes).

Las constantes numéricas solo podrán existir como:
- mecanismos internos de estabilidad,
- buffers matemáticos,
- límites de seguridad,
- adaptación estadística,
- parámetros derivados de los datos.

**Nunca** podrán representar el significado del mercado ni ser la fuente primaria
de una decisión ICT.

Si durante una implementación aparece un parámetro como `bos_gap`, `lookback`,
"20 velas", "50 barras", "X minutos", "X pips", Hermes deberá preguntarse primero:

> **¿Qué concepto del mercado intenta representar este número?**

Si existe un concepto estructural equivalente (contexto, narrativa, estado,
liquidez, desplazamiento, intención, MarketObject, etc.), deberá proponerse una
solución basada en dicho concepto para **R10+**.

Si la sustitución modifica el comportamiento de una fase congelada (como R7), NO
deberá implementarse inmediatamente. Deberá documentarse como mejora arquitectónica
para una versión posterior.

---

## PRINCIPIO 2 — Modelamos el mercado, no las velas

> SMC SYSTEMS no modela velas. Modela el mercado.

Las velas, OHLC, ATR, indicadores y cualquier representación temporal son
**únicamente una fuente de observación**.

El motor de decisión deberá operar sobre entidades semánticas (`MarketObjects`),
relaciones entre ellas y el contexto estructural vigente.

La IA aprenderá sobre dichas entidades y relaciones, **nunca directamente sobre
velas o indicadores**.

Jerarquía objetivo del motor:

```
Datos del mercado  ->  Representación matemática (MarketObjects)
                   ->  Contexto estructural
                   ->  Narrativa del mercado
                   ->  Interpretación
                   ->  Decisión
                   ->  Ejecución
```

La decisión nace del significado del mercado, no de "10 velas", "50 barras" o
"ATR × 2". Esos valores pueden existir internamente como herramientas de
implementación, pero la arquitectura los trata como detalles técnicos, no como la
explicación de por qué el sistema decidió actuar.

---

## PRINCIPIO 3 — Las 4 preguntas obligatorias antes de cualquier parámetro

Antes de introducir cualquier parámetro nuevo, Hermes deberá responder
**obligatoriamente** cuatro preguntas:

1. ¿Este número representa un concepto del mercado o es un valor arbitrario?
2. ¿Puede derivarse automáticamente del estado del mercado?
3. ¿Puede representarse mediante `MarketObjects` o relaciones estructurales?
4. Si el mercado cambia de régimen, ¿el parámetro sigue siendo válido o debería
   adaptarse?

Si alguna respuesta indica que el parámetro es arbitrario, Hermes **no debe
implementarlo** sin antes documentar por qué no puede eliminarse.

---

## PRINCIPIO 4 — Interpretación contextual sobre regla fija (con límite auditable)

> SMC SYSTEMS deberá aproximarse al razonamiento de un trader institucional experto
> mediante modelos matemáticos auditables.

Cuando exista un conflicto entre una regla fija y una interpretación contextual
equivalente, se preferirá la **interpretación contextual**, siempre que pueda
expresarse de forma **objetiva, medible, reproducible y verificable mediante
pruebas**.

Diferencia clave: no imitamos la *intuición* humana, imitamos el *razonamiento*
humano transformado en matemáticas y reglas auditables. Eso mantiene el sistema
científico y reproducible, en lugar de un conjunto de heurísticas imposibles de
validar.

---

## CASO PILOTO — `bos_gap` (deuda R10+)

El primer caso detectado bajo estos principios: discrepancia de `bos_gap` entre
`ict_backtest/sequence.py:66` (`SequenceConfig.bos_gap = 40`) y
`ict_backtest/run_backtest.py:67` (`generate_sequence_signals(..., bos_gap = 10)`).

- Es un **número mágico sin concepto estructural** (Principio 1): no deriva de
  mercado, no es buffer/seguridad, no está anclado a la tesis.
- La "ventana de confirmación BOS" debería representar "¿cuándo una estructura
  deja de ser relevante?" (estado del `MarketObject`), no una cuenta fija de velas.
- **NO se implementa en R7** (congelado). Documentado como **PRIMER CANDIDATO R10**
  (registro 2026-07-15, tras T3.2B).
- Estado 2026-07-15: T3.2B (eliminar `build_signals_from_frames`) se completó como
  borrado MECÁNICO de código muerto SIN tocar `bos_gap`. La divergencia de
  equivalencia 2-vs-5 que motivó el bloqueo original NO se resuelve en R7: queda
  como deuda de R10, donde `bos_gap` se derivará de estado estructural (no se
  unifica el literal 40/10).

### Implementación R10 — Propuesta A (SIN INDICADORES, 2026-07-15)

Arrancada bajo TDD estricto (test rojo → verde, sin commit sin auth). Diseño
consensuado con el usuario: **sin ATR ni indicadores técnicos**; la ventana de
confirmación BOS se deriva del ESTADO del mercado por MATEMÁTICA PURA +

PROBABILIDAD EMPÍRICA del backtest:

- `SequenceConfig.bos_gap: int | None = 40` (default 40 = comportamiento
  histórico canónico, compatible R7). `bos_gap=None` => dinámico.
- `confirmation_window(bos_obj, ctx, ctx_len, bos_table)` (sequence.py):
  `r = rango_bos / rango_promedio_contexto` (rango = high−low, promedio simple,
  SIN ATR). Mapea `r` a un bucket 1..5 y lo busca en `bos_table` (tabla empírica
  P(mitigación en N velas | fuerza r), pre-calculada del backtest). Sin tabla =>
  fallback 40 (determinista).
- Cableado en `run_sequence` (DISPLACE_DONE y BOS_DONE) vía `_effective_bos_gap`.
- `generate_sequence_signals` / `run_sequence_backtest` aceptan `bos_table` y
  `bos_gap: int | None` (sin romper llamadores: default 10 fijo en runner).
- Tests: `tests/test_r10_bos_gap_dynamic.py` (unitario de confirmation_window +
  no-regresión de integración). El test R7 rootcause (`== 40`) sigue verde.

Pendiente (NO hecho en este paso, alcance estricto R10): calibrar la tabla
empírica REAL con `scripts/calibrate_bos_window.py` sobre el histórico del repo
(hoy el test usa tabla sintética determinista); eso es R10.B. Tampoco se toca
`displace_gap` / `sweep_lookback` / reglas ICT.

**ESTADO 2026-07-16 (tras auditoría vs Principios):** R10 Propuesta A
commiteada (057a44d, TDD, sin indicadores). La auditoría determinó que
`confirmation_window` sigue siendo, en el fondo, una ventana en NÚMERO DE
VELAS (`int`, usos `índice - índice > N`): cumple P3 100%, P1/P2/P4 solo
parcial. R10.B queda EN PAUSA. El diseño que elimina la caducidad por timer y la
reemplaza por EVENTO semántico (StateMachine + Invalidators + ObjectGraph +
MarketNarrative + EventEngine) está en `docs/plan/DISENO_R10C_R11.md` como
BORRADOR PENDIENTE DE APROBACIÓN del usuario. Sin código hasta que se apruebe
toda la arquitectura. Restricción dura del usuario: ningún componente nuevo puede
ser "un número mágico más inteligente"; toda constante debe justificarse como
derivable de contexto/MarketObjects/narrativa.

---

## PRINCIPIO 5 — Geometría pura, cero indicadores en análisis de mercado

> Toda lectura, clasificación o ranking del mercado debe usar exclusivamente
> **geometría del precio + matemática pura**, nunca indicadores técnicos derivados.

Queda **PROHIBIDO** el uso de ATR, medias móviles, RSI, estocástico, bandas de
Bollinger, o cualquier indicador derivado en **código de análisis estructural**
(lectura de mercado, detección de estructura, ranking, censo, scoring, bias,
veredicto, fichas técnicas).

Herramientas permitidas (lista completa y excluyente):
- **Niveles de precio reales:** swing high/low, BOS level, CHOCH level, sweep
  level (prior_high/prior_low), FVG zone (high/low), OB zone (top/bottom),
  PD Array (zone_high/zone_low)
- **Distancias en pips:** `abs(close - nivel)`, `min(abs(close - zone_high),
  abs(close - zone_low))`
- **Ratios geométricos:** distancia / leg_range, porcentaje de retracción
  (OTE 61.8-78.6%), posición porcentual en el rango PD
- **Conteos y estados:** edad en velas, estado activo/invalidado, dirección
- **Operaciones aritméticas puras:** suma, resta, multiplicación, división,
  comparación, valor absoluto, mínimo, máximo

**Única excepción:** el módulo de **activación de entradas automáticas del bot**
(trigger de ejecución) puede usar indicadores (estocástico, bollinger, etc.)
exclusivamente para decidir el momento exacto de la orden de entrada. Nunca para
leer, clasificar o rankear el mercado.

**Vigencia:** inmediata. Cualquier código nuevo de análisis que introduzca ATR
o indicadores será rechazado en revisión. Código existente debe migrarse.

**Cumplimiento confirmado 2026-07-29:**
- ATR removido de `detectors/liquidity.py`, `detectors/liquidity_context.py`,
  `scripts/rutina_eurusd.py`.
- Reemplazo: `atr_period` → `range_window`; cálculo puro high-low (`avg_candle_range`).
- Cobertura: detección OB/FVG, `_last_event()` scan-back, `setup_quality_pct`.
- Guarda CI: `grep -E atr|ATR|_atr detectors/ scripts/ app_observador/core/pipeline.py`
  no debe matchear en ruta de análisis estructural.

---

## PROCESO DE CUMPLIMIENTO

1. Ante un parámetro nuevo/observable, Hermes aplica el Principio 3 (4 preguntas).
2. Si es arbitrario → propone sustitución por concepto para R10+; documenta.
3. Si afecta fase congelada (R7) → documenta, NO implementa.
4. **Guarda anti-indicadores:** antes de cualquier cambio en análisis de mercado,
   verificar que no introduzca ATR, medias móviles, RSI, estocástico u otros
   indicadores derivados en el camino de lectura de mercado. Usar `grep` de
   `atr|ATR|_atr|rsi|RSI|ema|EMA|sma|SMA|stoch|bollinger` como gate.
5. El `grep`-equivalente de "constantes arbitrarias" (estilo test T3.2A) puede
   usarse como guarda arquitectónico en R10+.
