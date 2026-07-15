# Revision Final de Arquitectura — Convivencia MarketObject x DataFrames

> **Para Hermes:** revision FINAL antes del PLAN DE EJECUCION TDD. Solo
> diseno. No se toca codigo del sistema. Sin "haz commit y push" no se
> commitea. Complementa DISENO_ARQUITECTURA_OBJETOS_MERCADO.md.

---

## 0. Hallazgo critico de la revision

El ecosistema de columnas sueltas es MUCHO mas amplio que `ict_backtest/`.
No solo `engine.py`/`sequence.py`/`rules.py` usan `bos_dir`, `fvg_state`,
`ob_direction`, `choch_dir`, `liquidity_sweep_*`, `bsl_price`, `bos_status`.
TAMBIEN (confirmado por busqueda real en el repo):

- `signals/pipeline.py` — pipeline de senales EN VIVO: corre `detect_bos/
  choch/fvg/ob` directo, usa `bos_status`, `ob_status`, `macro_direction`,
  `fvg_bullish/ob_bullish` por columnas. Consumidor MASIVO.
- `features/engine.py` — otro motor de features para ML: lee `bos_direction`,
  `choch_signal`, `liquidity_sweep_down/up` por columnas.
- `adapters/feature_enrichment_adapter.py` — tiene SU PROPIA definicion de
  sweep (`_detect_liquidity_sweeps`, columnas `liquidity_sweep_detected`/
  `sweep_type`). Es la 4ta definicion divergente que `liquidity_context.py`
  intento unificar y NO logro (porque este adapter no lo usa).
- `agents/ict_agent.py`, `app_observador/core/engine.py`, `ml/*` (trainer,
  validator, train) — consumen columnas.
- Tests: test_detectors, test_feature_engine, test_ict_backtest,
  test_liquidity_context, test_po3, test_r4_po3_isolated, test_signal_pipeline,
  test_agents — dependen de las columnas sueltas.

Consecuencia: un reemplazo completo rompe el pipeline vivo, el ML, el
observador y 8 suites de tests. La migracion DEBE ser GRADUAL con capa de
traduccion y aliases. (Ver respuesta 4.)

---

## 1. ¿Que componentes actuales siguen usando columnas pandas?

Seccion por capa (evidencia: busqueda en repo):

| Capa | Archivos que usan columnas sueltas | Columnas clave |
|------|------------------------------------|----------------|
| Detectores (motores) | `detectors/{bos,choch,fvg,ob,liquidity,displacement,liquidity_context}.py` | salida por columna (`bos_direction`, `fvg_state`, etc.) |
| Features | `ict_backtest/data_feed.py:43-86` (`build_features`) | arma todas las columnas por TF |
| Backtest | `ict_backtest/engine.py`, `sequence.py`, `rules.py` | `estructura[tf][...]` dict de columnas |
| Pipeline vivo | `signals/pipeline.py` | `bos_status`, `ob_status`, `macro_direction`, `fvg_bullish` |
| Features ML | `features/engine.py` | `bos_direction`, `choch_signal`, `liquidity_sweep_*` |
| Adapter | `adapters/feature_enrichment_adapter.py` | `liquidity_sweep_detected`, `sweep_type` (propia) |
| Agent/UI | `agents/ict_agent.py`, `app_observador/core/engine.py`, `ui/resumen_widget.py:335-338`, `ui/noticias_widget.py:25-28` | `bos_status`/`choch_status`/`ob_status` == "active" |
| ML | `ml/{trainer,validator,train}.py` | columnas de features |
| Tests | 8 suites (arriba) | asserts sobre columnas |

TODOS estos siguen con columnas durante la Fase de compatibilidad. El nuevo
MarketObject convive, NO reemplaza de golpe.

---

## 2. ¿Donde debe existir la capa de traduccion DataFrame -> MarketObject?

En UN modulo nuevo, unico punto de conversion bidireccional:

`ict_backtest/translation.py`

```
df_to_objects(frames: dict[tf, DataFrame], symbol) -> dict[tf, list[MarketObject]]
    # corre los detectores (o reusa build_features) y ENVUELVE cada fila
    # detectada en MarketObject con origin_tf=tf y role por regla de capa.
    # ESTO es donde se sella la capa (resuelve origin_tf/role).

objects_to_legacy_df(objects: list[MarketObject]) -> DataFrame
    # reconstruye las columnas sueltas (bos_dir, fvg_state, ob_dir, etc.)
    # desde los objetos. PERMITE que sequence/rules/engine/pipeline/ML/UI
    # sigan leyendo columnas SIN cambios durante la convivencia.
```

Por que ahi:
- `build_features` (data_feed.py:43-86) ya es el lugar que corre todos los
  detectores por TF. `df_to_objects` LO REEMPLAZA conceptualmente pero mantiene
  la misma entrada `{tf: df}`.
- `objects_to_legacy_df` es el ESCUDO: nadie mas debe cambiar. sequence.py,
  rules.py, engine.py, signals/pipeline.py, features/engine.py, ml/*, UI y
  tests siguen igual porque reciben el df/columnas que siempre recibieron.
- La regla de capa (HTF->POI, LTF->REFINEMENT) vive DENTRO de `df_to_objects`,
  no repartida. Unico punto de verdad del sello.

---

## 3. ¿Como evitar romper sequence.py, rules.py y engine.py?

Estrategia: ADAPTADOR, no reescritura. Tres reglas:

A) NO tocar las firmas internas de sequence/rules/engine al inicio.
   - `sequence._has_bos/_has_choch/_latest_fvg_zone/_latest_ob_zone` siguen
     leyendo `row_ltf.get("bos_dir")` etc. Mientras `objects_to_legacy_df`
     siga produciendo esas columnas, sequence NO se entera del cambio.
   - `rules.evaluate` sigue recibiendo `estructura: dict[tf, dict]` (columnas).
     El adaptador le pasa el df legacy reconstruido.
   - `engine.build_signals_from_frames` sigue recibiendo `{tf: df}`.

B) El cambio de "sello de capa" se hace EN `df_to_objects`, no en los
   consumidores. Los consumidores ven columnas iguales; el objeto nuevo vive
   "debajo" como fuente canonica.

C) Solo en la FASE FINAL (cuando todo este detras del adaptador y los tests
   pasen), se refactorea sequence/rules/engine para leer `MarketObject`
   directamente (opcional, no obligatorio para que funcione). Hasta entonces
   quedan intactos.

Resultado: sequence.py, rules.py, engine.py NO se tocan en las fases A-D.
Solo se toca `data_feed.build_features` (se envuelve en `df_to_objects`) y se
agrega `translation.py`. Riesgo de rotura: BAJO.

---

## 4. ¿Conviene migracion gradual o reemplazo completo?

GRADUAL. Justificacion concreta (de la seccion 0):

- `signals/pipeline.py` es el pipeline EN VIVO. Romperlo = bot en vivo caido.
- `features/engine.py` + `ml/*` alimentan el modelo de ML. Romperlo = ML roto.
- `adapters/feature_enrichment_adapter.py` tiene definicion de sweep PROPIA;
  no usa `canonical_sweep`. Reemplazo completo obligaria a tocar ese adapter
  y su sweep divergente (alcance aparte, R3/R4).
- 8 suites de tests asumen columnas. Reemplazo completo = 8 suites en rojo.

Reemplazo completo solo seria viable si el sistema fuera solo `ict_backtest/`.
Como tiene pipeline vivo + ML + adapter + UI + agente, el reemplazo completo
es inviable y riesgoso. GRADUAL con adaptador es la unica via segura.

---

## 5. Plan de compatibilidad temporal

### 5.1 Objetos nuevos (fuente canonica)
- `ict_backtest/market_object.py`: `MarketObject` (del diseno), con
  `origin_tf`, `role`, `state`, `parent_object`, `related_objects`,
  `quality_score`.
- `ict_backtest/translation.py`: `df_to_objects` + `objects_to_legacy_df`.
- `ict_backtest/market_structure.py`: emite `MarketObject` (estado
  event-driven), borra `max_age*` y bloque aged (228-241).

### 5.2 Aliases antiguos (para que nada se rompa)
`objects_to_legacy_df` reconstruye EXACTAMENTE estas columnas desde objetos:
- `bos_direction`, `bos_status` (mapea ObjectState-> "active"/"none"/etc.)
- `choch_signal`, `choch_dir`, `choch_status`
- `fvg_state`, `fvg_bullish`, `fvg_bearish`
- `ob_direction`, `ob_bullish`, `ob_bearish`, `ob_status`
- `liquidity_sweep_up/down`, `sweep_low/high`, `bsl_price`, `ssl_price`
- `macro_direction`, `trend`
- `displacement_bullish/bearish/magnitude`

Mapeo de estado (objeto -> columna legacy) documentado y testeado:
```
ObjectState.ACTIVE      -> "active"
ObjectState.CREATED     -> "active"   (aun no mitigado = vigente)
ObjectState.MITIGATED  -> "active"   (sigue vigente hasta consumo/invalid)
ObjectState.INVALIDATED-> "none"     (compatible con bos_alive de pipeline)
ObjectState.CONSUMED   -> "active"   (ya operado; pipeline no lo filtra)
```
Nota: `aged` DESAPARECE. Pipeline usa `bos_status.isin(["active","none"])`;
como INVALIDATED->"none", el filtro `bos_alive` sigue funcionando IGUAL.
ESTO es clave: matar aged es compatible con `signals/pipeline.py:177-189`.

### 5.3 Tests de regresion (obligatorios antes de tocar consumidores)
1. `test_translation_roundtrip`: `df_to_objects` -> `objects_to_legacy_df`
   reproduce el df original (columnas iguales, mismos valores). PRUEBA que
   ningun consumidor se entera.
2. `test_pipeline_unchanged`: correr `signals/pipeline.build_scalping_context`
   sobre EURUSD M15 ANTES y DESPUES de la migracion; mismos asserts pasan.
3. `test_sequence_unchanged`: `run_sequence` sobre EURUSD H4->M15 da mismo
   numero de senales que el baseline (Fase 0: 76 senales, 28 trades).
4. `test_features_ml_unchanged`: `features/engine.extract_features` sobre una
   fila da mismos valores que antes.
5. `test_adapter_sweep_unchanged`: `feature_enrichment_adapter` sigue con su
   sweep propio (NO se toca en esta migracion; se deja para R3/R4).
6. `test_marketobject_capas`: `MarketObject(origin_tf="M15", role=POI)` se
   rechaza (regla de capa).
7. `test_aged_desaparece`: BOS no cruzado en 200 velas sigue ACTIVE (no muere
   por max_age); y `bos_status` reconstruido != "aged" nunca.

Estos 7 tests son la RED de seguridad: si alguno falla, la migracion rompio
algo y se frena.

---

## 6. Orden recomendado (continuous, no big-bang)

1. Crear `market_object.py` + `translation.py` (fases A/B del diseno).
2. `data_feed.build_features` llama internamente `df_to_objects` y expone
   `objects_to_legacy_df` (los consumidores no lo notan).
3. Correr tests 5.1-5.4, 5.7. Si pasan, la capa vive.
4. Matar aged en `market_structure.py` + detectores (fase D). Correr test 5.7
   + 5.3 (sequence sigue igual porque `bos_status` reconstruido es compatible).
5. Solo al final, refactor OPTIONAL de sequence/rules/engine para leer
   MarketObject directo (fase C del diseno: POI de HTF). Esto es donde se
   gana la fidelidad ICT; las fases 1-4 solo aseguran NO ROMPER.

Esto responde el objetivo: evitar una migracion que rompa todo el motor.
