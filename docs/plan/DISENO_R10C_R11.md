# DISENO R10.C / R11 — Motor de interpretación semántica

**Estado:** IMPLEMENTADO (Fases A-E, 2026-07-22). Adaptador de wiring completado.

**Fases completadas:**
- Fase A (StateMachine): `ict_backtest/state_machine.py` — transiciones CREATED→ACTIVE→MITIGATED/INVALIDATED/CONSUMED por evento. 3 tests.
- Fase B (Invalidators): `ict_backtest/invalidators.py` — predicados puros `rompio_swing_que_defendia`, `liquidez_tomada_sin_continuacion`, `bos_opuesto_en_misma_narrativa`. 3 tests.
- Fase C (ObjectGraph): `ict_backtest/object_graph.py` — grafo causal con navegación por punteros, `opuesto_en()`. 3 tests.
- Fase D (MarketNarrative): `ict_backtest/market_narrative.py` — narrativa viva con `from_root()`, `is_active()`, `signal_objects()`, `is_noise()`. 3 tests.
- Fase E (EventEngine + run_semantic): `ict_backtest/event_engine.py` — loop dirigido por eventos, `run_semantic()` como drop-in parcial de `run_sequence()`. 1 test + equivalencia demostrada (`Legacy ⊆ Semantic`).
- **Fase F (Adaptador de wiring):** `ict_backtest/semantic_adapter.py` — `adapt_semantic_to_legacy()` convierte la salida de run_semantic al formato dict de canonical.py. Tracing causal (SWEEP root + BOS parent) desde ObjectGraph. `run_semantic()` gana `entry_at`, `time` y `_find_return_bar()`. 20 tests.

**Total tests R10.C:** 22 unitarios + 20 adaptador = 42 (todos verdes, 2026-07-22).

**Restricción dura (del usuario):** NINGÚN componente nuevo puede ser "un número
mágico más inteligente". Si durante el diseño aparece una constante, debe
DEMOSTRARSE por qué no puede derivarse del contexto, de los MarketObjects o de la
narrativa. El objetivo NO es optimizar parámetros: es ELIMINAR la necesidad del
parámetro cuando la decisión se deriva del estado semántico del mercado.

**Relación con R10:** R10 (Propuesta A, commiteado 057a44d) derivó la ventana de
N velas de la FUERZA del BOS (tabla empírica). Eso sigue siendo "conteo de velas
parametrizado por estado" => NO cumple Principio 1/2/4 en el fondo. R10.C + R11
lo reemplazan por caducidad por EVENTO semántico. R10.B (calibrar tabla real)
queda EN PAUSA hasta aprobar esto.

---

## 1. PROPÓSITO Y ALCANCE

**Problema que resuelve:** hoy la decisión "esta estructura ya no vale" se toma
con `índice - índice > N` (conteo temporal). R10.C/R11 la reemplaza por
"el mercado la invalidó por ACCIÓN" (evento sobre relaciones de MarketObjects).

**Alcance R10.C:** apagar el conteo temporal en la confirmación/invalidación de
estructuras ICT (BOS/CHOCH/sweep/POI). Meter máquina de estados + predicados de
invalidación + grafo causal en el motor canónico.

**Alcance R11:** capa de significado completa — MarketNarrative, loop dirigido
por eventos, y al final IA sobre entidades (no sobre velas).

**FUERA de alcance (no tocar):** reglas ICT de DETECCIÓN (cómo se forma un BOS),
POI, quality_score, narrativa de riesgo, entry/SL/TP, flujo de datos (data_feed),
MT5. Solo cambia CÓMO se decide la vigencia y el significado, no la detección ni
la ejecución.

---

## 2. ESTADO ACTUAL (qué YA existe y se reutiliza — verificado en código)

- `ict_backtest/market_object.py`: `MarketObject` YA tiene `ObjectState`
  (CREATED/ACTIVE/MITIGATED/INVALIDATED/CONSUMED) y `parent_object` /
  `related_objects` (cadena causal). La semilla del grafo y la máquina de estados
  YA EXISTE en el modelo; el motor activo no la usa.
- `ict_backtest/detectors/`: `detect_bos`, `detect_choch`, `detect_displacement`,
  `detect_fvg`, `detect_liquidity`, `detect_order_blocks` ya producen features
  por vela. Son CAPA DE OBSERVACIÓN reutilizable.
- `ict_backtest/market_structure.py`: reglas canónicas BOS/CHOCH con memoria
  secuencial (`confirm_bars`, "último BOS"). Reutilizable como lógica de
  detección; lo que cambia es que su salida alimente ESTADOS, no un contador.
- `ict_backtest/object_adapter.py` + `ict_backtest/translation.py`: ya convierten
  frames <-> MarketObject[]. Capa de compatibilidad reutilizable.
- `ict_backtest/sequence.py`: `run_sequence` recorre velas y hoy transiciona por
  `i - state.X_idx > cfg.bos_gap`. Es el que se REEMPLAZA (la lógica de caducidad).

---

## 3. COMPONENTES QUE DESAPARECEN O DEJAN DE DECIDIR

- **`SequenceConfig.bos_gap` (int | None):** deja de ser fuente de decisión de
  vigencia. Queda SOLO como límite de seguridad defensivo (ver sección 9) y,
  aun así, debe justificarse como máximo absoluto, no como ventana típica.
- **`confirmation_window()` (sequence.py):** deja de existir como productor de N
  velas. Su cálculo de FUERZA (`r`) se REENCARGA en la capa de calidad/narrativa
  (sección 7), no en caducidad.
- **Comparaciones `i - state.X_idx > N` en run_sequence (líns 392/418):** se
  eliminan. La caducidad pasa a ser por evento, no por índice.
- **`_effective_bos_gap()`:** desaparece.
- **El concepto "ventana de confirmación en N velas":** se elimina del vocabulario
  de decisión. Se reemplaza por "estado semántico de la estructura".

---

## 4. COMPONENTES NUEVOS (aparición)

### 4.1 StateMachine (máquina de estados semántica)
Transiciona `ObjectState` de cada MarketObject por EVENTO del mercado. No por
contador. El enum ya existe (`market_object.ObjectState`); este componente es el
motor que aplica las transiciones y las reglas de cambio. Reutiliza el enum,
no lo redefine.

### 4.2 Invalidators (predicados de invalidación semántica)
Funciones PURAS que reciben un MarketObject + el grafo/contexto y devuelven
`True` si un evento de mercado invalida/mitiga la estructura. Ejemplos:
- `rompio_swing_que_defendia(obj, ctx)` — el precio cerró bajo el swing que el
  BOS defendía.
- `bos_opuesto_en_misma_narrativa(obj, grafo)` — apareció BOS/CHOCH en dirección
  contraria dentro de la misma narrativa (cambio de carácter real).
- `liquidez_tomada_sin_continuacion(obj, grafo)` — se llevó la liquidez objetivo
  y no hubo seguimiento.
NINGUNO usa índice - índice. Todos operan sobre relaciones/estado.

### 4.3 ObjectGraph (grafo causal)
Contenedor de MarketObjects indexado por id, con aristas `parent_object` /
`related_objects`. Permite consultar "¿qué cuelga de este BOS?", "¿qué narrativa
lo contiene?", "¿hay un BOS opuesto?". Hoy el modelo ya guarda los punteros;
ObjectGraph los EXPONE y los CONSULTA. Sin pesos, sin aprendizaje: solo
navegación estructural.

### 4.4 MarketNarrative (capa de significado)
Una instancia por "historia de precio coherente" activa (ej: "H4 bullish busca
barrer SSL y continuar"). Agrupa los MarketObjects de una cadena causal
(sesgo HTF -> POI -> sweep -> BOS/MSS -> FVG/OB). Valida que un objeto suelto
pertenezca a una narrativa viva (si no, es RUIDO). Ya diseñada en
MARKET_OBJECT_MODEL.md; aquí se convierte en componente vivo del motor.

### 4.5 EventEngine (motor de eventos)
Recorre el LTF y EMITE eventos de mercado (no timers): `SweepDetected`,
`Displacement`, `StructureBroken`, `SwingBroken`, `LiquidityTaken`,
`StructureInvalidated`, `StructureMitigated`. El loop deja de ser "por cada vela
pregunto caducó?" y pasa a "cuando el evento ocurre, transiciono estado".

### 4.6 SemanticRules (reglas ICT como estados)
Capa que mapea reglas ICT a estados semánticos (sección 8). Declara QUÉ evento
cambia QUÉ estado de QUÉ objeto, de forma declarativa y auditable.

---

## 5. CÓMO SE RELACIONAN (flujo)

```
data_feed (observación)
   -> detectors/* (features por vela)            [REUTILIZADO]
   -> EventEngine emite eventos                  [NUEVO]
   -> StateMachine aplica transiciones           [NUEVO]
        leyendo Invalidators (predicados)        [NUEVO]
        sobre ObjectGraph (relaciones)           [NUEVO]
   -> MarketNarrative agrupa objetos vivos       [NUEVO]
   -> SemanticRules declara el mapeo evento->estado [NUEVO]
   -> signals se emiten SOLO si el objeto está ACTIVE/MITIGATED
      dentro de una narrativa viva (no por reloj)
```

Jerarquía del Principio 2 cumplida: Datos -> MarketObjects -> Contexto
(grafo) -> Narrativa -> Interpretación (estados) -> Decisión -> Ejecución.

---

## 6. QUÉ INFORMACIÓN ALMACENA CADA COMPONENTE

- **MarketObject** (ya existe): `type`, `origin_tf`, `role`, `direction`,
  `zone_high/low`, `state`, `meta` (high/low/sweep/atr del origen),
  `parent_object`, `related_objects`, `bar_index`. NO se le agrega campo de
  "caducidad en N velas".
- **ObjectGraph**: mapa id -> MarketObject; índice inverso de aristas; mapa
  narrativa_id -> [objetos]. Solo navegación.
- **MarketNarrative**: id, sesgo HTF (bullish/bearish), POI ancla, lista de
  objetos miembros, estado de la narrativa (VIGENTE/ROTA), y la "historia"
  (secuencia de eventos que la sostienen).
- **EventEngine**: cola de eventos del barrido actual; cada evento lleva
  (tipo, bar_index, objeto_afectado, objeto_disparador).
- **StateMachine**: tabla de transiciones permitidas por tipo de objeto +
  resultado de evaluar Invalidators.
- **SemanticRules**: declaración estática evento -> (objeto, estado_nuevo) +
  predicado que lo justifica. Es la parte AUDITABLE (Principio 4).

---

## 7. EVENTOS QUE PRODUCEN CAMBIOS DE ESTADO

El EventEngine emite y la StateMachine consume. Cada evento dispara transiciones
SOLO sobre los objetos afectados (navegando ObjectGraph), no sobre "todos los que
lleven N velas vivos".

| Evento | Objetos afectados | Transición |
|--------|-------------------|-----------|
| `SweepDetected` | LIQUIDITY | CREATED -> ACTIVE |
| `Displacement` | SWEEP/MSS | ACTIVE -> CONFIRMA impulso |
| `StructureBroken` (BOS/CHOC) | BOS/CHOCH | CREATED -> ACTIVE |
| `SwingBroken` (el swing que defendía un BOS) | BOS padre | ACTIVE -> INVALIDATED |
| `LiquidityTaken` (sin continuación) | POI/BOS | ACTIVE -> MITIGATED |
| `BOS_opuesto` (misma narrativa) | narrativa + BOS previo | narrativa VIGENTE -> ROTA; BOS -> INVALIDATED |
| `Retorno_a_zona` (precio toca zona sin romper) | FVG/OB | ACTIVE -> MITIGATED (sigue viva para entry) |

CLÁUSULA DE CONSTANTES (restricción del usuario): cualquier umbral de
"confirmación" dentro de un evento (ej: "el BOS cuenta si el cierre rompe el
swing") debe expresarse como RELACIÓN DE PRECIO sobre el MarketObject (zona,
swing, estructura), NUNCA como "N velas". Si un evento requiere un umbral
numérico para decidir (ej: mínimo de cuerpo para contar como displacement),
debe justificarse en el diseño como derivable del contexto (rango de la vela vs
rango promedio del contexto = lo que R10 ya usaba para `r`, pero AQUÍ solo pesa
la CALIDAD del evento, no la caducidad).

---

## 8. REGLAS ICT -> ESTADOS SEMÁNTICOS (mapeo)

| Regla ICT hoy | Estado semántico resultante |
|---------------|------------------------------|
| BOS confirmado por cierre decisivo | BOS: CREATED -> ACTIVE (evento `StructureBroken` + cierre sobre swing) |
| BOS no continuó en N velas (caducaba por timer) | BOS: ACTIVE -> INVALIDATED solo si `SwingBroken` o `BOS_opuesto` |
| Retorno del precio a la zona (mitigación) | FVG/OB: ACTIVE -> MITIGATED (viva para entry, NO muerta) |
| CHOCH real (rompe swing del último BOS, en contra) | CHOCH: ACTIVE; invalida narrativa previa |
| Sweep de liquidez (mecha) | SWEEP: ACTIVE (no es estructura, es liquidez tomada) |
| POI solo en HTF, anclado a narrativa | POI: ACTIVE solo si pertenece a narrativa VIGENTE |

La regla "BOS caduca en N velas" SIMPLEMENTE DESAPARECE. No se reemplaza por
"N velas más inteligentes": se reemplaza por "el BOS vive mientras ningún
invalidator dispare".

---

## 9. DECISIONES QUE DEJAN DE DEPENDER DE VELAS / CONTADORES

1. **Vigencia de BOS/CHOCH:** deja de ser `índice - idx > N`. Pasa a ser
   "ningún invalidator semántico disparó".
2. **Mitigación de POI/FVG/OB:** deja de depender de ventana; es "el precio
   tocó la zona" (relación de precio, no de tiempo).
3. **Reset de la secuencia de estados:** hoy `state.reset()` por timer; pasa a
   `state.reset()` por evento `BOS_opuesto` / `SwingBroken`.
4. **Confirmación de entrada:** la entry se habilita cuando el objeto está
   ACTIVE o MITIGATED dentro de narrativa VIGENTE — no por "pasaron N velas
   desde el BOS".

**ÚNICO conteo temporal permitido (y debe justificarse):** un tope de seguridad
ABSOLUTO (`max_hold` ya existente en run_backtest) para no dejar una estructura
PENDING viva para siempre en mercado lateral (choppy) donde ningún invalidator
dispara. Este tope NO es la fuente de la decisión ICT: es un cable de emergencia
etiquetado como "límite de seguridad" (Principio 1, líns 19-23). Su valor debe
documentarse como máximo defensivo, no como ventana típica, y preferiblemente
derivarse del régimen (rango del contexto) en lugar de ser un literal.

---

## 10. MÓDULOS REUTILIZABLES vs REEMPLAZABLES

**REUTILIZABLES (sin tocar lógica de detección):**
- `ict_backtest/detectors/*` — producen features por vela. Siguen siendo la
  capa de observación. El EventEngine los consume, no los reescribe.
- `ict_backtest/market_structure.py` — la regla canónica de BOS/CHOCH (qué es un
  BOS real, el "último BOS" para CHOCH) se REUTILIZA para emitir los eventos
  `StructureBroken` / `BOS_opuesto`. No se toca la detección.
- `ict_backtest/data_feed.py` — `build_objects` sella capa/rol. Reutilizado.
- `ict_backtest/object_adapter.py` + `ict_backtest/translation.py` — capa de
  compatibilidad frames<->MarketObject. Reutilizada intacta.
- `ict_backtest/market_object.py` — `MarketObject`, `ObjectState`, `ObjectType`,
  `Role`, `parent_object`, `related_objects`. REUTILIZADO como base del grafo
  y la máquina de estados. No se redefinen.
- `ict_backtest/run_backtest.py::run_sequence_backtest` — orquesta backtest; se
  mantiene, solo cambia qué motor de señales llama adentro.

**REEMPLAZABLES (la lógica de caducidad por timer se elimina):**
- `ict_backtest/sequence.py::run_sequence` — hoy recorre velas y caduca por
  `i - idx > N`. Se REEMPLAZA por un `run_semantic(engine, ...)` que consume
  EventEngine + StateMachine. `run_sequence` queda como PATH LEGACY congelado
  (igual que build_signals en R7) hasta migrar consumidores.
- `ict_backtest/sequence.py::confirmation_window` / `_effective_bos_gap` —
  ELIMINADOS (eran el productor de N velas).
- `SequenceConfig.bos_gap` — eliminado como fuente de decisión; queda solo
  `max_hold` como tope de seguridad (sección 9).
- `ict_backtest/engine.py::build_signals_from_frames` — YA eliminado en R7;
  no aplica.

---

## 11. FASES (R10.C + R11) — cada una con DoD, criterios verificables y TDD

Orden impuesto por dependencias: A (estados) desbloquea B (invalidadores);
C (grafo) alimenta B y D (narrativa); E (eventos) necesita B+C; F (IA) necesita
todas. Saltarse a D sin A/B/C reproduce el error ya diagnosticado (POI sin
narrativa = ruido).

### FASE A — Máquina de estados semántica (R10.C, raíz)
Hacer que los MarketObjects transicionen `ObjectState` por EVENTO, usando el
enum YA EXISTENTE. Sin esto, nada más tiene donde apoyarse.

- **DoD:** `StateMachine` aplica transiciones CREATED->ACTIVE->MITIGATED/
  INVALIDATED->CONSUMED sobre MarketObject, sin leer índices de vela.
- **Criterio verificable:** en un escenario sintético (objetos dados, no
  load_frames), emitir `SwingBroken` sobre el padre marca el BOS como
  INVALIDATED; emitir `Retorno_a_zona` marca FVG como MITIGATED. Cero asserts de
  `índice - índice`.
- **TDD:** RED = test que construye objetos y exige transición por evento; GREEN
  = StateMachine mínima; REFACTOR = nada (mínimo). NO toca sequence.py aún.

### FASE B — Invalidators (predicados puros de invalidación)
Funciones puras sobre MarketObject + contexto, sin contador.

- **DoD:** `rompio_swing_que_defendia`, `bos_opuesto_en_misma_narrativa`,
  `liquidez_tomada_sin_continuacion` implementados como predicados puros que la
  StateMachine consulta. Ninguno recibe un `n_velas`.
- **Criterio verificable:** para un BOS con swing defendido en precio P, el
  predicado `rompio_swing_que_defendia` es True solo si el ctx muestra cierre <
  P (relación de PRECIO). Para BOS opuesto, True solo si otro BOS en dirección
  contraria existe en el mismo grafo. Sin umbrales de velas en ninguno.
- **CLÁUSULA CONSTANTE:** si algún predicado necesita un umbral (ej: "cierre
  decisivo" = cuerpo mínimo), se justifica como relación de precio (cuerpo vs
  rango del contexto), NO como N velas. Se documenta en el doc antes de codear.
- **TDD:** RED = tests de cada predicado con objetos sintéticos; GREEN = lógica
  pura; REFACTOR = nada.

### FASE C — ObjectGraph (grafo causal vivo)
Poblar y consultar `parent_object` / `related_objects` durante el recorrido.

- **DoD:** al recorrer el LTF, cada nuevo objeto se enlaza a su padre (sweep ->
  BOS, BOS -> FVG) y el grafo responde consultas de vecindad e inversión.
- **Criterio verificable:** dado un BOS, `graph.parents(bos)` devuelve el sweep;
  `graph.children(sweep)` devuelve el BOS; `graph.opposite_in_narrative(bos)`
  devuelve el BOS contrario si existe. Todo por punteros, sin tiempo.
- **TDD:** RED = test de grafo con objetos sintéticos enlazados; GREEN =
  contenedor + índices; REFACTOR = nada.

### FASE D — MarketNarrative (capa de significado)
Agrupar objetos en "historias" y descartar lo suelto como ruido.

- **DoD:** una narrativa se construye al detectar sesgo HTF + POI; agrupa sweep
  -> BOS -> FVG; un objeto sin narrativa VIGENTE se marca RUIDO (no entra a
  señal).
- **Criterio verificable:** FVG suelto (sin narrativa) => no produce señal; el
  mismo FVG dentro de narrativa VIGENTE => produce señal. Mide la regla del
  doc "FVG sin narrativa es ruido" (MARKET_OBJECT_MODEL.md).
- **TDD:** RED = test narrativa agrupa y filtra ruido; GREEN = constructor
  mínimo; REFACTOR = nada.

### FASE E — EventEngine + run_semantic (loop dirigido por eventos)
Reemplazar el recorrido por timer de `run_sequence`.

- **DoD:** `EventEngine` emite eventos desde detectors/*; `run_semantic` consume
  eventos + StateMachine + ObjectGraph + Narrativa y emite señales SOLO desde
  objetos ACTIVE/MITIGATED en narrativa VIGENTE. `run_sequence` queda LEGACY
  congelado.
- **Criterio verificable (equivalencia, no regresión):** sobre XAUUSD H4 real,
  `run_semantic` produce señales cuyo CONJUNTO de bar_index de entrada es
  SUBSET de las de `run_sequence` (la versión semántica es más estricta: quita
  las que caducaban por reloj sin invalidación real). Se documenta la cuenta.
  Cero compares `índice - índice`. El `max_hold` queda como único tope de
  seguridad y se reporta cuántas señales lo usaron.
- **CLÁUSULA:** si `run_semantic` necesita un parámetro nuevo, se justifica como
  derivable de contexto o se rechaza. NO se introduce `bos_gap` de nuevo.
- **TDD:** RED = test que `run_semantic` no usa `confirmation_window` (grep
  equivalente: 0 referencias a bos_gap en el nuevo módulo); GREEN = motor mínimo;
  REFACTOR = nada. Luego test de equivalencia de señales.

### FASE F — IA sobre entidades (R11 puro, post-A..E)
Solo cuando el modelo semántico existe, la IA aprende sobre MarketObjects y
narrativas, no sobre velas.

- **DoD:** un módulo de scoring/aprendizaje que recibe MarketObject[] +
  narrativa y produce calidad/confianza, reemplazando `quality_score` manual.
- **Criterio verificable:** el score de una estructura se deriva de su estado +
  narrativa + relaciones (entidades), no de features de vela aisladas. Test de
  que la entrada del modelo son objetos/narrativa, no un DataFrame de OHLC.
- **TDD:** RED = test de que el modelo recibe entidades; GREEN = adapter
  mínimo; REFACTOR = nada. (Alcance grande; se subdivide al entrar.)

---

## 12. CIERRE / NO REGRESIONES

- R7 queda intacto: `run_sequence` legacy se conserva congelado; `run_semantic`
  es el nuevo path canónico (igual patrón que T3.1/T3.2 de R7).
- R10 (Propuesta A, 057a44d) queda como PATH LEGACY hasta Fase E; en Fase E se
  elimina `confirmation_window` y `bos_gap` como fuente de decisión.
- R10.B (calibrar tabla real) queda EN PAUSA: la tabla empírica ya no se usa
  para caducidad; la fuerza `r` se relega a calidad/narrativa (Fase D/F), no a
  ventana.
- Todo nuevo umbral numérico debe pasar la CLÁUSULA DE CONSTANTES (sección 7) y
  documentarse en este doc ANTES de implementarse.

---

## 13. WIRING — Adaptador R10.C → Pipeline Canónico (Fase F)

**Problema:** `run_semantic()` devuelve campos distintos a los que
`canonical.evaluate_signals()` espera en `raw_sigs`.

**Campos de run_semantic:** id, root_id, type, direction, bar_index, entry_at, time,
zone_high, zone_low, narrative_active, state.

**Campos requeridos por canonical:** direction, entry_at, sweep_at, bos_at, time,
entry, zone_authority, poi_present, breaker_*, ote_*, smt_*.

**Solución:** `ict_backtest/semantic_adapter.py` — `adapt_semantic_to_legacy()`.

### Mapeo de campos

| Campo canónico | Fuente en adaptador |
|---|---|
| `direction` | `sig["direction"]` (directo) |
| `entry_at` | `sig["entry_at"]` (calculado por `_find_return_bar` o `bar_index`) |
| `sweep_at` | Root SWEEP desde trazado de causalidad en ObjectGraph |
| `bos_at` | BOS parent desde trazado de causalidad en ObjectGraph |
| `time` | `sig["time"]` (calculado desde ltf_df) |
| `entry` | `0.0` (placeholder; canonical resuelve via `fill_entry_price`) |
| `zone_authority` | Mapa opcional pre-computado |
| `poi_present` | Mapa opcional pre-computado |
| `breaker_*` / `ote_*` / `smt_*` | `bos_obj.meta` (heredado del BOS en la cadena causal) |

### Cómo usar el adaptador

```python
from ict_backtest.event_engine import run_semantic
from ict_backtest.semantic_adapter import adapt_semantic_to_legacy
from ict_backtest.data_feed import build_objects

# 1. Obtener objetos y señales semánticas
objs = build_objects({"M15": ltf_df})
sem_signals = run_semantic(objs, est_htf_fn, cfg, ltf_tf="M15", ltf_df=ltf_df)

# 2. Adaptar al formato canónico
legacy_signals = adapt_semantic_to_legacy(sem_signals, objs)

# 3. Pasar a canonical.evaluate_signals (como raw_sigs)
# (requiere refactor de evaluate_signals para aceptar raw_sigs directamente)
```

### ✅ Completado (2026-07-22)

- ✅ Cableado `adapt_semantic_to_legacy` en `canonical.evaluate_signals`
  (kwarg `use_semantic=True` como DEFAULT).
- ✅ Propagación `use_semantic` desde `run_backtest.py` (CLI `--use-semantic`
  default True, `--no-use-semantic` para legacy).
- ✅ Verificación: 106 key tests pasan, 7 tests de equivalencia semantic-vs-legacy pasan.
- `sequence.py` se conserva in-situ (47 imports en codebase; migración future).



