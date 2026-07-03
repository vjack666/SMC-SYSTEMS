# Harness — Scenario-Based Testing Framework

> Every future module must be introduced through the harness first.

---

## Purpose

The Harness provides isolated, scenario-driven validation for all SMC_SUCCESSOR modules. It enforces a **harness-first** development workflow where new code is tested in isolation before integration.

---

## Architecture

```
harness/
├── __init__.py              # Package marker
├── __main__.py              # CLI entry point + 10 adapter registrations
├── contracts.py             # Core types: Scenario, ScenarioResult, ModuleAdapter
├── assertions/
│   └── core.py              # Expected-output assertion engine
├── fixtures/
│   ├── __init__.py
│   ├── loader.py            # YAML fixture loader
│   ├── echo_fixture.yaml
│   ├── risk_smoke_fixture.yaml
│   ├── risk_caution_fixture.yaml
│   ├── risk_defensive_fixture.yaml
│   ├── risk_lockdown_fixture.yaml
│   ├── signal_smoke_fixture.yaml
│   ├── feature_enrichment_smoke.yaml
│   ├── mt5_bridge_smoke.yaml
│   ├── mt5_ea_smoke.yaml
│   ├── langgraph_validation_smoke.yaml
│   ├── monitoring_smoke.yaml
│   └── governance_smoke.yaml
├── metrics/
│   ├── __init__.py
│   └── collector.py         # Runtime metric collection
├── reports/
│   ├── __init__.py
│   ├── json_report.py       # JSON report writer
│   └── out/                 # Generated reports
├── runners/
│   ├── __init__.py
│   └── scenario_runner.py   # Scenario execution engine
├── scenarios/
│   ├── __init__.py
│   ├── loader.py            # YAML scenario loader
│   ├── echo_smoke.yaml
│   ├── signal_smoke.yaml
│   ├── risk_normal.yaml
│   ├── risk_caution.yaml
│   ├── risk_defensive.yaml
│   ├── risk_lockdown.yaml
│   ├── feature_enrichment_smoke.yaml
│   ├── mt5_bridge_smoke.yaml
│   ├── mt5_ea_smoke.yaml
│   ├── langgraph_validation_smoke.yaml
│   ├── monitoring_smoke.yaml
│   └── governance_smoke.yaml
└── validators/
    ├── __init__.py
    └── scenario_validator.py # Pre-run scenario validation
```

---

## Core Concepts

### ModuleAdapter Protocol

Every testable module must implement `ModuleAdapter`:

```python
class ModuleAdapter(Protocol):
    name: str
    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]: ...
```

### Scenario

A YAML file defining:
- `name` — Test name
- `module` — Which adapter to use
- `fixture` — Data/parameters for the module
- `expected` — Expected output (asserted via subset comparison)
- `tags` — Metadata for filtering

### Fixture

A YAML file providing:
- `events` — Input events for the module
- `parameters` — Configuration parameters

---

## Usage

```bash
# Run all scenarios
python -m harness

# Run specific adapter scenarios
python -m harness --adapters echo,risk_governor

# Custom report path
python -m harness --report results/harness_report.json
```

---

## Adding a New Module

1. Create a `ModuleAdapter` implementation in `adapters/`
2. Create a fixture YAML in `harness/fixtures/`
3. Create a scenario YAML in `harness/scenarios/`
4. Register the adapter in `harness/__main__.py`
5. Run: `python -m harness`

---

## Current Adapters

| Adapter | Module | Scenarios | Status |
|---------|--------|-----------|--------|
| `echo` | Echo test — inline adapter | 1 | ✅ All pass |
| `signal_pipeline` | Signal generation pipeline | 1 | ✅ All pass |
| `risk_governor` | Risk state machine (NORMAL/CAUTION/DEFENSIVE/LOCKDOWN) | 4 | ✅ All pass |
| `backtest` | Backtest engine | 0 | ⚠️ No scenarios yet |
| `feature_enrichment` | Feature pipeline (liquidity sweeps, displacement, zones, regime) | 1 | ✅ Pass (19s) |
| `mt5_bridge` | ZeroMQ bridge (exporter + receiver) | 1 | ✅ Built |
| `mt5_ea` | MQL5 EA simulation | 1 | ✅ Built |
| `langgraph_validation` | LangGraph 7-node validation graph | 1 | ✅ Built |
| `monitoring` | Production monitoring (drift, alerts, equity) | 1 | ✅ Built |
| `governance` | Governance (model registry, retraining, reports) | 1 | ✅ Built |

---

## Design Principles

- **Isolation** — Each scenario runs a single module with zero dependencies on other modules.
- **Determinism** — Given the same fixture, a module must produce the same output.
- **Subset assertion** — `expected` only checks specified keys; extra output keys are ignored.
- **Speed** — Harness scenarios complete in < 2ms each (except feature_enrichment which reads real data).
