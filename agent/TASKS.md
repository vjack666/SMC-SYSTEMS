# TASKS.md — Task Tracking

> Update at end of every session.

---

## In Progress

*None*

---

## Next

- [ ] Create `knowledge/inbox/` and `knowledge/outbox/` for formal communication
- [ ] Migrate key learnings from `results/` into `knowledge/learnings/`
- [ ] Cross-reference `knowledge/decisions/` with `agent/DECISIONS.md`

- [ ] Install dependencies: `pip install python-telegram-bot python-dotenv`
- [ ] Create Telegram bot via @BotFather and configure `.env`
- [ ] Test Telegram agent connectivity
- [ ] Switch provider from `local_python` to `opencode` when ready

- [ ] Optimize TP from 2R to 1.5R to improve win rate
- [ ] Increase `min_confidence` from 0.52 to 0.60
- [ ] Restrict LONG signals (require confluencia ≥ 6 or eliminate)
- [ ] Activate ML Quality Filter with GridSearchCV
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
