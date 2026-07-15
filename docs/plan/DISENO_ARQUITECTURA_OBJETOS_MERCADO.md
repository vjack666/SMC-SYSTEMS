# Diseno de Arquitectura Final — SMC-SYSTEMS (Objetos de Mercado ICT)

> **Para Hermes:** Este es el PLANO. No implementa codigo. La implementacion
> detallada (TDD, tareas bite-sized) se escribe en un plan aparte SIGUIENDO
> este diseno. Ver seccion "Siguiente paso".
>
> **Estado:** diseno aprobado en auditoria (Fase 0 baseline hecha, auditoria
> multi-timeframe hecha). No se toca codigo del sistema hasta aprobar este
> plano y el plan de ejecucion.
>
> **Restriccion:** sin "haz commit y push" no se commitea nada.
>
> **Ajustes de aprobacion (revision usuario):** (1) el criterio de aceptacion
> ya NO es "±0.05 del baseline"; es comparar delta y justificar cualquier
> cambio. (2) se agregan `parent_object` / `related_objects` (cadena causal
> ICT) y `quality_score` opcional (sin ML) al MarketObject.

---

## 0. Resumen de los 3 problemas conectados (raiz unica)

La auditoria multi-timeframe (docs/auditorias/) encontro que SMC-SYSTEMS
tiene jerarquia HTF→LTF INCOMPLETA. Las tres fallas que parecen distintas
tienen UNA raiz comun: **el modelo de datos no da identidad ni capa a las
estructuras de mercado.**

| Problema | Sintoma | Raiz |
|----------|---------|------|
| 1. `aged` (mueren por tiempo) | BOS/CHoCH/OB caducan por N velas | El objeto no tiene maquina de estados; muere por contador, no por evento |
| 2. `origin_tf` (no saben su origen) | Un FVG M15 y uno H4 son la misma columna `fvg_state` | El detector es ciego al TF; `build_features` no sella la capa |
| 3. `POI` (no existe como concepto) | El "cuadro" de entrada se saca del M15, no del H4 | No hay `role` que distinga POI (HTF) de refinement (LTF) |

Los tres se curan JUNTOS si cada estructura se convierte en un
**MarketObject** con identidad, capa (origin_tf) y rol (role), y una maquina
de estados event-driven.

---

## 1. Modelo de datos: MarketObject

Reemplaza el esquema actual de "dataframe con columnas sueltas por TF" por
objetos con identidad. Ubicacion propuesta: `ict_backtest/market_object.py`.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import uuid


class ObjectType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"          # incluye MSS (Market Structure Shift)
    FVG = "FVG"
    ORDER_BLOCK = "ORDER_BLOCK"
    LIQUIDITY = "LIQUIDITY" # BSL / SSL
    SWEEP = "SWEEP"


class Role(str, Enum):
    # Un MISMO tipo (ej FVG) juega roles distintos segun su capa.
    POI = "POI"                       # Point of Interest institucional (HTF)
    REFINEMENT = "REFINEMENT"         # entrada/confirmacion (LTF)
    CONTEXT = "CONTEXT"               # sesgo/marea (HTF trend)


class ObjectState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"                 # vigente, esperando reaccion
    MITIGATED = "MITIGATED"           # precio toco el cuadro (parcial)
    INVALIDATED = "INVALIDATED"       # evento de mercado lo mato (cruce de nivel)
    CONSUMED = "CONSUMED"             # ya se opero con el


@dataclass
class MarketObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    type: ObjectType = ObjectType.FVG
    origin_tf: str = ""               # SELLO DE CAPA OBLIGATORIO: "H4"/"M15"/"M5"
    role: Role = Role.REFINEMENT
    direction: int = 0                # +1 long, -1 short, 0 neutral
    zone_high: float = 0.0
    zone_low: float = 0.0
    creation_time: object = None      # pd.Timestamp de la vela que lo creo
    state: ObjectState = ObjectState.CREATED
    # Metadatos especificos por tipo (sweep_level, liquidity_side, etc.)
    meta: dict = field(default_factory=dict)
    # --- Relaciones (cadena causal ICT, revision usuario) ---
    parent_object: str | None = None  # id del objeto padre en la cadena
    related_objects: list[str] = field(default_factory=list)  # ids vinculados
    # --- Calidad opcional (SIN ML; solo heuristica ICT) ---
    quality_score: float | None = None  # None = no evaluado
```

Puntos clave que resuelven los 3 problemas:
- `origin_tf` es OBLIGATORIO en el constructor (no opcional) → problema 2.
- `role` separa POI de refinement → problema 3.
- `state` es la maquina de 5 estados; NO hay `max_age` → problema 1.

---

## 2. Detectores: de ciegos al TF a "sellan capa"

Hoy: `detectors/*.py` reciben `frame` y no saben el TF;
`data_feed.build_features(df)` (data_feed.py:43-86) corre todos sin sellar.

Diseno:
- Cada detector conserva su logica (ya estan bien: canonical_sweep es
  canonico, FVG/OB/BOS/CHoCH funcionan). Lo unico que cambia es la FIRMA de
  salida: devuelven `list[MarketObject]` con `origin_tf` y `role` seteados.
- `build_features` se vuelve `build_objects(frames: dict[tf, df])`:
  para cada tf en frames, corre los detectores y setea `origin_tf=tf` y
  `role` segun la regla de capa (ver seccion 3).
- Los detectores legacy (detectors/bos.py, choch.py, ob.py, fvg.py) se
  mantienen como MOTORES de deteccion pero su salida se envuelve en
  MarketObject. No se duplican.

---

## 3. Regla de rol por capa (resuelve POI)

Mapeo fijo, documentado y TESTEADO:

| Capa (origin_tf) | Tipos detectados | role por defecto |
|------------------|------------------|------------------|
| HTF (D1/H4)      | FVG, ORDER_BLOCK, LIQUIDITY, BOS, CHOCH | POI (FVG/OB/LIQ) / CONTEXT (BOS/CHoCH de marea) |
| ITF (H1/M15)     | BOS, CHOCH, SWEEP, FVG, OB  | REFINEMENT (timing/confirmacion) |
| LTF (M5/M3/M1)   | FVG, OB, SWEEP             | REFINEMENT (entrada fina) |

Regla dura (tesis 18, libro 16): la ENTRADA se forma
`H4 POI + M15 MSS/BOS + M5/M3 refinement`. Un objeto con
`origin_tf="M15"` y `role=POI` es INVALIDO por construccion → el sistema
no puede confundir FVG M15 con POI institucional.

---

## 4. Flujo corregido (resuelve la jerarquia incompleta)

De (actual, incompleto):
```
H4 bias --> M15 setup --> entry
```
A (diseno final):
```
H4 bias (CONTEXT)
  |
  v
H4 POI (zona institucional: FVG/OB/LIQ de HTF)
  |
  v
M15 MSS/BOS + SWEEP (REFINEMENT de timing, debe tocar el H4 POI)
  |
  v
M5/M3 refinement (FVG/OB pequeno como entrada fina)
  |
  v
entry (SL anclado a mecha de sweep del LTF; TP a liquidez OPUESTA del HTF)
```

Donde H4 manda (se preserva lo que YA funciona):
- Sesgo: `engine.build_signals_from_frames` usa `htf_trend` como bias
  (engine.py:85) — SE MANTIENE.
- Direccion BOS/CHOCH: `sequence._has_bos` / `_has_choch` exigen alineacion
  al H4 (sequence.py:111-133) — SE MANTIENE.
- Anti-look-ahead: `TF_FREQ` + `_row_at_time(freq=...)` (engine.py:250-261)
  — SE MANTIENE.

Donde H4 DEBE mandar y hoy no lo hace (se corrige con el plano):
- POI se resuelve desde `role=POI` (HTF), no del LTF — corrige
  `sequence._latest_fvg_zone` / `_latest_ob_zone` (sequence.py:136-160).
- Liquidez objetivo (TP) se resuelve desde LIQUIDITY de HTF — corrige
  `engine._tp_liquidity` (engine.py:283-299) y `calc_structural_sl`.
- Sweep debe barrer la LIQUIDITY del HTF — corrige `canonical_sweep`
  (liquidity_context.py:36-55) agregando chequeo contra BSL/SSL de HTF.

---

## 5. Maquina de estados (resuelve aged)

Los objetos ya tienen identidad (seccion 1) → la muerte por tiempo se
reemplaza por eventos. Unica fuente de verdad:
`ict_backtest/market_structure.py` (ya tiene `detect_market_structure` con
`max_age_*` en lineas 65-66 y bloque aged en 228-241 — ESO SE BORRA).

Transiciones:
```
CREATED --(vela cierra, zona valida)--> ACTIVE
ACTIVE --(precio toca zone_high/low)--> MITIGATED
ACTIVE --(precio cruza nivel opuesto)--> INVALIDATED   # evento, no max_age
MITIGATED --(entry ejecutada)--> CONSUMED
CREATED/ACTIVE --(nueva estructura la supera)--> INVALIDATED
```
- Se ELIMINAN: `max_age`, `max_age_bars`, `max_age_atr` de
  detectors/bos.py:15, choch.py:28, ob.py:39, market_structure.py:65-66.
- Se ELIMINA el bloque aged en market_structure.py:228-241 y los ramas
  `_track_*_validity` en detectors/* que cuentan velas.
- `aged` desaparece del df; nadie lo consume (ya lo confirme en auditoria:
  solo rules.py:82-85 lee "active", aged tiene CERO consumidores).

---

## 6. Consumidores (lo que se actualiza, no se rompe)

Confirmado en auditoria que consumen bos_status/choch_status/ob_status solo
leyendo =="active":
- `ict_backtest/rules.py:82-85, 279`
- `ict_backtest/engine.py:97,120,106,128` (resumen para UI)
- UI: `app_observador/resumen_widget.py:335-338,148`,
  `noticias_widget.py:25-28`

Cambio: esos consumidores pasan de leer `row["bos_status"]=="active"` a
leer `obj.state == ObjectState.ACTIVE`. El concepto "active" se conserva;
solo cambia de columna suelta a atributo de objeto con capa.

El motor de secuencia (`sequence.py`) usa `bos_dir`/`choch_dir` (int), no
`bos_status`. Al matar aged, esos ints NO cambian → la secuencia sigue
igual. Riesgo BAJO para el motor.

---

## 7. Mapeo a archivos (que se toca, que se deja)

| Archivo | Accion | Por que |
|---------|--------|---------|
| `ict_backtest/market_object.py` | CREAR | el MarketObject (seccion 1) |
| `ict_backtest/market_structure.py` | MODIFICAR | borrar max_age + bloque aged (228-241); unica fuente; emitir MarketObject |
| `detectors/bos.py`, `choch.py`, `ob.py`, `fvg.py`, `liquidity.py`, `liquidity_context.py`, `displacement.py` | MODIFICAR firma | devolver list[MarketObject] con origin_tf/role |
| `ict_backtest/data_feed.py` | MODIFICAR | `build_features` -> `build_objects(frames)` que sella capa (43-86) |
| `ict_backtest/engine.py` | MODIFICAR | `_build_estructura` arma dict de MarketObject; `_tp_liquidity`/`calc_structural_sl` usan LIQUIDITY de HTF; `evaluate` recibe objetos |
| `ict_backtest/sequence.py` | MODIFICAR | `_latest_fvg_zone`/`_latest_ob_zone` usan role=POI de HTF; `_has_sweep` chequea barrido a HTF |
| `ict_backtest/rules.py` | MODIFICAR | leer `obj.state` en vez de `status` columna |
| `app_observador/*` | MODIFICAR | leer `obj.state` |
| `docs/ict/*` | NO TOCAR | la tesis ya describe esto; el codigo se alinea |

NO se toca la estrategia (Turtle Soup / PO3 / Silver Bullet). Solo el modelo
de datos y el cableado de capa/rol/estado.

---

## 8. Verificacion (como se prueba que el plano sirvio)

Baseline de referencia (ya medido en Fase 0): EURUSD H4→M15 = 28 trades,
PF 1.424, WR 50%, exp 0.203 R, DD -3.4 R. Tras migrar se compara A vs A'
y se JUSTIFICA cualquier delta (criterio de aceptacion corregido por
revision de usuario — ya NO es "±0.05 del baseline"):

- Si PF/WR/expectancy cambian, se explica POR QUE (ej. mas estructuras vivas
  porque ya no mueren por aged; o menos trades porque el POI de HTF filtra
  ruido M15). No se busca "igualar" — igualar podria obligar a conservar
  errores. El objetivo es MAYOR FIDELIDAD ICT, no numeros iguales.
- No-look-ahead se preserva (TF_FREQ + _row_at_time ya lo garantizan).
- Reporte de migracion obligatorio: tabla A vs A' con delta y causa raiz de
  cada diferencia (ver docs/plan/MIGRACION_* fase F).

Tests unitarios de regresion (independientes del numero de PF):
- Test: `MarketObject(origin_tf="M15", role=POI)` -> rechazado (regla de
  capa). Imposible confundir FVG M15 con POI.
- Test: BOS que no es cruzado por el precio en 200 velas sigue ACTIVE (no
  muere por aged).
- Test: `_tp_liquidity` devuelve BSL/SSL del HTF, no del M15.
- Test: objeto con `parent_object` apunta a un id existente (cadena causal).

---

## 9. Siguiente paso

Este documento es el PLANO. La implementacion detallada (tareas bite-sized
con TDD, exactas lineas a modificar, comandos pytest) se escribe en un plan
separado (`docs/plan/MIGRACION_OBJETOS_MERCADO.md` o `.hermes/plans/`)
SIGUIENDO este diseno, respetando el orden:

- Fase A — MarketObject + regla de rol (secciones 1, 3)
- Fase B — Detectores sellan capa (seccion 2)
- Fase C — Flujo corregido H4 POI→M15→M5 (seccion 4)
- Fase D — Maquina de estados, matar aged (seccion 5)
- Fase E — Consumidores (seccion 6)
- Fase F — Backtest A vs A', doc (seccion 8)

Orden de riesgo: D (aged) es el mas delicado pero mejor aislado; C (flujo
POI) es el que mas valor aporta a la tesis. Se recomienda D primero (ya
tiene baseline de Fase 0 para comparar), luego A/B, luego C, luego E/F.
