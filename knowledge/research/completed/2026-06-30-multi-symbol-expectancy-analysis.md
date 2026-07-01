# Multi-Symbol Expectancy Analysis

**Date**: 2026-06-30  
**Session**: Post deep-pipeline debug  
**Data**: Backtest 10k bars M15 (2024-2026), EURUSD+GBPUSD+XAUUSD, TP=3R, ML filter OFF  
**Config**: PAC ON, Wyckoff ON, Stochastic Exhaustion ON, min_confidence=0.52, max_hold=48  

---

## Global Results

| Metric | Value |
|--------|-------|
| Total trades | 11 |
| Win Rate | 27.3% |
| Profit Factor | 1.258 |
| Expectancy | +0.168R |
| Total PnL | +1.84R |
| Sharpe | 1.45 |
| Max DD | -4.16R |
| Avg Win | +3.000R |
| Avg Loss | -0.894R |
| Avg Hold | 3.9h |

---

## Per-Symbol Breakdown

| Symbol | Trades | WR | PF | EV(R) | Total(R) |
|--------|--------|----|----|-------|---------|
| **EURUSD** | 11 | 27.3% | 1.258 | +0.168 | +1.84 |
| **GBPUSD** | 0 | — | — | — | 0.00 |
| **XAUUSD** | 0 | — | — | — | 0.00 |

**The backtest only captured EURUSD trades.** Debug pipeline confirms GBPUSD (9 signals) and XAUUSD (22 signals) produce signals but are lost during trade simulation — likely a time-matching issue in `_simulate_trade_with_stats`.

---

## Per-Direction Breakdown (EURUSD only)

| Direction | Trades | WR | PF | EV(R) | Total(R) |
|-----------|--------|----|----|-------|---------|
| LONG | 1 | 0% | 0.0 | -0.156 | -0.16 |
| SHORT | 10 | 30% | 1.286 | +0.200 | +2.00 |

**Strong bearish bias**: 10/11 trades are SHORT. All 3 winners are SHORT.

---

## Monthly PnL

| Month | Trades | PnL(R) |
|-------|--------|--------|
| 2026-01 | 1 | -1.00 |
| 2026-03 | 7 | +5.00 |
| 2026-04 | 1 | -0.16 |
| 2026-05 | 2 | -2.00 |

**Single-trend dependency**: All profits come from March 2026 EURUSD SHORT.

---

## Debug Pipeline Signals (per Symbol)

| Symbol | Signals | LONG | SHORT | pac_ready | wyckoff_accum | wyckoff_dist |
|--------|---------|------|-------|-----------|---------------|--------------|
| EURUSD | 11 | 1 | 10 | 446 | 8110 | **0** |
| GBPUSD | 9 | 1 | 8 | 432 | 8108 | **0** |
| XAUUSD | 22 | 17 | 5 | 401 | 6272 | **0** |

---

## Critical Findings

### 1. wyckoff_distribution = 0 for ALL symbols
Despite the phase priority fix, distribution detection never fires on this 10k-bar sample. The functions `_upthrust()`, `_sign_of_weakness()`, `_last_point_supply()` return False for all bars. The EURUSD/GBPUSD data shows only ACCUMULATION_B/C/D/E and NONE phases. This means:
- Bearish PAC entries get NO exhaustion signal from Wyckoff
- The short bias comes from stochastic exhaustion + macro trend, not from Wyckoff distribution
- **Root cause**: Distribution event conditions are too strict for the current data

### 2. Confidence uniformity
11 EURUSD signals have only 2 unique confidence values (0.689, 0.787). The confluence scorer needs more dynamic range to properly rank setups.

### 3. Backtest only captures EURUSD
GBPUSD and XAUUSD produce debug signals but 0 backtest trades. Possible causes:
- `_simulate_trade_with_stats` time matching precision
- Frame loading path discrepancy

### 4. All profits from a single trend
3 winning trades (all EURUSD SHORT, March 3-13 2026) contribute +9R. The remaining 8 trades lose -7.16R. The system is not robust outside this specific trend window.

---

## Proposed Actions

### Immediate (Session-blocking)

1. **Fix trade sim time matching** — Debug `_simulate_trade_with_stats` for GBPUSD/XAUUSD so all symbols contribute to backtest results
2. **Investigate distribution detection** — Run `_upthrust()` and `_sign_of_weakness()` diagnostic on the 10k-bar sample; either relax thresholds or find why they never trigger
3. **Add wyckoff_distribution to PAC exhaustion_series** — Currently only `wyckoff_accumulation` feeds PAC exhaustion for bearish entries (since distribution never fires). Add a fallback using stochastic exhaustion direction or EMA crossover

### Short-term

4. **Retrain ML quality filter** — Current pickle fails to load (sklearn version mismatch); retrain with current environment
5. **Reduce confidence uniformity** — Add more variance to confluence score inputs (e.g., market_regime, ATR ratio, volume)
6. **Run 30k-bar backtest** — Once time matching is fixed, validate whether PF > 1.0 holds on larger data

### Medium-term

7. **Wire distribution-phase Wyckoff features** into SMC_SUCCESSOR ML dataset
8. **Add per-symbol filter tuning** — Different thresholds for XAUUSD (16% of filter_wyckoff passes) vs EURUSD (1.4%)
9. **Reduce TP from 3R to 2.5R** if PF drops below 1.0 at scale
