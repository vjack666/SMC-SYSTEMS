# Robust Validation Report — EURUSD

- **Total trades**: 396

## Risk & Performance Metrics

| Metric | Value |
|--------|-------|
| total_trades | 396 |
| win_rate | 0.4141 |
| profit_factor | 1.4447 |
| expectancy_r | 0.2178 |
| total_r | 86.2666 |
| std_r | 1.4573 |
| max_drawdown_r | -21.0822 |
| max_drawdown_pct | 22.6333 |
| sharpe_ratio | 2.3729 |
| sortino_ratio | 11.1305 |
| omega_ratio | 1.4447 |
| gain_to_pain_ratio | 1.4447 |
| tail_ratio_5pct | 3.0000 |
| tail_ratio_10pct | 3.0000 |
| recovery_factor | 4.0919 |
| ulcer_index | 0.2385 |
| k_ratio | 0.4541 |
| var_95 | -1.0000 |
| var_99 | -1.0000 |
| cvar_95 | -1.0000 |
| risk_of_ruin | 0.8797 |
| dd_avg_duration_bars | 21.3750 |
| dd_max_duration_bars | 99.0000 |
| dd_median_duration_bars | 13.5000 |
| rolling_sharpe_5pct | -2.9267 |
| rolling_sharpe_95pct | 6.8776 |
| rolling_sharpe_ci_low | -2.9267 |
| rolling_sharpe_ci_high | 6.8776 |
| rolling_pf_5pct | 0.6387 |
| rolling_pf_95pct | 2.7717 |
| rolling_pf_ci_low | 0.6387 |
| rolling_pf_ci_high | 2.7717 |
| rolling_expectancy_5pct | -0.2131 |
| rolling_expectancy_95pct | 0.7557 |
| rolling_expectancy_ci_low | -0.2131 |
| rolling_expectancy_ci_high | 0.7557 |
| num_win_trades | 164 |
| num_loss_trades | 232 |
| avg_win_r | 1.7088 |
| avg_loss_r | -0.8361 |

## Bootstrap Validation
- **Iterations**: 396
- **Original trades**: 396

| Metric | Mean | Std | P5 | P25 | P50 | P75 | P95 |
|--------|------|-----|----|-----|-----|-----|------|
| win_rate | 0.4145 | 0.025 | 0.3712 | 0.3965 | 0.4167 | 0.4318 | 0.4545 |
| profit_factor | 1.4529 | 0.1688 | 1.163 | 1.3394 | 1.4562 | 1.5646 | 1.7301 |
| expectancy_r | 0.218 | 0.0736 | 0.0871 | 0.1702 | 0.2214 | 0.2689 | 0.3307 |
| max_drawdown_r | -14.8325 | 4.7306 | -24.2229 | -16.9298 | -13.6127 | -11.5349 | -9.3277 |

## Purged K-Fold Cross Validation
- **Folds**: 5

| Metric | Mean | Std | Min | Max | P25 | P75 |
|--------|------|-----|-----|-----|------|------|
| test_expectancy_r | 0.2175 | 0.1545 | 0.0356 | 0.3803 | 0.1331 | 0.3773 |
| test_max_drawdown_r | -12.8873 | 1.2502 | -14.4461 | -11.777 | -13.9774 | -11.7883 |
| test_profit_factor | 1.4734 | 0.379 | 1.0743 | 1.8986 | 1.2249 | 1.8567 |
| test_total_trades | 79.2 | 0.4472 | 79.0 | 80.0 | 79.0 | 79.0 |
| test_trades | 79.2 | 0.4472 | 79.0 | 80.0 | 79.0 | 79.0 |
| test_win_rate | 0.4141 | 0.0353 | 0.3671 | 0.4557 | 0.3924 | 0.4375 |

## Overfitting Tests

- **Probability of Backtest Overfitting (PBO)**: 0.9737
  - MUY ALTO riesgo — el rendimiento probablemente es producto del azar.
- **Shuffles**: 100

- **Deflated Sharpe Ratio p-value**: 0.0000
  - Observed Sharpe: 2.3729
  - Estimated trials: 39
  - ALTAMENTE SIGNIFICATIVO — el Sharpe real supera el azar con >99% confianza.

## Interpretation

**Muestra**: 396 trades.  
Profit Factor 1.44: ACEPTABLE — ligeramente rentable.  
Sharpe 2.37: EXCELENTE.  
Sortino 11.13: Excelente gestión del downside.  
VaR(95%): -1.0000R por trade — el peor 5% de trades pierde hasta 1.00R.  
CVaR(95%): -1.0000R — pérdida esperada en el peor 5%.  
Riesgo de ruina 0.8797: ALTO — sistema vulnerable a rachas perdedoras.  
Bootstrap WR P5: 0.3712 — en el peor 5% de escenarios.  
PBO: 97.37% — muy alto riesgo — el rendimiento probablemente es producto del azar.  
DSR p-value: 0.0000 — altamente significativo — el sharpe real supera el azar con >99% confianza.
