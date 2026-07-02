# Robust Validation Report — GBPUSD

- **Total trades**: 738

## Risk & Performance Metrics

| Metric | Value |
|--------|-------|
| total_trades | 738 |
| win_rate | 0.4485 |
| profit_factor | 1.6399 |
| expectancy_r | 0.2975 |
| total_r | 219.5362 |
| std_r | 1.4711 |
| max_drawdown_r | -20.8883 |
| max_drawdown_pct | 9.3238 |
| sharpe_ratio | 3.2100 |
| sortino_ratio | 15.7703 |
| omega_ratio | 1.6399 |
| gain_to_pain_ratio | 1.6399 |
| tail_ratio_5pct | 3.0000 |
| tail_ratio_10pct | 3.0000 |
| recovery_factor | 10.5100 |
| ulcer_index | 0.4233 |
| k_ratio | 0.6959 |
| var_95 | -1.0000 |
| var_99 | -1.0000 |
| cvar_95 | -1.0000 |
| risk_of_ruin | 0.8942 |
| dd_avg_duration_bars | 14.0476 |
| dd_max_duration_bars | 102.0000 |
| dd_median_duration_bars | 7.5000 |
| rolling_sharpe_5pct | -3.6464 |
| rolling_sharpe_95pct | 7.7219 |
| rolling_sharpe_ci_low | -3.6464 |
| rolling_sharpe_ci_high | 7.7219 |
| rolling_pf_5pct | 0.5787 |
| rolling_pf_95pct | 3.4026 |
| rolling_pf_ci_low | 0.5787 |
| rolling_pf_ci_high | 3.4026 |
| rolling_expectancy_5pct | -0.2677 |
| rolling_expectancy_95pct | 0.7793 |
| rolling_expectancy_ci_low | -0.2677 |
| rolling_expectancy_ci_high | 0.7793 |
| num_win_trades | 331 |
| num_loss_trades | 407 |
| avg_win_r | 1.6997 |
| avg_loss_r | -0.8429 |

## Bootstrap Validation
- **Iterations**: 738
- **Original trades**: 738

| Metric | Mean | Std | P5 | P25 | P50 | P75 | P95 |
|--------|------|-----|----|-----|-----|-----|------|
| win_rate | 0.4482 | 0.019 | 0.4173 | 0.435 | 0.4485 | 0.4607 | 0.4785 |
| profit_factor | 1.6419 | 0.14 | 1.41 | 1.5465 | 1.6378 | 1.7326 | 1.8722 |
| expectancy_r | 0.2962 | 0.0549 | 0.2023 | 0.2602 | 0.297 | 0.3325 | 0.3836 |
| max_drawdown_r | -14.131 | 3.9108 | -21.2792 | -16.1476 | -13.3636 | -11.4417 | -9.2451 |

## Purged K-Fold Cross Validation
- **Folds**: 5

| Metric | Mean | Std | Min | Max | P25 | P75 |
|--------|------|-----|-----|-----|------|------|
| test_expectancy_r | 0.2978 | 0.1586 | 0.0998 | 0.4667 | 0.1621 | 0.4009 |
| test_max_drawdown_r | -14.468 | 2.5305 | -17.2773 | -11.281 | -16.7967 | -13.1474 |
| test_profit_factor | 1.668 | 0.387 | 1.1853 | 2.0662 | 1.3467 | 1.9757 |
| test_total_trades | 147.6 | 0.5477 | 147.0 | 148.0 | 147.0 | 148.0 |
| test_trades | 147.6 | 0.5477 | 147.0 | 148.0 | 147.0 | 148.0 |
| test_win_rate | 0.4485 | 0.0399 | 0.3919 | 0.5 | 0.4324 | 0.4626 |

## Overfitting Tests

- **Probability of Backtest Overfitting (PBO)**: 0.9921
  - MUY ALTO riesgo — el rendimiento probablemente es producto del azar.
- **Shuffles**: 100

- **Deflated Sharpe Ratio p-value**: 0.0000
  - Observed Sharpe: 3.21
  - Estimated trials: 73
  - ALTAMENTE SIGNIFICATIVO — el Sharpe real supera el azar con >99% confianza.

## Interpretation

**Muestra**: 738 trades.  
Profit Factor 1.64: BUENO — genera ganancias consistentes.  
Sharpe 3.21: EXCELENTE.  
Sortino 15.77: Excelente gestión del downside.  
VaR(95%): -1.0000R por trade — el peor 5% de trades pierde hasta 1.00R.  
CVaR(95%): -1.0000R — pérdida esperada en el peor 5%.  
Riesgo de ruina 0.8942: ALTO — sistema vulnerable a rachas perdedoras.  
Bootstrap WR P5: 0.4173 — en el peor 5% de escenarios.  
PBO: 99.21% — muy alto riesgo — el rendimiento probablemente es producto del azar.  
DSR p-value: 0.0000 — altamente significativo — el sharpe real supera el azar con >99% confianza.
