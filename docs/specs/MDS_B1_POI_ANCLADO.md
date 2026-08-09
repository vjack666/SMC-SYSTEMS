# MDS_B1_POI_ANCLADO.md — POI anclado a la narrativa del TF padre (B1)

- **Clasificación**: OBLIGATORIO · Fase B1 (Brecha B, tesis 18 / libro 21 §4) · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja el código REAL de tres módulos:
  - `engine/poi_anchor.py` — ancla narrativa (`make_htf_poi_fn`, `poi_present`,
    `build_htf_structure_index`).
  - `engine/htf_pd_index.py` — índice temporal de PD arrays HTF (`HtfPdIndex`, `HtfPdZone`).
  - `engine/zone_authority.py` — peso de autoridad de zona (`evaluate_zone_authority`, `ZoneAuthority`).
- **Ley**: `engine/` única fuente de decisión y percepción; `ict_backtest/` consume.
  `engine/` **NUNCA** importa `ict_backtest/`.

---

## 1. Propósito

Un FVG/OB del LTF por sí solo es **geometría suelta** (auditoría: 100 % de zonas
sin ancla). El POI real está **ANCLADO a la narrativa**: existe un BOS/CHOCH en el
TF padre (D1/H4/H1), en la **misma dirección** del setup LTF y **ya cerrado**.

Este SDD define dos señales complementarias, ambas **BONUS / PESO, nunca gate duro**:

- `poi["anchored"]` — ¿hay evento estructural padre en la dirección del setup?
  (`engine/poi_anchor.py`)
- `poi["authority"]` — ¿cuánta autoridad contextual tiene la zona LTF según los PD
  arrays HTF vigentes? (`engine/htf_pd_index.py` + `engine/zone_authority.py`)

---

## 2. Por qué importa

1. **Narrativa antes que geometría**: la tesis 18 / libro 21 §4 dice que el POI
   vale por el contexto que lo respalda, no por el dibujo.
2. **Regla de hierro (R4 / auditoría Fase E)**: la autoridad es **PESO DE
   CONFIANZA**, NUNCA gate duro. Convertir POI en gate duro **destruye edge**:
   medido **PF 0.900 (gate) vs 1.511 (bonus)**. Por eso `make_htf_poi_fn` devuelve
   `True` cuando no hay eventos padre cargados (no bloquea el histórico) y
   `evaluate_zone_authority` no altera el conteo de señales por diseño.
3. **Contrato de no invasión**: estos módulos son **percepción**, no decisión.
   No deciden dirección, entry, SL ni TP; no crean zonas — solo leen las que el
   motor/detectores ya trazaron.

---

## 3. Entradas (firmas reales)

### 3.1 `engine/poi_anchor.py`
```python
_HTF_PARENTS = ("D1", "H4", "H1")
_DIR_NUM = {BULLISH: 1, BEARISH: -1, "BULLISH": 1, "BEARISH": -1}

@dataclass(frozen=True)
class _ParentEvent:
    time: pd.Timestamp
    direction: int   # 1 / -1
    kind: str        # "BOS" / "CHOCH"
    tf: str

def build_htf_structure_index(
    htf_frames: dict[str, pd.DataFrame],
    parents: tuple[str, ...] = _HTF_PARENTS,
) -> list[_ParentEvent]: ...

def make_htf_poi_fn(
    ltf_frame: pd.DataFrame,
    htf_frames: dict[str, pd.DataFrame],
    parents: tuple[str, ...] = _HTF_PARENTS,
    window_n: int = 20,
):  # -> htf_poi_fn(i: int, target) -> bool

def poi_present(
    ltf_frame: pd.DataFrame,
    htf_frames: dict[str, pd.DataFrame],
    i: int,
    target,
    parents: tuple[str, ...] = _HTF_PARENTS,
) -> bool: ...
```

### 3.2 `engine/htf_pd_index.py`
```python
@dataclass(frozen=True)
class HtfPdZone:
    tf: str          # "D1" / "H4" / "H1"
    pd_type: str     # FVG / OB / BPR / REJECTION_BLOCK / MITIGATION_BLOCK / BREAKER
    pd_tier: str     # T1 / T2 / T3
    direction: int   # +1 bullish, -1 bearish
    zone_high: float
    zone_low: float

class HtfPdIndex:
    def __init__(self, htf_frames: dict[str, pd.DataFrame]): ...
    def build_ltf_map(self, ltf_df: pd.DataFrame) -> dict[str, pd.DataFrame]: ...
    def zones_at(self, ltf_i: int, htf_tf: str,
                 ltf_map: dict[str, pd.DataFrame] | None = None) -> list[HtfPdZone]: ...
    @property
    def timeframes(self) -> list[str]: ...
```

### 3.3 `engine/zone_authority.py`
```python
TIER_RANK = {"T1": 3, "T2": 2, "T3": 1, "NONE": 0}

@dataclass(frozen=True)
class ZoneAuthority:
    has_htf_anchor: bool
    tier: str
    stacking_level: int
    confidence_weight: float   # invariante: 0.0 <= w <= 1.0 (ValueError si no)
    level: str                 # "Alta" | "Media" | "Baja"

def evaluate_zone_authority(
    ltf_zone: HtfPdZone | None,
    htf_zones: list[HtfPdZone],
) -> ZoneAuthority: ...
```

Entradas de datos: frames OHLC por TF (`time` como columna o índice), solo velas
cerradas. **Cero indicadores**: sin EMA/RSI/ATR/MACD.

---

## 4. Lógica (geometría pura)

### 4.1 Índice de eventos padre (`build_htf_structure_index`)
Para cada TF de `parents` con `len(frame) >= 3`:
1. `times` se toma de la columna `time` (`to_datetime(..., utc=True)`) o del índice.
2. `struct = detect_market_structure(frame)` — se reusa la **única fuente de
   estructura** del motor (`engine.bos`). Excepción → se salta ese TF.
3. Por cada vela con `bos_dir != 0` se emite un `_ParentEvent(kind="BOS")`; con
   `choch_dir != 0`, uno `kind="CHOCH"`.
4. Orden estable por `time`; los eventos sin timestamp van al final y **no anclan**.

### 4.2 Ancla del POI (`make_htf_poi_fn` → `poi["anchored"]`)
Se indexan los eventos por dirección (`by_dir[1]`, `by_dir[-1]`). La closure:
```python
def htf_poi_fn(i, target) -> bool:
    tnum = _direction_to_num(target)      # BULLISH->1, BEARISH->-1, 0 si desconocido
    if tnum == 0: return False
    if not by_dir[tnum]: return True      # BONUS, no veto: sin eventos padre NO bloquea
    if i < 0 or i >= len(ltf_times): return False
    ltf_t = ltf_times.iloc[i]
    prior = [e for e in by_dir[tnum] if e.time is not None and e.time <= ltf_t]
    prior = prior[-window_n:] if window_n else prior
    return bool(prior)
```
Clave: comparación **por timestamp cross-TF** (`e.time <= ltf_t`) — un H4 no
comparte `bar_index` con un M15. `window_n=20` limita la memoria a los últimos
eventos padre. `poi_present(...)` es el wrapper de una sola llamada para anotar
metadata sin que el backtest tenga lógica propia de POI.

### 4.3 PD arrays HTF vigentes (`HtfPdIndex`)
`_detect_pd_arrays(frame)` aplica `detectors.fvg.detect_fvg` +
`detectors.ob.detect_order_blocks` y, por barra HTF, mantiene la **zona ACTIVA
vigente por dirección** (los flags `fvg_*`/`ob_*` solo valen en la barra de
creación):
- Se guarda la zona bull/bear más reciente de FVG y de OB (el OB tiene prioridad
  sobre el FVG al publicar `act_*`).
- Invalidación: `fvg_fill_status` fuera de `{"bullish_unfilled","just_created"}`
  (resp. bearish) limpia el FVG; `ob_status == "invalidated"` limpia ambos OB.
- Salida por barra: `act_{bull,bear}_{on,type,tier,high,low}`.

`build_ltf_map(ltf_df)` resuelve el mapa LTF→HTF **una sola vez por TF**, O(n) no
O(n²), con `pd.merge_asof(..., on="time", direction="backward")`: para cada vela
LTF entrega la **última barra HTF ya cerrada** (`htf_close <= ltf_time`).
`zones_at(ltf_i, htf_tf, ltf_map)` es lookup O(1) y construye los `HtfPdZone` de
la fila (`_row_zones`).

Tiers (libro 21 §2): `T1 = BPR` (resuelto en `zone_authority`),
`T2 = FVG / OB / PROPULSION`, `T3 = REJECTION_BLOCK`. Orden: T1 > T2 > T3.

### 4.4 Autoridad de zona (`evaluate_zone_authority` → `poi["authority"]`)
1. `ltf_zone is None` (el motor no trazó zona) → sin ancla, `weight=0.0`,
   `level="Baja"`. **C no inventa zonas.**
2. `anchors = [z for z in htf_zones if z.direction == ltf_zone.direction]`.
   Vacío → sin ancla, `weight=0.0`, `"Baja"`.
3. Con anclas:
   - `best_tier` = mejor tier entre los anclas (`_higher_tier` sobre `TIER_RANK`).
   - `stacking = len({z.tf for z in anchors})` — capas TF distintas que respaldan.
   - Peso monótono y determinista:
     ```
     w = 0.5                                  # ancla HTF presente
     w += {"T1":0.3, "T2":0.15, "T3":0.05}[best_tier]
     w += {1:0.0, 2:0.1}.get(stacking, 0.2 if stacking>=3 else 0.0)
     w  = min(1.0, w)                         # nunca negativo, nunca >1
     ```
   - `level = "Alta" if w >= 0.8 else ("Media" if w >= 0.5 else "Baja")`.
4. `__post_init__` defiende el invariante `0.0 <= confidence_weight <= 1.0`
   (lanza `ValueError` si se viola).

### 4.5 Nunca gate duro
Ni `htf_poi_fn` ni `evaluate_zone_authority` eliminan señales:
- sin eventos padre → `True` (no bloquea el histórico);
- sin ancla HTF → `weight=0.0` y `"Baja"`, pero la zona **sigue existiendo**.
El consumidor (observador / umbral / scoring) decide si pondera o filtra.

### 4.6 Volumen
No se usa volumen en estos tres módulos. Geometría OHLC + estructura.

---

## 5. Salidas

Campos que el motor publica sobre el POI:

| campo | origen | tipo | uso |
|---|---|---|---|
| `poi["anchored"]` | `poi_present` / `htf_poi_fn(i, target)` | bool | **bonus**, nunca veto |
| `poi["authority"]` | `evaluate_zone_authority(...)` | `ZoneAuthority` | **peso** 0..1 |

```python
ZoneAuthority(
  has_htf_anchor=bool,
  tier="T1"|"T2"|"T3"|"NONE",
  stacking_level=int,          # nº de TF distintos que respaldan
  confidence_weight=float,     # 0..1 (redondeado a 4 decimales)
  level="Alta"|"Media"|"Baja",
)
```
Auxiliares: `build_htf_structure_index -> list[_ParentEvent]`,
`HtfPdIndex.zones_at -> list[HtfPdZone]`, `HtfPdIndex.timeframes -> list[str]`.

---

## 6. Integración

- **engine/**: aquí vive la **DECISIÓN** de qué es un POI anclado.
  `engine/poi_anchor.py` importa solo `engine.bos` y `engine.bias.narrative`;
  `engine/htf_pd_index.py` importa `detectors.fvg` / `detectors.ob`;
  `engine/zone_authority.py` importa solo `engine.htf_pd_index`.
- **ict_backtest/**: **CONSUME**. Se le enchufa la closure:
  ```python
  from engine.poi_anchor import make_htf_poi_fn
  htf_poi_fn = make_htf_poi_fn(ltf_frame, {"D1": d1, "H4": h4, "H1": h1})
  # -> ict_backtest.sequence.run_sequence(..., htf_poi_fn=htf_poi_fn)
  ```
  El backtest **no** tiene lógica propia de POI ni de autoridad.
- **Rescate 2026-08-07**: `htf_pd_index.py` y `zone_authority.py` fueron migrados
  desde `ict_backtest/` (capa desechable) al motor para cumplir la Ley Fundamental;
  los originales se borraron. **CERO imports de `ict_backtest/`**.

---

## 7. Anti-look-ahead

1. **Cross-TF por timestamp, nunca por índice**: `e.time <= ltf_t`; un H4 no
   comparte `bar_index` con un M15.
2. `merge_asof(..., direction="backward")` sobre `time`: cada vela LTF ve solo la
   última barra HTF **ya cerrada** (`htf_close <= ltf_time`). Un HTF que cierra
   después de la vela LTF nunca se lee.
3. Los eventos sin `time` no anclan (se ordenan al final y quedan fuera del filtro
   `e.time <= ltf_t`).
4. La estructura padre viene de `detect_market_structure`, que es causal
   (swings con exposición diferida, sin ventana centrada).
5. Las zonas HTF activas se propagan hacia adelante (estado vivo por barra), nunca
   hacia atrás.
6. `window_n` recorta hacia el pasado (`prior[-window_n:]`), nunca hacia el futuro.

---

## 8. Verificación (pytest existente)

- `tests/test_poi_anchor.py`
- `tests/test_engine_poi_anchor.py`
- `tests/test_poi_engine_book21.py`
- `tests/test_engine_htf_pd_index.py`
- `tests/test_engine_zone_authority.py`
- `tests/test_plan_driver_poi.py`

Suite `engine/` en verde (116 passed). Criterios adicionales:
- `grep -E "EMA|RSI|ATR|MACD" engine/poi_anchor.py engine/zone_authority.py engine/htf_pd_index.py` vacío.
- `grep -R "ict_backtest" engine/` vacío en estos tres módulos.
- Invariante medido: activar `authority` **no altera el conteo de señales**
  (efecto cero por diseño).

---

## 9. Estado

✅ **HECHO** — los tres módulos están implementados, rescatados al motor y en
verde. Regla vigente e inviolable: **`anchored` y `authority` son bonus/peso,
NUNCA gate duro** (PF 0.900 gate vs 1.511 bonus).
