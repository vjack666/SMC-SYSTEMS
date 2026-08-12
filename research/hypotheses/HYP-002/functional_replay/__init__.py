"""HYP-002 functional_replay — replay funcional del MOTOR (consumidor puro).

Pruebas de comportamiento temporal/operacional del motor real (engine/),
ubicadas fuera de ict_backtest/ para que SOBREVIVAN la eliminacion del
backtest. NUNCA importan ict_backtest/.

Modulos:
  replay_core.py                     nucleo compartido (make_signal_objs, run_session, ...)
  functional_replay_battery.py      bateria FASE 2-10 (causalidad, determinismo, ...)
  operational_continuity_battery.py bateria M4 (reinicios multi, gaps, duplicados, ...)
"""
