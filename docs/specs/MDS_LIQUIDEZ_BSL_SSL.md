# MDS_LIQUIDEZ_BSL_SSL.md — Liquidez BSL / SSL anclada al sesgo HTF

- **Clasificación**: OBLIGATORIO · Fase A (Deuda 4 de la lectura HTF) · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja el código REAL de `engine/liquidity_levels.py`
  (`detect_liquidity_htf`, `nearest_liquidity_target`, `_bias_direction`).
- **Ley**: `engine/` única fuente; `ict_backtest/` consume. `engine/` **NUNCA**
  importa `ict_backtest/` ni usa ATR/EMA.

---

## 1. Propósito

Marcar, por vela y sin look-ahead, dónde está la **liquidez** que el mercado va a
buscar, y cuál de los dos lados es el **objetivo del día** según el sesgo HTF:

- **BSL** (Buy Side Liquidity) = máximos previos **por encima** del precio actual
  (stops de vendedores).
- **SSL** (Sell Side Liquidity) = mínimos previos **por debajo** del precio actual
  (stops de compradores).

Regla de objetivo:
| sesgo HTF | `target_liquidity` |
|---|---|
| `BULLISH` | `BSL` (barrer máximos arriba) |
| `BEARISH` | `SSL` (barrer mínimos abajo) |
| `NEUTRAL` | `NONE` |

---

## 2. Por qué importa

1. **El precio se mueve entre pools de liquidez**, no hacia niveles arbitrarios.
   Sin BSL/SSL el motor no tiene destino geométrico para el TP.
2. **El sweep precede a la reversión**: el barrido de un extremo (mecha que lo
   supera con cierre de vuelta dentro) es la firma del stop hunt que antecede al
   giro. Sin BSL/SSL identificados no hay sweep que medir.
3. **Objetivo dirigido por el sesgo**: un mismo gráfico tiene BSL y SSL a la vez;
   el sesgo HTF decide cuál es el objetivo real del día — el motor no opera
   ambos lados a ciegas.

---

## 3. Entradas (firmas reales)

```python
# engine/liquidity_levels.py
BULLISH = "BULLISH"; BEARISH = "BEARISH"; NEUTRAL = "NEUTRAL"

def _bias_direction(htf_bias) -> str: ...   # acepta HtfBias o str; normaliza a upper()

def detect_liquidity_htf(
    frame: pd.DataFrame,
    htf_bias,                 # HtfBias | str | None
    left: int = 3,
    margin_ticks: float = 0.0,
) -> pd.DataFrame: ...

def nearest_liquidity_target(
    frame: pd.DataFrame,
    htf_bias,
    left: int = 3,
) -> dict: ...

__all__ = ["detect_liquidity_htf", "nearest_liquidity_target"]
```

Columnas requeridas: `high`, `low`, `close` — **solo velas cerradas**. Si falta
alguna se lanza `KeyError(f"falta la columna requerida '{col}'")`. Si `left < 1`
se lanza `ValueError("left debe ser >= 1")`.

**Cero indicadores**: sin EMA/RSI/ATR/MACD. Solo geometría `high`/`low`/`close`.

---

## 4. Lógica (geometría pura)

### 4.1 Extremos previos (sin look-ahead)
```python
prev_high = high.astype("float64").rolling(left).max().shift(1)
prev_low  = low.astype("float64").rolling(left).min().shift(1)
```
El `shift(1)` es la garantía dura: en la vela `i` solo se ven los `left` extremos
de velas **previas ya cerradas**.

### 4.2 Niveles BSL / SSL relevantes
```python
margin = float(margin_ticks)
bsl = prev_high.where(prev_high > close + margin, np.nan)
ssl = prev_low.where(prev_low  < close - margin, np.nan)
```
Un máximo previo solo es BSL si sigue **por encima** del cierre actual (aún no ha
sido tomado); simétrico para SSL. `margin_ticks` permite exigir una separación
mínima en precio (no normalizada por volatilidad — no hay ATR en el motor).
Si el nivel ya no cumple la condición → `NaN`: el pool fue barrido o quedó del
lado equivocado del precio. Ese paso de valor a `NaN` es, geométricamente, la
huella del **sweep de liquidez**.

### 4.3 Objetivo por sesgo
```python
direction = _bias_direction(htf_bias)              # BULLISH | BEARISH | NEUTRAL
target = {BULLISH: "BSL", BEARISH: "SSL"}.get(direction, "NONE")
```
`_bias_direction` acepta un `HtfBias` (lee `.direction`) o un `str`; normaliza a
mayúsculas y devuelve `NEUTRAL` para cualquier valor no reconocido o `None`.

### 4.4 Objetivo más cercano (`nearest_liquidity_target`)
1. `frame` vacío / `None` → `{"side": "NONE", "level": None, "distance": nan}`.
2. Se llama `detect_liquidity_htf(frame, htf_bias, left=left)` y se lee
   `target_liquidity` de la **última** vela; si es `NONE` → dict vacío.
3. Se toma la columna `bsl_level` o `ssl_level`, se hace `dropna()`. Si no queda
   nada → `{"side": side, "level": None, "distance": nan}`.
4. Elección del nivel vigente frente al último `close`:
   - `BSL`: de los valores `> close`, el **mínimo** (el más cercano por encima);
     si no hay ninguno, el `max()` de todos los vistos.
   - `SSL`: de los valores `< close`, el **máximo** (el más cercano por debajo);
     si no hay ninguno, el `min()` de todos los vistos.
5. `distance = abs(level - close)` — distancia en **precio**, sin normalizar por
   volatilidad.

### 4.5 Volumen
Este módulo no consume volumen. El volumen (único dato no-OHLC permitido) se usa
como confirmación **opcional y nunca gate** en los módulos que evalúan el sweep
(`engine/silver_bullet.py`, `engine/turtle_soup.py`, diseño B3
`engine/liquidity_zones.py`).

---

## 5. Salidas

`detect_liquidity_htf(...) -> pd.DataFrame` (copia del frame + columnas):

| columna | tipo | significado |
|---|---|---|
| `bsl_level` | float / NaN | máximo previo vigente por encima del close |
| `ssl_level` | float / NaN | mínimo previo vigente por debajo del close |
| `target_liquidity` | str | `BSL` / `SSL` / `NONE` (según sesgo) |

Con `frame` vacío devuelve el frame con esas tres columnas vacías y dtypes
correctos (`float64`, `float64`, `object`) — sin excepción.

`nearest_liquidity_target(...) -> dict`:
```python
{"side": "BSL" | "SSL" | "NONE", "level": float | None, "distance": float}  # nan si no hay
```

---

## 6. Integración

- **engine/**: `engine/liquidity_levels.py` es la única fuente de niveles BSL/SSL.
  Base del diseño B3 (`MDS_B3_LIQUIDEZ_INT_EXT.md`), donde `bsl_level` / `ssl_level`
  alimentan la clasificación **ERL** frente al dealing range.
- **ict_backtest/**: **CONSUME** los niveles para fijar TP (liquidez opuesta) y
  para anotar sweeps. No calcula liquidez por su cuenta.
- **Ley Fundamental**: cero imports de `ict_backtest/`.

---

## 7. Anti-look-ahead

1. `rolling(left).max().shift(1)` / `.min().shift(1)`: en la vela `i` solo se ven
   extremos de velas previas cerradas.
2. Prohibido `df.max()` / `df.min()` globales sobre el histórico para definir
   niveles por vela (los `max()`/`min()` de `nearest_liquidity_target` operan
   sobre la serie ya recortada hasta la vela actual).
3. `nearest_liquidity_target` lee `iloc[-1]`: la última vela cerrada disponible.
4. La vela en formación se excluye aguas arriba.
5. `margin_ticks` es una constante de precio, no depende de datos futuros.

---

## 8. Verificación (pytest existente)

- `tests/test_engine_liquidity_levels.py`

Complementarios (consumo de liquidez / sweep):
`tests/test_engine_plan_pd.py`, tests de `silver_bullet` / `turtle_soup`.

Suite `engine/` en verde (116 passed). Criterio adicional:
`grep -E "EMA|RSI|ATR|MACD" engine/liquidity_levels.py` vacío.

---

## 9. Estado

✅ **HECHO** — implementado, en verde y consumido. Es la base sobre la que se
apoya la clasificación IRL/ERL de la fase B3.
