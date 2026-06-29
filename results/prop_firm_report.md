# Prop Firm Report

## Executive Summary
| Metric | In-Sample | Out-of-Sample |
|---|---:|---:|
| total_trades | 9 | 0 |
| win_rate | 0.2222 | 0.0000 |
| profit_factor | 0.2933 | 0.0000 |
| max_drawdown_pct | 5.0000 | 0.0000 |
| max_daily_drawdown_pct | 4.0000 | 0.0000 |
| sharpe_ratio | -9.0953 | 0.0000 |
| expectancy_r | -0.5497 | 0.0000 |

## Per-Symbol Metrics
| Symbol | Trades | Win Rate | PF | DD% | Daily DD% | Sharpe | Expectancy | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| EURUSD | 9 | 0.2222 | 0.2933 | 5.0000 | 4.0000 | -9.0953 | -0.5497 | FAIL |
| GBPUSD | 5 | 0.0000 | 0.0000 | 4.0000 | 4.0000 | 0.0000 | -1.0000 | FAIL |
| XAUUSD | 10 | 0.2000 | 0.4131 | 6.0000 | 4.0000 | -6.9514 | -0.4695 | FAIL |

## Calibration History
- Option A: trades=9, win_rate=0.2222, pf=0.2933, dd%=5.0000
- Option B: trades=9, win_rate=0.2222, pf=0.2933, dd%=5.0000
- Option C: trades=9, win_rate=0.2222, pf=0.2933, dd%=5.0000
- Option D: trades=9, win_rate=0.2222, pf=0.2933, dd%=5.0000
- Option E: trades=10, win_rate=0.2000, pf=0.2566, dd%=5.0000
- Option F: trades=10, win_rate=0.2000, pf=0.2566, dd%=5.0000
- Option G: trades=10, win_rate=0.2000, pf=0.2566, dd%=5.0000

## ML Model Performance
- swing: samples=11968, features=5, cv_mean=0.5206, cv_std=0.0156
- choch: samples=12000, features=5, cv_mean=0.9903, cv_std=0.0009
- fvg: samples=11987, features=5, cv_mean=0.9290, cv_std=0.0053
- ob: samples=11987, features=5, cv_mean=0.9973, cv_std=0.0007
- fractal: samples=12000, features=5, cv_mean=0.9302, cv_std=0.0031
- indicators: samples=11987, features=5, cv_mean=0.5239, cv_std=0.0283
- bos: samples=2823, features=6, cv_mean=0.5123, cv_std=0.0371
- trend: samples=121597, features=8, cv_mean=0.7681, cv_std=0.0310

## Final Recommended Parameters
- trend_confidence_threshold: 0.55
- require_d1_h4_agreement: False
- ob_fvg_proximity_atr: 1.5
- allow_xau_asia_session: False
- relaxed_bos: False
- use_confluence_mode: True
- min_confluence_score: 5
- min_atr_ratio: 1.0
- min_confidence: 0.55
- enabled_symbols: ['EURUSD', 'GBPUSD', 'XAUUSD']

## Risk Warnings
- OOS degradation >30% on win_rate: IS=0.2222, OOS=0.0000
- OOS degradation >30% on profit_factor: IS=0.2933, OOS=0.0000