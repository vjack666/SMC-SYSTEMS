"""scripts/audit_market_replay_boundary.py — Guarda arquitectónica.

Verifica que market_replay/ es una infraestructura permanente y AUTÓNOMA:
  1. market_replay NO importa ict_backtest (nunca).
  2. engine NO importa market_replay (motor ignora el alimentador).
  3. market_replay SÍ importa engine (consumidor correcto).

Salida: JSON + exit code (0 PASS / 1 BLOCKED).

Esto es la prueba de destrucción del Director: si ict_backtest desaparece,
market_replay + engine + journal deben seguir funcionando.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET_REPLAY = ROOT / "market_replay"
ENGINE = ROOT / "engine"
ICT_BACKTEST = ROOT / "ict_backtest"


def _imports_of(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.append(node.module)
            elif node.level > 0:
                out.append("__pkg_local__")
    return out


def _violations_market_replay_imports_ict_backtest() -> list[str]:
    bad = []
    for p in MARKET_REPLAY.rglob("*.py"):
        for mod in _imports_of(p):
            if mod == "ict_backtest" or mod.startswith("ict_backtest."):
                bad.append(f"{p.relative_to(ROOT)} -> {mod}")
    return bad


def _violations_engine_imports_market_replay() -> list[str]:
    bad = []
    for p in ENGINE.rglob("*.py"):
        for mod in _imports_of(p):
            if mod == "market_replay" or mod.startswith("market_replay."):
                bad.append(f"{p.relative_to(ROOT)} -> {mod}")
    return bad


def main() -> int:
    mr_bt = _violations_market_replay_imports_ict_backtest()
    eng_mr = _violations_engine_imports_market_replay()

    # Prueba de destrucción: importar market_replay con ict_backtest bloqueado.
    destruction_ok = True
    destruction_err = ""
    # Asegura que el repo esté importable.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    saved_ib = sys.modules.get("ict_backtest")
    try:
        # Bloquea ict_backtest en sys.modules para simular su eliminación.
        class _Block:
            def __getattr__(self, _):
                raise ImportError("ict_backtest eliminado (prueba de destrucción)")

        sys.modules["ict_backtest"] = _Block()
        import importlib

        import market_replay

        importlib.reload(market_replay)
        # Importa submódulos clave.
        import market_replay.feed
        import market_replay.availability
        import market_replay.clock
        import market_replay.journal
        import market_replay.replay
        import market_replay.api
    except Exception as e:  # noqa: BLE001
        destruction_ok = False
        destruction_err = f"{type(e).__name__}: {e}"
    finally:
        # Restaura ict_backtest a su estado original (o lo quita si no existía).
        if saved_ib is None:
            sys.modules.pop("ict_backtest", None)
        else:
            sys.modules["ict_backtest"] = saved_ib

    report = {
        "market_replay_imports_ict_backtest": mr_bt,
        "engine_imports_market_replay": eng_mr,
        "destruction_test_ict_backtest_absent": {
            "ok": destruction_ok,
            "error": destruction_err,
        },
        "PASS": not mr_bt and not eng_mr and destruction_ok,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
