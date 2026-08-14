"""Fase 2 — aislar si la SUBLISTA (objs[:i+1]) rompe la paridad batch vs stream.

Usa el dataset sintético de functional_replay (dispara 1 setup LONG).
No toca engine/. Solo orquesta run_sequence_traced de dos formas:

  A) BATCH: run_sequence_traced(objs_full, est, cfg)  [una sola llamada]
  B) STREAM anti-patrón: en bucle, run_sequence_traced(objs[:i+1], est, cfg,
                          initial_state=state, start_i=i-1)  [sublista]

Si B da 0 y A da 1, la sublista es la causa raíz (rebasea posiciones).
"""

import sys, os, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.sequence import SequenceConfig, run_sequence_traced, SequenceState

_spec = importlib.util.spec_from_file_location(
    "replay_core_diag",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "research", "hypotheses", "HYP-002", "functional_replay", "replay_core.py"))
_rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc)
make_signal_objs, make_signal_est, _role_graph = _rc.make_signal_objs, _rc.make_signal_est, _rc._role_graph


def main():
    objs = make_signal_objs(n=12)
    est = make_signal_est()
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)

    # A) BATCH (una sola llamada, sin start_i)
    sigs_a, _, _, _ = run_sequence_traced(objs, est, cfg, ltf_tf="M15")
    a_graphs = [_role_graph(s) for s in sigs_a]
    print(f"[A] BATCH: setups={len(a_graphs)}")
    for g in a_graphs:
        print(f"    dir={g['direction']} roles={list(g['roles'].keys())}")

    # B) STREAM con sublista (anti-patrón de mi replay actual)
    state = None
    sigs_b_total = []
    n = len(objs)
    for i in range(1, n):
        win = objs[:i+1]  # <-- anti-patrón: sublista rebasea posiciones
        sigs_b, _, _, state = run_sequence_traced(
            win, est, cfg, ltf_tf="M15", initial_state=state, start_i=i-1,
            copy_objs=False,
        )
        sigs_b_total.extend(sigs_b)
    b_graphs = [_role_graph(s) for s in sigs_b_total]
    print(f"[B] STREAM(sublista): setups={len(b_graphs)}")

    # C) STREAM con df COMPLETO + start_i (patrón contrato §6)
    state = None
    sigs_c_total = []
    for i in range(1, n):
        sigs_c, _, _, state = run_sequence_traced(
            objs, est, cfg, ltf_tf="M15", initial_state=state, start_i=i-1,
            copy_objs=False,
        )
        sigs_c_total.extend(sigs_c)
    c_graphs = [_role_graph(s) for s in sigs_c_total]
    print(f"[C] STREAM(df completo+start_i): setups={len(c_graphs)}")

    print("\n=== Veredicto ===")
    print(f"A batch          = {len(a_graphs)}")
    print(f"B stream sublista= {len(b_graphs)}  (anti-patrón, esperado 0 si rompe)")
    print(f"C stream completo= {len(c_graphs)}  (contrato §6)")


if __name__ == "__main__":
    main()
