# MDS_VOLUMEN.md — Volumen como ÚNICO dato extra permitido

- **Clasificación**: OBLIGATORIO (regla transversal) · **Estado: ✅ DEFINIDO**
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

## Verificación
Smoke: `load_frames` devuelve columna `volume` no-nula; los módulos que lo usan
no importan indicadores.
