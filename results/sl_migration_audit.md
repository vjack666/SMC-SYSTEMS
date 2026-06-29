# FASE 1 — AUDITORÍA DEL STOP LOSS ACTUAL

## 1. Resumen ejecutivo
El sistema actual utiliza un Stop Loss **basado en ATR** con un multiplicador variable.
- Formula actual: `sl = entry ± (atr * sl_mult)`
- `sl_mult` típicamente oscila entre `1.5` y `2.0` ATR
- El riesgo se calcula como: `risk = |entry - sl|`
- El `pnl_r` (P&L en riesgo) se expresa como: `pnl_r = (exit_price - entry) / risk`

## 2. Módulos que intervienen en el SL actual

### 2.1 Backtesting
- `backtest/combined_backtest.py`: función `_simulate_trade_with_stats()` y `_build_signals_from_context()`
- `backtest/fvg_mitigation_backtest.py`: función `_simulate_trade()` con `sl_mult` como parámetro
- `modules/choch/backtest.py`, `modules/trend/backtest_impl.py`, `modules/swing/backtest.py`: todas usan `sl = entry ± atr`
- `backtest/bos_backtest.py`: también utiliza `sl = entry ± atr`

### 2.2 Signal Generation
- `strategy/scalping_setup.py`: genera señales con SL basado en ATR
- `backtest/combined_backtest.py`: crea `ScalpingSignal` con `stop_loss = entry ± atr`

### 2.3 Feature Engineering
- `ml/feature_pipeline.py`: genera features de riesgo/reward como `risk_r`, `rr_ratio` basados en ATR SL

### 2.4 Datasets & Labeling
- `scripts/run_forensic_analytics.py`: reconstruye stop prices a partir de `entry_price - sl_dist` o `entry_price + sl_dist`
- `backtest/fvg_mitigation_backtest.py`: computa `pnl_r` usando `sl_dist = atr * sl_mult`

### 2.5 Paper Trading
- `scripts/paper_trading_logger.py`: almacena `stop_price` como parte del log de señales

## 3. Cómo afecta el SL actual al cálculo de métricas

### 3.1 Impacto en `pnl_r`
```
risk_distance = |entry - sl|
pnl_r = (exit_price - entry) / risk_distance

Ejemplo LONG:
  entry = 1.1000
  sl = 1.0950  (ATR de 0.005 * 1.5 mult)
  risk_distance = 0.0050
  
  Si exit = 1.1050:
    pnl_r = (1.1050 - 1.1000) / 0.0050 = 1.0 R
```

### 3.2 Impacto en RR (Risk/Reward)
```
rr_ratio = (TP - entry) / (entry - SL)

Ejemplo:
  entry = 1.1000
  sl = 1.0950  (riesgo = 0.005)
  tp = 1.1100  (reward = 0.01)
  rr_ratio = 0.01 / 0.005 = 2.0
```

### 3.3 Impacto en Win Rate
- La distancia del SL afecta al W% porque un SL más cercano es más fácil de tocar.
- ATR variable implica SL variable: en volatilidad alta, SL más lejano; en volatilidad baja, más cercano.

## 4. Cómo afecta al entrenamiento ML

### 4.1 Features relacionadas con SL
- `risk_r`: distancia en riesgo
- `rr_ratio`: relación riesgo/recompensa
- `stop_distance_atr`: multiplicador del SL
- `sl_atr_mult`: parámetro clave usado en ablación

### 4.2 Problema actual
- El SL es **independiente de la estructura** que originó el BOS.
- Un BOS puede tener una mitigación profunda pero un SL basado solo en ATR.
- El modelo ML entrena con features de ATR pero ignora la **distancia estructural real**.

## 5. Archivos clave que deben modificarse

| Archivo | Función | Cambio necesario |
|---------|---------|-----------------|
| `backtest/combined_backtest.py` | `_build_signals_from_context()` | Reemplazar `sl = entry ± atr` con `sl = origin_swing_price` |
| `backtest/fvg_mitigation_backtest.py` | `_simulate_trade()` | Pasar `structural_sl` en lugar de `sl_mult` |
| `strategy/scalping_setup.py` | Signal generation | Incorporar `structural_stop_price` del análisis BOS |
| `ml/feature_pipeline.py` | Feature engineering | Añadir features estructurales: `structural_stop_distance`, `distance_to_origin_swing`, etc. |
| `scripts/run_forensic_analytics.py` | Reconstruction | Usar `structural_sl` en lugar de ATR-based |
| `backtest/bos_backtest.py` | Trade simulation | Compatibilidad con nuevo SL estructural |

## 6. Nuevas features necesarias para el SL estructural

Se propone capturar:

```
- structural_stop_price: precio del origin swing
- structural_stop_distance: distancia en pips del entry al origin swing
- structural_stop_atr_ratio: distancia estructural / ATR en entry
- distance_to_origin_swing: distancia en ATR units
- distance_to_sweep: distancia en ATR units del sweep
- bos_displacement_size: tamaño del BOS en pips
- bos_displacement_atr: tamaño del BOS en ATR units
- liquidity_sweep_size: tamaño del sweep en pips
- liquidity_sweep_atr: tamaño del sweep en ATR units
```

Estas features permitirán auditar si el SL estructural es **más eficiente** que el ATR-based.

## 7. Impacto esperado del cambio

### 7.1 Posibles beneficios
- **Mejor validez estructural**: el SL respeta la estructura que originó la señal.
- **Reducción de SL tocados por ruido**: ruido intrabar cerca del entry no invalida la estructura.
- **MAE mejorado**: ganadores tienen MAE menor porque el SL está más validado.
- **Mejor RR**: potencialmente RR más altos si el origin swing está lejano.

### 7.2 Posibles riesgos
- **SL demasiado lejano**: en algunos casos, origin swing muy profundo → SL grande → RR bajo.
- **Sesgo histórico**: si se usa el SL antiguo en backtests anteriores, la comparación sería sesgada.

## 8. Plan de acción para FASES 2-7

| Fase | Tarea | Output |
|------|-------|--------|
| FASE 2 | Implementar cálculo de origin swing y structural SL | Nuevo módulo `modules/structural_sl/` |
| FASE 3 | Extender features en `ml/feature_pipeline.py` | Feat list actualizada con 8 features nuevas |
| FASE 4 | Reconstruir pipeline: BOS→FVG→Mitigación→Signals | Código limpio, sin reutilización de CSVs antiguos |
| FASE 5 | Generar experiment_F_structural_sl desde OHLC raw | CSV nuevo con datos completamente regenerados |
| FASE 6 | Comparar experiment_E vs experiment_F | Reporte de comparación: W%, PF, Exp, Sharpe, DD |
| FASE 7 | Analizar distribución de SL, MAE, RR | Evidencia numérica del impacto del nuevo SL |

## 9. Criterio de éxito

El nuevo SL habrá alcanzado su objetivo si **experiment_F**:
- ✅ Mantiene o **mejora expectancy** (>= 0.265 R o mayor)
- ✅ Mantiene o **mejora PF** (>= 1.56 o mayor)
- ✅ **Reduce drawdown** significativamente
- ✅ **Mantiene estabilidad** OOS (robustez de validación)
- ✅ Muestra **MAE reducido** en ganadores
- ✅ Demuestra **mejoría estructural** en auditoría de SL

---

## 10. Dependencias
- Módulos de detección BOS ya existentes y funcionales
- FVG detection y mitigation tracking
- ATR calculation pipeline
- ML quality model (para filtrado)
