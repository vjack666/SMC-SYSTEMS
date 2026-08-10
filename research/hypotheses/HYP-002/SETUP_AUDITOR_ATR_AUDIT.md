# SETUP_AUDITOR_ATR_AUDIT.md — Auditoría de la contradicción ATR vs Ley Fundamental

> **Auditoría documental (2026-08-10). LECTURA DEL REPOSITORIO, CERO código, CERO ejecución.**
> Responde a la orden del Director: revisar la compatibilidad de C1-C7 con la Ley Fundamental
> ("Sin indicadores: matemática pura y geometría del mercado"; ATR/EMA/RSI en `engine/` es sospechoso)
> frente a C2 (`|close-open| >= k·atr`) y C5 (`bos_level ± 0.5·atr`).

---

## 0. Veredicto de cabeza

**Contradicción encontrada: SÍ, pero es de NOMBRE, no de SUSTANCIA.** El motor NO usa ATR
(indicador). Lo que el código llama `atr` es, por contrato explícito, **`avg_candle_range` = media
móvil de `(high - low)`** — geometría pura, sin indicadores. La contradicción real es que C2/C5
(vistos por el Director) **mencionan "ATR"**, lo que viola el ESPÍRITU de la Ley (naming sospechoso)
aunque no su letra (la sustancia ya es rango puro). La Reconciliación ya retiró el umbral de C2; este
doc cierra el flanco del nombre y propone C2/C5 sin la palabra ATR y sin que el rango sea gate.

---

## 1. ¿Aparece ATR realmente en el motor y para qué? (verificado en código)

**NO aparece ATR como indicador en ningún módulo de `engine/`.** Cada módulo de `engine/` lo declara
explícitamente en su docstring:
- `engine/micro.py:8`: "Geometría pura: solo OHLC + swings. SIN indicadores (EMA/RSI/ATR)."
- `engine/fvg_poi.py:8`: "Sin indicadores (no ATR/EMA). Solo geometría: high/low/open/close."
- `engine/dealing_range.py:10-11`: "geometría pura (rolling max/min de high/low). SIN indicadores (no ATR, no medias)."
- `engine/bos/structure.py:32`: "Sin indicadores: ni ATR ni medias móviles (volatilidad = rango high-low)."
- `engine/bias/narrative.py:25`: "Sin indicadores: ni ATR ni medias móviles (volatilidad = rango high-low)."
- `engine/htf_narrative.py:12`, `engine/multitf_context.py`: mismo patrón.

**Lo que SÍ aparece es la columna `atr`**, pero es un ALIAS contractual de `avg_candle_range`:
- `ict_backtest/_util.py:128 avg_candle_range`: "rango promedio de la vela = promedio de (high - low)
  sobre ventana móvil... MATEMÁTICA PURA del gráfico, SIN INDICADORES (equivalente a True Range
  promedio pero sin el componente close-anterior)". Devuelve `rolling(window).mean()` de `high-low`.
- `ict_backtest/data_feed.py:70`: `d["atr"] = avg_candle_range(d, window=50)` con nota: "La columna se
  sigue llamando 'atr' por CONTRATO (object_adapter, sequence.meta, translation la esperan con ese
  nombre), pero su contenido es el rango promedio puro. Migración ATR -> rango (Fase 1)."
- `engine/sequence.py:586`: comenta que `meta["atr"]` "ya es avg_candle_range, fuente única de
  volatilidad; migrado de ATR a rango puro, Fase 1".

**Conclusión 1:** el motor NO depende de un indicador ATR. La métrica de volatilidad es rango
high-low puro. El nombre `atr` es deuda de contrato (columnas legacy esperan ese nombre) y el propio
repo lo documenta como migrado a geometría.

---

## 2. ¿Ese uso es dependencia de indicador o variable matemática ya existente?

**Variable matemática ya existente (geometría del gráfico), NO indicador.** `avg_candle_range` es
equivalentemente "rango promedio de la vela" = una media móvil de `high - low`. No es ATR (que usa
True Range con `|close_prev - high|`, `|close_prev - low|`). No hay EMA/RSI/Wilder-smoothing en
`engine/`. Por tanto no viola la Ley Fundamental en sustancia. La única violación es de **nomenclatura**
("atr" en el código) y de **apariencia** en C2/C5 (donde yo escribí "ATR" literalmente).

---

## 3. ¿C2 necesita realmente un umbral de rango/ATR para auditar displacement?

**NO.** La Reconciliación ya lo retiró. El motor YA clasifica displacement vía
`detectors/displacement.py:detect_displacement` (verificado):
- `large_body = body > avg_range * 1.5` (rango puro, no ATR).
- `small_wick = wick_ratio < 0.4`.
- dirección: `close > open` (bull) / `close < open` (bear).

O sea el motor YA decide si hubo displacement usando **geometría del cuerpo vs rango promedio del
contexto + relación mecha/cuerpo**. El auditor NO necesita re-umbralizar: solo debe **registrar** la
decisión del motor y las propiedades observables (cuerpo, rango, mecha, relación con sweep). C2
queda como *evento observado*, no como gate numérico del auditor.

---

## 4. Separar "medir magnitud del movimiento" de "demostrar causalidad del displacement"

- **Magnitud** = propiedad descriptiva (cuerpo/rango, o `displacement_magnitude = body / avg_range`
  ya calculado en `detectors/displacement.py:56`). Es MEDICIÓN, no veredicto.
- **Causalidad** = que ese displacement nació del sweep y participa en el BOS (ligadura). Es
  INDEPENDIENTE de la magnitud. Un displacement pequeño pero bien ligado sigue siendo causal; uno
  grande pero suelto no lo es.
- El auditor mide magnitud como DATO (para la investigación futura de "qué caracteriza un displacement
  real de la tesis") pero NO la usa para PASS/FAIL. La causalidad se audita por orden+dirección+ligadura
  (Reconciliation C3), no por tamaño.

---

## 5. Propuesta de C2 sin ATR (geometría/estructura/causalidad primero)

C2 (enmendado definitivamente):
- **Evento afirmado:** impulso direccional posterior al sweep, en la dirección del setup.
- **Dato observable (geometría pura):** `displacement_*` flag del `MarketObject` (ya calculado por
  `detect_displacement` con cuerpo vs rango promedio + mecha pequeña) Y, como propiedades a
  **registrar** (no gate): cuerpo `|close-open|`, rango de la vela `high-low`, mecha, y
  `body / avg_range` (esta última calculable del `MarketObject` ya que `avg_range` vive en `meta["atr"]`
  = rango promedio — pero el auditor la trata como DESCRIPTIVA, no como umbral).
- **Relación causal:** `displace_at > sweep_at` Y dirección coherente con el sweep (C1). Sin ligar a
  magnitud.
- **Veredicto:** PASS = flag en dir correcta y posterior al sweep. UNKNOWN = sin `MarketObject` de
  `displace_idx`. NUNCA PASS por magnitud. La magnitud se archiva como observación, no decisión.
- **Sin palabra "ATR"** en la regla del auditor. Si se cita `meta["atr"]`, se etiqueta explícitamente
  como "rango promedio de la vela (geometría pura, migrado de ATR)".

---

## 6. Si el rango solo puede conservarse como dato descriptivo auxiliar → NO-GATE / NO evidencia

Declaración explícita: **el rango promedio de la vela (`avg_candle_range`, alias `meta["atr"]`) es
DATO DESCRIPTIVO AUXILIAR. NO es gate de ninguna capa del SETUP AUDITOR. NO es evidencia suficiente
de displacement, sweep, BOS, POI ni retorno.** Su único uso permitido en el auditor es normalizar la
magnitud del movimiento para el registro descriptivo (p.ej. "el cuerpo fue 1.8× el rango promedio del
contexto"), nunca para decidir PASS/FAIL ni para definir qué es un displacement.

---

## 7. C5 y el POI sintético basado en rango (`bos_level ± 0.5·atr`)

**Preocupación del Director:** que el auditor valide un POI sintético creado con un "indicador".

**Hecho verificado (`engine/sequence.py:582-596`):** el cuadro de retorno se traza con la zona
cacheada FVG/OB (REAL, geometría de imbalance). Solo si NO hay zona finita cae al fallback:
`zone_high = bos_level + 0.5 * atr`, `zone_low = bos_level - 0.5 * atr`, donde `atr` = `avg_candle_range`
(rango promedio, geometría pura). Es un cuadro de RESPALDO por si falta el FVG real, no un POI por
sí mismo.

**Corrección para C5 (ya en Reconciliation, aquí se blinda contra el flanco ATR):**
- El auditor NUNCA acepta el cuadro sintético como POI real. Si se usó el fallback `bos_level ± 0.5·rango`,
  la capa 8 (retorno) emite **WARNING**, no PASS, y se marca explícitamente "retorno a cuadro de
  respaldo, no a POI FVG/OB real".
- Se prohíbe nombrar ese fallback "POI": es un nivel derivado de geometría (rango) usado solo cuando
  falta el imbalance real. El auditor lo trata como evidencia INSUFICIENTE de POI.
- El uso de `0.5·rango` en el fallback NO es un indicador (es rango high-low puro), pero tampoco es
  evidencia de setup: es tolerancia de mitigación. Se documenta como tal, no como validación.

---

## 8. Compatibilidad final con la Ley Fundamental

| Punto de la Ley | Estado tras auditoría |
|---|---|
| "Sin indicadores" en `engine/` | CUMPLIDO: `engine/` no usa ATR/EMA/RSI; volatilidad = rango high-low. |
| ATR en motor es sospechoso | LA COLUMNA `atr` existe pero es alias de `avg_candle_range` (geometría); el repo lo documenta como migrado. No es indicador. |
| C2 de C1-C7 | YA enmendado por Reconciliation (sin umbral). Este doc lo blinda: sin palabra "ATR", magnitud = dato descriptivo, no gate. |
| C5 de C1-C7 | El fallback `bos_level ± 0.5·rango` NO se acepta como POI; capa 8 = WARNING si sintético. |
| El auditor no debe validar POI sintético por indicador | CUMPLIDO: el fallback es geometría (rango), no indicador, y se rechaza como POI real. |

**No se requiere cambio de `engine/`.** La sustancia ya es conforme a la Ley; solo había confusión de
nombre en mi doc original y en el fallback. Se documenta y se cierra.

---

## 9. Recomendación de la siguiente puerta

La contradicción ATR vs Ley Fundamental **queda resuelta documentalmente**: el motor usa geometría
pura; C2/C5 no introducen indicadores ni gates de magnitud. La siguiente puerta (piloto de 5
emisiones) puede proceder con las definiciones de C2/C5 ya blindadas. ANTES del piloto, la única
acción pendiente es **renombrar en la documentación** `atr` → `rango_promedio` donde el auditor lo
cite, para no reactivar la sospecha de la Ley. No se toca `engine/`, no se toca backtest, no se
ejecuta nada, no se crea EXP.

*Auditoría documental de la contradicción ATR. Sin código, sin ejecución. Complementa
`SETUP_AUDITOR_C1_C7.md`, `SETUP_AUDITOR_RECONCILIATION.md` y `SETUP_AUDITOR_DATA_FORENSICS.md`.*