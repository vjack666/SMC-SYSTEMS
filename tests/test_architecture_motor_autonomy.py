"""Prueba arquitectonica: el MOTOR permanente es autonomo respecto de ict_backtest.

Garantiza el contrato M4: engine/ NUNCA importa ict_backtest/ (ni directa ni
indirectamente via detectors/). Si aparece engine -> ict_backtest, el flujo de
datos se invierte (backtest alimentando al motor) y esta prueba FALLA,
bloqueando la deriva antes de que el backtest se convierta en el tronco.

Tambien verifica que el backtest (ict_backtest/data_feed.build_features) es un
consumidor puro: reenvia a engine.market_features y no duplica logica.

No mide WR/PF/edge. Es una guarda de arquitectura.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
DETECTORS = ROOT / "detectors"


def _module_imports_ict_backtest(path: Path) -> list[str]:
    """Devuelve las lineas de import que referencian ict_backtest en `path`."""
    hits: list[str] = []
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # Si no parsea, inspeccion textual (fallback)
        for ln in src.splitlines():
            if "ict_backtest" in ln and ("import" in ln or "from" in ln):
                hits.append(ln.strip())
        return hits
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
    for sub in (ENGINE, DETECTORS):
        for p in sorted(sub.rglob("*.py")):
            # los __pycache__ no cuentan
            if "__pycache__" in str(p):
                continue
            hits = _module_imports_ict_backtest(p)
            # Ignora imports DENTRO de docstrings/comentarios: ast ya filtra solo
            # sentencias reales de import. Si hay hits en texto pero no en AST,
            # _module_imports_ict_backtest (fallback) los habria incluido; el AST
            # real es la fuente de verdad. Para mayor robustez, re-chequea que el
            # archivo no tenga import real (no docstring) via grep de sentencias.
            if hits:
                offenders[str(p.relative_to(ROOT))] = hits
    assert not offenders, (
        "engine/ o detectors/ importan ict_backtest (arquitectura rota):\n"
        + "\n".join(f"  {k}: {v}" for k, v in offenders.items())
    )


def test_ict_backtest_build_features_is_pure_consumer():
    """ict_backtest.data_feed.build_features reenvia a engine.market_features."""
    import importlib
    import engine.market_features as emf

    # Remueve de sys.modules para forzar reimport limpio del backtest
    for mod in list(sys.modules):
        if mod == "ict_backtest.data_feed" or mod.startswith("ict_backtest.data_feed."):
            del sys.modules[mod]
    import ict_backtest.data_feed as idf

    assert idf.build_features is emf.build_features, (
        "ict_backtest.data_feed.build_features no reenvia a engine.market_features"
    )
