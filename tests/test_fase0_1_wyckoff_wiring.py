"""RED: fase_wyckoff_m15.fase_actual() debe devolver la fase Wyckoff real
(phase_es en el set conocido), SIN el error de API vieja
`StructureConfig got unexpected keyword argument 'atr_period'`.

Esto es el call-site real: el motor del dashboard (engine.run_cycle) llama
fase_wyckoff_m15.fase_actual() para pintar el MARKET STATE. Si explota,
el dashboard muestra "(no disponible)". El test prueba que el fix deja
la fase viva con datos reales.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_KNOWN_PHASES = {
    "ACUMULACION", "ACUMULACION (temprana)", "ACUMULACION (tardia)",
    "MARKUP (subida)", "DISTRIBUCION", "DISTRIBUCION (temprana)",
    "DISTRIBUCION (tardia)", "MARKDOWN (bajada)", "INDEFINIDA",
}


def test_fase_actual_returns_real_wyckoff_phase():
    """fase_actual() no debe lanzar TypeError por atr_period y debe devolver
    una fase del set conocido (MARKET STATE vivo)."""
    mod = _load_module("fase_wyckoff_m15", ROOT / "scripts" / "fase_wyckoff_m15.py")
    # fase_actual() lee data/raw/EURUSD_M15.parquet (datos reales, deterministico)
    r = mod.fase_actual("EURUSD", "M15")
    assert isinstance(r, dict)
    assert "phase_es" in r
    assert r["phase_es"] in _KNOWN_PHASES, f"Fase inesperada: {r.get('phase_es')}"
    # el script ya no pasa atr_period a StructureConfig
    src = (ROOT / "scripts" / "fase_wyckoff_m15.py").read_text(encoding="utf-8")
    assert "atr_period=" not in src, "Queda atr_period en StructureConfig"


def test_fase_actual_bias_and_confidence_present():
    mod = _load_module("fase_wyckoff_m15", ROOT / "scripts" / "fase_wyckoff_m15.py")
    r = mod.fase_actual("EURUSD", "M15")
    assert "bias" in r
    assert "confidence" in r
    assert 0.0 <= float(r["confidence"]) <= 1.0
