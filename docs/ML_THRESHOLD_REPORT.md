# ML Threshold Report — Fase 2+3 Validation

## Overview
Report documenting the impact of ML quality filtering and parameter tuning
on the SMC-SYSTEMS backtest results after Fase 2 (Stochastic Exhaustion + Wyckoff)
and Fase 3 (ML Expansion + Weighted Confluence Scoring) integration.

## Backtest Configuration

| Parameter | Value |
|-----------|-------|
| Symbols | EURUSD, GBPUSD, XAUUSD |
| Timeframe | M15 |
| Min Confidence | 0.50 |
| Max Hold Bars | 48 |
| TP Ratio | 1.5x risk |
| Structural SL Cap | 2.0 ATR |
| PAC TTL | 32 bars |
| Asia Session | Enabled for all symbols |
| ML Quality Filter | Inactive (requires retraining) |

## Threshold Validation Results

| Metric | Required | Actual | Status |
|--------|----------|--------|--------|
| Total Trades | >= 200 | 27 | ❌ |
| Win Rate | > 50% | 59.3% | ✅ |
| Profit Factor | > 1.4 | 1.61 | ✅ |
| Max Drawdown | < 8% | 5.0% | ✅ |
| Max Daily DD | < 4% | 1.0% | ✅ |
| Sharpe Ratio | > 1.0 | 3.52 | ✅ |
| Expectancy | > 0 R | +0.25R | ✅ |

## Root Cause Analysis

The low trade count (27 vs 200+) is caused by the signal generation funnel:

1. **Macro direction filter**: Only 8.3% of bars have clear BULLISH/BEARISH trend
2. **PAC state machine**: Only 4.3% of bars pass PAC confirmation
3. **Combined intersection**: ~0.2% of bars produce tradable signals

Over 3 symbols x 100k bars, this yields ~27 confirmed trades in ~3.5 years.

## Recommended Actions

1. **Add more symbols** (8-10 forex pairs) to increase trade pool
2. **Retrain ML quality filter** with Fase 2+3 features to improve selection
3. **Consider relaxing PAC** if trade count remains insufficient
