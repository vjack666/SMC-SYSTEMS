# PROJECT_STATE.md — Current Project State

> Last updated: 2026-06-30 (Session 2 — deep debug)
> Always keep updated at end of each session.

---

## Current Architecture

```
MT5 Data (parquet)
    │
    ▼
build_scalping_context()
    ├── BOS detection
    ├── CHOCH detection
    ├── FVG detection
    ├── OB detection
    ├── Displacement detection (❌ NOT WIRED)
    ├── Zones (premium/discount) (❌ NOT WIRED)
    ├── Indicators (ATR, EMA, RSI)
    ├── Trend context (D1/H4/LTF)
    ├── Stochastic Exhaustion (Fase 2)
    ├── Wyckoff phases (Fase 2) — ✅ FIXED: distribution no longer overridden
    ├── PAC State Machine — ✅ FIXED: exhaustion no longer skips BOS check
    └── Structural SL — ✅ FIXED: removed from confidence (circular dep)
    │
    ▼
AgentOrchestrator (optional)
    ├── ICT Agent
    ├── Wyckoff Agent
    ├── Structure Agent
    └── Decision Agent
    │
    ▼
Filter computation (exhaustion, wyckoff, trend, bos, ob_fvg, choch, swing)
    ├── filter_wyckoff ✅ FIXED: all phases, not just terminal
    └── filter_exhaustion ✅ FIXED: directional (accum→bear, distrib→bull)
    │
    ▼
ConfluenceScorer (weighted, regime-adaptive) — ✅ FIXED: structural_sl removed
    │
    ▼
ScalpingSignal list — TP changed to 3R
    │
    ▼
Backtest engine / Risk Governor / ML quality filter
    │
    ▼
Results
```

---

## Current Milestone

**Fase 3 in progress.** Pipeline debug and fixes.

| Fase | Description | Status |
|------|-------------|--------|
| Fase 0 | Diagnosis & current state | ✅ Completed |
| Fase 1 | PAC State Machine + Structural SL | ✅ Completed |
| Fase 2 | Stochastic Exhaustion + Wyckoff + PAC EXHAUSTION_CONFIRMED | ✅ Completed |
| Fase 3 | ML Expansion + Weighted Confluence Scoring + GridSearchCV | 🔄 In progress |
| Fase 4 | Multi-Agent Architecture (SMC_SUCCESSOR integration) | ⬜ Pending |
| Fase 5 | Live Trading & Optimization | ⬜ Pending |
| Fase 6 | Documentation, Testing & Closure | ⬜ Pending |

---

## Implemented Systems

- **PAC State Machine**: FVG → Mitigation → BOS → Entry sequence with invalidation
- **Structural SL**: ICT-origin swing stops with 3:1 TP
- **Stochastic Exhaustion**: RSI cycle exhaustion detection (oversold/overbought)
- **Wyckoff Detector**: Full cycle (accum + dist + markup + markdown), all 14 columns
- **Weighted Confluence Scoring**: Regime-adaptive weights (PAC 30%, Wyckoff 25%, Exhaustion 20%, ML 10%)
- **ML Pipeline**: Feature engineering, XGBoost/LightGBM training, GridSearchCV, walk-forward validation
- **Agent Architecture**: ICT, Wyckoff, Structure, Decision agents with weighted voting
- **Harness**: Scenario-based testing framework for isolated module validation
- **Multi-symbol data**: 7 forex pairs (EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF)
- **KOS**: `/knowledge/` directory with architecture, theories, research, summaries, index
- **Debug scripts**: `scripts/debug_signal_pipeline.py` — signal flow diagnostic (10k bar truncated)

---

## Systems Under Development

- **Displacement detection**: Functions exist in `detectors/displacement.py` but NOT wired
- **Premium/Discount Zones**: Functions exist in `detectors/zones.py` but NOT wired
- **SMC_SUCCESSOR integration**: Not wired into main pipeline
- **Bearish signals**: Now working (debug output shows SHORT signals across all 3 symbols)
- **Multi-symbol**: All 3 symbols produce signals in debug mode; backtest only captures EURUSD (time matching issue in trade sim)

---

## Known Problems

| # | Problem | Severity | Status |
|---|---------|----------|--------|
| 1 | ~~Bearish signal path broken~~ — ✅ **FIXED** | ✅ FIXED |
| 2 | ~~Multi-symbol dead~~ — ✅ **FIXED**. Debug pipeline shows all 3 symbols produce signals. Backtest still only captures EURUSD due to trade sim time matching bug. | ⚠️ PARTIALLY FIXED |
| 3 | PF=1.258 (10k bars, EURUSD only, TP=3R) — profits come from single March 2026 trend window | HIGH | Needs larger data validation |
| 4 | TP at 2R → **changed to 3R** — PF now positive | ✅ DONE |
| 5 | Low trade count: 11 trades in 10k bars (EURUSD only) — need GBPUSD/XAUUSD to contribute | HIGH | Trade sim bug blocks multi-symbol |
| 6 | Phase detection bugs (accum override dist, event `continue` block) — ✅ FIXED | ✅ FIXED |
| 7 | **wyckoff_distribution = 0 for ALL symbols** — distribution detection never fires on real data. `_upthrust()`, `_sign_of_weakness()`, `_last_point_supply()` return False for all bars. | HIGH | Needs diagnostic |
| 8 | Backtest only captures EURUSD — GBPUSD/XAUUSD signals (9 + 22) lost in `_simulate_trade_with_stats` time matching | HIGH | Needs fix |
| 9 | Signal confidence too uniform — 11 signals cluster at only 2 values (0.689, 0.787) | MEDIUM | Needs scorer variance |
| 10 | ML quality filter pickle load fails (sklearn version mismatch) | MEDIUM | Needs retrain |
| 11 | Displacement & Zones not wired into pipeline | MEDIUM | Fase 4 |

---

## Next Objectives

### Short term

1. Re-train ML quality filter model (pickle load fails — sklearn version mismatch)
2. Fix trade sim time matching in backtest for GBPUSD/XAUUSD
3. Run 30k-bar backtest with all fixes + TP=3R, verify PF > 1.0
4. Reduce `min_confidence` from 0.52 if trade count still too low
5. Wire distribution-phase Wyckoff features into SMC_SUCCESSOR ML dataset

### Medium term

6. **Fase 4**: Wire displacement + zones into pipeline
7. **Fase 4**: Integrate SMC_SUCCESSOR multi-agent system with main pipeline
8. Retrain ML model on v4 dataset
9. Performance benchmark on 500k bars O(n × lookback)
10. **Telegram Agent**: Install deps, create bot, configure .env, test connectivity
11. **Telegram Agent**: Switch provider from `local_python` to `opencode`
