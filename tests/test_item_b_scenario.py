from __future__ import annotations

"""Item B scenario gate — verifies the new YAMLs load via the real harness
loaders and that assert_expected_subset behaves as a change-detector:

- BEFORE the production diff (adapter exposes only aggregated `metrics`):
  the gate must FAIL (missing `metrics_by_symbol` / `metrics_by_symbol_oos`).
- AFTER the production diff (adapter exposes both per-symbol keys):
  the gate must PASS.

No backtest is executed here, so this stays fast and MT5-free.
"""

from pathlib import Path

from harness.assertions.core import assert_expected_subset
from harness.fixtures.loader import load_fixture
from harness.scenarios.loader import load_scenario

HARNESS_SCENARIOS = Path(__file__).resolve().parent.parent / "harness" / "scenarios"
SYMBOLS = ["EURUSD", "GBPUSD", "NZDUSD", "USDCHF"]


def _adapter_output() -> dict:
    return {
        "module": "backtest",
        "status": "ok",
        "mode": "backtest",
        "metrics": {},
        "total_trades": 91,
    }


def test_item_b_scenario_and_fixture_load() -> None:
    scn = load_scenario(HARNESS_SCENARIOS / "backtest_symbol_breakdown.yaml")
    assert scn.module == "backtest"
    assert set(scn.expected.keys()) >= {"metrics_by_symbol", "metrics_by_symbol_oos"}

    fix = load_fixture("backtest_symbol_breakdown_fixture.yaml")
    assert fix.get("parameters", {}).get("mode") == "backtest"
    assert fix["parameters"]["config"]["walk_forward"] is True


def test_item_b_gate_fails_without_production_diff() -> None:
    scn = load_scenario(HARNESS_SCENARIOS / "backtest_symbol_breakdown.yaml")
    errors = assert_expected_subset(_adapter_output(), scn.expected)
    assert errors, "gate should FAIL before the production diff is applied"
    assert any("metrics_by_symbol" in e for e in errors)


def test_item_b_gate_passes_after_production_diff() -> None:
    scn = load_scenario(HARNESS_SCENARIOS / "backtest_symbol_breakdown.yaml")
    out = _adapter_output()
    out["metrics_by_symbol"] = {s: {} for s in SYMBOLS}
    out["metrics_by_symbol_oos"] = {s: {} for s in SYMBOLS}
    errors = assert_expected_subset(out, scn.expected)
    assert errors == []
