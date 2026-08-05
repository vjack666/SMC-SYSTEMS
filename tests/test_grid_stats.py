"""Tests de ict_backtest/diagnostics/grid_stats.py.

Cubre las dos deudas tecnicas de la auditoria R6:
  DEUDA A — cap roto (sesgo por confianza) => cap_signals_unbiased.
  DEUDA B — DSR/PBO no cableados en la grilla 168 => compute_grid_overfitting.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ict_backtest.diagnostics.grid_stats import (
    GridOverfittingReport,
    cap_signals_unbiased,
    compute_grid_overfitting,
)

_ROOT = Path(__file__).resolve().parent.parent
_FULL_RESULTS = _ROOT / "results" / "edge_diagnosis" / "full_results.json"


# --------------------------------------------------------------------------
# DEUDA A — cap roto
# --------------------------------------------------------------------------
class TestCapSignalsUnbiased:
    def test_no_cap_when_under_limit(self) -> None:
        sigs = [{"time": i, "confidence": 0.5} for i in range(10)]
        out = cap_signals_unbiased(sigs, max_signals=100)
        assert len(out) == 10

    def test_caps_to_limit(self) -> None:
        sigs = [{"time": i, "confidence": 0.5} for i in range(10000)]
        out = cap_signals_unbiased(sigs, max_signals=3000)
        assert len(out) <= 3000
        assert len(out) >= 2990  # submuestreo uniforme, casi exacto

    def test_preserves_time_span(self) -> None:
        """El cap uniforme conserva el primer y ultimo evento (no recorta la cola)."""
        sigs = [{"time": i, "confidence": (i % 7) / 7.0} for i in range(10000)]
        out = cap_signals_unbiased(sigs, max_signals=3000)
        times = [s["time"] for s in out]
        assert times[0] == 0
        assert times[-1] == 9999

    def test_no_confidence_selection_bias(self) -> None:
        """CLAVE (fix del cap roto): la confianza media del subset NO debe estar
        inflada respecto al universo. El cap viejo (argsort(-conf)[:N]) daba una
        media MUY superior; el uniforme la mantiene ~igual."""
        rng = np.random.default_rng(0)
        confs = rng.random(10000)
        sigs = [{"time": i, "confidence": float(confs[i])} for i in range(10000)]
        out = cap_signals_unbiased(sigs, max_signals=3000)
        mean_all = float(np.mean(confs))
        mean_sub = float(np.mean([s["confidence"] for s in out]))
        assert abs(mean_sub - mean_all) < 0.03  # sin sesgo

    def test_works_with_objects(self) -> None:
        class Sig:
            def __init__(self, t: int, c: float) -> None:
                self.time = t
                self.confidence = c

        sigs = [Sig(i, 0.5) for i in range(5000)]
        out = cap_signals_unbiased(sigs, max_signals=1000)
        assert len(out) <= 1000
        assert out[0].time == 0

    def test_invalid_max_raises(self) -> None:
        with pytest.raises(ValueError):
            cap_signals_unbiased([{"time": 1}], max_signals=0)


# --------------------------------------------------------------------------
# DEUDA B — DSR/PBO cableados en la grilla 168
# --------------------------------------------------------------------------
def _synthetic_grid(n_symbols: int = 8, n_variants: int = 21, seed: int = 1) -> list[dict]:
    rng = np.random.default_rng(seed)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    variants = [f"var{i}" for i in range(n_variants)]
    grid = []
    for s in symbols:
        for v in variants:
            grid.append(
                {
                    "symbol": s,
                    "variant": v,
                    "oos": {"sharpe": float(rng.normal(0.2, 1.0)), "n": 200},
                    "is": {"sharpe": float(rng.normal(0.3, 1.0)), "n": 500},
                    "insufficient": False,
                }
            )
    return grid


class TestComputeGridOverfitting:
    def test_returns_report(self) -> None:
        grid = _synthetic_grid()
        rep = compute_grid_overfitting(grid, n_pbo_simulations=200)
        assert isinstance(rep, GridOverfittingReport)
        assert rep.n_cells == 168
        assert rep.n_variants == 21
        assert rep.n_symbols == 8
        assert rep.num_trials == 21

    def test_dsr_and_pbo_in_range(self) -> None:
        grid = _synthetic_grid()
        rep = compute_grid_overfitting(grid, n_pbo_simulations=200)
        assert 0.0 <= rep.dsr <= 1.0
        assert 0.0 <= rep.pbo <= 1.0

    def test_num_trials_equals_variants(self) -> None:
        """DSR debe corregir por multiple testing: num_trials = #variantes."""
        grid = _synthetic_grid(n_variants=21)
        rep = compute_grid_overfitting(grid, n_pbo_simulations=100)
        assert rep.num_trials == 21

    def test_handles_nan_and_inf_sharpe(self) -> None:
        grid = _synthetic_grid(n_symbols=3, n_variants=3)
        grid[0]["oos"]["sharpe"] = float("inf")
        grid[1]["oos"]["sharpe"] = float("nan")
        rep = compute_grid_overfitting(grid, n_pbo_simulations=50)
        assert np.isfinite(rep.dsr)
        assert np.isfinite(rep.pbo)


class TestRealGridCallSite:
    """Call-site REAL sobre results/edge_diagnosis/full_results.json (grilla 168)."""

    @pytest.mark.skipif(not _FULL_RESULTS.exists(), reason="full_results.json ausente")
    def test_wired_on_real_168_grid(self) -> None:
        grid = json.loads(_FULL_RESULTS.read_text(encoding="utf-8"))
        assert len(grid) == 168, "la grilla real debe tener 168 celdas"
        rep = compute_grid_overfitting(grid, n_pbo_simulations=300)
        assert rep.n_cells == 168
        assert rep.n_variants == 21
        assert rep.n_symbols == 8
        assert 0.0 <= rep.dsr <= 1.0
        assert 0.0 <= rep.pbo <= 1.0
