# Wyckoff Phase-Aware Filter — Backtest Analysis

**Date**: 2026-06-30  
**Data**: EURUSD, GBPUSD, XAUUSD M15 (30k bars ≈ 2 years)  
**Config**: PAC ON, Exhaustion ON, Structural SL ON, ML Quality OFF  

---

## Results

| Metric | Wyckoff ON | Wyckoff OFF | Delta |
|--------|-----------|-------------|-------|
| Total Trades | 22 | 19 | +3 |
| Win Rate | 31.82% | 31.58% | +0.24% |
| Profit Factor | 0.4042 | 0.4121 | -0.0079 |
| Max DD% | 8.24% | 8.34% | -0.10% |
| Sharpe | -6.87 | -6.80 | -0.06 |
| Expectancy (R) | -0.397 | -0.386 | -0.011 |

## Key Findings

### 1. Wyckoff Phase-Aware Filter Effect: NEUTRAL
The phase-aware filter has essentially no impact on performance:
- PF difference: -0.0079 (0.79% worse with Wyckoff — noise level)
- Trade count: 22 vs 19 (3 more with Wyckoff — negligible)
- Win rate, Sharpe, Expectancy all within noise

**Conclusion**: The Wyckoff filter neither helps nor hurts performance on this data.

### 2. 100% LONG, 100% EURUSD (with or without Wyckoff)
Both configurations:
- Only trade EURUSD (no GBPUSD, XAUUSD)
- Only LONG (no SHORT)

The bearish signal path is completely broken regardless of Wyckoff.

### 3. Poor R:R / Win Rate (systemic issue)
- ~31% WR, ~-0.40R expectancy
- Losers consistently -1R, winners variable
- Net negative regardless of Wyckoff

### 4. Bugs Fixed During Analysis

| Bug | Impact | Fix |
|-----|--------|-----|
| `confluence_scorer.py` line 64: Wyckoff weight always in denominator | OFF case had ~0% confidence → 0 trades | Make wyckoff weight conditional on column existence |
| `scalping_setup.py` line 386: `pac_entry_ready` access not guarded | Crash when `use_pac=False` | Guard with `if config.use_pac` |
| `scalping_setup.py` `_build_exhaustion_series` no fallback | 0 trades when Wyckoff OFF + stochastic OFF | Add fallback when both exhaustion sources disabled |

## Root Causes of Low PF

1. **No SHORT trades**: Both configs produce 100% LONG. The bearish `macro_direction` paths never generate signals.

2. **EURUSD only**: Session filter or detector logic prevents GBPUSD/XAUUSD from triggering.

3. **Poor R:R**: 2R TP rarely hit; -1R SL frequently hit. Net negative expectancy.

4. **Low trade count**: 19-22 trades in 2 years across 3 symbols is ~7 trades/symbol/year — too sparse for statistical significance.

## Recommendations

1. **Fix bearish signal path** (HIGH priority): Debug why `macro_direction == "BEARISH"` never produces PAC entries
2. **Fix multi-symbol** (HIGH priority): Check session filter + detector logic for GBPUSD/XAUUSD
3. **Improve R:R**: Test TP at 1.5R, tighten stops, or use ATR-based dynamic targets
4. **Increase trade count**: Relax min_confidence from 0.52 to 0.45, or reduce filters
5. **Run with ML quality filter**: Activate ML model in run_system.py to see if it improves PF
