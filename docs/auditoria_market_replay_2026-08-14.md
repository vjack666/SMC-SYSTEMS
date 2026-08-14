# Auditoría MarketReplay — Hallazgos y trazabilidad

**Fecha:** 2026-08-14  
**Objetivo:** explicar el `0 setups` de MarketReplay comparando el contrato canónico con el camino de replay.  
**Regla operativa:** investigación y documentación primero; no modificar código hasta aislar la causa.

## Estado actual

| Elemento | Estado |
|---|---|
| Arquitectura ENGINE → MarketReplay | Confirmada |
| `run_sequence` vs `run_sequence_traced` | No es una diferencia semántica del motor |
| Contexto HTF degradado original | Corregido en el working tree actual de `market_replay/replay.py` |
| Causa exacta del `0 setups` | Corregida en el working tree; pendiente de revisión final |
| Hipótesis prioritaria | Replay alimenta al motor con LTF OHLC crudo y pierde estructura `bos_dir`/`choch_dir` |
| Código modificado durante esta auditoría | Sí, fix mínimo solicitado |

## Hallazgo 1 — `run_sequence` y `run_sequence_traced` comparten el motor

**Evidencia:** ambos wrappers llaman a `_run_sequence_impl` en [engine/sequence.py:1079-1117](../engine/sequence.py). `run_sequence` devuelve `(signals, phase_seen)`; `run_sequence_traced` devuelve además expedientes y estado.

**Conclusión:** el nombre `traced` no explica por sí mismo el rechazo de setups. La diferencia real del replay es su ejecución incremental (`initial_state`, `start_i`, `copy_objs=False`) y los argumentos/contextos que entrega.

**Estado:** confirmado.

## Hallazgo 2 — La evidencia de 18 setups usa `bos_gap=10`

**Evidencia:** el runner de FASE A usa directamente `run_sequence_traced` y construye:

```python
SequenceConfig(
    counter_trend=False,
    require_displacement=True,
    displace_gap=6,
    bos_gap=10,
)
```

Fuente: [scripts/fase_a_semantic_light.py:137-148](../scripts/fase_a_semantic_light.py).

En cambio, `MarketReplay` recibe por defecto `SequenceConfig()`, cuyo `bos_gap` es `None`. En ese caso el motor usa la ventana dinámica y, si no recibe tabla, el fallback es 40 velas ([engine/sequence.py:553-600](../engine/sequence.py)).

**Impacto:** el replay y la evidencia de 18 setups no están usando la misma política de confirmación BOS. Una ventana 40 puede mantener una secuencia abierta durante cambios de contexto y permitir que el gate la reinicie; una ventana 10 puede confirmar o invalidar en otro momento.

**Estado:** diferencia funcional confirmada; causalidad sobre el `0 setups` todavía pendiente de experimento aislado.

## Hallazgo 3 — M5/M1 no son la causa del gate actual

**Evidencia:** el motor llama `top_down_allows_trade` con `require_pd=False` y no activa `require_ltf` ([engine/sequence.py:747-758](../engine/sequence.py)). `top_down_allows_trade` solo consulta M5/M1 cuando `require_ltf=True` ([engine/plan.py:444-449](../engine/plan.py)).

**Conclusión:** la ausencia de M5/M1 puede impedir equivalencia completa de contexto, pero no explica por sí sola el rechazo actual de LONG/SHORT en este camino.

**Estado:** confirmado para el gate actual.

## Hallazgo 4 — `anchored_pd_zones` no es veto en este camino

**Evidencia:** el gate se invoca con `require_pd=False`. Las zonas ancladas se incorporan al contexto, pero el gate no evalúa premium/discount en esta llamada ([engine/plan.py:435-442](../engine/plan.py)).

**Conclusión:** pasar `anchored_pd_zones=None` rompe equivalencia de metadata/contexto, pero no debería producir por sí solo el `0 setups` actual.

**Estado:** confirmado como no-veto; impacto exacto en metadata pendiente.

## Hallazgo 5 — `htf=None` afecta linaje POI, no necesariamente el conteo

**Evidencia:** Replay no pasa `htf` a `run_sequence_traced` ([market_replay/replay.py:148-159](../market_replay/replay.py)). El motor solo crea el objeto POI cuando `htf` es uno de D1/H4/H1 ([engine/sequence.py:902-915](../engine/sequence.py)).

**Conclusión:** esta diferencia puede afectar el grafo causal y el journal, pero no es evidencia suficiente para atribuirle el `0 setups`.

**Estado:** confirmado como diferencia de contrato; causalidad sobre el conteo no demostrada.

## Hallazgo 6 — El problema antiguo de `trend=RANGING` ya no describe el código actual

**Evidencia:** la versión actual de [market_replay/replay.py:119-127](../market_replay/replay.py) calcula `detect_market_structure` y construye `build_multitf_context`. La documentación previa ([docs/auditoria_frontera_engine_infra.md](auditoria_frontera_engine_infra.md)) describe el estado anterior, donde Replay pasaba un dict OHLC degradado.

**Conclusión:** esa documentación debe leerse como historial pre-fix, no como diagnóstico vigente.

**Estado:** confirmado. El cambio estaba ya presente en el working tree; no fue realizado durante esta auditoría.

## Evidencia de tests

Ejecutado el 2026-08-14:

```text
tests/test_market_replay_audit_battery.py
tests/test_market_replay_equivalence.py
14 passed
```

La batería real sobre el tramo de 2.000 velas no se tomó como veredicto porque su coste es alto y la ejecución fue detenida antes de obtener resultado. Por tanto, todavía no se afirma que Replay sea equivalente al backtest real.

## Siguiente experimento autorizado

Comparar cuatro configuraciones, sin modificar producción:

1. FASE A reproducida: 4 TF, contexto completo disponible, `bos_gap=10`, `run_sequence_traced`.
2. Replay con exactamente `bos_gap=10`.
3. Replay con `bos_gap=None` y sin tabla.
4. Repetir 2 y 3 cambiando únicamente `anchored_pd_zones`.

Registrar por corrida:

- cantidad de señales;
- funnel `SWEEP/DISPLACE/BOS/ENTRY`;
- índices de cada fase;
- razones de veto top-down;
- presencia de POI y objetos de linaje.

**Criterio de cierre:** solo se podrá declarar causa cuando una única diferencia produzca una divergencia reproducible y el resto del contrato permanezca igual.

## Experimento 1 — tramo inicial de 600 velas

**Ejecutado:** 2026-08-14. Se cargó EURUSD con cuatro TF y se compararon cuatro combinaciones: `bos_gap=10`/`None` y contexto anclado/no anclado.

| Configuración | Señales | SWEEP | DISPLACE | BOS | ENTRY |
|---|---:|---:|---:|---:|---:|
| Contexto canónico, `bos_gap=10`, anclado | 0 | 0 | 0 | 0 | 0 |
| Contexto canónico, `bos_gap=None`, anclado | 0 | 0 | 0 | 0 | 0 |
| Contexto Replay, `bos_gap=10`, no anclado | 0 | 0 | 0 | 0 | 0 |
| Contexto Replay, `bos_gap=None`, no anclado | 0 | 0 | 0 | 0 | 0 |

**Interpretación:** resultado no informativo. El tramo seleccionado no produjo ni siquiera un `SWEEP`, por lo que no permite comparar el efecto de `bos_gap` ni del anclaje.

**Acción:** repetir en el tramo final del mes, donde existe la evidencia histórica de setups.

## Experimento 2 — tramo final de 600 velas, ejecución batch

**Ejecutado:** 2026-08-14. Se utilizó EURUSD, D1/H4/H1/M15, del 2026-07-29 08:15 UTC al 2026-08-06 14:00 UTC. Se mantuvo fijo el resto del contrato y se compararon `bos_gap` y `anchored_pd_zones`.

| Configuración | Señales | SWEEP | DISPLACE | BOS | ENTRY | Índice nuevo |
|---|---:|---:|---:|---:|---:|---:|
| Contexto canónico, `bos_gap=10`, anclado | 18 | 33 | 32 | 18 | 18 | — |
| Contexto canónico, `bos_gap=None` / fallback 40, anclado | 19 | 23 | 22 | 19 | 19 | 487 |
| Contexto Replay, `bos_gap=10`, no anclado | 18 | 33 | 32 | 18 | 18 | — |
| Contexto Replay, `bos_gap=None` / fallback 40, no anclado | 19 | 23 | 22 | 19 | 19 | 487 |

**Conclusiones:**

1. `bos_gap` sí cambia la salida de forma reproducible.
2. El contexto anclado no cambió el resultado en esta muestra.
3. El contexto Replay y el contexto canónico dieron la misma salida batch en ambas políticas.
4. `bos_gap` queda confirmado como una diferencia real de contrato, pero queda descartado como explicación suficiente del `0 setups`.

**Estado:** `bos_gap` = diferencia real, no causa única del cero.

## Hallazgo 7 — Replay calcula estructura, pero no la entrega como LTF al motor

**Evidencia de ejecución:** sobre el tramo final de 600 velas:

| Camino | `bos_gap` | Señales | SWEEP | DISPLACE | BOS | ENTRY |
|---|---:|---:|---:|---:|---:|---:|
| Batch con contexto Replay | 10 | 18 | 33 | 32 | 18 | 18 |
| MarketReplay incremental | 10 | 0 | 0 | 0 | 0 | 0 |
| MarketReplay incremental | `None` / fallback 40 | 0 | 0 | 0 | 0 | 0 |

La diferencia se localiza en la preparación del LTF:

1. Replay calcula `self._ms_struct` con `detect_market_structure` ([market_replay/replay.py:119-124](../market_replay/replay.py)).
2. Pero convierte a `MarketObject` el DataFrame OHLC crudo `ltf_df_full` ([market_replay/replay.py:108,135](../market_replay/replay.py)).
3. El contexto HTF sí usa `self._ms_struct`, pero la lista de velas que consume la secuencia no.
4. `_candle_objects` copia los campos ICT disponibles; el OHLC crudo no contiene `bos_dir` ni `choch_dir` ([engine/sequence.py:297-314](../engine/sequence.py)).
5. `_has_bos` necesita esos campos y normaliza su ausencia/`NaN` a cero ([engine/sequence.py:369-384](../engine/sequence.py)).

La evidencia de columnas lo confirma:

```text
OHLC crudo:       bos_dir=False, choch_dir=False
estructura ms:    bos_dir=True,  choch_dir=True
objeto Replay:    bos_dir=NaN,    choch_dir=NaN
objeto canónico:  bos_dir=0,      choch_dir=1  # ejemplo en índice 188
```

**Conclusión:** el `0 setups` vigente no lo produce `run_sequence_traced`, `bos_gap`, M5/M1 ni `anchored_pd_zones`. El consumidor Replay calcula una autoridad estructural que luego no transporta al objeto LTF que realmente lee el motor.

**Estado:** causa aislada y reproducible; todavía no se aplica fix.

## Experimento 3 — Confirmación de la corrección mínima en arnés

**Ejecutado:** 2026-08-14. Se reprodujo el bucle incremental de MarketReplay durante 599 pasos, sin modificar producción, pero construyendo temporalmente `MarketObject[]` desde el LTF estructurado (`self._ms_struct["M15"]`).

Resultado:

```text
signals = 18
SWEEP = 33
DISPLACE = 32
BOS = 18
ENTRY = 18
entries = [188, 242, 246, 257, 261, 284, 288, 292,
           410, 420, 442, 461, 473, 506, 510, 559, 579, 598]
```

El resultado coincide con el batch canónico y con la evidencia FASE A.

**Conclusión:** queda cerrada la causalidad del `0 setups`: el problema está en el transporte del DataFrame LTF crudo hacia `_candle_objects`; el contexto HTF y `run_sequence_traced` sí pueden producir los setups cuando reciben el LTF estructurado.

**Fix mínimo identificado, aún no aplicado:** construir los objetos LTF del Replay desde el frame estructurado que ya calcula (`self._ms_struct[self.ltf]`).

**Pendiente de contrato:** verificar si además deben transportarse las features completas de `engine.market_features.build_features` (`fvg`, `OB`, displacement y sweeps) o si el contrato vigente de FASE A requiere únicamente la estructura calculada. Esa decisión se documentará antes de modificar código.

## Hallazgo 8 — También faltaba seleccionar la capa HTF

El arnés temporal que reprodujo los 18 setups pasaba `htf="H4"`. `MarketReplay` no pasaba ese argumento a `run_sequence_traced`; con `htf=None`, el motor no extrae ninguna capa del contexto y recibe `{}`, por lo que interpreta el sesgo como `RANGING` y reinicia.

**Fix aplicado:** `MarketReplay` acepta ahora `htf` opcional e infiere `H4` cuando está disponible; en feeds reducidos sin H4 conserva una capa alternativa disponible o el camino sin HTF. El valor seleccionado se pasa explícitamente a `run_sequence_traced`.

Fuente: [market_replay/replay.py](../market_replay/replay.py).

## Validación posterior al fix

Sobre el mismo tramo real de 600 velas y `bos_gap=10`:

```text
signals = 18
SWEEP = 33
DISPLACE = 32
BOS = 18
ENTRY = 18
```

La batería rápida pasó `14 passed`:

```text
tests/test_market_replay_audit_battery.py
tests/test_market_replay_equivalence.py
```

La prueba `tests/test_replay_equivalence.py::test_replay_equivalence_real` fue detenida tras más de cuatro minutos de CPU sin resultado. Su referencia congela el camino previo y debe revisarse separadamente como contrato de equivalencia, no tomarse como veredicto del fix funcional.
