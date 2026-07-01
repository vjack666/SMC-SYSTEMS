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
├── __main__.py              # CLI entry point
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
│   └── signal_smoke_fixture.yaml
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
│   └── risk_*.yaml          # Risk governor scenarios
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

1. Create a `ModuleAdapter` implementation in `smc_successor/adapters/`
2. Create a fixture YAML in `harness/fixtures/`
3. Create a scenario YAML in `harness/scenarios/`
4. Register the adapter in `harness/__main__.py`
5. Run: `python -m harness`

---

## Current Adapters

| Adapter | Module | Status |
|---------|--------|--------|
| `echo` | Echo test | ✅ All scenarios pass |
| `signal_pipeline` | Signal generation | ✅ All scenarios pass |
| `risk_governor` | Risk state machine | ✅ All scenarios pass |
| `backtest` | Backtest engine | ✅ All scenarios pass |

---

## Design Principles

- **Isolation** — Each scenario runs a single module with zero dependencies on other modules.
- **Determinism** — Given the same fixture, a module must produce the same output.
- **Subset assertion** — `expected` only checks specified keys; extra output keys are ignored.
- **Speed** — Harness scenarios complete in < 2ms each.
