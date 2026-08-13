"""Audit the permanent-engine/backtest boundary.

This is intentionally a read-only audit. It reports the remaining decision
modules under ``ict_backtest/`` and any forbidden reverse dependency from
``engine/``. A non-zero exit means the migration is incomplete and the task
must remain BLOCKED.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
BACKTEST = ROOT / "ict_backtest"

# These files are known decision-bearing surfaces (market logic: bias, structure,
# POI, BOS/CHOCH, setup, SL/TP, entry). They may only remain after becoming
# explicit shims (re-exporting engine.*) or moving their implementation into
# engine/. UI/checklist modules (rules, structure) and dead adapters are NOT
# listed here: they are presentation/feed concerns, not a second strategy
# (Ley: backtest may hold adapters/feed/metrics, never market decision logic).
DECISION_SURFACES = {
    "ict_backtest/market_structure.py",
    "ict_backtest/dealing_range.py",
    "ict_backtest/dealing_range_motor.py",
    "ict_backtest/po3_motor.py",
    "ict_backtest/plan_driver.py",
    "ict_backtest/plan_fsm.py",
    "ict_backtest/setups/ote.py",
}

# These are the only compatibility modules allowed to re-export permanent
# implementations. The list is deliberately small and reviewable.
#
# Todos los módulos aquí son SHIMs explícitos que re-exportan desde ``engine.*``
# (capa permanente del motor). Ninguno contiene lógica de decisión propia.
# Mantener esta lista sincronizada con cada migración HYP-002.
SHIM_FILES = {
    "ict_backtest/engine.py",
    "ict_backtest/sequence.py",
    "ict_backtest/data_feed.py",
    "ict_backtest/market_object.py",
    "ict_backtest/multitf_context.py",
    "ict_backtest/market_structure.py",
    "ict_backtest/dealing_range.py",
    "ict_backtest/dealing_range_motor.py",
    "ict_backtest/po3_motor.py",
    "ict_backtest/plan_attach.py",
    "ict_backtest/plan_driver.py",
    "ict_backtest/plan_fsm.py",
    "ict_backtest/setups/rr_map.py",
    "ict_backtest/setups/ote.py",
    "ict_backtest/setups/silver_bullet.py",
    "ict_backtest/setups/turtle_soup.py",
    "ict_backtest/v2/context_mtf.py",
}

# These modules may contain experimental detectors for isolated research
# tests, but they must not be imported by the active backtest path. They are
# not a source of production decisions.
EXPERIMENTAL_ONLY = {
    "ict_backtest/setups/breaker_block.py",
    "ict_backtest/setups/smart_money.py",
    "ict_backtest/setups/smt_divergence.py",
}


def _defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def main() -> int:
    violations: list[str] = []

    for path in sorted(ENGINE.rglob("*.py")):
        for module in _imports(path):
            if module == "ict_backtest" or module.startswith("ict_backtest."):
                rel = path.relative_to(ROOT).as_posix()
                violations.append(f"ENGINE_IMPORTS_BACKTEST: {rel} -> {module}")

    for rel in sorted(DECISION_SURFACES):
        path = ROOT / rel
        if not path.exists():
            continue
        if rel in SHIM_FILES:
            continue
        violations.append(f"DECISION_SURFACE_IN_BACKTEST: {rel}")

    facade = BACKTEST / "engine.py"
    if facade.exists():
        local_defs = _defined_names(facade)
        forbidden = local_defs & {
            "ICTSignal", "ICTTrade", "simulate_trade", "simulate_trade_with_context",
            "fill_entry_price", "calc_structural_sl", "_tp_liquidity",
        }
        for name in sorted(forbidden):
            violations.append(f"BACKTEST_ENGINE_IMPLEMENTATION: ict_backtest/engine.py::{name}")

    for path in sorted(BACKTEST.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in SHIM_FILES:
            continue
        for module in _imports(path):
            if module in {
                "ict_backtest.market_structure",
                "ict_backtest.dealing_range_motor",
                "ict_backtest.po3_motor",
                "ict_backtest.plan_driver",
                "ict_backtest.plan_fsm",
            }:
                violations.append(f"BACKTEST_DECISION_DEPENDENCY: {rel} -> {module}")

    # Experimental detectors are allowed only when explicitly exercised by
    # their own tests/research. A runtime import would turn them into a
    # second backtest motor.
    for path in sorted(BACKTEST.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in EXPERIMENTAL_ONLY:
            continue
        for module in _imports(path):
            for experimental in EXPERIMENTAL_ONLY:
                module_name = experimental[:-3].replace("/", ".")
                if module == module_name or module.startswith(module_name + "."):
                    violations.append(f"BACKTEST_EXPERIMENTAL_DEPENDENCY: {rel} -> {module}")

    if violations:
        print("MOTOR/BACKTEST BOUNDARY: BLOCKED")
        for violation in violations:
            print(f"- {violation}")
        print("Migrate implementation to engine/ or convert the module to an explicit shim.")
        return 1

    print("MOTOR/BACKTEST BOUNDARY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
