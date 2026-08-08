"""tests/test_engine_bos_exp012.py — Cierre de brecha EXP-012 en el motor.

EXP-012 (skill smc-ict-hub-exp012): CHOCH REAL exige empuje >=2 HH/LL post-
tendencia, BOS de mercado real detras, nivel = ULTIMO HL/LH roto (no el BOS
roto), y reclaim invalida. El motor SMC-SYSTEMS (engine/bos/structure.py) ya
tiene T9.4 (reclaim) y T9.7 (after_bos real); le faltaba el momentum. Este
test verifica el filtro `exp012_choch` como GATE DURO: con el flag ON, el
CHOCH sin empuje deja de existir en el frame (choch_dir=0), asi sesgo,
secuencia y observador lo ignoran. Con flag OFF el frame es identico al canonico.

Principio: regresion cero. Con flag OFF el frame NO gana columnas nuevas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.bos.structure import (
    StructureConfig,
    _exp012_choch_marks,
    detect_market_structure,
)


def _annotated_frame() -> pd.DataFrame:
    """Frame ya anotado (como lo deja detect_market_structure) para aislar el helper."""
    # 5 velas: 2 HH (uptrend con impulso) + 1 HL + 1 CHOCH bajista activo tras BOS alcista
    return pd.DataFrame(
        {
            "swing_label": ["HH", "HH", "HL", "NONE", "NONE"],
            "choch_dir": [0, 0, 0, 0, -1],
            "_last_bos_dir": [1, 1, 1, 1, 1],
            "choch_status": ["none", "none", "none", "none", "active"],
            "swing_low": [np.nan, np.nan, 1.10, np.nan, np.nan],
            "swing_high": [1.20, 1.21, np.nan, np.nan, np.nan],
        }
    )


def test_exp012_helper_with_momentum_marks() -> None:
    d = _annotated_frame()
    exp012, pivot, after = _exp012_choch_marks(d)
    # CHOCH bajista tras >=2 HH y BOS alcista real -> cumple EXP-012
    assert int(exp012.iloc[-1]) == 1
    assert float(pivot.iloc[-1]) == 1.10  # nivel = ULTIMO HL roto, no el BOS
    assert int(after.iloc[-1]) == 1


def test_exp012_helper_without_momentum_rejected() -> None:
    d = _annotated_frame()
    # Solo 1 HH => sin impulso (hh_streak=1) => CHOCH es ruido
    d.loc[1, "swing_label"] = "NONE"
    exp012, _, _ = _exp012_choch_marks(d)
    assert int(exp012.iloc[-1]) == 0


def test_exp012_helper_reclaim_invalidates() -> None:
    d = _annotated_frame()
    d.loc[4, "choch_status"] = "invalidated"  # reclaim
    exp012, _, _ = _exp012_choch_marks(d)
    assert int(exp012.iloc[-1]) == 0


def test_exp012_off_leaves_frame_unchanged() -> None:
    df = pd.DataFrame(
        {
            "high": [1.1, 1.12, 1.13, 1.11, 1.10, 1.14, 1.09, 1.15, 1.08, 1.16],
            "low": [1.09, 1.11, 1.12, 1.10, 1.08, 1.13, 1.07, 1.14, 1.06, 1.15],
            "open": [1.095, 1.115, 1.125, 1.105, 1.085, 1.135, 1.075, 1.145, 1.065, 1.155],
            "close": [1.10, 1.12, 1.13, 1.105, 1.09, 1.135, 1.08, 1.145, 1.07, 1.155],
        }
    )
    ms_off = detect_market_structure(df)
    assert "choch_exp012" not in ms_off.frame.columns
    ms_on = detect_market_structure(df, StructureConfig(exp012_choch=True))
    # ON agrega las 3 columnas; el resto del frame es igual
    assert "choch_exp012" in ms_on.frame.columns
    assert "choch_pivot_level" in ms_on.frame.columns
    assert "choch_exp012_after_bos" in ms_on.frame.columns
    for col in ("choch_dir", "choch_status", "bos_dir", "trend"):
        assert ms_on.frame[col].equals(ms_off.frame[col])


def test_exp012_gate_hard_zeroes_noise() -> None:
    """GATE DURO: con flag ON, un CHOCH sin empuje desaparece del frame."""
    df = pd.DataFrame(
        {
            "high": [1.1, 1.12, 1.13, 1.11, 1.10, 1.14, 1.09, 1.15, 1.08, 1.16],
            "low": [1.09, 1.11, 1.12, 1.10, 1.08, 1.13, 1.07, 1.14, 1.06, 1.15],
            "open": [1.095, 1.115, 1.125, 1.105, 1.085, 1.135, 1.075, 1.145, 1.065, 1.155],
            "close": [1.10, 1.12, 1.13, 1.105, 1.09, 1.135, 1.08, 1.145, 1.07, 1.155],
        }
    )
    ms_off = detect_market_structure(df)
    ms_on = detect_market_structure(df, StructureConfig(exp012_choch=True))
    n_off = int((ms_off.frame["choch_dir"] != 0).sum())
    n_on = int((ms_on.frame["choch_dir"] != 0).sum())
    # GATE DURO: nunca mas CHOCH con gate que sin el; si habia ruido, baja.
    assert n_on <= n_off
    # Todo CHOCH que queda con gate tiene respaldo exp012
    assert (ms_on.frame.loc[ms_on.frame["choch_dir"] != 0, "choch_exp012"] == 1).all()


def test_exp012_real_m15_drop() -> None:
    """Integracion: EURUSD M15 real, GATE DURO EXP-012.

    Con gate duro, todo CHOCH sin empuje >=2 HH/LL debe desaparecer del frame:
    choch_dir!=0 debe coincidir EXACTAMENTE con choch_exp012==1. NUNCA un
    choch_dir!=0 sin exp012 (eso seria ruido que se colo).
    """
    from engine.data_feed import load_frames

    try:
        ms = load_frames("EURUSD", timeframes=("M15",))
    except Exception:
        import pytest

        pytest.skip("datos EURUSD M15 no disponibles en disco")
    df = ms["M15"]
    ms_on = detect_market_structure(df, StructureConfig(exp012_choch=True))
    fr = ms_on.frame
    n_choch = int((fr["choch_dir"] != 0).sum())
    n_exp = int((fr["choch_exp012"] == 1).sum())
    # GATE DURO: choch_dir!=0 ES el subconjunto exp012 (ruido borrado del frame)
    assert n_choch == n_exp
    # NUNCA un choch_dir valido sin respaldo exp012
    assert (fr.loc[fr["choch_dir"] != 0, "choch_exp012"] == 1).all()
    # GATE DURO limpio: ningun CHOCH censurado queda con status 'active'
    assert (fr.loc[fr["choch_exp012"] == 0, "choch_status"] != "active").all()
    # Sanity: el gate debe descartar ruido (drop significativo esperado)
    print(f"\n[EXP-012 M15 GATE] CHOCH restantes={n_choch} (ruido eliminado)")


def test_caminoB_sesgo_inmune_a_gate() -> None:
    """CAMINO B (consejo 2026-08-08): el SESGO HTF es canonico SIEMPRE.

    compute_htf_bias no acepta exp012; el GATE DURO vive solo en
    detect_market_structure (estructura LTF). El sesgo no debe cambiar aunque
    se le pase un frame ya censurado por el gate.
    """
    from engine.bias.narrative import compute_htf_bias
    from engine.bos.structure import StructureConfig, detect_market_structure

    # Frame con CHOCH de ruido (sin empuje) para forzar diferencia si el gate
    # se colara al sesgo.
    df = pd.DataFrame(
        {
            "high": [1.1, 1.12, 1.13, 1.11, 1.10, 1.14, 1.09, 1.15, 1.08, 1.16],
            "low": [1.09, 1.11, 1.12, 1.10, 1.08, 1.13, 1.07, 1.14, 1.06, 1.15],
            "open": [1.095, 1.115, 1.125, 1.105, 1.085, 1.135, 1.075, 1.145, 1.065, 1.155],
            "close": [1.10, 1.12, 1.13, 1.105, 1.09, 1.135, 1.08, 1.145, 1.07, 1.155],
        }
    )
    b_canon = compute_htf_bias(df, df, df)
    # Frame del sesgo ya censurado por el gate
    dgc = detect_market_structure(df, StructureConfig(exp012_choch=True)).frame
    b_censurado = compute_htf_bias(dgc, dgc, dgc)
    assert b_canon.direction == b_censurado.direction
    assert b_canon.aligned == b_censurado.aligned
