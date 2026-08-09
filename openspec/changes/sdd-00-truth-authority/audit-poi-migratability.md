# Auditoría de migrabilidad del clúster POI a `engine/`

**Repositorio:** `C:\Users\v_jac\Desktop\SMC-SYSTEMS` · **Rama:** `feature/backtest-ict` · **HEAD:** `9842394`
**Fecha:** 2026-08-07 · **Modo:** SOLO LECTURA. No se ejecutó `pytest`, ni el harness, ni el backtest.
No se modificó, restauró ni versionó ningún archivo de producción. El contenido borrado se leyó con
`git show HEAD:<ruta>` y `git show a3c29e5^:<ruta>`.

**Criterio de juicio:** `AGENTS.md` §"LEY FUNDAMENTAL — MOTOR vs BACKTEST". `engine/` es la única
fuente de decisión; `ict_backtest/` es consumidor puro y desechable; `engine/` nunca importa
`ict_backtest/`.

---

## Veredicto ejecutivo

**La hipótesis del operador se CONFIRMA.** Los cinco módulos borrados forman un subgrafo
autocontenido. Ninguno toca costes de broker, fills, PnL, equity, simulación de trade, CLI ni IO.
El único acoplamiento real con la capa desechable es el prefijo de import `ict_backtest.`.

Con dos precisiones que corrigen el enunciado de partida:

1. `ict_backtest/htf_pd_index.py` **no** importa solo stdlib + pandas. Importa de forma diferida
   `detectors.fvg.detect_fvg` y `detectors.ob.detect_order_blocks` dentro de `_detect_pd_arrays`.
   No es un bloqueador (`engine/bos/structure.py:47` ya importa `detectors.displacement`), pero
   obliga a una decisión explícita de diseño.
2. `ict_backtest/market_object.py` **no es una ontología paralela**. Es un shim de re-export de
   23 líneas que reexporta `engine.market_object`. Las dos ontologías no son "compatibles": son
   **el mismo objeto**.

Los bloqueadores que quedan son **de diseño, no de acoplamiento**: una colisión de nombres, una
contradicción de contrato fail-open/fail-closed, y la elección de la fuente de detectores.

| Pregunta | Respuesta corta |
|---|---|
| ¿Es `engine/market_object.py` suficiente para `anchor_objects`? | **SÍ.** Cero atributos faltantes. |
| ¿Hay acoplamiento genuino al backtest en los 5 módulos? | **NO.** Ninguno. |
| ¿Se puede migrar mecánicamente? | **3 de 5 sí** (cambio de prefijo). 2 requieren decisión previa. |
| ¿La cobertura actual sustituye a la anterior? | **NO.** Se perdieron 10 comportamientos distintos. |

---

## Q1 — Compatibilidad de ontología

### Q1.1 — Diff de las dos ontologías

No hay diff que hacer. `ict_backtest/market_object.py` en `HEAD` es un shim puro:

```
"""ict_backtest/market_object.py — SHIM de compatibilidad (B1).

El objeto de mercado ICT es ahora la FUENTE UNICA del motor y vive en
``engine.market_object``. Este modulo SOLO re-exporta para no romper a los
~40 importadores (backtest, scripts, tests). Cero logica duplicada.
"""

from engine.market_object import (  # noqa: F401 — el motor es la fuente
    ObjectType,
    ObjectState,
    Role,
    MarketObject,
)
```

**Veredicto: IDÉNTICAS por construcción.** No son dos definiciones compatibles; son la misma clase
importada por dos rutas. Cualquier `MarketObject` creado por el backtest **es** un
`engine.market_object.MarketObject` (mismo objeto de clase, `isinstance` verdadero).

Miembros de la ontología única (`engine/market_object.py:21-75`):

| Elemento | Miembros | Cita |
|---|---|---|
| `ObjectType` | `BOS`, `CHOCH`, `FVG`, `ORDER_BLOCK`, `LIQUIDITY`, `SWEEP`, `CANDLE` | `engine/market_object.py:21-28` |
| `Role` | `POI`, `REFINEMENT`, `CONTEXT` | `:31-34` |
| `ObjectState` | `CREATED`, `ACTIVE`, `MITIGATED`, `INVALIDATED`, `CONSUMED` | `:37-42` |
| `MarketObject` | 15 campos + `__post_init__` | `:49-75` |

Invariante de capa que el motor ya impone: `_POI_TFS = {"D1", "H4", "H1"}` (`:46`) y
`__post_init__` lanza `ValueError` si `role == Role.POI` con `origin_tf` fuera de ese conjunto
(`:72-75`), y `TypeError` si falta `origin_tf` (`:70-71`).

### Q1.2 — Verificación atributo por atributo para `anchor_objects`

`anchor_objects` (borrado, `git show HEAD:ict_backtest/poi_anchor.py`) usa 8 atributos de instancia
y 4 miembros de `ObjectType`. **Los 12 existen en la ontología del motor.**

| Símbolo usado | Presente en `engine/market_object.py` | Declaración | Estado |
|---|---|---|---|
| `obj.meta` | Sí | `:61` `meta: dict = field(default_factory=dict)` | ✅ |
| `obj.parent_object` | Sí | `:62` `parent_object: str \| None = None` | ✅ |
| `obj.related_objects` | Sí | `:63` `related_objects: list[str] = field(default_factory=list)` | ✅ |
| `obj.direction` | Sí | `:56` `direction: int = 0` | ✅ |
| `obj.bar_time` | Sí | `:67` `bar_time: object = None` | ✅ |
| `obj.bar_index` | Sí | `:66` `bar_index: int \| None = None` | ✅ |
| `obj.type` | Sí | `:53` `type: ObjectType = ObjectType.FVG` | ✅ |
| `obj.id` | Sí | `:51` `id: str = field(default_factory=lambda: str(uuid.uuid4()))` | ✅ |
| `ObjectType.FVG` | Sí | `:24` | ✅ |
| `ObjectType.ORDER_BLOCK` | Sí | `:25` | ✅ |
| `ObjectType.BOS` | Sí | `:22` | ✅ |
| `ObjectType.CHOCH` | Sí | `:23` | ✅ |

Detalle relevante para la mutación: `meta` y `related_objects` usan `field(default_factory=...)`,
por lo que `obj.meta["anchored"] = False` y `obj.related_objects.append(anchor.id)`
(líneas del módulo borrado) funcionan sin inicialización previa.

### Q1.3 — Atributos presentes en la ontología del backtest y ausentes en la del motor

**NINGUNO.** No existe superficie divergente que auditar: hay una sola definición.
**Cero bloqueadores de migración por ontología.**

### Q1.4 — ¿Es `ict_backtest/market_object.py` una violación de la Ley?

**No viola el punto 2** (no contiene lógica de decisión ni de detección: cero cuerpo funcional).
**Sí colisiona con el punto 3** (el backtest es desechable): el día que se borre `ict_backtest/`,
los importadores del shim quedan rotos aunque la ontología siga viva en el motor.

Importadores del shim en el árbol de trabajo — **34 archivos**:

| Capa | Cantidad | Archivos |
|---|---:|---|
| `ict_backtest/` | 13 | `bos_table_builder.py`, `event_engine.py`, `invalidators.py`, `market_narrative.py`, `object_graph.py`, `plan_attach.py`, `plan_driver.py`, `plan_emitters.py`, `plan_fsm.py`, `semantic_adapter.py`, `state_machine.py`, `translation.py` (+ el propio shim) |
| `tests/` | 21 | `test_fvg_zone_gap.py`, `test_market_object.py`, `test_plan_attach.py`, `test_plan_cableado_real.py`, `test_plan_driver*.py` (×3), `test_plan_emitters.py`, `test_plan_gate_a1.py`, `test_poi_anchor.py`, `test_r10_bos_gap_dynamic.py`, `test_r10c_*.py` (×8), `test_run_backtest_attach_plan.py`, `test_translation.py` |
| `engine/` | **0** | — (la coincidencia en `engine/market_object.py:1` es el docstring, no un import) |

**Recomendación:** el shim **no** debe migrar (ya está migrado: es el destino el que vive en el
motor). Debe **retirarse** repuntando los 34 importadores a `engine.market_object`. Es un
`sed` de una línea por archivo, sin cambio semántico, verificable con
`tests/test_market_object.py`. No es urgente, pero es deuda de la Ley §3.

---

## Q2 — Grafo de dependencias y cumplimiento de la Ley tras la migración

### Tabla de veredictos

| Módulo | LOC | Veredicto | Ajuste requerido |
|---|---:|---|---|
| `ict_backtest/poi_anchor.py` | 88 | **MIGRA_LIMPIO** | Cambiar `ict_backtest.market_object` → `engine.market_object`. Eliminar el import muerto de `Role`. |
| `ict_backtest/poi_anchor_motor.py` | 45 | **MIGRA_LIMPIO** | Cambiar prefijo de `htf_pd_index`. **Recomendación: no migrar como módulo — fusionar** (ver abajo). |
| `ict_backtest/zone_authority.py` | 103 | **MIGRA_LIMPIO** | Cambiar prefijo de `htf_pd_index`. **Salvedad semántica**: decidir antes si es decisión u ornamento. |
| `ict_backtest/htf_pd_index.py` | 212 | **MIGRA_CON_AJUSTE** | Decidir la fuente de detectores: `detectors/` (trae `pd_type`/`pd_tier`) vs `engine/fvg_poi.py` + `engine/order_block.py` (no los traen). |
| `ict_backtest/poi_filter.py` | 74 | **MIGRA_CON_AJUSTE** | **Colisión de nombres**: sus dos símbolos públicos ya existen en `engine/poi_anchor.py` con firma y semántica distintas. Requiere renombrado. |

### Q2.1 / Q2.2 — Detalle por módulo

#### `ict_backtest/poi_anchor.py` — MIGRA_LIMPIO

| Import | Tipo | Destino post-migración |
|---|---|---|
| `from __future__ import annotations` | stdlib | igual |
| `from ict_backtest.market_object import MarketObject, ObjectType, Role` | shim → motor | `from engine.market_object import MarketObject, ObjectType` |
| `import pandas as pd` (diferido, dentro de `_closed_before`) | tercero | igual |

Símbolos externos: `MarketObject`, `ObjectType.BOS`, `ObjectType.CHOCH`, `pd.to_datetime`.
`Role` se importa y **nunca se usa** — import muerto.

Función pura sobre grafo de objetos. Sin IO, sin DataFrame, sin estado global. Es el módulo **más
idiomático del motor** de los cinco: opera en la moneda nativa (`MarketObject`), no en columnas.

Concerns de backtest (costes / fills / PnL / equity / simulación / CLI / IO): **ninguno**. ✅

#### `ict_backtest/poi_anchor_motor.py` — MIGRA_LIMPIO (pero redundante)

| Import | Tipo | Destino post-migración |
|---|---|---|
| `from __future__ import annotations` | stdlib | igual |
| `from typing import Any` | stdlib | igual |
| `import pandas as pd` | tercero | igual (solo type hint) |
| `from ict_backtest.htf_pd_index import HtfPdIndex` | interno | `from engine.htf_pd_index import HtfPdIndex` |

Único símbolo externo: `HtfPdIndex` (y su método `zones_at` / propiedad `timeframes`).

**Redundancia comprobada:** `compute_htf_anchored(sig_dir, entry_at, htf_pd_index, ltf_map)` recorre
exactamente el mismo bucle que `poi_filter.poi_present(htf_pd_index, ltf_map, i, target)`. La única
diferencia de contrato es el retorno cuando falta el índice: `None` (tri-estado) frente a `False`.
**Recomendación:** no migrar como módulo separado; absorber en una única función con contrato
tri-estado explícito (`bool | None`).

Concerns de backtest: **ninguno**. ✅

#### `ict_backtest/zone_authority.py` — MIGRA_LIMPIO (con salvedad semántica)

| Import | Tipo | Destino post-migración |
|---|---|---|
| `from __future__ import annotations` | stdlib | igual |
| `from dataclasses import dataclass` | stdlib | igual |
| `from ict_backtest.htf_pd_index import HtfPdZone` | interno | `from engine.htf_pd_index import HtfPdZone` |

Único símbolo externo: `HtfPdZone` (dataclass congelada, datos puros: `tf`, `pd_type`, `pd_tier`,
`direction`, `zone_high`, `zone_low`).

Concerns de backtest: **ninguno** (aritmética determinista, sin IO). ✅

**Salvedad — ¿decisión o medición?** El módulo se autodeclara *"PERCEPCIÓN, no decisión"* y
*"Regla de hierro (R4 del plan): C es PESO DE CONFIANZA, NUNCA gate duro"*. Pero los pesos
(`+0.5` por ancla, `+0.3` T1 / `+0.15` T2 / `+0.05` T3, `+0.2` por 3 capas) **son un juicio humano
sobre qué importa más**, exactamente el tipo de política que la Ley reserva al motor. La prueba por
contradicción: si mañana un umbral consume `confidence_weight`, la política estaría en la capa
desechable. Si nunca lo consume nadie, es ornamento y no debería entrar al motor.

**Recomendación:** **no migrar hasta que exista un consumidor con contrato declarado.** Hoy no lo
hay: `engine/sequence.py:521-523` lo anuló explícitamente (`state.zone_authority = None`) con el
comentario `# zone_authority eliminado del backtest: era ornamento del backtest (tier/stacking).`

#### `ict_backtest/htf_pd_index.py` — MIGRA_CON_AJUSTE

| Import | Tipo | Destino post-migración |
|---|---|---|
| `from __future__ import annotations` | stdlib | igual |
| `from dataclasses import dataclass` | stdlib | igual |
| `from typing import Any` | stdlib | igual |
| `import pandas as pd` | tercero | igual |
| `from detectors.fvg import detect_fvg` (**diferido**, en `_detect_pd_arrays`) | paquete `detectors/` | **decisión requerida** |
| `from detectors.ob import detect_order_blocks` (**diferido**) | paquete `detectors/` | **decisión requerida** |

> **Corrección al enunciado de partida.** Este módulo no importa "solo stdlib + pandas". Los dos
> imports de `detectors/` están dentro del cuerpo de la función, por eso no aparecen en la cabecera.

Símbolos externos consumidos, más allá de las dos funciones: las **columnas de DataFrame** que esos
detectores producen y que `_detect_pd_arrays` lee — `fvg_bullish`, `fvg_bearish`, `fvg_fill_status`,
`ob_bullish`, `ob_bearish`, `ob_top`, `ob_bottom`, `ob_status`, `pd_type`, `pd_tier`.

**¿`engine/` puede importar `detectors/`?** Sí. Precedente vigente y no cuestionado:
`engine/bos/structure.py:47` — `from detectors.displacement import DisplacementConfig, detect_displacement`.
La Ley solo prohíbe `engine/` → `ict_backtest/`.

**El cierre transitivo hoy está limpio, pero no está protegido.** `detectors/killzones.py:25` importa
`from ict_backtest.rules import server_to_utc, _et_band_to_utc`. `detectors/__init__.py` **no**
importa `killzones` (solo `displacement`, `fvg`, `liquidity`, `ob`, `zones`), y ninguno de esos cinco
toca `ict_backtest`. Ver Riesgo R-3.

**La decisión real: qué detector usar.** Hay cuatro implementaciones de FVG/OB conviviendo:

| Implementación | Emite `pd_type` / `pd_tier` | Cita |
|---|:---:|---|
| `detectors/fvg.py:7` + `detectors/ob.py:7` | **SÍ** | `detectors/fvg.py:42-46`, `detectors/ob.py:60-67` |
| `engine/fvg_poi.py:29` + `engine/order_block.py:35` | **NO** | columnas emitidas: `fvg_bullish/bearish/top/bottom/size/mid/fill_status`, `ob_bullish/bearish/top/bottom/status` |

La taxonomía T1/T2/T3 y `REJECTION_BLOCK` **solo existe en `detectors/`**. Migrar `htf_pd_index`
apuntando a los detectores nativos del motor exige portar esa clasificación, lo que **cambia la
salida** y rompe la paridad con `test_fase_c0` / `test_fase_c2`. Mantener `detectors/` conserva la
paridad al coste de una dependencia de tercer paquete.

Concerns de backtest: **ninguno**. Es percepción pura, sin IO ni CLI. ✅

#### `ict_backtest/poi_filter.py` — MIGRA_CON_AJUSTE

| Import | Tipo | Destino post-migración |
|---|---|---|
| `from __future__ import annotations` | stdlib | igual |
| `from typing import Any, Callable` | stdlib | igual |
| `from ict_backtest.htf_pd_index import HtfPdIndex, HtfPdZone` | interno | `from engine.htf_pd_index import HtfPdIndex` (`HtfPdZone` es **import muerto**) |

**Bloqueador de diseño: colisión de nombres.** Los dos símbolos públicos ya existen en
`engine/poi_anchor.py` con **firma distinta y semántica distinta**:

| Nombre | Versión borrada (`poi_filter`) | Versión vigente (`engine/poi_anchor.py`) |
|---|---|---|
| `poi_present` | `(htf_pd_index, ltf_map, i, target) -> bool`. Pregunta: *¿hay una ZONA PD (FVG/OB) del HTF vigente en esta dirección?* | `engine/poi_anchor.py:127` `(ltf_frame, htf_frames, i, target, parents=...) -> bool`. Pregunta: *¿hay un BOS/CHOCH padre cerrado en esta dirección?* |
| `make_htf_poi_fn` | `(htf_pd_index, ltf_map, *, as_gate=False) -> Callable[[int,int],bool]` | `engine/poi_anchor.py:86` `(ltf_frame, htf_frames, parents=..., window_n=20)` |

Son **conceptos diferentes**: geometría de zona frente a narrativa de estructura. Migrar sin
renombrar produce una colisión silenciosa e indetectable por los tests actuales.

**Hallazgo colateral — corrección de `evidence-code.md` §6.** Ese documento marcó como `STALE` el
comentario `ict_backtest/canonical.py:233` (`as_gate=False: NO veta …`) por no existir el parámetro
`as_gate` en `engine/poi_anchor.make_htf_poi_fn`. La causa real es otra: **el parámetro `as_gate`
existía de verdad**, en `poi_filter.make_htf_poi_fn`, y desapareció con el borrado. El comentario no
es una invención: es un residuo de un módulo eliminado. Con esta corrección, la conclusión de
`evidence-code.md` (que hoy no existe forma de convertir el POI en veto) sigue siendo válida: el
modo `as_gate=True` era el único mecanismo y ya no está.

Concerns de backtest: **ninguno**. ✅

### Q2.4 — Confirmación de ausencia de preocupaciones de backtest

Barrido explícito sobre los cinco módulos, buscando lo que la Ley reserva a la capa desechable:

| Preocupación (medición / simulación) | Presente en alguno de los 5 |
|---|:---:|
| Costes de broker (spread / comisión / slippage) | **No** |
| Fills / next-open / precio de ejecución | **No** |
| PnL, `pnl_r`, R múltiple | **No** |
| Equity, drawdown, curva | **No** |
| Simulación de trade, `simulate_trade`, `max_hold` | **No** |
| CLI / `argparse` | **No** |
| IO de ficheros / parquet / `load_frames` | **No** |
| Conteo de señales / métricas agregadas | **No** |

**Los cinco son lógica de percepción y decisión.** Nada de medición se colaría con la migración.

---

## Q3 — Consumidores y radio de impacto

### Q3.1 — Quién importaba cada módulo ANTES del borrado (estado `HEAD`)

| Módulo borrado | Consumidores en `HEAD` |
|---|---|
| `htf_pd_index.py` | `ict_backtest/zone_authority.py:27`, `ict_backtest/poi_filter.py:26`, `ict_backtest/poi_anchor_motor.py:21`, `scripts/cierre_brecha_b_demo.py:22`, `scripts/verify_brecha_ce_cableado.py:21`, y 6 tests ya eliminados (ver Q4) |
| `zone_authority.py` | `tests/test_fase_d_paso2_trade_context.py:94`, `tests/test_r10c_adapter.py:219`, tests eliminados `test_fase_c2.py`, `test_fase_c4.py` |
| `poi_filter.py` | Solo el test eliminado `tests/test_a_poi_anchored.py` |
| `poi_anchor_motor.py` | Solo el test eliminado `tests/test_poi_anchor_motor.py`; referencia en prosa en `ict_backtest/po3_motor.py:3` |
| `poi_anchor.py` | `ict_backtest/plan_attach.py:100` (import diferido, dentro de `anchor_m15`), `tests/test_poi_anchor.py:40,50,60,70`, `tests/test_plan_cableado_real.py:58` |

Historia de creación (`git log --name-status`):

| Commit | Alta |
|---|---|
| `5ca8b3e` — *Fase C (C0-C4): capa de autoridad de zonas HTF (percepcion, no invasion)* | `htf_pd_index.py`, `zone_authority.py` |
| `c7a635c` — *Fase 5 medidor de alineacion cierra brechas B/C/A1/E de la tesis* | `poi_anchor.py` |
| `f9ae685` — *cierra Brecha B en motor (Opcion 2) + repara medidor Fase 5* | `poi_anchor_motor.py` (+ modificación de `poi_anchor.py`) |
| `3ab3169` — *Cierra Brecha A1 real … + Brecha A (POI bonus)* | `poi_filter.py` |

**Hallazgo:** `ict_backtest/canonical.py` **nunca importó** ninguno de los cinco. La única mención
en `HEAD:ict_backtest/canonical.py:167` es texto de docstring (`construye HtfPdIndex y anota
zone_authority …`). Consecuencia directa: los dos scripts que hacen
`patch("ict_backtest.canonical.HtfPdIndex", …)` (`scripts/cierre_brecha_b_demo.py:77`,
`scripts/verify_brecha_ce_cableado.py:50`) **ya estaban rotos en `HEAD`**, antes del borrado, porque
el atributo que parchean no existe en ese módulo.

### Q3.2 / Q3.3 — Huérfanos HOY y acción requerida

La lista aportada se **confirma íntegra** y se **amplía con 6 huérfanos no listados**. Los nuevos
no son `ImportError`: son huérfanos de comportamiento (código vivo que ahora recorre una rama
permanentemente vacía).

#### Huérfanos duros (`ImportError` garantizado al recorrer esa ruta)

| # | Huérfano | Línea | Naturaleza | Acción post-migración |
|---|---|---|---|---|
| 1 | `scripts/verify_brecha_ce_cableado.py` | `:21` `from ict_backtest.htf_pd_index import HtfPdZone` | Import de nivel de módulo | **Decisión del operador.** Ya estaba roto en `HEAD` por `:50`. Recomendación: **borrar** como script de verificación muerto. |
| 2 | `scripts/cierre_brecha_b_demo.py` | `:22` `from ict_backtest.htf_pd_index import HtfPdZone` | Import de nivel de módulo | Igual que el anterior; también roto en `HEAD` por `:77`. Recomendación: **borrar**. |
| 3 | `ict_backtest/plan_attach.py` | `:100` `from ict_backtest.poi_anchor import anchor_objects` | Import **diferido** dentro de `anchor_m15` (`:99-106`) | **Borrar `anchor_m15` como código muerto.** Verificado: `anchor_m15` no tiene ni un solo llamador en el árbol. Al ser diferido, `attach_alignment` (sí invocada, `ict_backtest/run_backtest.py:73`) **no** se rompe hoy. |
| 4 | `tests/test_r10c_adapter.py` | `:219` `from ict_backtest.zone_authority import ZoneAuthority` | Import diferido dentro del test | **Repuntar** si `ZoneAuthority` migra; **borrar el test** si se decide no migrarlo. |
| 5 | `tests/test_fase_d_paso2_trade_context.py` | `:94` idem | Import diferido | Igual que el anterior. |
| 6 | `tests/test_poi_anchor.py` | `:40,50,60,70` + `:16` `from ict_backtest.market_object import …` | Imports diferidos + import de cabecera | **Repuntar** (2 prefijos) y eliminar el `sys.path.insert` de `:11-14`. Ver Q4.3. |
| 7 | `tests/test_plan_cableado_real.py` | `:58` `from ict_backtest.poi_anchor import anchor_objects` | Import diferido | **Repuntar** a `engine.poi_anchor`. |

#### Huérfanos de comportamiento (no listados en el enunciado; hallazgos nuevos)

| # | Huérfano | Línea | Problema | Acción |
|---|---|---|---|---|
| 8 | `tests/test_fase_d_paso1_backtest_wiring.py` | `:71,75` | Afirma `s.zone_authority is not None` con `enable_pd_index=True`. `engine/sequence.py:523` fija `state.zone_authority = None` incondicionalmente. Solo pasa **de forma vacua** gracias al guard `if sigs:` de `:69`. | **Reescribir o borrar.** Es un test que ya no puede fallar. |
| 9 | `scripts/validate_fase_d_integrity.py` | `:76,94,101,118` | Mide cobertura de `ctx.zone_authority`; reportará 0 % de forma permanente. | Script de **medición**: no migra. Decidir si sobrevive. |
| 10 | `ict_backtest/diagnostics/context_builder.py` + `trade_context.py` | `:70,114` / `:82` | Passthrough de `zone_authority`, siempre `None`. | Forense post-trade: **no migra**. Limpiar el campo o dejarlo documentado como muerto. |
| 11 | `ict_backtest/semantic_adapter.py` | `:28,43,70,121` | Parámetro `zone_authority_map` sin productor. | Parámetro muerto salvo que `ZoneAuthority` regrese. |
| 12 | `ict_backtest/po3_motor.py` | `:3` | Prosa: *"Copia del patrón de Brecha B (ict_backtest/poi_anchor_motor.py)"*. | Actualizar el texto tras la migración. |
| 13 | `ict_backtest/setups/ote.py:4`, `ict_backtest/trade_mgmt.py:3`, `tests/test_c2_silver_bullet.py:15`, `tests/test_rr_map.py:4` | — | Prosa que cita `poi_filter.py` como archivo intocado. | Actualizar texto. Sin efecto funcional. |

### Q3.4 — Referencias de documentación colgantes en `engine/`

Barrido completo de `engine/**/*.py` buscando referencias a tipos y módulos inexistentes.
**11 hallazgos**, agrupados por gravedad.

#### A. Tipos que ya no existen, citados como si existieran

| Cita | Texto | Problema |
|---|---|---|
| `engine/sequence.py:101` | `zone_authority: Any = None     # Fase C (C2/C3): ZoneAuthority anotada (peso de confianza)` | `ZoneAuthority` no existe en ninguna parte del árbol |
| `engine/sequence.py:403` | `HTF vigentes (HtfPdZone) a la vela i.` | `HtfPdZone` no existe |
| `engine/sequence.py:420-423` | `htf_pd_index -> HtfPdIndex OPCIONAL (Fase C, C1/C2). Si se pasa, cada zona LTF trazada se ANOTA con su ZoneAuthority (peso de confianza de zona, NO gate duro). El conteo de senales NO cambia` | **Dos tipos inexistentes** y, además, describe un comportamiento que este archivo nunca implementó (ver B) |
| `engine/sequence.py:424` | `Cada senal: {time, direction, entry, phase_log, zone_authority}.` | El campo siempre vale `None` |

#### B. Parámetros muertos: `htf_pd_index` y `ltf_map`

Verificado con `git show HEAD:engine/sequence.py`: los parámetros se declaran en **tres firmas** y
se reenvían entre ellas, pero **nunca se leen en el cuerpo** de `_run_sequence_impl`.

| Cita | Rol |
|---|---|
| `engine/sequence.py:392` | Declaración en `_run_sequence_impl` |
| `engine/sequence.py:643` + `:654` | Declaración y reenvío en `run_sequence` |
| `engine/sequence.py:662` + `:669` | Declaración y reenvío en `run_sequence_traced` |

**No hay ninguna otra aparición.** Ya estaban muertos en `HEAD`, antes de los borrados. Toda la
lógica que los usaba vivía en `ict_backtest/sequence.py`; al replicarse el motor, el parámetro viajó
y el cuerpo no.

#### C. Contradicción interna en el mismo archivo

`engine/sequence.py:521-523` documenta la decisión de suprimir la anotación:

```
521:                # zone_authority eliminado del backtest: era ornamento del
522:                # backtest (tier/stacking). El motor es la unica fuente.
523:                state.zone_authority = None
```

Esto **contradice frontalmente** el docstring de `:420-423` del mismo archivo, que sigue prometiendo
la anotación. Un agente que lea el docstring y no el cuerpo concluirá que la capacidad existe.

#### D. Inversión documental de la Ley

| Cita | Texto | Problema |
|---|---|---|
| `engine/poi_anchor.py:16` | `# luego pasar htf_poi_fn a ict_backtest.sequence.run_sequence(...)` | El ejemplo de uso del **motor** apunta al **backtest**. El destino correcto es `engine.sequence.run_sequence`. Inversión de la Ley a nivel de documentación. |

#### E. Cabeceras con la ruta de módulo equivocada (heredadas de la migración)

| Cita | Texto |
|---|---|
| `engine/market_object.py:1` | `"""ict_backtest/market_object.py - Objeto de mercado ICT (fuente canonica).` |
| `engine/sequence.py:1` | `"""ict_backtest/sequence.py - Capa 2: motor EVENT-SEQUENCE (memoria de eventos).` |

#### F. Afirmación de aislamiento contradicha por el código

| Cita | Texto | Evidencia en contra |
|---|---|---|
| `engine/dealing_range.py:11` | `El motor no importa ict_backtest/ ni detectors/.` | `engine/bos/structure.py:47` — `from detectors.displacement import DisplacementConfig, detect_displacement`. La primera mitad es cierta; la segunda es falsa. Relevante porque es exactamente el permiso que necesita `htf_pd_index`. |

#### G. Función muerta relacionada

| Cita | Símbolo | Estado |
|---|---|---|
| `engine/sequence.py:223` | `_htf_has_poi(est_htf, target)` | Definida, reexportada por `ict_backtest/sequence.py:23,51`, **sin ningún llamador**. Su única cobertura era `tests/test_e_poi.py`, eliminado. Es una **tercera** noción de POI (lee las banderas `fvg_bullish`/`ob_bullish` de un dict HTF). |

<!--PART3-->

