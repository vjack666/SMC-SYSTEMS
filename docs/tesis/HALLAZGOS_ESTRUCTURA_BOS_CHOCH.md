# Hallazgos y verificación — BOS/CHOCH (T9)

Fecha: 2026-08-03
Símbolo: EURUSD
Timeframe medido: H4
Datos fuente: M15 → resample a H4
Barras M15 usadas: 2000
Config motor: `swing_lookback=5`, `confirm_bars=2`

## Tests T9 — estado

- `tests/test_structure_medicion.py`: 3/3
- `tests/test_structure_run.py`: 2/2
- Total: 5/5 tests pasando

## Backtest T9 — frecuencia de eventos

- Total barras H4: 130
- BOS: 16 alcistas / 21 bajistas
- CHOCH: 14 alcistas / 12 bajistas
- BOS activos: 48 / invalidados: 6
- CHOCH activos: 3 / invalidados: 24
- Tendencia: 45 BULLISH / 64 BEARISH / 21 RANGING

Lectura inicial:
- El mercado está en tendencia el ~84% del tiempo (~109/130 barras). Eso coincide con la premisa de operar a favor del sesgo, no en rango.
- Los BOS se mantienen activos mucho más tiempo que invalidados. Eso indica que, una vez confirmada la estructura, el nivel suele respetarse por varias velas.
- Los CHOCH tienen alta tasa de invalidación (24 inválidos vs 3 activos). Eso coincide con la tesis: un CHOCH es solo aviso de giro, no confirmación. El motor no debe entrar solo por CHOCH; espera el BOS de confirmación en la nueva dirección.

## Efectividad predictiva — backtest T10

Script: `scripts/measure_structure_effectiveness.py`
Comando: `SMCS_EFFECTIVENESS_MAX_BARS=2000 SMCS_EFFECTIVENESS_K=5 PYTHONPATH=. python scripts/measure_structure_effectiveness.py`

Resultados reales:
- BOS alcista: 15 eventos, 12 aciertos → 80.00%
- BOS bajista: 21 eventos, 13 aciertos → 61.90%
- CHOCH alcista: 14 eventos, 2 confirmados, 12 invalidados → 14.29%
- CHOCH bajista: 12 eventos, 1 confirmado, 11 invalidados → 8.33%
- Baseline buy-and-hold: -1.32%

Lectura contra la tesis:
- El BOS alcista tiene mayor efectividad que el BOS bajista en este tramo. Eso sugiere que, en este dataset, la ruptura por máximo tiene más fiabilidad que la ruptura por mínimo.
- El CHOCH sigue siendo un mal predictor directo: la mayoría se invalida antes de generar un BOS en la nueva dirección.
- La regla práctica preliminar es: usar CHOCH solo como filtro de atención, no como entrada; usar BOS como señal estructural principal.

## Arquitectura aplicada

- Backtest separado del motor: el script solo carga datos, resamplea y llama a `engine.bos.structure.detect_market_structure()`.
- No hay lógica de decisión ni detección duplicada en `scripts/` o tests.
- El motor puede eliminarse del backtest sin perder datos; el motor sigue funcionando igual.

## Próximo paso recomendado

- Aumentar la muestra con más símbolos y periodos.
- Probar otros valores de `k` para medir sensibilidad de la efectividad.
- Integrar esta medición en el flujo de backtest del sesgo para evaluar BOS/CHOCH bajo bias HTF.
