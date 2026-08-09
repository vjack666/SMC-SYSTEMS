# MDS_DEALING_RANGE.md — Dealing Range / Premium-Discount / OTE

- **Clasificación**: OBLIGATORIO · Fase A (Deuda 1 de la lectura HTF) · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: refleja el código REAL de `engine/dealing_range.py`
  (`compute_dealing_range`, `dealing_range_htf`, `DealingRangeConfig`,
  `OTE_MIN_RETRACE`, `OTE_MAX_RETRACE`).
- **Ley**: `engine/` única fuente; `ict_backtest/` consume. `engine/` **NUNCA**
  importa `ict_backtest/` ni `detectors/` desde este módulo.

---

## 1. Propósito

Tras definir el sesgo (`engine/bias`), el trader mide **DÓNDE** está el precio
dentro del rango vigente para operar solo en la mitad correcta: **descuento** si
el sesgo es alcista, **premium** si es bajista. Este módulo salda esa "Deuda 1":
marca por vela el rango, su equilibrio (EQ, 50%) y las bandas OTE.

Contrato:
- ENT: velas cerradas (`high`/`low`/`close`) + `HtfBias`.
- SAL: zona premium/discount/OTE por vela + resumen del estado actual.
- CRIT: geometría pura (rolling max/min). **SIN indicadores** (no ATR, no medias).

---

## 2. Por qué importa

1. **No se compra caro ni se vende barato**: comprar en premium con sesgo alcista
   es pagar el máximo del rango. El EQ al 50% parte el rango en la mitad que
   acompaña y la que castiga.
2. **OTE como zona de ejecución**: el retroceso óptimo (0.62–0.79 del rango) es
   donde el precio ofrece la entrada con invalidación estructural más corta y
   mejor RR.
3. **Filtro barato y determinista**: una comparación de precio contra dos números
   geométricos, sin estado ni suavizado.

---

## 3. Entradas (firmas reales)

```python
# engine/dealing_range.py
BULLISH = "BULLISH"; BEARISH = "BEARISH"; NEUTRAL = "NEUTRAL"

# Retrocesos OTE clásicos (Fibonacci geométrico sobre el rango, NO indicador).
OTE_MIN_RETRACE = 0.62
OTE_MAX_RETRACE = 0.79
_EPS = 1e-9

@dataclass(frozen=True)
class DealingRangeConfig:
    lookback: int = 10
    ote_min_retrace: float = OTE_MIN_RETRACE
    ote_max_retrace: float = OTE_MAX_RETRACE

def compute_dealing_range(
    frame: pd.DataFrame,
    lookback: int = 10,
    config: DealingRangeConfig | None = None,
) -> pd.DataFrame: ...

def dealing_range_htf(
    frame: pd.DataFrame,
    htf_bias,          # HtfBias (se lee .direction) o cualquier objeto con .direction
    lookback: int = 10,
) -> dict: ...
```

Interno: `_is_favorable(zone: str, direction: str) -> bool`.

Columnas requeridas: `high`, `low`, `close` — **solo velas cerradas**.
**Cero indicadores**: sin EMA/RSI/ATR/MACD.

---

## 4. Lógica (geometría pura)

### 4.1 Rango vigente
```python
range_high = high.rolling(lookback, min_periods=1).max()
range_low  = low.rolling(lookback,  min_periods=1).min()
span       = range_high - range_low
```
Alias compatibles con `detectors/zones.py`: `zone_high = range_high`,
`zone_low = range_low`.

### 4.2 EQ — equilibrio al 50 %
```python
zone_mid = (range_high + range_low) / 2.0
is_discount = close <  zone_mid
is_premium  = close >= zone_mid
```
El EQ es la línea de corte premium/discount: exactamente el 50 % del rango.

### 4.3 Bandas OTE (0.62 – 0.79)
```python
ote_long_min  = range_low  + ote_min_retrace * span   # low + 0.62*span
ote_long_max  = range_low  + ote_max_retrace * span   # low + 0.79*span
ote_short_min = range_high - ote_max_retrace * span   # high - 0.79*span
ote_short_max = range_high - ote_min_retrace * span   # high - 0.62*span
```
Fibonacci **geométrico** sobre el rango: proporciones del propio span, sin
suavizados ni normalizaciones. No es un indicador.

### 4.4 Clasificación de zona
```python
in_ote_long  = (close >= ote_short_min) & (close <= ote_short_max)
in_ote_short = (close >= ote_long_min)  & (close <= ote_long_max)

premium_discount_zone = np.select(
    [in_ote_long & is_discount,      # -> "OTE_LONG"
     in_ote_short & is_premium,      # -> "OTE_SHORT"
     is_discount,                    # -> "DISCOUNT"
     is_premium],                    # -> "PREMIUM"
    ["OTE_LONG", "OTE_SHORT", "DISCOUNT", "PREMIUM"],
    default="OTE_NONE")
```
La etiqueta OTE solo se aplica si además el precio está en la mitad coherente:
`OTE_LONG` exige descuento, `OTE_SHORT` exige premium. En caso contrario cae a
`DISCOUNT` / `PREMIUM`.

### 4.5 Distancia normalizada al EQ
```python
premium_distance = np.where(
    is_premium,
     (close - zone_mid) / (zone_high - zone_mid + _EPS),   # + hacia premium
    -(zone_mid - close) / (zone_mid - zone_low + _EPS))    # - hacia descuento
```
Rango efectivo aproximado `[-1, +1]`; `_EPS` evita división por cero en rangos
degenerados.

### 4.6 Favorabilidad según sesgo (`_is_favorable`)
| `direction` | zonas favorables |
|---|---|
| `BULLISH` | `DISCOUNT`, `OTE_LONG` |
| `BEARISH` | `PREMIUM`, `OTE_SHORT` |
| `NEUTRAL` | ninguna (`False`) |

### 4.7 Volumen
No se usa volumen en este módulo. Geometría OHLC pura.

---

## 5. Salidas

`compute_dealing_range(...) -> pd.DataFrame` (copia del frame + columnas):

| columna | tipo |
|---|---|
| `range_high`, `range_low` | float |
| `zone_high`, `zone_low`, `zone_mid` | float (alias + EQ) |
| `ote_long_min`, `ote_long_max` | float |
| `ote_short_min`, `ote_short_max` | float |
| `premium_discount_zone` | str: `PREMIUM` / `DISCOUNT` / `OTE_LONG` / `OTE_SHORT` / `OTE_NONE` |
| `premium_distance` | float |

`dealing_range_htf(...) -> dict`:
```python
{
  "zone": "PREMIUM"|"DISCOUNT"|"OTE_LONG"|"OTE_SHORT"|"OTE_NONE",
  "distance": float,
  "bias": "BULLISH"|"BEARISH"|"NEUTRAL",
  "is_favorable": bool,
}
```
Contrato: con `frame` vacío o `None` devuelve
`{"zone": "OTE_NONE", "distance": 0.0, "bias": <bias o NEUTRAL>, "is_favorable": False}`
— **nunca lanza**.

---

## 6. Integración

- **engine/**: `engine/dealing_range.py` es la única fuente de premium/discount y
  OTE. Consumido por `engine/plan.py` (capas top-down), por el diseño de
  `engine/liquidity_zones.py` (B3, IRL/ERL relativos al rango) y por el observador.
- **ict_backtest/**: **CONSUME** las columnas/dict para filtrar entradas
  (`is_favorable`) y para situar la zona de ejecución. No recalcula el rango.
- **Ley Fundamental**: cero imports de `ict_backtest/` y de `detectors/`.

---

## 7. Anti-look-ahead

1. `rolling(lookback, min_periods=1)` sobre `high`/`low`: la ventana termina en
   la vela actual, nunca incluye futuro.
2. Prohibido `df.max()` / `df.min()` globales: toda extremidad es rolling.
3. `dealing_range_htf` evalúa `marked.iloc[-1]` — la última vela **cerrada**
   disponible.
4. La clasificación de zona usa solo el `close` de la propia vela contra niveles
   derivados de velas `<= i`.
5. La vela en formación se excluye aguas arriba (contrato de entrada).

---

## 8. Verificación (pytest existente)

- `tests/test_engine_dealing_range.py`
- `tests/test_dealing_range.py`
- `tests/test_dealing_range_motor.py`
- `tests/test_engine_plan_pd.py` (consumo top-down)

Suite `engine/` en verde (116 passed). Criterio adicional:
`grep -E "EMA|RSI|ATR|MACD" engine/dealing_range.py` vacío.

---

## 9. Estado

✅ **HECHO** — implementado, en verde y consumido. Constantes OTE fijas en el
módulo (`OTE_MIN_RETRACE=0.62`, `OTE_MAX_RETRACE=0.79`) y sobreescribibles por
`DealingRangeConfig` sin tocar código.
