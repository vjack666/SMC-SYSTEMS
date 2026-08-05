"""tests/test_labels_isolation.py — B4 (Ley 12 / Ley 1).

Verifica el contrato anti-look-ahead de la separación de etiquetas futuras:

  (a) AST: el ÚNICO archivo de `engine/` autorizado a usar slicing `[i + 1 :]`
      (mirar el futuro) es `engine/labels.py`. Ningún otro archivo de engine/
      puede contener ese patrón.

  (b) Invariancia causal: correr `detect_market_structure` sobre un DataFrame
      COMPLETO y sobre el MISMO DataFrame TRUNCADO en la barra `i` debe
      producir columnas de DECISIÓN idénticas hasta `i`. Las etiquetas de
      desenlace (`label_*`) solo se calculan al final y no alimentan la
      decisión, por lo que truncar el futuro no cambia lo decidido hasta `i`.
"""

from __future__ import annotations

import ast
import pathlib

import numpy as np
import pandas as pd
import pytest

from engine.bos.structure import detect_market_structure
from engine.bias.narrative import _swing_points

ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1] / "engine"


def _uses_future_slice(path: pathlib.Path) -> list[int]:
    """Devuelve las líneas donde aparece slicing `[i + 1 :]` (o equivalente)."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            s = node.slice
            # Patrón: [i + 1 : ...]  (slice con lower = BinOp(i, Add, 1))
            if isinstance(s, ast.Slice) and s.lower is not None:
                low = s.lower
                if isinstance(low, ast.BinOp) and isinstance(low.op, ast.Add):
                    if isinstance(low.right, ast.Constant) and low.right.value == 1:
                        hits.append(node.lineno)
    return hits


def test_only_labels_module_looks_future():
    """(a) AST: solo engine/labels.py puede mirar i+1:."""
    offenders = []
    for p in ENGINE_ROOT.rglob("*.py"):
        if p.name == "labels.py":
            continue
        lines = _uses_future_slice(p)
        if lines:
            offenders.append((p.name, lines))
    assert not offenders, (
        f"Engine modules con slicing futuro no autorizado: {offenders}"
    )

    # Y labels.py SÍ lo usa (la autorización existe).
    labels_py = ENGINE_ROOT / "labels.py"
    assert labels_py.exists()
    assert _uses_future_slice(labels_py), "labels.py debe mirar i+1:"


def _make_frame(n: int = 80, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Caminata aleatoria suave para generar swings/estructura.
    base = 1.0 + np.cumsum(rng.normal(0, 2e-4, n))
    times = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    high = base + np.abs(rng.normal(0, 1e-4, n))
    low = base - np.abs(rng.normal(0, 1e-4, n))
    return pd.DataFrame(
        {
            "time": times,
            "open": base,
            "high": high,
            "low": low,
            "close": base + rng.normal(0, 1e-4, n),
            "volume": 100.0,
        }
    )


# Columnas de DECISIÓN que deben ser idénticas hasta i bajo truncado.
# Se excluyen a propósito las columnas que MIRAN EL FUTURO (labels.py /
# confirm_score): bos_discard_reason, choch_discard_reason, bos_quality_score,
# bos_real. Esas son etiquetas/score DESCRIPTIVOS del desenlace, no deciden la
# estructura. La decisión vive en _consecutive_break + presente/pasado.
DECISION_COLS = (
    "swing_high", "swing_low", "swing_label",
    "bos_dir", "bos_level", "bos_status",
    "choch_dir", "choch_status",
    "mss_dir", "trend",
)


def test_causal_invariance_under_truncation():
    """(b) Truncar el DataFrame en i no cambia la decisión hasta i."""
    full = detect_market_structure(_make_frame())
    fcols = {c: full.frame[c].to_numpy() for c in DECISION_COLS}

    # Probamos varios puntos de corte.
    for i in range(5, len(full.frame) - 5, 17):
        trunc = full.frame.iloc[: i + 1].reset_index(drop=True)
        t = detect_market_structure(trunc)
        tcols = {c: t.frame[c].to_numpy() for c in DECISION_COLS}
        for c in DECISION_COLS:
            a = pd.Series(fcols[c][: i + 1])
            b = pd.Series(tcols[c])
            same = bool(a.equals(b))
            assert same, f"decisión cambió en columna {c} al truncar en i={i}"
