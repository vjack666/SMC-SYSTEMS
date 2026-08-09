# MDS_VOLUMEN.md — Volumen como ÚNICO dato extra permitido

- **Clasificación**: OBLIGATORIO (regla transversal) · **Estado: ✅ IMPLEMENTADO**
- **Regla de Ruben (2026-08-08)**: "nada de indicadores, solo geometría de
  mercado; el ÚNICO indicador será el de volumen".

## Propósito
Establecer la ÚNICA excepción a la regla "cero indicadores": el VOLUMEN (tick
volume / volume por vela). No es un indicador técnico suavizado (como OBV, VWAP
móvil, volumen relativo con bands); es el dato crudo de cuántas operaciones
ocurrieron en esa vela.

## Por qué el volumen SÍ entra y los indicadores NO
- Los indicadores (EMA/RSI/ATR/MACD) son TRANSFORMACIONES de precio/volumen que
  añaden lag y "opinan" por el trader. La tesis ICT es geometría pura del precio.
- El volumen CRUDO es una DIMENSIÓN del mercado, no una opinión: confirma si un
  movimiento tuvo convicción (sweep con volumen alto = real) o fue débil (fakeout
  con volumen bajo). Se usa como FILTRO de confirmación, no como señal direccional.

## Cómo se usa (geometría + volumen, sin indicadores)
1. **Confirmación de sweep**: un barrido de liquidez (BSL/SSL) con volumen alto
   es más válido que uno con volumen bajo. `engine/liquidity_levels` puede anotar
   `sweep_volume_ratio = vol_sweep / vol_promedio`.
2. **Agotamiento en OTE/BE**: si el precio llega a la zona OTE o a BE con volumen
   decreciente, la reversión es más probable.
3. **Breakout de estructura**: BOS con volumen alto confirma; BOS con volumen bajo
   es sospechoso de fallo.

## Lo que NUNCA se hace
- NO VWAP suavizado como nivel dinámico (es indicador).
- NO RSI/OBV/Volumen-Relative-Bands como señal.
- El volumen solo aparece como `volume` (crudo) o `volume_ratio` (vol_vela /
  media móvil simple de N velas, que es estadística, no indicador suavizado).

## Integración
`engine/data_feed.load_tf` ya carga `volume` desde parquet (columna `volume`).
Los módulos de decisión lo LEEN como dato extra, nunca lo transforman en señal
direccional. Consumido por backtest sin duplicar lógica.

### Helper único (DRY)
`engine/_volume.py::volume_confirm(df, idx, window=20) -> float | None`
Ratio `volumen[vela] / media(volumen ventana previa)`. Devuelve `None` si no hay
columna `volume` o el índice está fuera de rango. **NUNCA es gate.**
Reexportado/delegado por `engine/silver_bullet.py` (`volume_confirm`),
`engine/turtle_soup.py` (`_volume_on_sweep`) y
`engine/liquidity_internal_external.py` (`volume_confirm`).

### Módulos que ANOTAN volumen (todos: float, nunca filtro)
| Módulo | Campo | Punto de anotación |
|---|---|---|
| `engine/silver_bullet.py` | `volume_confirm()` | helper del setup |
| `engine/turtle_soup.py` | `_volume_on_sweep()` | sweep PDH/PDL |
| `engine/liquidity_internal_external.py` | `erl_volume_ratio` / `irl_volume_ratio` | sweep ERL / retorno IRL |
| `engine/liquidity_levels.py` | `sweep_volume_ratio` (columna, NaN si no aplica) | vela que barre el BSL/SSL previo |
| `engine/bos/structure.py` | `bos_volume_ratio` (columna, NaN fuera de evento) | vela de breakout BOS/CHOCH |
| `engine/trade_mgmt.py` | `touch_volume_ratio` (clave dict, `None` si no hubo toque) | toque de tp1 / paso a BE |

## Verificación
Smoke: `load_frames` devuelve columna `volume` no-nula; los módulos que lo usan
no importan indicadores.

Tests: `tests/test_engine_volume_wiring.py` (17 tests) verifica por módulo:
(a) se anota el ratio cuando hay columna `volume`; (b) sin `volume` el campo es
`None`/NaN y la geometría es IDÉNTICA (regresión cero); (c) con volumen ínfimo
la geometría no cambia → **no-gate demostrado**.
