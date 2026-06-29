# Experiment Comparison: E vs F Broken vs F Fixed

## Overview

| Metric | E (Baseline) | F Broken | F Fixed | Improvement |
|--------|--------------|----------|---------|-------------|
| Total trades | 1776 | 141 | 14344 | Fixed has +14203 more |
| Win rate | N/A | 0.9574468085106383 | 0.39821528165086445 | - |
| Profit factor | N/A | 22.833333333333332 | 1.0258339650109183 | - |
| Expectancy (R) | N/A | 0.9290780141843972 | 0.014241992727054988 | - |
| Total R | 471.51667342304296 | 131.0 | 204.2871436768767 | - |
| Max Drawdown | -28.062187075715713 | -1.0 | -158.06925535310774 | - |
| Avg Holding Bars | 10.416103603603604 | 1.0 | 49.680354155047404 | - |

## Stop Loss Validation

| Metric | E | F Broken | F Fixed |
|--------|---|----------|---------|
| Invalid LONG stops | N/A (different format) | 78 | 0 ✅ |
| Invalid SHORT stops | N/A (different format) | 55 | 0 ✅ |

## Exit Logic Validation

| Invalid exit logic | N/A | 133 | 0 ✅ |

## ATR Validation

| stop_distance_atr NaN count | N/A | 141 | 0 ✅ |

## Trade Distribution

| LONG trades | 873 | 82 | 7422 |
| SHORT trades | 903 | 59 | 6922 |

## Holding Bars Distribution

| Unique holding bar values | 16 | 1 | 100 ✅ |

## Key Findings

### Experiment E (ML-based baseline)
- 1776 trades
- Uses machine learning confidence score and feature engineering
- Different structure from F (no explicit stop_price/entry_price columns)

### Broken F Issues
- Only 141 trades (highly selective filter - structural stop broken)
- 78 LONG and 55 SHORT trades with inverted stops
- holding_bars constant at 1 (indicates exit logic corruption - immediate stops)
- stop_distance_atr all NaN (ATR loading issue)
- 133 exit logic violations

### Fixed F Improvements ✅
- 14344 trades generated (recovered from broken 141 to realistic volume)
- ✅ 0 invalid stops (LONG all below entry, SHORT all above entry)
- ✅ holding_bars varies across 100 values (realistic hold times)
- ✅ stop_distance_atr has finite values (ATR properly computed)
- ✅ 0 exit logic violations (no sl_hit with positive pnl_r)
- Realistic trade volume and distribution