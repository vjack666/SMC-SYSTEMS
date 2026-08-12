# HYP-002 / FUNCTIONAL_REPLAY_CONTRACT

**Fase:** Auditoría de funcionamiento del motor (replay vela-a-vela).
**Fecha:** 2026-08-11 · **Autor:** Hermes (modo autónomo, CEO delegado).
**No objetivo de esta misión:** WR/PF/edge. Solo comportamiento temporal/operacional.

## 1. Qué significa "vela disponible"

Una vela `k` es DISPONIBLE para el motor en el instante `k` si y solo si todas las
columnas de `build_features(df.iloc[:k+1])` en la fila `k` se calculan usando
EXCLUSIVAMENTE filas `j <= k`. Si alguna columna en la fila `k` depende de una fila
`j > k`, hay fuga de futuro (look-ahead).

## 2. Qué significa "evento observable"

Un evento (LIQUIDITY/SWEEP/DISPLACE/BOS/POI/REFINEMENT/RETURN/CONTRACT) emitido con
`bar_index == k` es observable en `k` si su cálculo no requiere información de `j > k`.

## 3. Estado persistente permitido

El motor puede conservar, entre velas:
- `SequenceState` (fase actual, ids de eventos previos, zona cacheada, idx de sweep/bos).
- Memoria de swings/estructura (vía `detect_market_structure`, que es causal).
NO puede conservar referencias a filas futuras ni leer el dataframe completo.

## 4. Información PROHIBIDA antes del cierre de la vela

- Cualquier columna calculada con `shift(-N)` (mirando hacia adelante).
- Cualquier ventana `rolling(center=True)` (ventana centrada = simétrica).
- Cualquier estadística sobre filas `j > k`.

## 5. Look-ahead = cualquier dependencia de j > k en la fila k.

## 6. Reinicio (HYP-002 M3 — CERRADO)

Reinicio = serializar el estado en `k`, apagar, reconstruir en `k`, continuar.
`SequenceState` expone `to_snapshot()` / `from_snapshot()` / `save()` / `load()`
(JSON, `schema_version`). `run_sequence_traced` acepta `initial_state` + `start_i`
y devuelve `(signals, phase_seen, expedientes, state)`.

PARIDAD de reinicio (RUN CONTINUO == SAVE→CRASH→LOAD→RESUME):

- El motor almacena en `state.sweep_idx/displace_idx/bos_idx` la **POSICIÓN** en
  el feed (0-based), NO `obj.bar_index`. Por eso el resume re-alimenta el **df
  COMPLETO** con `start_i = cut+1` y el estado restaurado: las posiciones quedan
  absolutas y la genealogía es idéntica. Cortar con `df.iloc[k+1:]` REBASA las
  posiciones y ROMPE la paridad (anti-patrón documentado).
- El id de `MarketObject` es `uuid4` aleatorio (cambia cada invocación). La prueba
  de continuidad compara el **grafo causal** (rol + parent-rol + bar_index + type),
  que es determinista, NO los uuid crudos.

## 6b. Invariante de feed (deuda FASE3 → regla de infraestructura)

El feed en vivo DEBE conservar el historial de features acumulado. Recalcular
features POR BLOQUE olvidando el contexto introduce divergencias (FASE3 FAIL).
La continuidad del feed y la continuidad del estado son dos problemas distintos;
ambos resueltos: estado vía §6, feed vía acumulación de features en el replay.

## 7. Reproducibilidad

Mismo dataset + misma forma de alimentación ⇒ misma genealogía de eventos
(ids, parents, direction, POI/REF/RET/CONTRACT). Cambiar el tamaño de bloque o
el futuro NO debe cambiar el pasado.

## 8. Métricas de auditoría (PASS / FAIL / PARCIAL)

| Auditoría | PASS | FAIL |
|---|---|---|
| Batch vs Stream | eventos k-k idénticos | algún evento diverge |
| Determinismo (bloques) | bloque-indep == stream | diverge en borde de bloque |
| Corte temporal | futuro alterado no cambia ≤cut | cambia |
| Future Mutation | ídem | ídem |
| Reinicio | estado serializable + resume idéntico (grafo causal) | sin API → PARCIAL |
| Datos hostiles | detecta/rechaza/marca UNKNOWN | emite señal falsa |
| Intrabar | evento usa solo vela cerrada | usa high/low no finalizados |
| Shadow Market | journal + virtual exec sin broker | — |
| Cross-validation | 2 datasets, mismo veredicto causal | — |

## 9. Hallazgo de descubrimiento (FASE 0) — LIVE leaks en pipeline real

`ict_backtest/data_feed.build_features` es el puente real a `run_sequence`.
Contiene DOS fugas de futuro VIVAS:

1. `detectors/ob.py:20-21`: `close.shift(-1)` — un Order Block se marca MIRANDO la
   vela SIGUIENTE. La columna `ob_bullish/ob_bearish` en la fila `k` es FALSA hasta
   que existe la vela `k+1`. Esto rompe la regla §4.
2. `detectors/trend.py:31-32` y `detectors/bos.py:27-28`: `rolling(..., center=True)`
   — ventana centrada; la fila `k` usa `k-window..k+window`. Rompe §4.
   NOTA: `build_features` llama a `detect_market_structure` (causal, `center=False`),
   NO a `detectors/bos.py`/`trend.py` directamente. Hay que confirmar si narrative
   usa el trend centrado. (Verificado en lab: `engine.bias.narrative._label_swings`
   usa swing con shift hacia atrás → causal; el trend centrado de `detectors/trend.py`
   NO está en el path vivo de `build_features`.)

La única fuga VIVA confirmada en el path de `build_features` es **OB shift(-1)**.
El resto del pipeline (FVG shift(2) hacia atrás, sweep shift(1) hacia atrás,
structure causal) es causal.

## 10. Regla de no-parcheo automático

Si una auditoría falla, se INVESTIGA y se documenta. Solo se corrige si la corrección
está en el alcance de la tesis (cerrar look-ahead SIN alterar la lógica de decisión
del motor). En esta misión se corrige SOLO la fuga OB shift(-1) (cambio de
`shift(-1)` a ventana causal de confirmación), y se re-ejecuta toda la batería.
