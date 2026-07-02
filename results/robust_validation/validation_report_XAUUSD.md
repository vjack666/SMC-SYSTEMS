# Robust Validation Report — XAUUSD

- **Total trades**: 642

## Risk & Performance Metrics

| Metric | Value |
|--------|-------|
| total_trades | 642 |
| win_rate | 0.4237 |
| profit_factor | 1.5447 |
| expectancy_r | 0.2581 |
| total_r | 165.7138 |
| std_r | 1.4638 |
| max_drawdown_r | -28.0622 |
| max_drawdown_pct | 16.9341 |
| sharpe_ratio | 2.7993 |
| sortino_ratio | 12.6232 |
| omega_ratio | 1.5447 |
| gain_to_pain_ratio | 1.5447 |
| tail_ratio_5pct | 3.0000 |
| tail_ratio_10pct | 3.0000 |
| recovery_factor | 5.9052 |
| ulcer_index | 0.1327 |
| k_ratio | 0.3993 |
| var_95 | -1.0000 |
| var_99 | -1.0000 |
| cvar_95 | -1.0000 |
| risk_of_ruin | 0.9228 |
| dd_avg_duration_bars | 24.6364 |
| dd_max_duration_bars | 182.0000 |
| dd_median_duration_bars | 11.0000 |
| rolling_sharpe_5pct | -3.8045 |
| rolling_sharpe_95pct | 10.3186 |
| rolling_sharpe_ci_low | -3.8045 |
| rolling_sharpe_ci_high | 10.3186 |
| rolling_pf_5pct | 0.5563 |
| rolling_pf_95pct | 4.6513 |
| rolling_pf_ci_low | 0.5563 |
| rolling_pf_ci_high | 4.6513 |
| rolling_expectancy_5pct | -0.2667 |
| rolling_expectancy_95pct | 1.0300 |
| rolling_expectancy_ci_low | -0.2667 |
| rolling_expectancy_ci_high | 1.0300 |
| num_win_trades | 272 |
| num_loss_trades | 370 |
| avg_win_r | 1.7277 |
| avg_loss_r | -0.8222 |

## Bootstrap Validation
- **Iterations**: 642
- **Original trades**: 642

| Metric | Mean | Std | P5 | P25 | P50 | P75 | P95 |
|--------|------|-----|----|-----|-----|-----|------|
| win_rate | 0.423 | 0.0195 | 0.391 | 0.4097 | 0.4237 | 0.4361 | 0.4564 |
| profit_factor | 1.5464 | 0.1405 | 1.3161 | 1.4394 | 1.548 | 1.6394 | 1.781 |
| expectancy_r | 0.2568 | 0.0575 | 0.1573 | 0.2147 | 0.2586 | 0.2977 | 0.3501 |
| max_drawdown_r | -15.285 | 4.5131 | -23.2214 | -17.4704 | -14.629 | -11.9629 | -9.4967 |

## Purged K-Fold Cross Validation
- **Folds**: 5

| Metric | Mean | Std | Min | Max | P25 | P75 |
|--------|------|-----|-----|-----|------|------|
| test_expectancy_r | 0.2582 | 0.2848 | -0.1429 | 0.5967 | 0.14 | 0.4454 |
| test_max_drawdown_r | -19.8595 | 7.818 | -27.369 | -8.4326 | -27.0622 | -17.8669 |
| test_profit_factor | 1.6738 | 0.7999 | 0.7423 | 2.8309 | 1.2534 | 2.0511 |
| test_total_trades | 128.4 | 0.5477 | 128.0 | 129.0 | 128.0 | 129.0 |
| test_trades | 128.4 | 0.5477 | 128.0 | 129.0 | 128.0 | 129.0 |
| test_win_rate | 0.4237 | 0.0913 | 0.3023 | 0.5504 | 0.3906 | 0.4609 |

## Overfitting Tests

- **Probability of Backtest Overfitting (PBO)**: 0.9932
  - MUY ALTO riesgo — el rendimiento probablemente es producto del azar.
- **Shuffles**: 100

- **Deflated Sharpe Ratio p-value**: 0.0000
  - Observed Sharpe: 2.7993
  - Estimated trials: 64
  - ALTAMENTE SIGNIFICATIVO — el Sharpe real supera el azar con >99% confianza.

## Interpretation

**Muestra**: 642 trades.  
Profit Factor 1.54: BUENO — genera ganancias consistentes.  
Sharpe 2.80: EXCELENTE.  
Sortino 12.62: Excelente gestión del downside.  
VaR(95%): -1.0000R por trade — el peor 5% de trades pierde hasta 1.00R.  
CVaR(95%): -1.0000R — pérdida esperada en el peor 5%.  
Riesgo de ruina 0.9228: ALTO — sistema vulnerable a rachas perdedoras.  
Bootstrap WR P5: 0.3910 — en el peor 5% de escenarios.  
PBO: 99.32% — muy alto riesgo — el rendimiento probablemente es producto del azar.  
DSR p-value: 0.0000 — altamente significativo — el sharpe real supera el azar con >99% confianza.
