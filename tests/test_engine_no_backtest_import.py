"""B1 — Guarda la Ley arquitectónica: engine/ NUNCA importa ict_backtest/.

AST-scan de todo engine/ buscando `import ict_backtest` o `from ict_backtest`.
Solo cuentan IMPORTS REALES (no menciones en docstrings/strings). Debe dar 0.
"""

from __future__ import annotations

import ast
import pathlib

ENGINE = pathlib.Path(__file__).resolve().parent.parent / "engine"


def _real_backtest_imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "ict_backtest":
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "ict_backtest":
                hits.append(f"from {node.module} import ...")
    return hits


def test_engine_does_not_import_ict_backtest():
    offenders: dict[str, list[str]] = {}
    for p in sorted(ENGINE.rglob("*.py")):
        bad = _real_backtest_imports(p)
        if bad:
            offenders[str(p)] = bad
    assert not offenders, (
        "engine/ contiene imports reales a ict_backtest (viola la Ley "
        "arquitectónica): " + "; ".join(f"{k}: {v}" for k, v in offenders.items())
    )
