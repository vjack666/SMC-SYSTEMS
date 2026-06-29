# Quantitative System Audit

## SECCIÓN 1 — INVENTARIO ACTUAL

### Métricas existentes
- `win_rate`, `profit_factor`, `max_drawdown`, `sharpe_ratio`, `expectancy_r`, `equity_final`
- `calmar_ratio` in forward validation only
- month/year breakdown, symbol/side/session breakdown
- Monte Carlo summary (results/e_montecarlo.csv)
- stress test outputs, threshold analysis, permutation importance

### Features existentes
- ATR ratio, EMA slope, RSI, tick volume, session bucket, hour, weekday
- FVG, Order Block, BOS, CHOCH, structure events, mitigation depth, anchor proximity
- regime labels from `ml/regime_detector.py`
- feature importance set from `results/feature_importance.csv`

### Modelos ML existentes
- ML quality filter pipeline in `ml/train_quality_model.py`
- Multi-framework classifier support: XGBoost, LightGBM, CatBoost, fallback HistGradientBoosting
- Trend model scaffold in `modules/trend` with feature engineering and signal confidence model
- Regime detector in `ml/regime_detector.py`

### Filtros existentes
- session filter, ATR state gate, volume threshold, FVG/OB proximity, BOS/EOS, CHOCH, micro trend filter
- confluence scoring, mandatory session + ATR filters

### Validaciones existentes
- forward validation via 70/30 split (`scripts/run_forward_validation.py`)
- walk-forward summary and comparison outputs
- robustness audit for Experiment E (`results/e_robustness_audit.md`)
- Monte Carlo and stress scenario outputs
- filter diagnostics and feature drift snapshot in `ml/feature_pipeline.py`

### Datasets existentes
- `results/experiment_E.csv`, `experiment_A/B/C/D.csv`
- `results/ml_trade_dataset.csv`
- `results/forensic_trades_dataset.csv`
- `data/mt5/*.parquet` market data
- `paper_trading/data/paper_trading_signals.csv`

### Logs existentes
- `paper_trading/logs/daily_performance.csv`
- `paper_trading/logs/weekly_performance.csv`
- `paper_trading/logs/model_monitoring.csv`
- `run_system_latest.log`, `run_system_live.log`
- `results/status.json`, `results/invalidation_log.csv`

### Dashboards existentes
- Static markdown and CSV reports across `results/`
- visual artifacts under `results/charts/` and trade visual PNGs
- New edge decomposition report with supporting charts: `results/quant_audit/edge_decomposition_report.md`
- no interactive dashboard layer detected

## SECCIÓN 2 — GAP ANALYSIS

### Resumen de brechas principales
1. Backtest engine carece de un motor de simulación completo; no hay fill model ni market-impact model.
2. Validation pipeline no usa Purged KFold ni embargo, lo que deja riesgo de leakage en activos correlacionados.
3. Monitoring es estático: no existe producción real-time drift detection para predicción, características o equity.
4. ML pipeline es funcional pero falta model governance y robustez estadística de MLFinLab.
5. Feature engineering es relevante en SMC, pero insuficiente en microestructura, temporal y estadísticos avanzados.

## SECCIÓN 3 — MÉTRICAS FALTANTES

Identificadas las métricas profesionales ausentes, con especial foco en riesgo y robustez.

- Rendimiento faltante: Sortino, Omega Ratio, Ulcer Index, Recovery Factor, MAR Ratio, Tail Ratio, Gain-to-Pain Ratio, Information Ratio, K-Ratio.
- Riesgo faltante: CVaR, Expected Shortfall, VaR, Risk of Ruin, Max Adverse Excursion / Max Favorable Excursion agregados, Time Under Water.
- Estabilidad faltante: Rolling Sharpe, Rolling PF, Rolling Expectancy, Equity Stability Score, Strategy Decay Score.
- Robustez faltante: Probability of Backtest Overfitting, Deflated Sharpe Ratio, White Reality Check, CSCV, Bootstrap Validation.

## SECCIÓN 4 — FEATURE ENGINEERING

### Revisiones y brechas
- Categoría SMC: se usan FVG, OB, BOS, CHOCH y mitigación, pero faltan sweeps, inducements, displacement, premium discount arrays, breaker blocks, mitigation blocks.
- Microestructura: ATR y volumen están presentes, faltan volatility clustering, volatility regime y microstructure flow proxies.
- Temporal: hay session/hora/día de semana y reportes mensuales; faltan semana del mes, transiciones de sesión, macro windows y holiday/event windows.
- Estadísticas: hay correlación y algunos rolling cálculos; faltan zscores, rolling ranks, percentiles, entropy y Hurst exponent.
- ML: hay pipeline con one-hot, numeric scaling y feature importance; faltan target encoding, interaction features, regime labels, meta labels y stacking.

## SECCIÓN 5 — VALIDACIÓN

### Estado de la validación
- Implementado: walk-forward 70/30, forward validation, robustness audit, stress tests.
- Ausente/insuficiente: Purged KFold, embargo, nested cross validation, outlier validation, regime-specific validation, combinatorial and bootstrap validation.

## SECCIÓN 6 — MONITOREO EN PRODUCCIÓN

### Estado actual
- Existe monitoreo de paper trading y logs de estado.
- No hay implementación de drift monitoring automatizado para conceptos, features, etiquetas, predicciones, equity o régimen.
- No hay alertas de degradación ni metadatos de producción.

## SECCIÓN 7 — PRIORIZACIÓN

### Mejores mejoras de alto impacto
- Controles de validación: Purged KFold, embargo, nested CV, bootstrap, deflated Sharpe.
- Monitoreo en producción: drift detection, equity alerts, model degradation.
- Métricas de riesgo: CVaR, VaR, MFE/MAE agregados, rolling performance.

### Mejoras de impacto medio/alto
- Expansión de features SMC y microestructura.
- Dashboard de KPI para traders y riesgo.
- Documentación de gobernanza.

## SECCIÓN 8 — ROADMAP

1. FASE 13 — Validación robusta y métricas de riesgo.
2. FASE 14 — Enriquecimiento de features y labels de régimen.
3. FASE 15 — Monitorización de producción y alertas.
4. FASE 16 — Automatización y gobernanza.

## Observaciones finales
- El proyecto tiene una base sólida de backtesting, ML y análisis de robustez de Experimento E.
- Para ser plataforma cuantitativa profesional falta completar la capa de gobernanza, validación estadística y monitoreo de producción.
- Todas las recomendaciones se sustentan en prácticas públicas de QuantConnect, MLFinLab, Hudson & Thames, LuxAlgo PAC, y estándares institucionales de riesgo y evaluación de modelos.
