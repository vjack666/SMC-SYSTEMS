# AUDITORÍA PROFESIONAL COMPLETA — SMC-SYSTEMS

Comité de revisión técnica: Principal Software Architect · Quant Developer Senior ·
Python Staff Engineer · ML Engineer · Software Testing Architect · Performance Engineer ·
Trading Systems Architect.

Fecha: 2026-07-17 · Commit base: 104964c · Método: lectura directa del código real,
ejecución de imports y tests, trazado de llamadas entre módulos. Evidencia citada como
`archivo:línea`. Donde no pude demostrar algo, lo digo explícitamente.

Alcance recorrido: 325 archivos .py, ~41.7k LOC, 64 archivos de test (~1158 asserts/tests),
paquetes: `ict_backtest/` (+`v2/`), `detectors/`, `signals/`, `ml/`, `agents/`, `legacy/`,
`features/`, `regime/`, `data/`, `scripts/`, `tests/`.

---

## RESUMEN EJECUTIVO

SMC-SYSTEMS es un proyecto cuantitativo ICT/SMC con ambición real: motor event-driven
de secuencia (sweep→displace→BOS→retorno), backtest con costos y fill next-open, capa v2
multi-TF, capa ML de filtro de calidad, y una capa semántica R10/R11 basada en MarketObjects.
La disciplina documental es alta (docs/, METRICS_CANON, caveats honestos sobre cobertura).

Pero como sistema de software presenta **fragmentación de motores**: coexisten 3
implementaciones de estructura de mercado (BOS/CHOCH) con reglas distintas, y 2 motores de
señales (canonical/sequence vs legacy) donde el ML entrena sobre el legacy y producción
corre el canónico. Esto es el riesgo #1: **train/serve mismatch**.

Veredicto global: base sólida de dominio, arquitectura fragmentada, testing amplio pero
lento y con integración frágil, ML desalineado del motor de producción. NO listo para
producción ni para capital institucional en su estado actual, pero a 2-3 refactors
estructurales de estarlo.

---

## FASE 1 — ARQUITECTURA

### 1.1 Coexistencia de 3 motores de estructura de mercado (CRÍTICO)
Evidencia:
- `ict_backtest/market_structure.py:137` `detect_market_structure` — BOS = cierre rompe
  swing previo CONFIRMADO por `confirm_bars` cierres consecutivos (`market_structure.py:159`);
  CHOCH real = rompe el nivel del ÚLTIMO BOS en dirección opuesta (`:170-176`).
- `detectors/bos.py` `detect_bos` — segunda implementación de BOS.
- `detectors/choch.py:14-24` `detect_choch` — CHOCH por medias móviles 20/50 como contexto
  + ruptura de `high.rolling(20).max().shift(1)`. Criterio COMPLETAMENTE distinto al de
  `market_structure`.

Consumidores divergentes:
- El motor canónico (`ict_backtest/canonical.py:30`, `sequence.py:446`, `v2/orchestrator.py:22`,
  `run_backtest.py:60`) usa `detect_market_structure`.
- Scripts y tests (`scripts/ablation_study.py:20-21`, `scripts/build_real_dataset.py:13-14`,
  `tests/test_liquidity_context.py:19`, `detectors/__init__.py:1-2`) usan `detectors.bos/choch`.

Impacto: dos definiciones de BOS/CHOCH que pueden contradecirse sobre el mismo dato. Un
"BOS" para el dataset ML (detectors) no es el mismo "BOS" que decide el trade (canonical).
Riesgo: features ML etiquetadas con una semántica y decisiones tomadas con otra.
Recomendación: declarar `market_structure.detect_market_structure` como ÚNICA fuente;
`detectors/bos.py` y `detectors/choch.py` → o se borran o se reescriben como wrappers finos
que llaman al canónico. Prioridad: ALTA.

### 1.2 Dos motores de señales; ML entrena sobre el legacy (CRÍTICO)
Evidencia:
- Producción/canónico: `run_backtest.py:103` delega en `canonical.evaluate_signals`.
- ML: `ml/dataset_builder.py:14` `from legacy.backtest.engine import _build_signals_from_context,
  _simulate_trade_with_stats` y `:234` los usa para construir el dataset de entrenamiento.
- `canonical.py` documenta que `legacy/backtest/engine.py` es deuda fuera de alcance.

Impacto: el filtro de calidad ML se entrena sobre señales del motor LEGACY, pero en
producción filtra señales del motor CANÓNICO. Distribución de entrenamiento ≠ distribución
de inferencia = **train/serve skew**. Cualquier métrica ML es optimista/no transferible.
Recomendación: `dataset_builder` debe consumir `canonical.evaluate_signals` +
`engine.simulate_trade` (mismos que producción). Prioridad: ALTA.

### 1.3 Separación dominio/infraestructura — parcial
Positivo: la capa v2 SÍ separa responsabilidades (Strategy decide, Simulator ejecuta sin
leer columnas de decisión — `v2/simulator.py:23` "Does not read bos/fvg/sweep columns";
Plan/Order/TradeResult como contratos en `v2/contracts.py`). Esto es Clean/Hexagonal bien
hecho en el subárbol v2.
Negativo: fuera de v2 no hay capas. `engine.py`, `market_structure.py`, `sequence.py`,
`canonical.py` mezclan carga de datos (imports de `data_feed`), reglas de dominio y I/O de
progreso (`run_backtest.py:31 _write_runner_progress` embebido en el runner). No hay puerto/
adaptador para datos: cada módulo hace su `load_frames`/`load_frame`.
Recomendación: extraer un port de datos único y mover el dominio ICT (structure/sequence/
POI) a un paquete `domain/` sin dependencias de I/O. Prioridad: MEDIA.

### 1.4 Acoplamiento y cohesión
- `ml/dataset_builder.py` acopla 6 subsistemas (agents, legacy, data, features, regime,
  signals) en un solo módulo de 334 líneas → baja cohesión, alto fan-in.
- `sequence.py` (23 KB) concentra secuencia + helpers + `__main__` de prueba. Cohesión media.
- `detectors/__init__.py` reexporta el motor duplicado, propagando el acoplamiento a v2 legacy.
Code smells arquitectónicos detectados: motor duplicado (1.1), god-module (dataset_builder),
import tardío para romper ciclo (`engine.py` importa `row_at_time` al final, `:207`),
función duplicada `_coerce_ts` (engine.py:160 y ~:229 — ver Fase 7).

### 1.5 Flujo de datos / ejecución (event-driven)
El camino canónico está bien trazado: `run_backtest.run_sequence_backtest` → `load_frames`
→ `detect_market_structure` por TF → `evaluate_signals` (canonical) → `simulate_trade`
vela a vela. La capa v2 añade `build_context_stack` + `top_down_allows_trade` (gate D1/H4/
H1/PD) antes de emitir `Order`. El EventLog (`v2/event_log.py`) da trazabilidad real de
OrderAccepted→EntryFilled→TradeClosed. Es genuinamente event-driven en v2.

---

## FASE 2 — MOTOR ICT

### 2.1 BOS — correcto en el canónico
`market_structure.py:157-163`: BOS por cuerpo (close) sobre swing previo con confirmación
de N cierres (`_consecutive_break`). Nivel guardado (`bos_level`). Estado seguido vela a vela
(`_track_structure`). Es una implementación seria y sin look-ahead (usa `.shift(1)`).
Inconsistencia: `detectors/bos.py` NO exige confirm_bars (una vela basta) — ver 1.1.

### 2.2 CHOCH — correcto conceptualmente en canónico, contradictorio entre módulos
`market_structure.py:166-176`: CHOCH = ruptura del nivel del ÚLTIMO BOS en dirección opuesta,
con confirmación. Esto es CHOCH real (no un alias de BOS) — bien.
`detectors/choch.py:17-24`: CHOCH derivado de cruce de medias 20/50 + ruptura rolling. Es
otra cosa. Dos definiciones contradictorias del MISMO concepto en el mismo repo. Riesgo alto
para quien lea features del dataset creyendo que es el CHOCH de producción.

### 2.3 Invalidación event-driven (bien, y alineado con preferencia del owner)
`market_structure.py:220-230`: la estructura muere SOLO por evento (cruce del nivel), se
eliminó la caducidad por tiempo/volatilidad ("aged"). Consistente con la regla de Ruben de
"no reloj disfrazado". `detectors/choch.py:59` idem. Esto es un acierto de diseño.

### 2.4 FVG / Order Blocks / Liquidity / Sweep / Displacement
- `detectors/fvg.py`: FVG de 3 velas estándar. Correcto y compacto.
- `detectors/ob.py`: OB básico. Correcto.
- `detectors/liquidity.py`: port de LuxAlgo (clusters de swings por banda ATR). Documentado
  como "solo informativo, no afecta trading" (`liquidity.py:14`). OK, pero significa que la
  liquidez NO alimenta la decisión — brecha vs tesis ICT (la liquidez es el objetivo del TP).
- Sweep/Displacement viven en `sequence.py`/`canonical.py` (event-driven con memoria y reset).

### 2.5 POI — la brecha definitoria (ya documentada por el propio repo)
`v2/coverage.py:44-63` (legacy_subset) marca C05 "POI anchored to narrative" = **missing**;
en mtf (`:71`) = **partial** ("PD side as soft POI proxy; full POI narrative later"). El
propio sistema reconoce que el filtro más definitorio de ICT (POI anclado a narrativa HTF)
NO está cableado. Coincide con el caveat de AGENTS.md. Honestidad alta; capacidad ICT
incompleta a propósito (roadmap R3.5/v30).

### 2.6 Sequence Engine / Semantic Engine
- `sequence.py`: secuencia event-driven completa (sweep→displace→BOS→retorno con memoria y
  reset). Es el corazón real del sistema y está bien construido.
- `semantic_scorer.py`: R11 puro — score sobre MarketObjects (completitud causal + estado +
  relación), rechaza DataFrame OHLC (`:37-40`). Diseño limpio y coherente con "IA sobre
  entidades, no sobre velas". Buen norte arquitectónico, pero aún no cableado al runner de
  producción (ver Fase 6).

Veredicto Fase 2: el motor ICT canónico (structure+sequence) es sólido y honesto sobre sus
huecos. El problema no es el canónico sino los DOS detectores paralelos que contradicen su
semántica, y POI/liquidez sin cablear a la decisión.

---

## FASE 3 — MOTOR DE BACKTESTING

### 3.1 Look-ahead / future leakage — CONTROLADO en el canónico
Evidencia positiva:
- Swing points confirmados con retardo: `test_ict_backtest.py:35-41` verifica que un pico en
  idx 10 solo se expone en idx 15 (lookback=5). Sin look-ahead en estructura.
- Fill next-open (`engine.py:60-64`): entra al OPEN de la vela siguiente a la señal, no al
  close de la vela de señal. Es el fill realista. El modo `signal_close` existe pero está
  marcado "theory/paper, sobre-estima" (`:54-55`) — contrato cerrado, levanta ValueError si
  el modo es desconocido (`:67`). Diseño correcto.
- HTF closed-only: v2 usa snapshots cerrados de TF superiores (`strategy_mtf.py:3`).

Riesgo residual: `simulate_trade` resuelve la barra de entrada buscando `signal.time` por
igualdad de string (`engine.py:88-89 times == signal.time`). Si el timestamp de la señal no
existe EXACTO en el frame LTF, la señal se descarta como `time_not_found` (`:91`). Es seguro
(no filtra futuro) pero puede perder señales silenciosamente por desalineación de formato de
tiempo entre TFs. Recomendación: unir por índice entero, no por string de tiempo. Prioridad: MEDIA.

### 3.2 Simulación intra-vela — sesgo optimista SL/TP simultáneo (MEDIO)
`engine.py:117-138`: dentro de una vela evalúa primero SL y luego TP para longs (SL en `:120`,
TP en `:124`). Si una vela toca AMBOS (SL y TP dentro del mismo rango high-low), el motor
asume SL primero para longs (conservador ✓) — pero la lógica es por dirección y no modela el
path intra-barra real. Es el sesgo clásico de backtests OHLC. Está resuelto de forma
conservadora (asume el peor caso para el trader), lo cual es CORRECTO. Bien.

### 3.3 Costos — aplicados pero calibración parcial (MEDIO)
`engine.py:84-105,143-144`: spread/2 + slippage adverso al entry, comisión restada en PRECIO
(no en /risk) para no inflar pnl_r cuando risk es pequeño (fix R6.3). Modelo de costos serio.
Brecha: `costs.py` solo tiene calibración real para XAU/EUR/GBP (documentado en AGENTS.md);
otros símbolos usan defaults. Métricas de USDCHF/USDCAD/NZD/AUD con costos son aproximadas.
Recomendación: calibrar COST_BY_SYMBOL por par antes de comparar PF entre símbolos.

### 3.4 Cap por confianza rompe la comparabilidad de variantes (ALTO)
`scripts/edge_diagnosis/run.py`: `MAX_SIGNALS_PER_VARIANT=3000` corta las señales por
confianza DESCENDENTE. Efecto medido: 13 de 21 variantes de XAUUSD colapsan al MISMO
resultado (PF 1.379 / WR 60.1% / N=900) porque el cap deja el mismo subconjunto de tope.
Esto invalida la ablación: relajar un filtro NO cambia el set evaluado. (Instrumentado en
commit 104964c: ahora se reporta `n_raw` y `capped` por celda para cuantificarlo.)
Recomendación: cortar por ventana temporal o muestreo aleatorio con seed, no por confianza.
Prioridad: ALTA.

### 3.5 Survivorship / repainting
- Survivorship: N/A a nivel de símbolo (FX/XAU, no universo de acciones). No hay sesgo de
  supervivencia estructural.
- Repainting: la estructura se sigue vela a vela con estado inmutable hacia atrás; no
  reescribe historia. Bajo riesgo.

### 3.6 ¿Son confiables los resultados del backtest?
Los NÚMEROS del motor son confiables COMO MEDICIÓN DE UN SUBCONJUNTO (coverage_pct honesto en
`v2/coverage.py:161-169`, verdict auto-degradado si <85%). Pero NO son evidencia sobre la
tesis ICT completa: C02-C06/C15 missing/partial. El PF negativo de R6.4 mide una versión
SIMPLIFICADA. El propio repo lo declara (AGENTS.md caveat). Conclusión: backtest
metodológicamente correcto, pero cobertura de estrategia incompleta → no concluir "sin edge".

---

## FASE 4 — TESTING

### 4.1 Estructura y volumen
64 archivos de test, ~1158 asserts. Cobertura amplia por módulo: detectors (126), feature_engine
(98), agents (72), ml_trainer (69), po3 (59), persistence (57), live_trading (51). Muchos usan
datos SINTÉTICOS deterministas (`test_ict_backtest.py:1-6`) → rápidos y reproducibles. Bien.

### 4.2 La suite completa NO termina en tiempo razonable (ALTO)
Evidencia: `pytest tests/ -q` → timeout >600s; `pytest tests/test_ml_dataset.py test_ml_train.py
test_data_legacy.py test_trend_context.py` → timeout >180s con solo "..". Causa probable:
tests de integración que construyen contextos pesados o intentan auto-download MT5
(`dataset_builder.py:146-161 _download_if_missing`, `auto_download=True` por defecto). Un test
que toca red/MT5 es frágil y no determinista.
Impacto: no hay señal de CI verde rápida; el "verde" real es incomprobable en <10 min.
Recomendación: marcar tests de integración con `@pytest.mark.slow`/`network`, mockear MT5,
separar `pytest -m "not slow"` para el gate rápido. Prioridad: ALTA.

### 4.3 Import roto en un test / desalineación módulo-test (MEDIO)
`tests/test_trend_context.py:8` y `signals/pipeline.py:25` importan
`trend_context.build_trend_context_frame`. La función EXISTE (`trend_context.py:75`) pero al
importar el módulo aislado se observó ImportError por ciclo de import (`trend_context` ↔
`signals`/`data`). Bajo el orden normal de la suite carga; aislado, falla. Es fragilidad de
dependencias circulares, no ausencia de código.
Recomendación: romper el ciclo (mover `build_trend_context_frame` a un módulo sin dependencia
inversa). Prioridad: MEDIA.

### 4.4 Qué validan / qué NO validan
Validan bien: no-look-ahead (R1), CHOCH≠BOS (R2), costos (R4), fill next-open, split
walk-forward, invalidación por evento, equivalencia legacy⊆semantic (R10c). Es testing de
COMPORTAMIENTO real, no solo smoke.
NO validan: la ausencia de train/serve skew (nadie testea que ML entrene sobre el mismo motor
que produce señales en prod — porque justamente NO lo hace, 1.2); la equivalencia entre los 3
detectores BOS/CHOCH (1.1); performance/regresión de tiempo.
Riesgo de falso positivo: tests que dependen de auto-download pueden "pasar" con datos
distintos en cada máquina. Riesgo de falso negativo: la fragmentación de motores no tiene test
que la ataje.

### 4.5 ¿Testing de arquitectura o de implementación?
Mayormente implementación (comportamiento de funciones). Hay señales de test arquitectónico
(`test_check_separation.py`, `test_r7_single_source.py:26`, `test_r7_t32b_elimination.py`
atacan "single source"/eliminación de motor divergente) — bien orientados, pero no cubren la
duplicación detectors/ vs market_structure/.

---

## FASE 5 — PERFORMANCE

### 5.1 Bucles Python sobre arrays numpy (MEDIO)
- `market_structure._track_structure` (`:211-232`): loop Python vela a vela con `.iloc[i]`
  para status/age. Sobre 50k velas × varios TF × símbolos es costoso. `.iloc` en loop es
  anti-patrón pandas.
- `detectors/liquidity.py:29-36`: doble loop O(n·left) para pivotes; `:71-97` clustering O(n²)
  en el peor caso. Aceptable para "solo informativo", caro si se activara en decisión.
- `simulate_trade` (`engine.py:110-140`): loop por trade × max_hold_bars. Correcto (es
  event-driven por diseño) pero `frame.iloc[j]` en loop repite overhead; convertir a arrays
  numpy una vez daría 5-20x.
Recomendación: vectorizar `_track_structure` con numpy puro (ya usa `.to_numpy()` pero escribe
con `.iloc`), y en `simulate_trade` extraer high/low/close a arrays antes del loop. Prioridad: MEDIA.

### 5.2 Copias de DataFrame
`detect_market_structure:148 frame.copy()`, `detectors/*` `.copy()`, `detect_regimes`. Cada
detector copia el frame completo. En pipeline multi-TF se copian los mismos datos N veces.
Recomendación: operar sobre columnas/arrays y ensamblar al final; evitar `.copy()` en cadena.

### 5.3 Complejidad temporal/espacial global
El grid de edge_diagnosis (168 celdas) × construcción de contexto por celda es el mayor costo
(explica el cap de 3000 y los timeouts de test). No hay caché de contexto entre variantes del
mismo símbolo → recomputación masiva. `run_one_reuse` sugiere intención de reuso; verificar que
realmente reutilice el contexto y no lo reconstruya por variante. Prioridad: MEDIA.

---

## FASE 6 — MACHINE LEARNING

### 6.1 Train/serve skew (CRÍTICO) — ver 1.2
El dataset se construye con el motor legacy (`dataset_builder.py:14,234`); producción usa el
canónico. El modelo aprende una distribución que no verá en vivo.

### 6.2 Data leakage en features/labels — mayormente controlado
Positivo: labels de trade (`dataset_builder.py:271-288`) se calculan simulando el trade hacia
adelante (`_simulate_trade_with_stats`) — es el outcome, correcto como target. Walk-forward por
AÑO (`walk_forward.py:59-78`) y PurgedKFold con purge/embargo (`walk_forward.py:184`,
`ml/stats_validator.py`) — buena higiene temporal.
Riesgo: `train.py:311-314` mete como features TODAS las columnas numéricas extra
(`extra_cols = [c for c ... is_numeric_dtype ...]`) además de la lista blanca. Esto puede
colar columnas de outcome/futuro (p.ej. mfe/mae si quedaran) como features. Los drop_cols
(`:300-301`) cubren pnl_r/exit_reason/mfe/mae, pero el patrón "usar todo lo numérico" es
peligroso: un nuevo campo de label futuro entraría como feature sin aviso.
Recomendación: feature list ESTRICTA (allowlist), prohibir el fallback "todo lo numérico".
Prioridad: ALTA.

### 6.3 Pipeline ML — bien construido
`train.py:131-154`: ColumnTransformer (impute+scale numérico, impute+onehot categórico),
selección de estimador con fallback xgboost→lightgbm→catboost→histGBM (`:64-128`),
calibración isotónica/sigmoid según tamaño de clase (`:245-256`), TimeSeriesSplit. Es un
pipeline sklearn profesional. Métricas: logloss, roc_auc, brier, precision/recall.

### 6.4 Separación entrenamiento/inferencia y escalabilidad
Entrenamiento (`train.py`) e inferencia (`ml/inference.py` vía `agents`) separados. El
`SemanticScorer` (R11) apunta a scoring sobre entidades pero NO está cableado al runner de
producción (no aparece en el camino `run_backtest→canonical→simulate`). Capacidad de integrar
nuevos modelos: buena (fallback de estimadores, joblib dump). Modularidad: media (dataset_builder
god-module).
Recomendación: cablear semantic_scorer al pipeline o marcarlo explícitamente como R11-futuro
en coverage. Prioridad: MEDIA.

---

## FASE 7 — CALIDAD DEL CÓDIGO

### 7.1 Función duplicada / dead code
- `engine.py`: `_coerce_ts` aparece definida DOS veces (`:160` y de nuevo más abajo ~`:229`);
  la segunda redefine la primera. Además `simulate_trade` NO la usa. Dead code + shadowing.
  Recomendación: eliminar una y confirmar si alguna se usa. Prioridad: BAJA.
- `strategy_mtf.py:101-103`: bloque muerto `if not hasattr(s, "meta") or s.meta is None: pass`
  (no-op tras haber seteado `s.meta` en la línea previa). Ruido.

### 7.2 Legibilidad y nombres
Buena en general: nombres de dominio claros (bos_dir, choch_status, dealing_range, killzone),
docstrings extensos y honestos (citan hallazgos y fixes por Rx). El español técnico es
consistente. Contras: módulos largos (sequence.py 23KB, dataset_builder 334 líneas) con
múltiples responsabilidades; comentarios que mezclan histórico de fases con lógica actual
(ruido cognitivo para un recién llegado).

### 7.3 Abstracciones y responsabilidades
v2 tiene abstracciones limpias (Order/Plan/TradeResult/EventLog/CoverageReport). El resto es
más procedural (funciones que cargan+calculan+imprimen). `_write_runner_progress` embebido en
run_backtest mezcla observabilidad con dominio.

### 7.4 Duplicación (la deuda central)
3× estructura (market_structure vs detectors/bos vs detectors/choch) + 2× señales (canonical
vs legacy). Es la mayor fuente de complejidad accidental del repo.

### 7.5 Complejidad ciclomática
Alta en `sequence.py` (secuencia con estados y resets) y `_track_structure` (loop con
ramas active/crossed/choch). Justificable por el dominio event-driven, pero pide extracción de
la máquina de estados a una clase testeable aparte.

---

## FASE 8 — DEUDA TÉCNICA (clasificada)

### ALTA (bloquea confiabilidad / producción)
1. Fragmentación de motor de estructura (3 impl. BOS/CHOCH). Impacto: semántica inconsistente
   entre dataset y decisión. Riesgo: conclusiones ML/backtest no comparables. (1.1, 2.2)
2. Train/serve skew ML (dataset=legacy, prod=canónico). Impacto: modelo no transferible.
   Riesgo: filtro de calidad optimista en backtest, degradado en vivo. (1.2, 6.1)
3. Suite de tests que no termina + tests con auto-download MT5. Impacto: sin CI verde rápido.
   Riesgo: regresiones no detectadas; "verde" no reproducible. (4.2)
4. Cap por confianza en edge_diagnosis. Impacto: ablación inválida. Riesgo: decidir filtros
   sobre métricas colapsadas. (3.4)
5. Fallback ML "todo lo numérico" como features. Impacto: leakage latente. Riesgo: AUC
   inflado por columnas de outcome futuras. (6.2)

### MEDIA (fricción / riesgo latente)
6. Sin capa de datos única (cada módulo carga por su cuenta). (1.3)
7. Ciclo de import trend_context ↔ signals/data. (4.3)
8. Costos calibrados solo XAU/EUR/GBP. (3.3)
9. Match de entrada por string de tiempo (pérdida silenciosa de señales). (3.1)
10. Loops `.iloc` sobre 50k velas (performance). (5.1)
11. semantic_scorer (R11) sin cablear al runner. (6.4)

### BAJA (limpieza)
12. `_coerce_ts` duplicada / dead code en engine.py. (7.1)
13. Bloques no-op en strategy_mtf.py. (7.1)
14. Comentarios histórico-de-fases mezclados con lógica. (7.2)

---

## FASE 9 — ROADMAP PROFESIONAL

### Quick Wins (días)
- QW1: Eliminar `_coerce_ts` duplicada y bloques no-op (Fase 7). Riesgo cero.
- QW2: Marcar tests lentos/red con `@pytest.mark.slow`/`network`; `auto_download=False` por
  defecto en tests; gate rápido `pytest -m "not slow"`. Desbloquea CI. (4.2)
- QW3: Endurecer feature allowlist en `train.py`; eliminar el fallback "todo lo numérico". (6.2)
- QW4: Rediseñar el cap de edge_diagnosis (muestreo por ventana/seed). (3.4) — ya instrumentado.

### Medium Refactors (semanas)
- MR1: Unificar estructura: `market_structure.detect_market_structure` como única fuente;
  `detectors/bos|choch` → wrappers o borrado; test de equivalencia que impida regresión. (1.1)
- MR2: Redirigir `dataset_builder` al motor canónico (canonical.evaluate_signals +
  engine.simulate_trade). Re-entrenar y re-medir ML sin skew. (1.2/6.1)
- MR3: Extraer port de datos único (`domain` sin I/O; `infra/data_feed` con carga). (1.3)
- MR4: Romper ciclo de import trend_context. (4.3)

### Major Refactors (meses)
- MJ1: Cerrar brecha ICT (C02-C06/C15): POI anclado a narrativa, 3 capas reales, dealing
  range/premium-discount en la decisión, trade management (BE/parciales). Es el R3.5/v30 del
  propio roadmap; sin esto el "edge" no es medible. (2.5, coverage)
- MJ2: Máquina de estados de secuencia como clase testeable + vectorización numpy. (5.1/7.5)
- MJ3: Cablear semantic_scorer (R11) al runner como filtro/score real. (6.4)

### Long Term Vision
- Motor único de dominio ICT (structure→sequence→POI→plan) sin I/O, con adaptadores para
  backtest / paper / live sobre el MISMO código. Coverage report como gate de release.
  DSR/PBO (ml/stats_validator) aplicados de forma obligatoria a todo grid de optimización.
  Walk-forward OOS multi-año por símbolo como criterio de promoción a capital.

---

## FASE 10 — CALIFICACIÓN (1-10)

| Dimensión                    | Nota | Justificación breve (evidencia) |
|------------------------------|:----:|---------------------------------|
| Arquitectura                 | 5.5  | v2 limpia (Plan/Sim/contracts) pero 3 motores duplicados y sin capa de datos única (1.1/1.3) |
| Escalabilidad                | 5.0  | loops .iloc sobre 50k velas, recomputación de contexto por variante, sin caché (5.1/5.3) |
| Testing                      | 5.0  | 1158 asserts y tests de comportamiento reales, pero suite no termina y depende de MT5 (4.2) |
| Calidad Python               | 6.0  | nombres/docstrings buenos; dead code, god-modules, ciclos de import (7.1-7.4) |
| Calidad ML                   | 5.0  | pipeline sklearn pro y WF/PurgedKFold, pero train/serve skew y fallback de features (6.1/6.2) |
| Backtesting                  | 6.5  | look-ahead controlado, fill next-open, costos serios, SL conservador; cap inválido y costos parciales (3.1-3.4) |
| Motor ICT                    | 6.0  | structure+sequence canónico sólido y honesto; POI/liquidez sin cablear, detectores contradictorios (2.2/2.5) |
| Mantenibilidad               | 5.0  | duplicación de motores es la deuda central; módulos largos (7.4/8) |
| Documentación                | 8.0  | docs/, METRICS_CANON, caveats honestos, coverage auto-degradado. Punto fuerte del proyecto |
| Preparación para producción  | 4.0  | sin CI verde rápido, skew ML, motor múltiple, cobertura ICT incompleta |
| Capacidad para hedge fund    | 3.5  | metodología honesta y buenas piezas, pero edge no demostrado, OOS multi-año bloqueado por datos, gobernanza de features/motor insuficiente |

Media ponderada aproximada: **5.3 / 10** — "prototipo cuantitativo serio y honesto, con
fundaciones válidas, a 2-3 refactors estructurales de ser confiable".

---

## CIERRE — LO QUE NO PUDE DEMOSTRAR
- No pude ejecutar la suite completa hasta el final (timeout >600s); los 2 fallos observados
  en el arranque no los pude aislar por nombre. Afirmo el timeout, no el detalle de cada fallo.
- No re-entrené el ML ni corrí el grid de 168 celdas (fuera de presupuesto de tiempo y con
  cap inválido). Las cifras de PF citadas provienen de METRICS_CANON/AGENTS.md del propio repo.
- El train/serve skew (1.2/6.1) está demostrado por los imports (`dataset_builder.py:14` legacy
  vs `run_backtest.py:103` canonical), no por una corrida comparativa A/B — esa corrida es el
  siguiente paso de verificación recomendado.
