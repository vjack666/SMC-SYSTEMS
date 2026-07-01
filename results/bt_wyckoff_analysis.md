# Wyckoff Phase-Aware Filter — Backtest Analysis

**Date**: 2026-06-30
**Data**: EURUSD, GBPUSD, XAUUSD M15 (30k bars ≈ 2 years)
**Config**: PAC ON, Exhaustion ON, Structural SL ON, ML Quality OFF

---

## Results

| Metric | Wyckoff ON | Wyckoff OFF |
|--------|-----------|-------------|
| Total Trades | 22 | 0 |
| Win Rate | 31.82% | — |
| Profit Factor | 0.40 | — |
| Max DD% | 8.24% | — |
| Sharpe | -6.87 | — |
| Expectancy (R) | -0.40 | — |

## Key Findings

### 1. PAC Depends on Wyckoff
The PAC state machine uses Wyckoff accumulation as an exhaustion confirmation.  
Without Wyckoff, `_build_exhaustion_series()` returns all-False, so PAC mitigation never triggers.  
**Result**: 0 trades without Wyckoff. Wyckoff is mandatory.

### 2. Severe LONG Bias (100% EURUSD Long)
All 22 trades are:
- EURUSD only (no GBPUSD, XAUUSD)
- All LONG (no SHORT)

This indicates:
- The bearish signal path is broken or too restrictive
- Session + PAC + Wyckoff alignment for shorts is never satisfied
- Other symbols fail the session filter or other gates

### 3. Poor R:R / Win Rate
- 7 winners (31.8%), 15 losers (68.2%)
- Winners avg ~+1.0R, losers consistently -1.0R
- Net negative expectancy (-0.40R)
- Consecutive losers drain equity (Max DD 8.24%)

### 4. Short-Sample Luck
The first 3000-bar test showed PF 3.38 (7 trades, 57% WR).  
This was a lucky streak — the 30k-bar test shows the real performance.

## Root Causes

1. **No SHORT trades**: `signal_direction` in `build_scalping_context` only sets -1 for bearish macro_direction when `pac_entry_ready` is True. If the bearish PAC never completes, no short signals.

2. **All EURUSD only**: Session filter (`_session_filter`) may be blocking GBPUSD/XAUUSD. London/NY session only, 7-17 UTC.

3. **High loss rate**: The -1R stop loss hits frequently. TP at 2R sometimes hits, but not often enough.

## Recommendations

1. **Fix bearish signal path**: Debug why `macro_direction == "BEARISH"` never produces PAC entries with Wyckoff distribution phase
2. **Add symbol diversification**: Check session filter logic for GBPUSD/XAUUSD
3. **Improve R:R**: Consider tighter stops or wider targets
4. **Add short trades**: Without shorts, the system misses ~50% of market opportunity
5. **Run longer backtest**: 22 trades is still low for statistical significance
