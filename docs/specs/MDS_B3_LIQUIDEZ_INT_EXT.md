# MDS_B3_LIQUIDEZ_INT_EXT.md — Liquidez Interna (IRL) / Externa (ERL) — Fase B3

- **Clasificación**: OBLIGATORIO · Fase B3 · **Estado: ✅ diseño listo (implementable en `engine/`)**
- **SDD-first**: diseño a implementar en `engine/liquidity_zones.py` (módulo nuevo,
  permanente), apoyado en `engine/liquidity_levels.py` (BSL/SSL ya existentes),
  `engine/dealing_range.py`, `engine/fvg_poi.py` y `engine/bos/structure.py`.
- **Fuente teórica**: ICT (innercircletrader.net) — Internal Range Liquidity /
  External Range Liquidity dentro del dealing range.

---

## 1. Propósito

Clasificar la liquidez del mercado en dos clases geométricas, relativas al
**dealing range** (definido entre un swing high y un swing low confirmados):

- **ERL (External Range Liquidity)**: liquidez FUERA del rango. BSL por encima del
  swing high del rango; SSL por debajo del swing low del rango. Es el objetivo de
  barrido (stop hunt) que precede la reversión.
- **IRL (Internal Range Liquidity)**: liquidez DENTRO del rango. Fundamentalmente
  **FVG sin llenar** (y mechas internas) situados entre los extremos del rango. Es
  el destino del retorno tras barrer ERL.

Y detectar la **secuencia canónica ICT**: `ERL sweep → retorno a IRL`.

---

## 2. Por qué importa

1. **Filtro de falsas reversiones**: sin distinguir IRL de ERL, el motor confunde un
   pullback interno (ruido) con un barrido real del extremo. La clasificación
   geométrica elimina señales que nacen dentro del rango sin haber tomado ERL.
2. **Entrada precisa en IRL**: tras el barrido de ERL, el precio busca el FVG interno
   no llenado. Entrar en ese FVG (no en el extremo) da un punto de ejecución con
   invalidación estructural corta.
3. **Mejor RR**: stop detrás del extremo barrido (ERL), objetivo en la ERL opuesta.
   La distancia entrada→stop se comprime al entrar en IRL, mientras el target se
   mantiene en el extremo contrario: RR estructuralmente superior.

---

## 3. Entradas

| Entrada | Tipo | Descripción |
|---|---|---|
| `df` | `pd.DataFrame` | OHLC(V) **solo velas cerradas**, index temporal ascendente. |
| `dealing_range` | `dict` | Salida de `engine/dealing_range.py`: `range_high`, `range_low`, `range_high_ts`, `range_low_ts`, zona premium/discount, OTE 0.62–0.79. |
| `fvg_df` | `pd.DataFrame` | Salida de `engine/fvg_poi.py::detect_fvg`: `fvg_bullish`, `fvg_bearish`, `fvg_top`, `fvg_bottom`, `fvg_mid`, `fvg_fill_status`. |
| `htf_bias` | `str` | `"bullish"` / `"bearish"` / `"neutral"` (sesgo HTF). |
| `direction` | `str` | Dirección buscada en LTF: `"long"` / `"short"`. |
| `volume_confirm_fn` | `Callable \| None` | **OPCIONAL**. Firma `fn(df, idx, window=20) -> float` (ratio volumen/media). Mismo patrón que `engine/silver_bullet.py` y `engine/turtle_soup.py`. **Nunca gate.** |
| `cfg` | `LiquidityZonesConfig` | `swing_lookback`, `max_bars_erl_to_irl`, `require_unfilled_fvg=True`, `vol_window=20`. |

Sin parámetros de indicadores. No se aceptan EMA/RSI/ATR/MACD ni derivados.

---

## 4. Lógica (geometría pura)

### 4.1 Construcción del dealing range
Tomar `range_high` / `range_low` de `dealing_range.py` (rolling max/min sobre
`lookback`), validados contra swings confirmados de
`engine/bos/structure.py::detect_market_structure` (HL/LH). El rango es el
contenedor de referencia; todo se clasifica respecto a él.

### 4.2 Clasificación ERL
- `ERL_BSL = range_high` (más los máximos previos no barridos por encima, vía
  `liquidity_levels.detect_liquidity_htf(df).bsl_level`).
- `ERL_SSL = range_low` (idem con `ssl_level`).
- **Sweep de ERL** en la vela `i` (cerrada):
  - alcista para short: `high[i] > ERL_BSL` **y** `close[i] <= ERL_BSL`
    (mecha por encima, cierre dentro) → `erl_sweep = {"side": "BSL", ...}`.
  - bajista para long: `low[i] < ERL_SSL` **y** `close[i] >= ERL_SSL`
    → `erl_sweep = {"side": "SSL", ...}`.
  - Se registra `sweep_ts = df.index[i]`, `sweep_price`, `penetration`
    (`high[i]-ERL_BSL` o `ERL_SSL-low[i]`, en precio, no normalizado por ATR).

### 4.3 Clasificación IRL
Recorrer `fvg_df` y quedarse con los FVG que cumplan:
1. `fvg_top <= range_high` y `fvg_bottom >= range_low` (estrictamente **internos**).
2. `fvg_fill_status` indica **no llenado** (o parcialmente llenado, si
   `require_unfilled_fvg=False`).
3. Formados en velas con timestamp `<= sweep_ts` (ver §7).
4. Polaridad coherente: para `direction="long"` se buscan `fvg_bullish`; para
   `"short"`, `fvg_bearish`.

De los candidatos se elige el **más cercano al precio actual en la dirección del
retorno** (menor distancia de `close[sweep_idx]` a `fvg_mid`), desempatando por el
FVG más reciente. Ese es `irl_target` (nivel = `fvg_mid`, zona = `[fvg_bottom, fvg_top]`).
Mechas internas no barridas (máximos/mínimos menores dentro del rango) se
devuelven como `irl_pool` secundario, sin ser target por defecto.

### 4.4 Secuencia ERL → IRL
`seq_erl_then_irl = True` si y solo si:
1. Hubo `erl_sweep` en una vela cerrada.
2. Existe al menos un `irl_target` válido formado en/antes del sweep.
3. El precio se desplaza hacia el IRL dentro de `max_bars_erl_to_irl` velas
   (opcionalmente ya lo tocó → `irl_touched=True`, con `irl_touch_ts`).
4. El movimiento post-sweep es coherente con `htf_bias` (si `htf_bias` no es
   `"neutral"`); si contradice, se marca `bias_aligned=False` pero **no** se anula
   la detección — la decisión es del consumidor.

Si hay `irl_target` pero **no** hubo `erl_sweep` previo, `seq_erl_then_irl=False`:
es un pullback interno (ruido), señal de menor calidad.

### 4.5 Volumen (opcional, nunca gate)
Si `volume_confirm_fn` no es `None`:
- `erl_sweep["vol_ratio"] = volume_confirm_fn(df, sweep_idx, cfg.vol_window)`
- `irl_target["vol_ratio"] = volume_confirm_fn(df, irl_touch_idx, cfg.vol_window)`
  (solo si hubo toque).
Se anota `vol_confirmed = ratio >= 1.0` como **etiqueta informativa**. Ninguna rama
de control usa `vol_ratio` para descartar la detección. Si `volume_confirm_fn` es
`None` o falta la columna `volume`, los campos van a `None` y el resultado es
idéntico en todo lo demás.

---

## 5. Salidas

```python
{
  "dealing_range": {"high": float, "low": float, "high_ts": ts, "low_ts": ts},
  "erl": {"bsl": float, "ssl": float},
  "erl_sweep": None | {
      "side": "BSL" | "SSL",
      "idx": int, "ts": Timestamp,
      "sweep_price": float, "penetration": float,
      "vol_ratio": float | None, "vol_confirmed": bool | None,
  },
  "irl_target": None | {
      "fvg_idx": int, "top": float, "bottom": float, "mid": float,
      "kind": "bullish" | "bearish", "fill_status": str,
      "touched": bool, "touch_ts": Timestamp | None,
      "vol_ratio": float | None, "vol_confirmed": bool | None,
  },
  "irl_fvg_idx": int | None,
  "irl_pool": [ {...niveles internos secundarios...} ],
  "seq_erl_then_irl": bool,
  "bias_aligned": bool,
  "direction": "long" | "short",
}
```

Contrato: la función **nunca lanza** por datos insuficientes; devuelve la estructura
con `None`/`False` y `seq_erl_then_irl=False`.

API pública propuesta:

```python
# engine/liquidity_zones.py
@dataclass
class LiquidityZonesConfig:
    swing_lookback: int = 20
    max_bars_erl_to_irl: int = 12
    require_unfilled_fvg: bool = True
    vol_window: int = 20

def classify_liquidity(df, dealing_range, fvg_df, htf_bias, direction,
                       volume_confirm_fn=None, cfg=LiquidityZonesConfig()) -> dict: ...
```

---

## 6. Integración

- **engine/**: módulo nuevo `engine/liquidity_zones.py`. Importa solo de
  `engine/liquidity_levels.py`, `engine/dealing_range.py`, `engine/fvg_poi.py`,
  `engine/bos/structure.py` y stdlib/pandas.
- **ict_backtest/**: **CONSUME** `classify_liquidity(...)` por vela cerrada para
  filtrar entradas (`seq_erl_then_irl`) y fijar TP en la ERL opuesta.
- **Ley Fundamental**: `engine/` **NUNCA** importa `ict_backtest/`.
  `ict_backtest/` nunca reexporta este módulo de vuelta a `engine/`.
- Consumidores previstos: `engine/silver_bullet.py`, `engine/turtle_soup.py`
  (ambos ya con el patrón `volume_confirm`), y el motor de sesgo HTF.

---

## 7. Anti-look-ahead

1. `df` debe contener **solo velas cerradas**; la vela en formación se excluye
   aguas arriba.
2. Un FVG de 3 velas solo existe a partir del cierre de la vela `i` (gap `i-2`↔`i`);
   nunca se usa antes.
3. Solo son candidatos a IRL los FVG con `ts <= sweep_ts`.
4. `irl_touched` se evalúa con velas **posteriores** al sweep pero **anteriores o
   iguales** a la vela de evaluación actual — nunca con el futuro del dataset.
5. `dealing_range` se recalcula con ventana rolling terminada en la vela actual.
6. Prohibido `df.max()` / `df.min()` globales; toda extremidad es rolling o hasta `i`.

---

## 8. Verificación (pytest, datos sintéticos)

`tests/test_liquidity_zones.py`:

1. `test_erl_sweep_bsl_detected`: serie sintética con swing high claro, mecha que lo
   supera y cierre por debajo → `erl_sweep["side"] == "BSL"`.
2. `test_no_sweep_when_close_beyond`: cierre por encima del BSL (breakout real) →
   `erl_sweep is None`.
3. `test_irl_selects_nearest_unfilled_fvg`: dos FVG internos, uno llenado → se elige
   el no llenado y más cercano; `irl_fvg_idx` correcto.
4. `test_irl_ignores_fvg_outside_range`: FVG fuera del dealing range → descartado.
5. `test_sequence_true_erl_then_irl`: sweep + retorno al FVG dentro de
   `max_bars_erl_to_irl` → `seq_erl_then_irl is True`, `touched is True`.
6. `test_sequence_false_internal_only`: pullback a FVG sin sweep previo → `False`.
7. `test_volume_optional_none`: sin `volume_confirm_fn` → mismos flags booleanos que
   con él; `vol_ratio is None`.
8. `test_volume_never_gates`: `volume_confirm_fn` que devuelve `0.1` siempre →
   `seq_erl_then_irl` **sigue siendo True**, solo `vol_confirmed is False`.
9. `test_no_lookahead`: ejecutar sobre `df[:k]` para k creciente; los resultados
   pasados no cambian al añadir velas futuras.
10. `test_insufficient_data`: df de 3 velas → dict con `None`s, sin excepción.

Regla de aceptación: 10/10 verdes y `grep -E "EMA|RSI|ATR|MACD" engine/liquidity_zones.py` vacío.

---

## 9. Notas de volumen

- El volumen es el **único** dato no-OHLC permitido.
- Uso exclusivo: **confirmación opcional** del sweep de ERL y del retorno a IRL.
- Forma: `ratio = vol[idx] / mean(vol[idx-window:idx])` — dato crudo, no indicador
  (sin suavizados, sin bandas, sin normalizaciones exóticas).
- **Nunca gate**: prohibido `if vol_ratio < X: return None`. El ratio se adjunta al
  output; el consumidor decide si lo pondera.
- Si el feed no trae volumen (o trae ceros), el módulo degrada a `None` sin alterar
  la geometría.

---

## 10. Estado y siguiente paso

- **Estado**: ✅ diseño listo. Implementable tal cual en `engine/liquidity_zones.py`.
- Siguiente: implementación + `tests/test_liquidity_zones.py`, luego wiring de
  consumo en `ict_backtest/` (nunca al revés).
