# PROJECT_STATE.md — Current Project State

> Last updated: 2026-06-30
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
    ├── Wyckoff phases (Fase 2)
    ├── PAC State Machine
    └── Structural SL
    │
    ▼
AgentOrchestrator (optional)
    ├── ICT Agent
    ├── Wyckoff Agent
    ├── Structure Agent
    └── Decision Agent
    │
    ▼
Filter computation (exhaustion, wyckoff, trend, bos, ob_fvg, choch, swing, agents)
    │
    ▼
ConfluenceScorer (weighted, regime-adaptive)
    │
    ▼
ScalpingSignal list
    │
    ▼
Backtest engine / Risk Governor / ML quality filter
    │
    ▼
Results
```

---

## Current Milestone

**Fase 3 completed.** All Fases 1-3 implemented and pushed to GitHub.

| Fase | Description | Status |
|------|-------------|--------|
| Fase 0 | Diagnosis & current state | ✅ Completed |
| Fase 1 | PAC State Machine + Structural SL | ✅ Completed |
| Fase 2 | Stochastic Exhaustion + Wyckoff + PAC EXHAUSTION_CONFIRMED | ✅ Completed |
| Fase 3 | ML Expansion + Weighted Confluence Scoring + GridSearchCV | ✅ Completed |
| Fase 4 | Multi-Agent Architecture (SMC_SUCCESSOR integration) | ⬜ Pending |
| Fase 5 | Live Trading & Optimization | ⬜ Pending |
| Fase 6 | Documentation, Testing & Closure | ⬜ Pending |

---

## Implemented Systems

- **PAC State Machine**: FVG → Mitigation → BOS → Entry sequence with invalidation
- **Structural SL**: ICT-origin swing stops with 2:1 TP
- **Stochastic Exhaustion**: RSI cycle exhaustion detection (oversold/overbought)
- **Wyckoff Detector**: Accumulation phases A-E, Spring, SOS, LPS, SC, AR, ST
- **Weighted Confluence Scoring**: Regime-adaptive weights (PAC 30%, Wyckoff 25%, Exhaustion 20%, Structural SL 15%, ML 10%)
- **ML Pipeline**: Feature engineering, XGBoost/LightGBM training, GridSearchCV, walk-forward validation
- **Agent Architecture**: ICT, Wyckoff, Structure, Decision agents with weighted voting
- **Harness**: Scenario-based testing framework for isolated module validation
- **Multi-symbol data**: 7 forex pairs (EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF)
- **Autonomous Startup Workflow**: `/agent` documentation + opencode.json wiring for `start` command
- **KOS (Knowledge Operating System)**: `knowledge/` directory with architecture, theories, research, summaries, decisions, learnings, references, index
- **Harness README**: `SMC_SUCCESSOR/harness/README.md` with full framework documentation
- **Wyckoff Phase-Aware Pipeline**: Wyckoff detector with full cycle detection (accumulation + distribution + markup + markdown), phase-aware filter in scalping_setup, trend confidence adjustment in context_engine

---

## Systems Under Development

- **Displacement detection**: Functions exist in `detectors/displacement.py` but NOT wired into pipeline
- **Premium/Discount Zones**: Functions exist in `detectors/zones.py` but NOT wired into pipeline
- **Orchestrator in backtest**: AgentOrchestrator not passed to `build_scalping_context()` in backtest loop
- **Multi-Agent integration**: SMC_SUCCESSOR agents not yet integrated with main SMC-SYSTEMS pipeline

---

## Known Problems

| # | Problem | Severity | Status |
|---|---------|----------|--------|
| 1 | LONG trades lose systematically (-5.97R vs -0.10R for SHORTs) | HIGH | Under investigation |
| 2 | TP at 2R too far — 78% of trades exit by hold limit | HIGH | Needs TP adjustment |
| 3 | Profit Factor 0.64 (target > 1.4) | HIGH | Needs improvement |
| 4 | Confidence range too narrow (0.675–0.707) — scorer doesn't discriminate | MEDIUM | Confluence tuning needed |
| 5 | Displacement & Zones not wired into pipeline (silent columns) | MEDIUM | Scheduled for Fase 4 |
| 6 | 2023-H1 shows 0% win rate in backtest | MEDIUM | Needs investigation |
| 7 | `agent_decision_ml_probability` always NaN in datasets | LOW | Removed from v4 schema |

---

## Next Objectives

### Short term

1. Reduce TP from 2R to 1.5R to increase win rate
2. Increase `min_confidence` from 0.52 to 0.60
3. Eliminate or restrict LONG signals (require confluencia ≥ 6)
4. Activate ML Quality Filter with GridSearchCV

### Medium term

5. **Fase 4**: Wire displacement + zones into pipeline
6. **Fase 4**: Integrate SMC_SUCCESSOR multi-agent system with main pipeline
7. Retrain ML model on v4 dataset
8. Performance benchmark on 500k bars O(n × lookback)
9. **Telegram Agent**: Install deps, create bot, configure .env, test connectivity
10. **Telegram Agent**: Switch provider from `local_python` to `opencode`
