"""R1.4 — Tests sinteticos de po3_state sin look-ahead.

Escenarios (docs/ict/08_POWER_OF_THREE.md, aprobado 2026-07-13):
  - solo A            -> incomplete (falta M y D)
  - solo M (sin A)    -> incomplete (sweep sin sesgo no etiqueta PO3)
  - A+M sin D         -> incomplete (trampa hecha, falta expansion)
  - A+M+D a-favor     -> COMPLETO
  - look-ahead        -> la funcion es pura: si el dict tiene D pero NO M,
                         NO debe marcar complete (no se adelanta al futuro).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from signals.po3 import build_po3_state, evaluate_po3, compute_session_open  # noqa: E402
from ict_backtest.rules import evaluate  # noqa: E402


def _est(bias="", d1_trend="", h4_trend="", m15=None, htf_trend=None):
    """Arma un dict estructura minimo por TF."""
    m15 = m15 or {}
    h4 = {"trend": htf_trend or h4_trend}
    return {
        "D1": {"trend": d1_trend},
        "H4": h4,
        "M15": m15,
    }


def test_solo_A_incompleto():
    """Sesgo definido pero sin sweep ni BOS -> solo fase A."""
    est = _est(bias="BULLISH", d1_trend="BULLISH", h4_trend="BULLISH")
    st = build_po3_state(est, "BULLISH")
    assert st.A is True
    assert st.M is False
    assert st.D is False
    assert st.complete is False
    assert "M" in "".join(st.incomplete_reason)


def test_solo_M_sin_A_no_etiqueta_PO3():
    """Sweep en contra pero sin sesgo HTF -> no es PO3."""
    est = _est(
        bias="",
        d1_trend="",
        h4_trend="",
        m15={"sweep_down": True, "bos_dir": -1, "bos_status": "active", "choch_status": "bearish"},
    )
    st = build_po3_state(est, "")
    assert st.A is False
    assert st.M is False  # sin sesgo, el sweep no define M
    assert st.complete is False


def test_A_M_sin_D_incompleto():
    """Sesgo + sweep en contra, pero sin CHOCH/BOS a favor + zona -> falta D."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={"sweep_down": True},  # M presente, pero sin BOS/CHOCH ni FVG/OB
    )
    st = build_po3_state(est, "BULLISH")
    assert st.A is True
    assert st.M is True
    assert st.D is False
    assert st.complete is False
    assert "D" in "".join(st.incomplete_reason)


def test_A_M_D_completo_long():
    """Ciclo completo a favor (alcista): A + M(sweep down) + D(BOS up + FVG)."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={
            "sweep_down": True,                 # M: barre SSL
            "bos_dir": 1,
            "bos_status": "active",             # D: BOS alcista a favor
            "fvg_state": "bullish",             # D: zona FVG
        },
    )
    st = build_po3_state(est, "BULLISH")
    assert st.A and st.M and st.D
    assert st.aligned is True
    assert st.complete is True
    assert st.direction == "LONG"
    assert st.phases_present() == "AMD"


def test_A_M_D_completo_short():
    """Ciclo completo a favor (bajista)."""
    est = _est(
        bias="BEARISH",
        d1_trend="BEARISH",
        h4_trend="BEARISH",
        m15={
            "sweep_up": True,
            "bos_dir": -1,
            "bos_status": "active",
            "fvg_state": "bearish",
        },
    )
    st = build_po3_state(est, "BEARISH")
    assert st.complete is True
    assert st.direction == "SHORT"
    assert st.aligned is True


def test_sin_look_ahead_D_no_se_adelanta():
    """Si el dict trae D-like (BOS a favor) PERO no M, NO debe completar.

    Esto atrapa look-ahead: el estado no puede declarar D sin que M exista.
    """
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={
            # Sin sweep_down -> M=False, pero con BOS/FVG que "parecen" D.
            "bos_dir": 1,
            "bos_status": "active",
            "fvg_state": "bullish",
        },
    )
    st = build_po3_state(est, "BULLISH")
    assert st.M is False
    assert st.D is False
    assert st.complete is False


def test_evaluate_dispatch_po3():
    """evaluate(model='po3') en rules.py delega a evaluate_po3 y da complete."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={"sweep_down": True, "bos_dir": 1, "bos_status": "active", "fvg_state": "bullish"},
    )
    r = evaluate("po3", est, "BULLISH", None, None, "M15", "H4", False)
    assert r["model"] == "po3"
    assert r["complete"] is True
    assert r["ready"] is True
    assert r["phases"] == "AMD"


def test_evaluate_po3_separado_de_turtle():
    """PO3 a-favor no debe confundirse con reversión (Turtle Soup).

    Mismo sweep pero direccion del setup opuesta al sesgo -> no alineado -> incomplete.
    """
    est = _est(
        bias="BULLISH",  # sesgo alcista
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={
            "sweep_down": True,
            "bos_dir": -1,        # BOS BAJISTA -> en contra del sesgo
            "bos_status": "active",
            "fvg_state": "bearish",
        },
    )
    st = build_po3_state(est, "BULLISH")
    assert st.aligned is False  # seria Turtle Soup
    assert st.complete is False


# ---------------------------------------------------------------------------
# R3 — PO3-2: open del dia como filtro duro de la manipulacion (M)
# ---------------------------------------------------------------------------

def test_m_sin_session_open_degrada_a_r1():
    """Sin session_open en el dict, M = solo sweep en contra (comportamiento R1)."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={"sweep_down": True},  # sweep en contra pero sin ancla de open
    )
    st = build_po3_state(est, "BULLISH")
    assert st.M is True
    assert st.broke_open is False  # no hay ancla -> no puede saber si rompio el open


def test_m_requiere_romper_open_cuando_presente():
    """Con session_open, M exige que el sweep haya roto el open del dia."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={"sweep_down": True, "low": 1.0900},  # low por debajo del open
    )
    est["D1"]["session_open"] = 1.0950
    st = build_po3_state(est, "BULLISH")
    assert st.M is True
    assert st.broke_open is True


def test_m_no_rompe_open_incompleto():
    """Sweep en contra pero NO rompe el open -> M False (filtro duro)."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={"sweep_down": True, "low": 1.0980},  # low por encima del open
    )
    est["D1"]["session_open"] = 1.0950
    st = build_po3_state(est, "BULLISH")
    assert st.M is False
    assert st.broke_open is False


def test_m_rompe_open_short():
    """Sesgo bajista: el sweep alcista debe superar el open del dia."""
    est = _est(
        bias="BEARISH",
        d1_trend="BEARISH",
        h4_trend="BEARISH",
        m15={"sweep_up": True, "high": 1.1020},
    )
    est["D1"]["session_open"] = 1.1000
    st = build_po3_state(est, "BEARISH")
    assert st.M is True
    assert st.broke_open is True


def test_compute_session_open_ultima_vela_cerrada():
    """compute_session_open usa la ultima vela (ya cerrada) del DataFrame D1."""
    import pandas as pd

    d1 = pd.DataFrame({"open": [1.0900, 1.0950, 1.1000]})
    assert compute_session_open(d1) == 1.1000


def test_compute_session_open_vacio():
    assert compute_session_open(None) is None
    import pandas as pd

    assert compute_session_open(pd.DataFrame({"open": []})) is None


def test_complete_requiere_open_roto_si_presente():
    """Ciclo A+M+D pero M no rompio el open -> incomplete cuando hay ancla."""
    est = _est(
        bias="BULLISH",
        d1_trend="BULLISH",
        h4_trend="BULLISH",
        m15={
            "sweep_down": True,
            "low": 1.0980,           # NO rompe el open (filtro duro)
            "bos_dir": 1,
            "bos_status": "active",
            "fvg_state": "bullish",
        },
    )
    est["D1"]["session_open"] = 1.0950
    st = build_po3_state(est, "BULLISH")
    assert st.M is False
    assert st.complete is False
    assert "M" in "".join(st.incomplete_reason)
