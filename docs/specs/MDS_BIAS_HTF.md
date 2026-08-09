# MDS_BIAS_HTF.md — Sesgo HTF canónico D1 / H4 / H1 (Narrativa, Capa 1)

- **Clasificación**: OBLIGATORIO · Fase A (raíz del motor) · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja el código REAL de `engine/bias/narrative.py`
  (`compute_htf_bias`, `compute_htf_bias_series`, `HtfBias`, `_bias_for_frame`,
  `_compose_htf_bias`).
- **Ley**: `engine/` es la única fuente de decisión; `ict_backtest/` consume.
  `engine/` **NUNCA** importa `ict_backtest/`.

---

## 1. Propósito

Definir el **sesgo del día** — lo primero que hace un trader humano tras cargar
las barras: mirar D1, H4 y H1 y decidir si el contexto es alcista, bajista o
rango. Es la CAPA 1 del motor: todo lo demás (dealing range, liquidez, POI,
ejecución) se lee a favor o en contra de este sesgo.

Contrato original del SPEC §1:
- ENT: velas cerradas D1, H4, H1.
- SAL: `bias ∈ {BULLISH, BEARISH, NEUTRAL}` por TF + alineación D1→H4→H1.
- DEP: ninguna (es la raíz).

---

## 2. Por qué importa

1. **Jerarquía**: sin sesgo raíz, la capa de ejecución opera en ambos sentidos y
   el edge se diluye. El sesgo es el filtro más barato y más alto del motor.
2. **Verdad lenta**: el sesgo debe coincidir con la narrativa visible en el
   gráfico. Si el sesgo se ensucia con ruido de estructura LTF, el motor deja de
   parecerse al operador humano.
3. **Estructura vigente, no conteo de velas**: el sesgo NO se calcula con una
   ventana fija de N velas; es la dirección del último evento BOS/CHOCH **activo**
   (no invalidado). Un rango auténtico devuelve `NEUTRAL` de verdad, no por
   fallback.

---

## 3. Entradas (firmas reales)

```python
# engine/bias/narrative.py
BULLISH = "BULLISH"; BEARISH = "BEARISH"; NEUTRAL = "NEUTRAL"

@dataclass(frozen=True)
class HtfBias:
    d1: Bias
    h4: Bias
    h1: Bias
    @property
    def aligned(self) -> bool: ...
    @property
    def direction(self) -> Bias: ...

def compute_htf_bias(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    swing_lookback: int = 2,
) -> HtfBias: ...

def compute_htf_bias_series(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    m15: pd.DataFrame,
    swing_lookback: int = 2,
) -> pd.DataFrame: ...
```

Internos: `_swing_points(frame, lookback=2)`, `_label_swings(swing_high, swing_low)`,
`_bias_for_frame(frame, swing_lookback=5, tail=400)`, `_compose_htf_bias(d1, h4, h1)`.

Columnas requeridas: `high`, `low`, `close` (solo velas CERRADAS).
**Cero indicadores**: sin EMA/RSI/ATR/MACD. Volatilidad = rango `high-low`.

---

## 4. Lógica (geometría pura)

### 4.1 Swings sin look-ahead (`_swing_points`)
Ventana **NO centrada**: un extremo local (`low[i] < low[i-1] y low[i] < low[i-2]`,
o el simétrico para high) se registra crudo y luego se expone con
`shift(delay=2).ffill()`. El swing solo existe 2 velas después de formarse —
nunca en el instante en que ocurre.

### 4.2 Etiquetado HH/HL/LH/LL (`_label_swings`)
Comparación del nuevo swing contra el swing previo del mismo lado:
`HH` (high > prev_high), `LH` (high < prev_high), `HL` (low > prev_low),
`LL` (low < prev_low). Etiqueta propagada por `ffill`.

### 4.3 Sesgo por TF (`_bias_for_frame`) — estructura VIGENTE
1. Se ordena el frame, se recorta a `tail=400` velas (el sesgo del día mira la
   estructura reciente; `detect_market_structure` es O(n)).
2. Se llama `detect_market_structure(df, StructureConfig(swing_lookback=...))`
   — **única fuente de estructura del motor** (import lazy para romper el ciclo
   `narrative ↔ bos.structure`).
3. Se recorre el frame anotado y se guarda:
   - último índice/dirección con `bos_dir != 0` **y** `bos_status == "active"`.
   - último índice/dirección con `choch_dir != 0` **y** `choch_status == "active"`.
4. Resolución (criterio humano, CHOCH = memoria de giro):
   - Si hay **CHOCH activo** → manda: `BULLISH` si `dir > 0`, si no `BEARISH`.
     Un BOS posterior NO lo borra; solo lo mata el cruce de su nivel
     (`status = "invalidated"`, T9.4).
   - Si no, si hay **BOS activo** → su dirección.
   - Si no hay evento activo → `NEUTRAL` (rango auténtico).

### 4.4 REGLA EXP-012 — **NO aplica al sesgo** (camino B)
El sesgo usa **CHOCH CANÓNICO SIEMPRE**: `_bias_for_frame` llama a
`detect_market_structure` con `StructureConfig(...)` por defecto, es decir con
`exp012_choch=False`. El GATE DURO EXP-012 vive **solo** en
`detect_market_structure` (estructura LTF / entrada).

Motivo medido (bitácora 2026-08-08, `results/motor_veltick_EURUSD_M15.json`):
censurar CHOCH también en el sesgo desalineaba sesgo↔estructura
(**ALIGNED 42% → 1.5%**). El ruido de CHOCH daña la EJECUCIÓN, no el contexto
direccional.

### 4.5 Composición y alineación
```python
HtfBias.aligned  # True si >=2 de {d1,h4,h1} son no-NEUTRAL y todos coinciden
                 # non_neutral = [v for v in vals if v != NEUTRAL]
                 # len(non_neutral) >= 2 and len(set(non_neutral)) == 1
```
`HtfBias.direction` = `_compose_htf_bias(d1, h4, h1)`:
1. `D1` y `H4` direccionales y **coincidentes** → ese sentido (H1 no veta).
2. `D1` o `H4` en `NEUTRAL` → decide `H1` si es direccional, si no `NEUTRAL`.
3. `D1 != H4` ambos direccionales → H1 desempata por **mayoría 2/3**; sin
   mayoría → `NEUTRAL`.

### 4.6 Serie temporal (`compute_htf_bias_series`)
Se recalcula el sesgo en **cada cierre de H4** usando solo los cortes
acumulados `d1.loc[index <= ts]`, `h4_cum`, `h1_cum` (se exige `len >= 2` en los
tres). El resultado (`direction`, `aligned`) se reindexa sobre la línea de tiempo
`H1 ∪ M15` y se propaga con `ffill`, porque en vivo el operador reutiliza el
último bias confirmado hasta el próximo cierre de H4. Relleno inicial:
`direction=NEUTRAL`, `aligned=False`.

### 4.7 Volumen
El sesgo NO usa volumen. El volumen (único dato no-OHLC permitido en el motor)
se emplea aguas abajo como confirmación opcional, nunca como gate del sesgo.

---

## 5. Salidas

`compute_htf_bias(...) -> HtfBias`:
```python
HtfBias(d1="BULLISH"|"BEARISH"|"NEUTRAL",
        h4=..., h1=...)
# .aligned   -> bool
# .direction -> "BULLISH" | "BEARISH" | "NEUTRAL"
```

`compute_htf_bias_series(...) -> pd.DataFrame`:
| índice | columna | tipo |
|---|---|---|
| `timestamp` (H1 ∪ M15) | `direction` | str |
| | `aligned` | bool |

Si no hay filas computables devuelve un DataFrame vacío con esas columnas
(nunca lanza).

---

## 6. Integración

- **engine/**: `engine/bias/narrative.py` es la **única fuente** del sesgo.
  Consumidores internos: `engine/dealing_range.py` (`dealing_range_htf`),
  `engine/liquidity_levels.py` (`detect_liquidity_htf` acepta `HtfBias` o `str`),
  `engine/plan.py` (stack top-down), `engine/poi_anchor.py`.
- **ict_backtest/**: **CONSUME** el sesgo ya calculado (p. ej. vía
  `canonical.est_htf_ctx_fn`). No reimplementa sesgo ni lo devuelve al motor.
- **Ley Fundamental**: cero imports de `ict_backtest/` en este módulo.

---

## 7. Anti-look-ahead

1. Los DataFrames de entrada contienen **solo velas cerradas**.
2. `_swing_points` usa ventana NO centrada + `shift(2).ffill()`: exposición
   diferida del swing.
3. `_bias_for_frame` recorta con `tail(...)` (cola pasada), nunca con futuro.
4. `compute_htf_bias_series` corta cada TF con `index <= ts` antes de calcular:
   en el cierre de H4 solo se ven barras D1/H1 ya cerradas.
5. La propagación a H1/M15 es `ffill` (hacia adelante); nunca `bfill`.
6. Prohibido `df.max()` / `df.min()` global sobre todo el histórico.

---

## 8. Verificación (pytest existente)

- `tests/test_engine_bias.py`
- `tests/test_engine_htf_narrative.py`
- `tests/test_sesgo_cable_bias.py`
- `tests/test_r10c_market_narrative.py`

Suite `engine/` en verde (116 passed). Criterio de aceptación adicional:
`grep -E "EMA|RSI|ATR|MACD" engine/bias/narrative.py` vacío.

---

## 9. Estado

✅ **HECHO** — implementado, en verde y consumido por el resto del motor.
Regla EXP-012 (camino B) documentada y vigente: el gate duro **no** toca el sesgo.
