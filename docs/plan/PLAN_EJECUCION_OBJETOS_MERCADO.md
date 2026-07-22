> **✅ HISTORICAL** — Plan de ejecución TDD completado. La migración fue implementada vía R9.

# Plan de Ejecución TDD — Objetos de Mercado ICT (MarketObject)

> **For Hermes:** usar la skill `subagent-driven-development` para implementar
> tarea por tarea tras aprobar ESTE plan. Cada tarea es TDD estricto.
>
> **Estado:** PLAN de ejecución. Este documento NO modifica el repositorio.
> Los 3 documentos de diseño ya están aprobados por el usuario:
> - `docs/plan/DISENO_ARQUITECTURA_OBJETOS_MERCADO.md` (modelo de datos)
> - `docs/plan/REVISION_ARQUITECTURA_CONVIVENCIA.md` (capa de traducción)
> - `docs/plan/MARKET_OBJECT_MODEL.md` (ontología / contrato)
>
> **Restricción:** sin "haz commit y push" del usuario no se commitea. El
> plan propone commits FRECUENTES por tarea (como buena práctica TDD), pero
> el commit/push real solo se hace con su autorización explicita.

---

## Goal

Migrar SMC-SYSTEMS de un modelo de columnas pandas suelto a un modelo de
**MarketObject** con identidad (`origin_tf`, `role`), estado event-driven
(5 estados, sin `aged`), y relaciones causales (`parent_object`), SIN romper
el pipeline vivo, el ML, la UI ni los tests existentes. Todo gradual vía una
capa de traducción.

## Architecture

- `MarketObject` (dataclass) es la fuente canonica de una estructura.
- `translation.py` traduce `dict[tf, DataFrame]` <-> `list[MarketObject]`
  bidireccionalmente. `objects_to_legacy_df` reconstruye las columnas sueltas
  para que sequence/rules/engine/pipeline/ML/UI no se enteren del cambio.
- `market_structure.py` pasa a emitir `MarketObject` con estados por evento;
  se BORRA `max_age` (aged).
- Solo en la fase final (E) sequence/rules/engine leen `MarketObject` directo
  y aplican POI de HTF (donde H4 debe mandar en zona/objetivo).

## Tech Stack

Python 3.14, pandas, pyarrow. Tests: pytest (usar `C:\Python314\python.exe
-m pytest`, NO `python3` — el env Roaming está roto). Sin nuevas dependencias.

---

## Orden de fases (gradual, no big-bang)

```
Fase 0  Baseline de regresión (fijar números reales)
Fase A  MarketObject + regla de capa          (objeto puro, sin tocar consumidores)
Fase B  translation.py (df<->objects)         (capa de escudo)
Fase C  build_features envuelve translation   (sin romper columnas)
Fase D  market_structure emite objetos + mata aged
Fase E  refactor sequence/rules/engine a objetos + POI HTF  (fidelidad ICT)
Fase F  backtest A vs A' + documentar delta
```

---

## Fase 0 — Baseline de regresión

### Tarea 0.1: Fijar el baseline real de EURUSD como test de regresión

**Objective:** que cualquier paso futuro pueda comparar contra el número real
ya medido en Fase 0 (EURUSD H4→M15: 28 trades, PF 1.424, WR 50%, 76 señales).

**Files:**
- Create: `tests/test_regression_baseline.py`

**Step 1: Write failing test**
```python
# tests/test_regression_baseline.py
import subprocess, sys, json, os

def test_euruidus_baseline_regression():
    # Numero real medido en Fase 0 (diag run_sequence_backtest EURUSD H4->M15)
    expected = {
        "trades": 28, "profit_factor": 1.424, "win_rate": 50.0,
        "n_senales": 76, "exit_SL": 17, "exit_hold_limit": 9, "exit_TP": 2,
    }
    # No re-corre el backtest (OOM host). Solo afirma que el baseline esta
    # documentado y es el contrato de comparacion.
    here = os.path.dirname(__file__)
    data = json.load(open(os.path.join(here, "baseline_aged.json")))
    eur = data["symbols"]["EURUSD"]
    for k, v in expected.items():
        if k in ("exit_SL","exit_hold_limit","exit_TP"):
            continue
        assert abs(eur.get(k, 0) - v) < 0.01, f"{k}: {eur.get(k)} != {v}"
    assert eur["exit_reasons"]["SL"] == 17
    assert eur["exit_reasons"]["hold_limit"] == 9
    assert eur["exit_reasons"]["TP"] == 2
```

**Step 2: Run test to verify pass (ya debe pasar, es documentación)**
Run: `C:\Python314\python.exe -m pytest tests/test_regression_baseline.py -v`
Expected: PASS (1 passed) — el baseline ya existe en tests/baseline_aged.json.

**Step 3-5:** no hay implementación que hacer; el baseline ya está. Commit
solo si el usuario autoriza.

---

## Fase A — MarketObject + regla de capa

### Tarea A.1: Crear MarketObject con identidad y capa

**Objective:** dataclass con origin_tf obligatorio, role, state, parent_object,
related_objects, quality_score (según MARKET_OBJECT_MODEL.md).

**Files:**
- Create: `ict_backtest/market_object.py`
- Test: `tests/test_market_object.py`

**Step 1: Write failing test**
```python
# tests/test_market_object.py
from ict_backtest.market_object import MarketObject, ObjectType, Role, ObjectState

def test_origin_tf_obligatorio():
    import pytest
    with pytest.raises(TypeError):
        MarketObject(type=ObjectType.FVG, role=Role.REFINEMENT)

def test_poi_solo_en_htf():
    import pytest
    with pytest.raises(ValueError):
        MarketObject(type=ObjectType.FVG, origin_tf="M15", role=Role.POI)

def test_estado_inicial():
    o = MarketObject(type=ObjectType.BOS, origin_tf="H4", role=Role.CONTEXT, direction=1)
    assert o.state == ObjectState.CREATED
    assert o.parent_object is None
    assert o.related_objects == []
    assert o.quality_score is None
```

**Step 2: Run test**
Run: `C:\Python314\python.exe -m pytest tests/test_market_object.py -v`
Expected: FAIL — `ModuleNotFoundError: ict_backtest.market_object`

**Step 3: Write minimal implementation**
```python
# ict_backtest/market_object.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import uuid

class ObjectType(str, Enum):
    BOS = "BOS"; CHOCH = "CHOCH"; FVG = "FVG"
    ORDER_BLOCK = "ORDER_BLOCK"; LIQUIDITY = "LIQUIDITY"; SWEEP = "SWEEP"

class Role(str, Enum):
    POI = "POI"; REFINEMENT = "REFINEMENT"; CONTEXT = "CONTEXT"

class ObjectState(str, Enum):
    CREATED = "CREATED"; ACTIVE = "ACTIVE"; MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"; CONSUMED = "CONSUMED"

# Capas permitidas para POI (ONTología: POI solo en HTF).
_POI_TFS = {"D1", "H4", "H1"}

@dataclass
class MarketObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    type: ObjectType = ObjectType.FVG
    origin_tf: str = ""               # OBLIGATORIO en __post_init__
    role: Role = Role.REFINEMENT
    direction: int = 0
    zone_high: float = 0.0
    zone_low: float = 0.0
    creation_time: object = None
    state: ObjectState = ObjectState.CREATED
    meta: dict = field(default_factory=dict)
    parent_object: str | None = None
    related_objects: list[str] = field(default_factory=list)
    quality_score: float | None = None

    def __post_init__(self):
        if not self.origin_tf:
            raise TypeError("origin_tf es obligatorio (sello de capa)")
        if self.role == Role.POI and self.origin_tf not in _POI_TFS:
            raise ValueError(f"POI solo en HTF ({_POI_TFS}); recibido {self.origin_tf}")
```

**Step 4: Run test**
Run: `C:\Python314\python.exe -m pytest tests/test_market_object.py -v`
Expected: PASS (3 passed)

**Step 5: Commit** (solo con autorización del usuario)
`git add ict_backtest/market_object.py tests/test_market_object.py && git commit -m "feat: MarketObject con capa y rol (Fase A)"`

---

## Fase B — translation.py (capa de escudo)

### Tarea B.1: objects_to_legacy_df reconstruye columnas

**Objective:** desde lista de MarketObject, reconstruir el dict de columnas
que hoy leen sequence/rules/engine/pipeline/ML. Garantiza NO-ROMPER.

**Files:**
- Create: `ict_backtest/translation.py`
- Test: `tests/test_translation.py`

**Step 1: Write failing test**
```python
# tests/test_translation.py
import pandas as pd
from ict_backtest.market_object import MarketObject, ObjectType, Role, ObjectState
from ict_backtest.translation import objects_to_legacy_df

def test_reconstruye_columnas_clave():
    objs = [
        MarketObject(type=ObjectType.BOS, origin_tf="H4", role=Role.CONTEXT,
                     direction=1, state=ObjectState.ACTIVE),
        MarketObject(type=ObjectType.FVG, origin_tf="M15", role=Role.REFINEMENT,
                     direction=1, zone_high=1.1, zone_low=1.09,
                     state=ObjectState.ACTIVE),
    ]
    df = objects_to_legacy_df(objs)
    assert "bos_direction" in df.columns
    assert "fvg_state" in df.columns
    assert int(df["bos_direction"].iloc[0]) == 1
    # INVALIDATED -> "none" (compatible con bos_alive de pipeline)
    inv = MarketObject(type=ObjectType.BOS, origin_tf="H4", role=Role.CONTEXT,
                       state=ObjectState.INVALIDATED)
    df2 = objects_to_legacy_df([inv])
    assert df2["bos_status"].iloc[0] == "none"
```

**Step 2: Run test**
Run: `C:\Python314\python.exe -m pytest tests/test_translation.py -v`
Expected: FAIL — `ModuleNotFoundError: ict_backtest.translation`

**Step 3: Write minimal implementation**
```python
# ict_backtest/translation.py
from __future__ import annotations
import pandas as pd
from ict_backtest.market_object import MarketObject, ObjectState

_STATE_TO_STATUS = {
    ObjectState.ACTIVE: "active",
    ObjectState.CREATED: "active",
    ObjectState.MITIGATED: "active",
    ObjectState.CONSUMED: "active",
    ObjectState.INVALIDATED: "none",
}

def objects_to_legacy_df(objects: list[MarketObject]) -> pd.DataFrame:
    rows = []
    for o in objects:
        r = {
            "type": o.type.value,
            "origin_tf": o.origin_tf,
            "role": o.role.value,
            "direction": o.direction,
            "bos_direction": o.direction if o.type.value == "BOS" else 0,
            "bos_status": _STATE_TO_STATUS.get(o.state, "none"),
            "choch_dir": o.direction if o.type.value == "CHOCH" else 0,
            "fvg_state": (o.type.value if o.type.value == "FVG" else "-"),
            "fvg_bullish": (o.type.value == "FVG" and o.direction == 1),
            "fvg_bearish": (o.type.value == "FVG" and o.direction == -1),
            "ob_direction": (o.type.value if o.type.value == "ORDER_BLOCK" else "-"),
            "ob_bullish": (o.type.value == "ORDER_BLOCK" and o.direction == 1),
            "ob_bearish": (o.type.value == "ORDER_BLOCK" and o.direction == -1),
            "ob_status": _STATE_TO_STATUS.get(o.state, "none"),
            "macro_direction": o.type.value if o.type.value in ("BOS","CHOCH") else "-",
        }
        rows.append(r)
    return pd.DataFrame(rows)
```

**Step 4: Run test**
Run: `C:\Python314\python.exe -m pytest tests/test_translation.py -v`
Expected: PASS

**Step 5: Commit** (con autorización)

### Tarea B.2: df_to_objects sella capa (origen + rol por regla)

**Objective:** desde `{tf: df}` producir `list[MarketObject]` con origin_tf=tf
y role según capa (HTF→POI/CONTEXT, LTF→REFINEMENT). Reusa los detectores
ya existentes (no los reescribe).

**Files:**
- Modify: `ict_backtest/translation.py` (agregar `df_to_objects`)
- Test: `tests/test_translation.py` (agregar test)

**Step 1: Write failing test**
```python
def test_df_to_objects_sella_capa():
    import pandas as pd
    from ict_backtest.translation import df_to_objects
    h4 = pd.DataFrame({"close":[1,2],"high":[1.1,2.1],"low":[0.9,1.9],
                       "bos_direction":[1,0],"fvg_bullish":[True,False]})
    objs = df_to_objects({"H4": h4}, symbol="EURUSD")
    # H4 FVG -> POI por regla de capa; H4 BOS -> CONTEXT
    fvgs = [o for o in objs if o.type.value=="FVG"]
    assert fvgs and fvgs[0].origin_tf == "H4" and fvgs[0].role.value == "POI"
```

**Step 2: Run test** → FAIL (df_to_objects no existe)

**Step 3: Implementation mínima en translation.py**
```python
def df_to_objects(frames: dict[str, pd.DataFrame], symbol: str = "") -> list[MarketObject]:
    objs: list[MarketObject] = []
    POI_TFS = {"D1","H4","H1"}; CONTEXT_TFS = {"D1","H4","H1"}
    for tf, df in frames.items():
        for _, row in df.iterrows():
            # BOS/CHOCH -> CONTEXT en HTF, REFINEMENT en LTF
            bd = int(row.get("bos_direction", 0) or 0)
            if bd != 0:
                objs.append(MarketObject(type=ObjectType.BOS, origin_tf=tf,
                    role=Role.CONTEXT if tf in CONTEXT_TFS else Role.REFINEMENT,
                    direction=bd, symbol=symbol, state=ObjectState.ACTIVE))
            # FVG -> POI en HTF, REFINEMENT en LTF
            if bool(row.get("fvg_bullish", False)) or bool(row.get("fvg_bearish", False)):
                d = 1 if row.get("fvg_bullish") else -1
                objs.append(MarketObject(type=ObjectType.FVG, origin_tf=tf,
                    role=Role.POI if tf in POI_TFS else Role.REFINEMENT,
                    direction=d, symbol=symbol, state=ObjectState.ACTIVE))
    return objs
```

**Step 4: Run test** → PASS

**Step 5: Commit** (con autorización)

---

## Fase C — build_features envuelve translation (sin romper columnas)

### Tarea C.1: data_feed.build_features sigue dando columnas + expone objetos

**Objective:** `build_features` (data_feed.py:43-86) sigue devolviendo el df
con columnas (para que NADIE se entere), pero internamente también puede
producir objetos. NO se borra ninguna columna.

**Files:**
- Modify: `ict_backtest/data_feed.py` (agregar `build_objects` que llama a
  `build_features` y luego `df_to_objects`)
- Test: `tests/test_data_feed_objects.py`

**Step 1: Write failing test**
```python
def test_build_objects_preserva_columnas_y_sella_capa():
    from ict_backtest.data_feed import build_features, build_objects
    import pandas as pd
    df = pd.DataFrame({"open":[1,1],"high":[1.1,1.1],"low":[0.9,0.9],
                       "close":[1,1],"time":[0,1],"atr":[0.01,0.01]})
    feats = build_features(df.copy())
    assert "bos_direction" in feats.columns   # columnas siguen existiendo
    objs = build_objects({"H4": feats}, symbol="X")
    assert any(o.origin_tf == "H4" for o in objs)
```

**Step 2-4:** implementar `build_objects` en data_feed.py llamando
build_features + translation.df_to_objects. Test PASS.

**Step 5: Commit** (con autorización)

### Tarea C.2: Tests de NO-ROTURA (regresión de consumidores)

**Objective:** probar que pipeline/sequence/features ML siguen igual.

**Files:**
- Create: `tests/test_compat_consumidores.py`

**Step 1-4:** tests que corren `signals/pipeline.build_scalping_context`,
`sequence.run_sequence`, `features/engine.extract_features` sobre EURUSD M15
y afirman mismos resultados que ANTES de tocar nada (usar los tests existentes
test_signal_pipeline, test_ict_backtest, test_feature_engine como red).

Run: `C:\Python314\python.exe -m pytest tests/test_signal_pipeline.py tests/test_ict_backtest.py tests/test_feature_engine.py -q`
Expected: PASS (los consumidores no cambiaron; solo se agregó build_objects).

---

## Fase D — market_structure emite objetos + mata aged

### Tarea D.1: Borrar max_age y bloque aged

**Objective:** eliminar caducidad por velas. Archivos exactos (líneas vistas):
- `detectors/bos.py:15` `max_age=24`
- `detectors/choch.py:28` `max_age=20`
- `detectors/ob.py:39` `max_age=20`
- `ict_backtest/market_structure.py:65-66` `max_age_atr=1.5 / max_age_bars=24`
- `ict_backtest/market_structure.py:228-241` bloque aged en `_track_structure`
- Las ramas `_track_bos_validity`/`_track_choch_validity`/`_track_ob_validity`
  en detectors/* que cuentan velas.

**Files:** Modify los 4 archivos arriba + tests.

**Step 1: Write failing test**
```python
def test_bos_no_muere_por_tiempo():
    # BOS no cruzado por el precio en 200 velas sigue ACTIVE (no aged/none)
    from ict_backtest.market_structure import detect_market_structure
    import pandas as pd, numpy as np
    n = 200
    df = pd.DataFrame({
        "open": np.arange(n), "high": np.arange(n)+0.5,
        "low": np.arange(n)-0.5, "close": np.arange(n),
        "time": np.arange(n), "atr": [0.1]*n,
    })
    out = detect_market_structure(df)
    # Ningun bos_status debe ser "aged"
    assert "aged" not in set(out.get("bos_status", []))
```

**Step 2: Run** → FAIL (aparece "aged" en bos_status).

**Step 3:** borrar max_age y el bloque aged de los 4 archivos. El estado se
decide solo por evento (ver _track_structure: cruce de nivel = INVALIDATED).

**Step 4: Run test** → PASS. Run también test_ict_backtest (sequence unchanged:
76 señales / 28 trades vs baseline Fase 0).

**Step 5: Commit** (con autorización)

---

## Fase E — Refactor a objetos + POI HTF (fidelidad ICT) [OPCIONAL/FINAL]

### Tarea E.1: sequence usa POI de HTF, no FVG M15

**Objective:** corregir donde H4 NO mandaba (auditoría): `_latest_fvg_zone` /
`_latest_ob_zone` (sequence.py:136-160) deben buscar role=POI en HTF.

**Files:** Modify `ict_backtest/sequence.py` + test.

**Step 1: Write failing test**
```python
def test_poi_htf_no_m15():
    # Un FVG M15 nunca debe usarse como POI de entrada
    from ict_backtest.sequence import _latest_fvg_zone
    import pandas as pd
    row_m15 = pd.Series({"fvg_bullish": True, "high": 1.1, "low": 1.09})
    # Sin objeto HTF POI disponible -> la zona M15 NO cuenta como POI
    assert _latest_fvg_zone(row_m15, 1) is None  # requiere POI HTF
```

**Step 2-4:** modificar `_latest_fvg_zone` para que reciba la lista de
MarketObjects y solo acepte `role=POI` de HTF. Test PASS.

### Tarea E.2: engine TP usa liquidez HTF

**Objective:** `engine._tp_liquidity` (engine.py:283-299) y `calc_structural_sl`
deben leer BSL/SSL del HTF, no del M15.

**Files:** Modify `ict_backtest/engine.py` + test.

**Step 1-4:** test que `_tp_liquidity` sobre un row M15 con bsl_price M15 pero
existiendo BSL HTF devuelve el de HTF. Test PASS.

---

## Fase F — Backtest A vs A' + documentar delta

### Tarea F.1: Comparar y justificar

**Objective:** correr el backtest post-migración y comparar contra baseline
Fase 0. Criterio (revisado por usuario): NO es "±0.05"; es COMPARAR DELTA Y
JUSTIFICAR. Si PF cambia, explicar por qué (más estructuras vivas por sin-aged;
o menos trades por POI HTF filtrando ruido M15).

**Files:** Modify `scripts/fase0_one.py` (o nuevo script) + doc.

**Step 1-4:** generar tests/baseline_post_migracion.json, tabla A vs A' con
delta y causa raíz por diferencia. Documentar en
`docs/plan/MIGRACION_OBJETOS_REPORTE.md`.

---

## Riesgos y tradeoffs

- **OOM host (ya visto en Fase 0):** los backtests grandes mueren por RAM.
  Mitigación: usar fase0_one.py por símbolo; el baseline de regresión (Tarea
  0.1) NO re-corre el backtest, solo afirma el JSON existente.
- **adapter/feature_enrichment_adapter.py tiene SU sweep propio:** se DEJA
  fuera de esta migración (alcance R3/R4). No se toca en Fases A-F.
- **ML (features/engine.py, ml/*):** siguen con columnas vía
  objects_to_legacy_df. El quality_score explicable (ontología §4) se construye
  SOBRE las columnas, no las reemplaza.

## Criterio de aceptación (final)

- PF/WR/expectancy post-migración se COMPARAN contra baseline y se JUSTIFICAN.
  No se busca igualar (igualar podría conservar errores).
- Tests de regresión de consumidores (C.2) en VERDE: pipeline/sequence/ML/UI
  no se rompen.
- `MarketObject(origin_tf="M15", role=POI)` RECHAZADO (imposible confundir).
- BOS no cruzado en 200 velas sigue ACTIVE (sin aged).
- `parent_object` apunta a id existente (cadena causal).
