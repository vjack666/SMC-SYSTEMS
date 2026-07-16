"""tests/test_r10c_run_semantic_equivalence.py — Fase E: equivalencia causal.

RED 2 (redefinido, ver docs/plan/INFORME_EQUIVALENCIA_R10C.md):

La relacion correcta entre el motor legacy (reloj/displace_gap) y el motor
semantico (causalidad por zona) es:

    Legacy ⊆ Semantic

no `Semantic ⊆ Legacy`. El motor semantico es un modelo CAUSAL mas completo:
reconoce toda estructura que legacy reconoce (legacy esta contenido) y
adicionalmente otras validas por zona que legacy descarta por su ventana
temporal. Por eso semantico es MAS AMPLIO, no mas estricto.

Identidad causal: (direction, indice_de_la_estructura_BOS).
- legacy lo expone en s['bos_at'].
- semantico en s['bar_index'] del objeto BOS.

Ambos operan sobre el MISMO df H4 (+ D1 para est_htf_fn real) y derivan el
BOS de las MISMAS features, por lo que el BOS en el indice k con direccion d
es la MISMA entidad para ambos motores.

Contrato del test:
1. legacy_keys <= sem_keys   (legacy esta contenido en lo que semantico reconoce)
2. len(sem_keys) > 0         (semantico reconoce estructuras validas)
3. integridad causal: toda senal semantica debe tener un SWEEP causal como
   raiz (narrativa sweep -> bos causal -> estructura valida), no un BOS suelto.
"""

from __future__ import annotations

import warnings

import pytest

from ict_backtest.sequence import SequenceConfig
from ict_backtest.event_engine import run_semantic


@pytest.fixture(scope="module")
def h4_and_htf():
    warnings.filterwarnings("ignore")
    from ict_backtest.data_feed import load_frames
    from ict_backtest.market_structure import detect_market_structure

    fr = load_frames("XAUUSD", ("H4", "D1"))
    h4_full = detect_market_structure(fr["H4"])
    d1 = detect_market_structure(fr["D1"])
    h4 = h4_full.iloc[:2000].reset_index(drop=True)

    def est_htf_fn(i):
        t = h4.iloc[i]["time"]
        rows = d1[d1["time"] <= t]
        if len(rows) == 0:
            return {"trend": "RANGING", "sweep_up": False, "sweep_down": False}
        r = rows.iloc[-1]
        return {
            "trend": str(r.get("trend", "RANGING")),
            "sweep_up": bool(r.get("liquidity_sweep_up", False)),
            "sweep_down": bool(r.get("liquidity_sweep_down", False)),
        }

    return h4, est_htf_fn


def test_run_semantic_contains_legacy_by_causal_identity(h4_and_htf):
    from ict_backtest.sequence import run_sequence

    h4, est_htf_fn = h4_and_htf

    legacy, _ = run_sequence(h4, est_htf_fn, SequenceConfig(), ltf_tf="H4")
    sem = run_semantic(h4, est_htf_fn, SequenceConfig(), ltf_tf="H4")

    legacy_keys = {(s["direction"], s["bos_at"]) for s in legacy}
    sem_keys = {(s["direction"], s["bar_index"]) for s in sem}

    # Legacy esta contenido en lo que el motor causal reconoce (Legacy ⊆ Semantic).
    assert legacy_keys <= sem_keys, (
        f"run_semantic NO reconocio estructuras que legacy si: "
        f"{legacy_keys - sem_keys}"
    )
    # No-vacuo: el motor semantico reconoce estructuras validas.
    assert len(sem_keys) > 0, "run_semantic no emitio ninguna senal"


def test_run_semantic_signals_have_causal_sweep_root(h4_and_htf):
    """Integridad causal: toda senal semantica cuelga de un SWEEP (raiz).

    Verifica que cada senal trae root_id apuntando a un objeto SWEEP real
    (narrativa sweep -> bos causal -> estructura valida), no un BOS suelto.
    Se pasan los MISMOS objetos a run_semantic para que los ids coincidan.
    """
    from ict_backtest.market_object import ObjectType
    from ict_backtest.data_feed import build_objects
    from ict_backtest.market_structure import detect_market_structure

    h4, est_htf_fn = h4_and_htf

    objs = build_objects({"H4": detect_market_structure(h4)}, symbol="XAUUSD")
    sem = run_semantic(objs, est_htf_fn, SequenceConfig(), ltf_tf="H4")
    by_id = {o.id: o for o in objs}

    assert len(sem) > 0, "run_semantic no emitio senales para validar integridad"
    for s in sem:
        assert "root_id" in s, f"senal {s.get('id')} sin root_id"
        root = by_id.get(s["root_id"])
        assert root is not None, f"root_id {s['root_id']} no existe en los objetos"
        assert root.type == ObjectType.SWEEP, (
            f"la raiz de la senal {s.get('id')} no es SWEEP sino {root.type}"
        )
