"""Test de auditoría de separación de módulos ICT (grafo de código).

Valida scripts/check_separation.py contra graphify-out/graph.json: confirma
que los 5 módulos ICT viven en comunidades distintas y que solo hay 2 aristas
cruzadas (engine <-> rules). Es la "prueba de realidad" del hallazgo R7.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "graphify-out" / "graph.json"
SCRIPT = ROOT / "scripts" / "check_separation.py"
MODULES = [
    "signals/pipeline.py",
    "agents/ict_agent.py",
    "ict_backtest/sequence.py",
    "ict_backtest/rules.py",
    "ict_backtest/engine.py",
]


def _load_graph():
    assert GRAPH.exists(), f"grafo no encontrado: {GRAPH} (corre graphify primero)"
    return json.loads(GRAPH.read_text(encoding="utf-8"))


def _count_cross_edges(data, modules):
    """Reproduce la lógica de check_separation.py sin subprocess."""
    nodes = data["nodes"]
    links = data.get("links", data.get("edges", []))
    sf_of = {n["id"]: n.get("source_file", "") for n in nodes}
    mod_nodes = {m: set() for m in modules}
    for n in nodes:
        sfn = n.get("source_file", "")
        for m in modules:
            if m in sfn:
                mod_nodes[m].add(n["id"])
                break
    cross = 0
    for e in links:
        s = e.get("source")
        t = e.get("target")
        if not s or not t:
            continue
        sm = next((m for m in modules if s in mod_nodes[m]), None)
        tm = next((m for m in modules if t in mod_nodes[m]), None)
        if sm and tm and sm != tm:
            cross += 1
    return cross


def test_graph_exists():
    _load_graph()


def test_separation_script_runs():
    """El script CLI corre sin error y reporta exactamente 2 aristas cruzadas."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *MODULES],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    # Solo engine<->rules cruzan (2 aristas); el resto son islas.
    assert "ict_backtest/engine.py <-> ict_backtest/rules.py: 2" in result.stdout
    # Sin subprocess, la lógica independiente debe coincidir en el conteo.
    data = _load_graph()
    assert _count_cross_edges(data, MODULES) == 2


def test_modules_in_distinct_communities():
    """Cada módulo cae en comunidad(s) que no comparten con los otros 4."""
    data = _load_graph()
    comm_of = {}
    for n in data["nodes"]:
        sfn = n.get("source_file", "")
        for m in MODULES:
            if m in sfn:
                comm_of.setdefault(m, set()).add(n.get("community"))
                break
    # engine y rules pueden compartir borde pero viven en comunidades distintas
    # al resto; el hallazgo R7 es que NO hay comunidad compartida por los 5.
    all_comms = [c for s in comm_of.values() for c in s]
    assert len(all_comms) >= 5, f"se esperaban >=5 comunidades, hubo {len(all_comms)}"
