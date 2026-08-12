"""HYP-002 functional_replay — núcleo compartido (CONSUMIDOR PURO DEL MOTOR).

Vive FUERA de ict_backtest/ (arquitectura M4): importa únicamente del motor
permanente (engine.*) y de datos de mercado crudos. NUNCA importa ict_backtest/.

Contiene los helpers compartidos por las baterías de replay funcional
(M1/M2/M3 causality/look-ahead/restart y M4 continuidad operacional):
  - make_signal_objs / make_signal_est / _role_graph
  - run_session (dirige el motor barra-a-barra desde un feed de MarketObject)
  - audit_restart_parity (reinicio vela-a-vela, compara grafo causal)

El backtest (ict_backtest/) es un consumidor reemplazable; este replay
sobrevive a su eliminación.
"""

from __future__ import annotations

import os
import tempfile

import pandas as pd

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.sequence import (
    SequenceConfig,
    SequenceState,
    run_sequence_traced,
)


def make_signal_objs(n=12, base=1.1000):
    """Dataset que SÍ dispara un setup LONG (sweep→displace→BOS→return).

    Construye MarketObject[] directamente (el motor acepta objs como feed) con
    `meta` manual, para tener una corrida NO vacía y probar paridad de reinicio
    de forma no trivial. HTF estimator devuelve BULLISH en todas las velas.
    """
    objs = []
    for i in range(n):
        meta = {
            "open": base + 0.0005 * i,
            "high": base + 0.0005 * i + 0.0004,
            "low": base + 0.0005 * i - 0.0004,
            "close": base + 0.0005 * i + 0.0001,
            "volume": 100.0,
            "atr": 0.0008,
            "liquidity_sweep_down": False,
            "liquidity_sweep_up": False,
            "displacement_bullish": False,
            "displacement_bearish": False,
            "fvg_bullish": False,
            "fvg_bearish": False,
            "ob_direction": "-",
            "bos_dir": 0,
            "choch_dir": 0,
            "ssl_price": None,
            "bsl_price": None,
            "bos_level": None,
            "pd_type": None,
            "pd_tier": None,
        }
        objs.append(MarketObject(
            id=f"c{i}", symbol="EURUSD", type=ObjectType.CANDLE, origin_tf="M15",
            role=Role.REFINEMENT, direction=0, bar_index=i,
            bar_time=pd.Timestamp("2026-03-01 00:00") + pd.Timedelta(minutes=15 * i),
            meta=meta, state=ObjectState.ACTIVE))
    objs[1].meta["liquidity_sweep_down"] = True
    objs[1].meta["ssl_price"] = objs[1].meta["low"]
    objs[3].meta["displacement_bullish"] = True
    objs[4].meta["fvg_bullish"] = True
    objs[4].meta["high"] = base + 0.0100
    objs[4].meta["low"] = base + 0.0090
    objs[6].meta["bos_dir"] = 1
    objs[6].meta["bos_level"] = base + 0.0120
    objs[9].meta["high"] = base + 0.0101
    objs[9].meta["low"] = base + 0.0089
    return objs


def make_signal_est():
    """Estimador HTF trivial: BULLISH en todas las velas (setup LONG)."""

    def f(i):
        return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False,
                "displacement_bullish": False, "displacement_bearish": False,
                "fvg_bullish": False, "fvg_bearish": False,
                "ob_bullish": False, "ob_bearish": False, "bos_dir": 0}

    return f


def _role_graph(signal: dict) -> dict:
    """Extrae el grafo causal de un signal dict (roles + parent_role + bar_index)."""
    g = {"direction": signal.get("direction", 0), "roles": {}}
    ids = signal.get("event_ids", {})
    objs = signal.get("event_objects", {})
    for role, eid in ids.items():
        o = objs.get(eid)
        if o is None:
            continue
        g["roles"][role] = {
            "type": o.get("type"),
            "role": o.get("role"),
            "bi": o.get("bar_index"),
            "parent_role": None,
        }
    # parent_role desde el grafo de event_objects
    id_to_role = {eid: role for role, eid in ids.items()}
    for role, eid in ids.items():
        o = objs.get(eid)
        if o is None:
            continue
        parent = o.get("parent_object")
        g["roles"][role]["parent_role"] = id_to_role.get(parent)
    return g


def run_session(
    objs: list[MarketObject],
    est,
    cfg: SequenceConfig,
    initial_state: SequenceState | None = None,
    start_i: int = 0,
    save_each_bar: bool = False,
    save_path: str | None = None,
) -> dict:
    """Dirige el motor barra-a-barra desde un feed de MarketObject.

    Simula una sesion operacional: en cada barra el motor avanza y (si
    save_each_bar) el estado se persiste. Devuelve senales, phase_seen,
    grafos causales y el estado final.
    """
    sigs, phase_seen, exps, state = run_sequence_traced(
        objs, est, cfg, htf_poi_fn=None, ltf_tf="M15",
        est_htf_ctx_fn=None,
        initial_state=initial_state, start_i=start_i,
    )
    if save_each_bar and save_path is not None:
        state.save(save_path)
    graphs = [_role_graph(s) for s in sigs]
    return {
        "signals": sigs,
        "phase_seen": phase_seen,
        "expedientes": exps,
        "state": state,
        "causal_graphs": graphs,
        "n_signals": len(sigs),
    }


def audit_restart_parity(objs, est, cfg, cut: int) -> dict:
    """Paridad de reinicio vela-a-vela (M3): corrida completa vs cortar+resumir.

    Compara la ESTRUCTURA CAUSAL (roles, tipo, bar_index, parent_role), no los
    UUID. Devuelve continuous_signals, roundtrip_ok, causal_graphs_equal.
    """
    full = run_session(objs, est, cfg, start_i=-1)
    cont_graphs = full["causal_graphs"]

    # cortar en `cut`, persistir, y reanudar con el estado restaurado
    sess = run_session(objs, est, cfg, start_i=-1)
    cut_state = sess["state"]
    tmp = os.path.join(tempfile.gettempdir(), "replay_restart_state.json")
    cut_state.save(tmp)
    restored = SequenceState.load(tmp)
    resumed = run_session(objs, est, cfg, initial_state=restored, start_i=cut)
    res_graphs = resumed["causal_graphs"]

    def _norm(g):
        return {r: (g["roles"][r]["type"], g["roles"][r]["bi"], g["roles"][r]["parent_role"])
                for r in g["roles"]}

    equal = (len(cont_graphs) == len(res_graphs) and
             all(_norm(cont_graphs[i]) == _norm(res_graphs[i])
                 for i in range(len(cont_graphs))))
    return {
        "continuous_signals": len(cont_graphs),
        "roundtrip_ok": cut_state.to_snapshot() == restored.to_snapshot(),
        "causal_graphs_equal": equal,
        "pass": len(cont_graphs) > 0 and equal,
    }
