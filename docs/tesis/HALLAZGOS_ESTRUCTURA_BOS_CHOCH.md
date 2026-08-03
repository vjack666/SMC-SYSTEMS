# Hallazgos y verificación — BOS/CHOCH (T9)

Fecha: 2026-08-03
Símbolo: EURUSD
Timeframe medido: H4
Datos fuente: M15 → resample a H4
Barras M15 usadas: 2000
Config motor: `swing_lookback=5`, `confirm_bars=2`
Comando: `SMCS_STRUCTURE_MAX_BARS=2000 PYTHONPATH=. python scripts/measure_structure.py`
Script: `scripts/measure_structure.py`

## Tests T9 — estado

- `tests/test_structure_medicion.py`: 3/3
- `tests/test_structure_run.py`: 2/2
- Total: 5/5 tests pasando

## Resultados reales del backtest

- Total barras H4: 130
- BOS: 16 alcistas / 21 bajistas
- CHOCH: 14 alcistas / 12 bajistas
- BOS activos: 48 / invalidados: 6
- CHOCH activos: 3 / invalidados: 24
- Tendencia: 45 BULLISH / 64 BEARISH / 21 RANGING

## Lectura inicial

- El mercado está en tendencia el ~84% del tiempo (~109/130 barras). Eso coincide con la premisa de operar a favor del sesgo, no en rango.
- Los BOS se mantienen activos mucho más tiempo que invalidados. Eso indica que, una vez confirmada la estructura, el nivel suele respetarse por varias velas.
- Los CHOCH tienen alta tasa de invalidación (24 inválidos vs 3 activos). Eso coincide con la tesis: un CHOCH es solo aviso de giro, no confirmación. El motor no debe entrar solo por CHOCH; espera el BOS de confirmación en la nueva dirección.

## Arquitectura aplicada

- Backtest separado del motor: el script solo carga datos, resamplea y llama a `engine.bos.structure.detect_market_structure()`.
- No hay lógica de decisión ni detección duplicada en `scripts/` o tests.
- El motor puede eliminarse del backtest sin perder datos; el motor sigue funcionando igual.

## Próximo paso recomendado

- Medir la secuencia BOS → CHOCH → BOS para cuantificar cuántas veces se completa el patrón completo y cuántas veces el CHOCH se invalida antes del BOS de confirmación.
