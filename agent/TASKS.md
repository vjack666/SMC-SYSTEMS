# TASKS.md — Task Tracking

> Update at end of every session.

---

## In Progress

*None*

---

## In Progress

- [ ] Fix trade sim time matching in `_simulate_trade_with_stats` for GBPUSD/XAUUSD
- [ ] Diagnose why `wyckoff_distribution = 0` — standalone test of `_upthrust()`, `_sign_of_weakness()` on real data

## Next

- [ ] Add bearish exhaustion fallback — stochastic + EMA crossover when `wyckoff_distribution` unavailable
- [ ] Retrain ML quality filter (sklearn version mismatch — pickle load fails)
- [ ] Run 30k-bar backtest with all fixes + TP=3R, validate PF > 1.0 statistically
- [ ] Performance optimize backtest to handle 30k bars under 10 min
- [ ] Test TP at 2.5R as intermediate between 2R and 3R
- [ ] Increase confidence scorer variance (market_regime, ATR ratio, volume as inputs)
- [ ] Wire distribution-phase Wyckoff features into SMC_SUCCESSOR ML dataset

- [ ] Install dependencies: `pip install python-telegram-bot python-dotenv`
- [ ] Create Telegram bot via @BotFather and configure `.env`
- [ ] Test Telegram agent connectivity
- [ ] Switch provider from `local_python` to `opencode` when ready

- [ ] Increase `min_confidence` from 0.52 to 0.60 (if trade count adequate)
- [ ] Restrict LONG signals (require confluencia ≥ 6 or eliminate)
- [ ] Activate ML Quality Filter with GridSearchCV (after retrain)
- [ ] Wire displacement detection into pipeline (`detectors/displacement.py`)
- [ ] Wire premium/discount zones into pipeline (`detectors/zones.py`)
- [ ] Integrate SMC_SUCCESSOR agents with main pipeline (Fase 4)
- [ ] Retrain ML model on v4 dataset with walk-forward validation
- [ ] Performance benchmark on 500k bars

---

## Completed

- [x] Fase 0: Diagnosis and current state audit
- [x] Fase 1: PAC State Machine + Structural SL integration
- [x] Fase 2: Stochastic Exhaustion + Wyckoff + PAC EXHAUSTION_CONFIRMED
- [x] Fase 3: ML Expansion + Weighted Confluence Scoring + GridSearchCV
- [x] Multi-symbol dataset generation (7 pairs, M15)
- [x] V4 dataset schema (dropped `agent_decision_ml_probability`, added `year_month`)
- [x] Backtest 100k EURUSD M15 with all Fases 1-3 active
- [x] GitHub push with Fases 1-3
- [x] Telegram Remote Control Agent — automation/ module
- [x] Execution layer abstraction (OpenCode, Claude Code, Codex, local Python)
- [x] Telegram documentation (architecture, setup, security, commands)
- [x] .env.example configuration template
- [x] Autonomous startup workflow — `/agent` directory + opencode.json wiring
- [x] KOS (Knowledge Operating System) — `knowledge/` directory with architecture docs
- [x] Harness README — `SMC_SUCCESSOR/harness/README.md`
- [x] Wyckoff structured knowledge — `knowledge/references/wyckoff-theory.md`
- [x] Wyckoff implementation audit — `knowledge/learnings/wyckoff-implementation.md`
- [x] KOS inbox/outbox directories created
- [x] KOS theories/research/summaries + index.json
- [x] Wyckoff detector fix (dead code + distribution + markup/markdown)
- [x] Phase-aware Wyckoff filter in scalping_setup.py
- [x] apply_wyckoff_to_trend() in context_engine.py
