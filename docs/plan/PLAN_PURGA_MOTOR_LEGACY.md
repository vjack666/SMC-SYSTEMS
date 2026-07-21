# PLAN — Purga del motor de decisión LEGACY

**Estado:** Phase 0 DONE · Phase 1 READY  
**Fecha inventario:** 2026-07-21  
**Alcance Phase 0:** freeze + inventory only. **NO** delete, **NO** rewire ML/adapters, **NO** remove `legacy/`.

Autoridad previa: `docs/plan/R7_UNIFICACION_MOTOR.md` (R7 cerrado en path vivo; deuda `legacy/backtest` + `ml/dataset_builder` documentada).  
Conservación intencional: `docs/avances/BACKTEST_CLEANUP_2026-07-16.md` (legacy stack kept on purpose).

---

## 0. Freeze rule (OBLIGATORIO desde Phase 0)

### Qué está congelado

Nada **nuevo** puede importar el motor de **decisión** legacy:

| Prohibido en código nuevo | Motivo |
|---------------------------|--------|
| `from legacy.backtest...` / `import legacy.backtest...` | Motor de señales/simulación scalping legacy |
| `from backtest...` / `import backtest...` (path pre-move) | Mismo motor; imports rotos o vía `legacy/` cwd |
| `legacy.backtest.engine._build_signals_from_context` | Decision builder legacy |
| `legacy.backtest.engine._simulate_trade_with_stats` | Simulación legacy (no confudir con `ict_backtest.engine.simulate_trade`) |
| `legacy.backtest.run_combined_backtest` / `run_filter_diagnosis` | Orquestador backtest legacy |
| Nuevos call-sites de `signals.pipeline.build_scalping_context` como **fuente de trade decisions** | Pipeline de confluencia pre-R7 (otro decision path) |

### Qué SÍ se permite

| Permitido | Motivo |
|-----------|--------|
| `ict_backtest.canonical.evaluate_signals` / `latest_plan` | Única API de decisión ICT (PROTECT) |
| `ict_backtest.sequence.run_sequence` | Motor canónico event-sequence |
| `ict_backtest.engine` helpers (`simulate_trade`, `calc_structural_sl`, fill, TP) | Simulación compartida post-decisión, **no** dual decision path |
| Imports **existentes** listados en este inventario | Deuda congelada hasta Phase 2–4 rewire |
| `_data_legacy` / `data.load_frame` | **DATA only** — no es motor de decisión |
| `signals.po3` desde `ict_backtest` | Shared PO3 helpers, not the scalping checklist motor |

### Enforcement (lightweight)

Already exists: `scripts/check_separation.py` (graph island check; needs `graphify-out/graph.json`).

**Freeze grep (manual / CI-lite, no new CI required):** from repo root:

```bat
rg -n "from legacy\.backtest|import legacy\.backtest|from backtest\.|import backtest" --glob "*.py"
```

Expected hits after Phase 0 = **only** files in §1 tables below.  
Any **new** path not on the inventory = freeze violation → reject in review.

Optional follow-up (Phase 1+): a thin script `scripts/check_legacy_decision_freeze.py` that fails if a non-allowlisted file matches the patterns above. **Not built in Phase 0.**

---

## 1. Phase 0 inventory — import graph (evidence path:line)

### 1.1 Direct `legacy.backtest` / decision-motor consumers (outside `legacy/`)

| File | Evidence | Imports | Class |
|------|----------|---------|-------|
| `ml/dataset_builder.py` | `:14` | `_build_signals_from_context`, `_simulate_trade_with_stats` from `legacy.backtest.engine`; also `build_scalping_context` (`:18`) | **LIVE_PROD** (ML train path) |
| `scripts/edge_diagnosis/run.py` | `:54` | same engine symbols + `build_scalping_context` | **SCRIPT_DIAG** |
| `scripts/run_fundednext_compliance.py` | `:23` | `CombinedBacktestConfig`, `run_combined_backtest` | **SCRIPT_DIAG** |
| `scripts/_measure_orchestrator.py` | `:25` | `CombinedBacktestConfig` only (+ pipeline context) | **SCRIPT_DIAG** |
| `adapters/__init__.py` | `:4-6` | re-exports `legacy.adapters.*` + `legacy.paper_trading.harness_adapter` | **LIVE_PROD** (harness facade) |

### 1.2 Pre-move `from backtest...` (broken or legacy-cwd only)

These assume package name `backtest` (pyproject still lists `backtest*` but tree lives under `legacy/backtest/`).

| File | Evidence | Class | Note |
|------|----------|-------|------|
| `scripts/_measure_ml_filter.py` | `:27-37` | **SCRIPT_DIAG** | likely **dead/broken** at repo root |
| `scripts/_run_ml_iso.py` | `:20` | **SCRIPT_DIAG** | same |
| `scripts/_smc_measure_ml_gate.py` | `:16-21` | **SCRIPT_DIAG** | same |
| `scripts/download_data.py` | `:326` | **SCRIPT_DIAG** (string only) | print hint with stale import |
| `legacy/tests/test_e2e_backtest.py` | `:6` | **TEST_LEGACY** | runs under legacy path assumptions |
| `legacy/tests/test_backtest_engine.py` | `:10`, `:73+` | **TEST_LEGACY** | |
| `legacy/scripts/_smc_quick_backtest.py` | `:18` | **SCRIPT_DIAG** | internal legacy |
| `legacy/scripts/audit_problems.py` | `:37` | **SCRIPT_DIAG** | |
| `legacy/backtest/real/__main__.py` | `:10-14` | **TEST_LEGACY** / internal CLI | |
| `legacy/orchestration/backtest_validation_graph.py` | `:12-21` | **TEST_LEGACY** / harness | `from backtest.validation...` |
| `legacy/adapters/backtest_adapter.py` | `:8` / `:12` | **LIVE_PROD** facade | dual import try/except |
| `legacy/adapters/mt5_ea_harness.py` | `:6` / `:9` | **LIVE_PROD** facade | dual import |

### 1.3 `signals.pipeline` decision path (build_scalping_context / signals)

Not the same package as `legacy.backtest`, but it **is** the pre-R7 confluence decision motor that legacy engine wraps.

| File | Evidence | Class |
|------|----------|-------|
| `signals/pipeline.py` | `:89` `build_scalping_context`, `:410` `build_scalping_signals` | **LIVE_PROD** (motor itself) |
| `signals/__init__.py` | `:1-5` re-export | **LIVE_PROD** surface |
| `legacy/backtest/engine.py` | `:27`, `:390`, `:407`, `:580` | **LIVE_PROD** (core legacy engine) |
| `ml/dataset_builder.py` | `:18`, `:133` | **LIVE_PROD** |
| `paper_trading/runner.py` | `:26`, `:530` | **LIVE_PROD** (bot; not observador daily) |
| `adapters/signal_adapter.py` | `:6`, `:21` | **LIVE_PROD** (harness) |
| `scripts/edge_diagnosis/run.py` | `:53`, `:525+` | **SCRIPT_DIAG** |
| `scripts/edge_diagnosis/_precache.py` | `:21`, `:92` | **SCRIPT_DIAG** |
| `scripts/edge_diagnosis/_precache_variants.py` | `:21`, `:44` | **SCRIPT_DIAG** |
| `scripts/compare_choch_bos_confirm.py` | `:23`, `:77` | **SCRIPT_DIAG** |
| `scripts/_measure_orchestrator.py` | `:26-27`, `:56+` | **SCRIPT_DIAG** |
| `scripts/_measure_ml_filter.py` | `:39-40` | **SCRIPT_DIAG** |
| `scripts/_smc_measure_ml_gate.py` | `:27`, `:57` | **SCRIPT_DIAG** |
| `scripts/run_paper_trading.py` | `:25` (config only) | **LIVE_PROD** entry (bot) |
| `scripts/run_live_trading.py` | `:10` (config only) | **LIVE_PROD** entry (bot) |
| `scripts/run_ml_pipeline.py` | `:142` (config) | **LIVE_PROD** entry (ML) |
| `scripts/run_walkforward_validation.py` | `:159` | **SCRIPT_DIAG** / ML |
| `scripts/generate_large_synthetic.py` | `:11-12` | **SCRIPT_DIAG** |
| `legacy/scripts/audit_problems.py` | `:33`, `:84` | **SCRIPT_DIAG** |
| `legacy/backtest/real/__main__.py` | `:17` | **TEST_LEGACY** / CLI |
| `tests/test_pipeline_integration.py` | `:8` | **TEST_LEGACY** |
| `tests/test_signal_pipeline.py` | `:10`, `:41` | **TEST_LEGACY** |
| `tests/test_runner.py` | `:14`, patches | **TEST_LEGACY** (paper runner) |
| `tests/test_ml_inference.py` | `:10` ScalpingConfig | **TEST_LEGACY** (config only) |

### 1.4 Internal `legacy/*` graph (package self-use — not external)

| Area | Role | Class |
|------|------|-------|
| `legacy/backtest/engine.py` | Decision + sim + `run_combined_backtest` | core DEBT motor |
| `legacy/backtest/__init__.py` | public exports | surface |
| `legacy/backtest/validation/*` | MT5 compare harness | TEST_LEGACY / harness |
| `legacy/adapters/*` | harness adapters | LIVE_PROD facade via `adapters/__init__` |
| `legacy/harness/*` | scenarios/fixtures | TEST_LEGACY |
| `legacy/paper_trading/harness_adapter.py` | smoke stub | harness |
| `legacy/orchestration/*` | langgraph validation | harness |
| `legacy/tests/*` | unit/e2e legacy | **TEST_LEGACY** |
| `legacy/scripts/*` | one-shot audits | **SCRIPT_DIAG** |

### 1.5 DATA_ONLY — do NOT treat as decision motor

| File | Evidence | Notes |
|------|----------|-------|
| `_data_legacy.py` | root module | MT5 download / load parquet |
| `data/__init__.py` | `:5` `from _data_legacy import apply_time_window, load_frame` | facade |
| `adapters/feature_enrichment_adapter.py` | `:9` | load only |
| `scripts/update_mt5_data.py` | `:103` | download |
| `scripts/download_data.py` / `download_multiyear.py` / `download_h1_mtf.py` | MT5_TERMINAL_PATH / format notes | download |
| `scripts/live_market_read.py` | `:16` | load + enrich (not legacy decision) |
| `scripts/run_walkforward_validation.py` | `:112` path only | |
| `tests/test_data_legacy.py` | full file | DATA tests |
| `legacy/orchestration/backtest_validation_graph.py` | `:22` load_frame | data feed for validation graph |

### 1.6 ALREADY_CANONICAL — PROTECT (never break in purge)

| File / API | Evidence | Role |
|------------|----------|------|
| `ict_backtest/canonical.py` | module docstring; `evaluate_signals`, `latest_plan` | single decision API |
| `ict_backtest/sequence.py` | `run_sequence` | event-sequence motor |
| `ict_backtest/engine.py` | helpers only for sim/SL/TP | post-decision helpers |
| `ict_backtest/run_backtest.py` | `:68-69`, `:118` thin → canonical | backtest runner |
| `ict_backtest/__init__.py` | exports canonical | package surface |
| `app_observador/core/engine.py` | `:237`, `:251` `latest_plan` | live observador cycle |
| `app_observador/core/position_sizer_bridge.py` | prefers `result["canonical"]` | UI sizing |
| `agents/ict_agent.py` | docstring + column reader; **no** geometry reimpl | R7 consumer |
| Tests under `tests/test_*` that call `evaluate_signals` / `latest_plan` | many | regression for canonical |

**Naming trap:** `ict_backtest.v2.strategy_legacy` / `run_legacy_subset` = **alias of sequence packaging** (coverage mode), **not** `legacy/backtest`. Do not delete as part of this purge.

---

## 2. Inventory counts (Phase 0)

Counts are **consumer files / surfaces** classified for purge planning (not LOC).

| Class | Count | Meaning |
|-------|------:|---------|
| **LIVE_PROD** | **10** | Must rewire or explicitly retire before deleting motor |
| **SCRIPT_DIAG** | **14** | Safe kill or late rewire |
| **TEST_LEGACY** | **12+** | Legacy tests/harness (delete with package or quarantine) |
| **DATA_ONLY** | **9** | Keep; not decision motor |
| **ALREADY_CANONICAL** | **8** core surfaces | Protect |

### LIVE_PROD detail (must rewire before delete)

1. `legacy/backtest/engine.py` — motor core  
2. `signals/pipeline.py` (+ `signals/__init__.py`) — confluence decision  
3. `ml/dataset_builder.py` — ML labels/trades from legacy  
4. `paper_trading/runner.py` — bot loop  
5. `adapters/signal_adapter.py` — harness signal path  
6. `adapters/__init__.py` — re-export legacy adapters  
7. `legacy/adapters/backtest_adapter.py`  
8. `legacy/adapters/mt5_ea_harness.py`  
9. `scripts/run_paper_trading.py` / `scripts/run_live_trading.py` (entries)  
10. `scripts/run_ml_pipeline.py` (entry that assumes ML+paper stack)

### SCRIPT_DIAG detail

1. `scripts/edge_diagnosis/run.py`  
2. `scripts/edge_diagnosis/_precache.py`  
3. `scripts/edge_diagnosis/_precache_variants.py`  
4. `scripts/run_fundednext_compliance.py`  
5. `scripts/_measure_orchestrator.py`  
6. `scripts/_measure_ml_filter.py` (**broken import** `from backtest`)  
7. `scripts/_run_ml_iso.py` (**broken**)  
8. `scripts/_smc_measure_ml_gate.py` (**broken**)  
9. `scripts/compare_choch_bos_confirm.py`  
10. `scripts/generate_large_synthetic.py`  
11. `scripts/run_walkforward_validation.py` (partial)  
12. `legacy/scripts/_smc_quick_backtest.py`  
13. `legacy/scripts/audit_problems.py`  
14. `scripts/download_data.py` (stale print string only)

---

## 3. Phase 1 candidates — dead / safe-kill scripts

Criteria: one-shot, campaign finished, broken import, **no** production entry, only consumers of legacy decision motor.

| Priority | Path | Why safe-ish |
|----------|------|----------------|
| P0 | `scripts/_measure_ml_filter.py` | broken `from backtest`; measure one-shot |
| P0 | `scripts/_run_ml_iso.py` | broken `from backtest`; harness fixture runner one-shot |
| P0 | `scripts/_smc_measure_ml_gate.py` | broken `from backtest`; measure one-shot |
| P1 | `scripts/_measure_orchestrator.py` | one-shot orchestrator delta; uses `legacy.backtest` config only |
| P1 | `legacy/scripts/_smc_quick_backtest.py` | internal quick BT |
| P1 | `legacy/scripts/audit_problems.py` | static audit one-shot |
| P2 | `scripts/edge_diagnosis/*` | campaign completed (results under `results/edge_diagnosis*`); README marks Edge Diagnosis done |
| P2 | `scripts/run_fundednext_compliance.py` | compliance report script; rewire or archive |
| P2 | `scripts/compare_choch_bos_confirm.py` | ablation-style filter weight script |
| P3 | JSON/log leftovers under `scripts/_ml_*.json`, `_orchestrator_measure.json` | artifacts, not code |

**Do not Phase-1-delete without rewire:** `ml/dataset_builder.py`, `paper_trading/runner.py`, `adapters/*`, `signals/pipeline.py`, `legacy/backtest/*` package, harness.

---

## 4. Protect list vs delete candidates

### PROTECT (never break)

- `ict_backtest/canonical.py`, `sequence.py`, engine **helpers**, `run_backtest.py`  
- `app_observador/**` path that calls `latest_plan` / displays `canonical`  
- `agents/ict_agent.py` (column reader)  
- `_data_legacy.py` + `data/` load path  
- Daily observador stack: `scripts/loop_analisis.py`, `rutina_eurusd.py`, `vigilante_riesgo.py`, `run_app.py` (do not entangle with legacy decision purge)

### DELETE candidates (later phases only)

| Phase | Target |
|-------|--------|
| 1 | Dead/broken measure scripts (§3 P0–P1) |
| 2 | Edge diagnosis suite + fundednext_compliance if archived |
| 3 | Rewire `ml/dataset_builder` → canonical + `ict_backtest.engine.simulate_trade` |
| 4 | Rewire or retire `paper_trading` / `signal_adapter` / harness backtest adapter |
| 5 | Remove `legacy/backtest` package + `legacy/tests` + freeze allowlist shrink; update `pyproject.toml` (`backtest*` → remove) |

---

## 5. Hand-off contract — Phase 1–5 agents

### Shared rules (all phases)

1. **No commit/push** without explicit user OK (project rule).  
2. **Never** break PROTECT list.  
3. **No new** imports of frozen decision motor (§0).  
4. Prefer delete of **unused scripts** before touching LIVE_PROD.  
5. Update this plan’s status section when a phase completes.  
6. Artifacts language: English or neutral Spanish; identifiers English.

### Phase 1 — agent-scripts (READY)

- **May touch:** `scripts/_measure_*`, `scripts/_run_ml_iso.py`, `scripts/_smc_measure_ml_gate.py`, `legacy/scripts/*` one-shots, optional archive note under `docs/avances/`.  
- **May not touch:** `ml/`, `paper_trading/`, `adapters/`, `signals/pipeline.py`, `legacy/backtest/engine.py`, `ict_backtest/`, `app_observador/`.  
- **Done when:** P0 broken scripts removed or quarantined; freeze grep allowlist updated; no production path change.

### Phase 2 — agent-diag-archive

- **May touch:** `scripts/edge_diagnosis/`, `scripts/run_fundednext_compliance.py`, `scripts/compare_choch_bos_confirm.py`, related bats; docs note that metrics live in `docs/METRICS_CANON.md` / results archives.  
- **May not touch:** LIVE_PROD rewire targets.  
- **Done when:** diag scripts gone or clearly marked ARCHIVE; results retained.

### Phase 3 — agent-ml-rewire

- **May touch:** `ml/dataset_builder.py` (+ tests for dataset build).  
- **Must:** generate labels/trades via `ict_backtest.canonical.evaluate_signals` (or documented thin wrapper) + canonical sim helpers — **not** `_build_signals_from_context`.  
- **May not touch:** delete of `legacy/backtest` until Phase 5.  
- **Done when:** no `legacy.backtest` import in `ml/`.

### Phase 4 — agent-adapters-paper

- **May touch:** `paper_trading/runner.py`, `adapters/signal_adapter.py`, `adapters/__init__.py`, harness adapters under `legacy/adapters/` (rewire or stub).  
- **Decision required:** retire bot path vs rewire to canonical (product choice).  
- **May not touch:** observador canonical path.  
- **Done when:** no production import of legacy decision motor outside `legacy/` package itself.

### Phase 5 — agent-delete-legacy-package

- **May touch:** delete/quarantine `legacy/backtest`, orphan harness, `legacy/tests`, pyproject `backtest*`, freeze allowlist empty for decision motor.  
- **Prerequisite:** Phase 3–4 green; freeze grep only hits none (or intentional stubs).  
- **Done when:** package gone; CI/grep clean; R7 debt H2/H3 closed in docs.

---

## 6. Packaging / path debt (non-decision but relevant)

| Item | Evidence | Note |
|------|----------|------|
| `pyproject.toml` packages | `:31` includes `backtest*` | tree is `legacy/backtest/` — setuptools drift |
| Scripts `from backtest` | §1.2 | break unless cwd/sys.path points into `legacy/` |
| Root `harness/` | mostly empty + README | real harness under `legacy/harness/` |

Phase 1 may document; Phase 5 must fix package metadata.

---

## 7. Relationship to R7

R7 closed the **live** decision path on `canonical`/`sequence`.  
This purge plan closes the **documented debt** (H2/H3 in R7):

- H2 `legacy/backtest/engine.py`  
- H3 `ml/dataset_builder.py` still on legacy  

Phase 0 does **not** claim single-motor purity repo-wide — only freezes growth of debt.

---

## 8. Status

| Phase | Status |
|-------|--------|
| **0 Freeze + inventory** | **DONE** (2026-07-21) |
| **1 Dead scripts** | **DONE** (2026-07-21) |
| **2 Diag archive** | **DONE** (2026-07-21) |
| **3 ML rewire** | **DONE** (2026-07-21) |
|| **4 Delete package** | **DONE** (2026-07-21) — backup: `C:\Users\v_jac\Desktop\legacy_smc_backup\` |
|| 5 cierre / freeze | **DONE** (2026-07-21) — backup: `C:\Users\v_jac\Desktop\legacy_smc_backup\` |

**Next recommended:** `phase1-agent-scripts`
