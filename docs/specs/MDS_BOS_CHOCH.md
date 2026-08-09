# MDS_BOS_CHOCH.md — Estructura de mercado: BOS / CHOCH / MSS

- **Clasificación**: OBLIGATORIO · Fase A (ontología de estructura) · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja el código REAL de `engine/bos/structure.py`
  (`detect_market_structure`, `StructureConfig`, `MarketStructure`,
  `_consecutive_break`, `_track_structure`, `_exp012_choch_marks`,
  `_compute_bos_quality`).
- **Ley**: `engine/` única fuente de estructura; `ict_backtest/` consume.
  `engine/` **NUNCA** importa `ict_backtest/`.

---

## 1. Propósito

Detectar y mantener con memoria de estado los tres eventos de estructura del
canon ICT sobre un timeframe:

- **BOS** (Break of Structure): ruptura de un swing **a favor** de la tendencia,
  validada por **cierre de cuerpo** (`close`), nunca por mecha.
- **CHOCH** (Change of Character): ruptura del swing que produjo el **último
  BOS**, en dirección **OPUESTA** a ese BOS. Aviso de giro; **no** es una copia
  de BOS.
- **MSS**: secuencia canónica `BOS↑ → CHOCH↓ → BOS↓` (CHOCH + confirmación).

Es la ontología de estructura **única** del motor: el sesgo HTF, el POI anclado
y la secuencia de ejecución leen de aquí.

---

## 2. Por qué importa

1. **Fuente única**: si cada capa detecta su propio BOS, el sesgo y la ejecución
   divergen. `detect_market_structure` es el único detector; `engine/bias/narrative.py`
   y `engine/poi_anchor.py` lo reusan en lugar de duplicar lógica.
2. **Anti-fakeout**: exigir `confirm_bars` cierres CONSECUTIVOS rompiendo el
   nivel filtra Turtle Soups y mechas.
3. **Estado event-driven**: un BOS/CHOCH vive hasta que el precio cruza de vuelta
   su nivel. No caduca por tiempo ni por volatilidad — no hay ATR en el motor.
4. **Ruido de CHOCH**: en M15 el CHOCH sin empuje previo produce ~824 eventos/año
   de puro ruido. EXP-012 lo elimina en la fuente para la capa de ejecución.

---

## 3. Entradas (firmas reales)

```python
# engine/bos/structure.py
@dataclass(frozen=True)
class StructureConfig:
    swing_lookback: int = 5
    followthrough_bars: int = 8
    confirm_bars: int = 2        # 1 = vela única; 2 = filtra fakeouts
    k: int = 5
    quality_threshold: float = 0.45
    exp012_choch: bool = False   # GATE DURO (camino B), OFF por defecto

@dataclass(frozen=True)
class MarketStructure:
    frame: pd.DataFrame
    # .last_bos_dir -> int   .last_bos_level -> float
    # .last_choch_dir -> int .counts -> dict[str, int]

def detect_market_structure(
    frame: pd.DataFrame,
    config: StructureConfig | None = None,
) -> MarketStructure: ...
```

Columnas requeridas en `frame`: `open`, `high`, `low`, `close` — **solo velas
cerradas**. Primitivos de swing importados de `engine.bias.narrative`
(`_swing_points`, `_label_swings`): misma lógica en todo el motor.

Constantes de descarte:
```python
BOS_DISCARD_REASONS   = ("NO_HIT_IN_K", "INVALIDATED", "UNRESOLVED")
CHOCH_DISCARD_REASONS = ("NO_CONFIRMATION", "INVALIDATED", "UNRESOLVED")
```

**Cero indicadores**: sin EMA/RSI/ATR/MACD. El displacement se evalúa con
geometría pura (cuerpo/rango, mecha/rango) vía `detectors.displacement`.

---

## 4. Lógica (geometría pura)

### 4.1 Swings
`sh, sl = _swing_points(d, config.swing_lookback)` (ventana NO centrada +
exposición diferida) y `d["swing_label"] = _label_swings(sh, sl)` → HH/HL/LH/LL.

### 4.2 BOS
```python
bull_break = close > sh.shift(1)
bear_break = close < sl.shift(1)
bull_conf  = _consecutive_break(bull_break, confirm_bars)
bear_conf  = _consecutive_break(bear_break, confirm_bars)
bos_dir    = select([bull_conf, bear_conf], [1, -1], default=0)
bos_level  = sh.shift(1) si dir==1; sl.shift(1) si dir==-1; NaN si no
```
`_consecutive_break` cuenta una racha: marca True solo cuando hay
`confirm_bars` rupturas consecutivas.

### 4.3 Estado (`_track_structure`)
Recorrido secuencial con memoria:
- **T9.6 (superseded)**: si aparece un evento nuevo en la MISMA dirección con
  otro ya `active`, el anterior pasa a `status="superseded"` /
  `discard_reason="SUPERSEDED"`. El humano no acumula BOS: solo hay **uno vigente
  por dirección** (evita 21k BOS activos en M15).
- **Invalidación**: si `close` cruza de vuelta el nivel
  (`dir==1 and close < level`, o `dir==-1 and close > level`) → `status="invalidated"`
  en la vela del cruce **y también en la vela del evento original** (`last_idx`),
  con `discard_reason="INVALIDATED"`. Así el sesgo, que lee el estado en la vela
  del evento, no ve CHOCH vivos de por vida.
- Se exponen internamente `_last_bos_dir` / `_last_bos_level` (y sus gemelas de
  CHOCH), consumidas más abajo y **borradas** antes de devolver el frame.

### 4.4 CHOCH — evento de giro (flanco de una vela)
```python
up_flank  = (close_now > last_bos_level) & (close_prev <= level_prev)
dn_flank  = (close_now < last_bos_level) & (close_prev >= level_prev)
up_choch  = up_flank & (last_bos_dir == -1)
dn_choch  = dn_flank & (last_bos_dir ==  1)
choch_dir = select([up_choch, dn_choch], [1, -1], default=0)
```
Corrección verificada 2026-08-06: el CHOCH es un **flanco único**, no un estado
sostenido. Marcarlo en toda vela de continuación generaba CHOCH espurios
repetidos (30 en 400 velas H1). **No** se le aplica `_consecutive_break` (eso
mataría el flanco de 1 vela); su confirmación es el BOS subsiguiente en la nueva
dirección.

### 4.5 T9.4 — nivel de invalidación real del CHOCH (reclaim)
```python
d["choch_proj_level"] = d["_last_bos_level"]
d["choch_status"], _, choch_discard = _track_structure(
    d, config, is_choch=True, inval_level=d["choch_proj_level"])
d["choch_inval_level"] = d["choch_proj_level"]
```
El CHOCH muere cuando el precio **reclama** (cruza) el nivel del BOS contrario
que rompió — no el swing de su propia vela. Si no se pasa `inval_level`, cae al
swing de la vela. Un giro alcista muere si el precio cae y rompe el BOS bajista
previo.

Niveles T9.2 publicados (lo que el trader marca en pantalla):
`bos_proj_level = bos_inval_level = bos_level`; `choch_proj_level`;
`choch_inval_level`.

### 4.6 EXP-012 — GATE DURO (camino B)
Con `config.exp012_choch=True`, `_exp012_choch_marks(d)` recorre el frame ya
anotado y, por cada vela con `choch_dir != 0`, exige las cuatro condiciones:

| Cond. | Regla |
|---|---|
| (a) **MOMENTUM** | racha `hh_streak >= 2` (uptrend) para CHOCH bajista; `ll_streak >= 2` (downtrend) para CHOCH alcista. Sin empuje no hay "carácter" que cambiar. |
| (b) **AFTER_BOS real** | `int(last_bos_dir[i]) == -cd`: hubo BOS de mercado confirmado en la dirección de la tendencia opuesta al CHOCH (**T9.7**, se reusa `_last_bos_dir` del frame, no una suposición). |
| (c) **NIVEL** | `pivot_level` = último **HL** roto (CHOCH bajista) / último **LH** roto (CHOCH alcista) — **NO** el nivel del BOS (`choch_proj_level`). Son pivotes distintos; usar el BOS dispara CHOCH prematuro. |
| (d) **RECLAIM** | `choch_status == "invalidated"` descalifica (T9.4 vigente). |

Detalle de rachas: `HH` incrementa `hh_streak` y resetea `ll_streak`; `LL` al
revés; **`HL` NO resetea `hh_streak`** (la cadena HH/HL sostiene el impulso) y
fija `last_hl_price`; `LH` sí resetea `hh_streak` y fija `last_lh_price`.

**Gate duro — el CHOCH de ruido DEJA DE EXISTIR en la fuente**:
```python
mask_noise = exp012 == 0
d.loc[mask_noise & (d["choch_dir"] != 0), "choch_dir"] = 0
d.loc[mask_noise & (d["choch_status"] != "none"), "choch_status"] = "none"
```
Las columnas `choch_exp012`, `choch_pivot_level`, `choch_exp012_after_bos`
quedan como **auditoría** de lo censurado. Ningún consumidor necesita cambiar.

> El gate vive **SOLO** aquí (estructura LTF / entrada). El **sesgo HTF NO lo
> aplica**: `engine/bias/narrative.py` llama con `exp012_choch=False`
> (ver `MDS_BIAS_HTF.md` §4.4).

### 4.7 MSS
Tras el gate, se recorre el frame: se guarda el último `choch_dir != 0` y se
marca `mss_dir[i] = bos_dir[i]` cuando aparece un BOS en dirección **opuesta al
último CHOCH** (secuencia BOS → CHOCH → BOS). No depende del estado
activo/invalidado del CHOCH (es un evento puntual).

### 4.8 Tendencia y calidad
- `trend` (`_derive_trend`): `HH|HL → BULLISH`, `LH|LL → BEARISH`, resto `RANGING`.
- `bos_quality_score` (`_compute_bos_quality`), 4 componentes × 0.25, clip [0,1]:
  1. displacement previo en la misma dirección (0/1, `detectors.displacement`),
  2. cuerpo del break / rango de esa vela,
  3. distancia del `close` al nivel roto / rango medio (clip a 0.5),
  4. confirmación posterior (no retorno inmediato), delegada a
     `engine.labels.confirm_score`.
- `bos_real = score >= config.quality_threshold`.

### 4.9 B4 — separación decisión / etiqueta
Toda lógica que **mira el futuro** (`i+1:`) vive exclusivamente en
`engine/labels.py` (`label_bos_outcome`, `label_choch_outcome`, `confirm_score`).
`structure.py` conserva la decisión causal con `_consecutive_break`
(pasado/presente) y solo delega la **anotación** (`bos_discard_reason`,
`choch_discard_reason`, alias `label_*_reason`). `_assert_no_upstream_label_consumption`
es la guarda documental de que ninguna columna `label_*` alimenta una decisión.

---

## 5. Salidas

`MarketStructure.frame` (una fila por vela):

| columna | tipo | significado |
|---|---|---|
| `swing_high`, `swing_low`, `swing_label` | float/str | swings y HH/HL/LH/LL |
| `bos_dir` | int | 1 / -1 / 0 |
| `bos_level`, `bos_proj_level`, `bos_inval_level` | float | nivel roto |
| `bos_status` | str | `none` / `active` / `invalidated` / `superseded` |
| `bos_discard_reason` | str | `INVALIDATED` / `UNRESOLVED` / `NO_HIT_IN_K` / `SUPERSEDED` |
| `bos_quality_score` | float | 0–1 |
| `bos_real` | bool | `score >= quality_threshold` |
| `choch_dir` | int | 1 / -1 / 0 (0 si censurado por EXP-012) |
| `choch_status` | str | `none` / `active` / `invalidated` |
| `choch_proj_level`, `choch_inval_level` | float | nivel del BOS contrario roto |
| `choch_discard_reason` | str | `INVALIDATED` / `UNRESOLVED` / `NO_CONFIRMATION` |
| `choch_exp012`, `choch_pivot_level`, `choch_exp012_after_bos` | int8/float/int8 | solo si `exp012_choch=True` (auditoría) |
| `mss_dir` | int | 1 / -1 / 0 |
| `trend` | str | `BULLISH` / `BEARISH` / `RANGING` |

Propiedades: `last_bos_dir`, `last_bos_level`, `last_choch_dir`, `counts`.

---

## 6. Integración

- **engine/**: fuente única de estructura. Consumidores internos:
  `engine/bias/narrative.py` (import lazy, sin gate EXP-012),
  `engine/poi_anchor.py` (eventos BOS/CHOCH del TF padre), `engine/plan.py`.
- **ict_backtest/**: **CONSUME** el frame anotado (secuencia, métricas,
  observador). No detecta estructura por su cuenta.
- **Ley Fundamental**: cero imports de `ict_backtest/`. Dependencias externas
  permitidas: `detectors.displacement`, `engine.bias.narrative`, `engine.labels`.

---

## 7. Anti-look-ahead

1. Entrada solo con **velas cerradas**.
2. Swings con ventana NO centrada + `shift(lookback).ffill()`.
3. Ruptura contra `sh.shift(1)` / `sl.shift(1)`: nunca contra el swing de la
   propia vela.
4. `_consecutive_break` acumula hacia adelante en el tiempo (racha del pasado).
5. `_track_structure` es un recorrido causal `for i in range(1, n)`; el estado
   solo depende de `close[<=i]`.
6. Todo lo que mira `i+1:` está aislado en `engine/labels.py` (`USES_FUTURE`) y
   es **solo etiqueta**, nunca decisión.
7. `_exp012_choch_marks` recorre hacia adelante acumulando rachas y usa
   `_last_bos_dir` (pasado), sin mirar velas futuras.

---

## 8. Verificación (pytest existente)

- `tests/test_engine_bos.py`
- `tests/test_engine_bos_exp012.py` (gate duro camino B)
- `tests/test_market_structure.py`
- `tests/test_structure_run.py`, `tests/test_structure_medicion.py`
- `tests/test_r10_bos_gap_dynamic.py`, `tests/test_build_bos_table.py`

Suite `engine/` en verde (116 passed). Criterio adicional:
`grep -E "EMA|RSI|ATR|MACD" engine/bos/structure.py` vacío.

---

## 9. Estado

✅ **HECHO** — implementado y en verde. `exp012_choch` es flag experimental con
caducidad documentada en bitácora 2026-08-08 (commit 375efc6); por defecto `False`.
