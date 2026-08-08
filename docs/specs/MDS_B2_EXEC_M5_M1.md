# MDS_B2_EXEC_M5_M1.md — Ejecución fina M5/M1 (B2)

- **Clasificación**: OBLIGATORIO · Fase B2 · **Estado: ✅ HECHO (en motor)**
- **SDD-first**: este documento refleja el código real en `engine/execution.py` + `engine/micro.py`.

## Propósito
Bajar la decisión ya validada por el gate top-down (D1→H4→H1) a la ENTRADA FINA
en el TF de ejecución (M5/M1). La tesis (libro 18) dicta: la entrada SIEMPRE va
en el TF fino, nunca en M15.

## Por qué importa (geometría, no indicadores)
Sin exec fino, el motor marca la zona en M15 pero entra "en el aire". El humano
opera el breakout del último swing en M5/M1 con SL en la mecha del sweep del
mismo TF (estructural). Geometría pura: swings + mecha de sweep + objetivo de
liquidez. Cero indicadores.

## Entradas (geometría + volumen)
- `ms`: DataFrames OHLC por TF (M5/M1 como exec TF).
- `entry_ts`, `direction`, `sweep_ts` (tiempo del sweep del LTF).
- `rr` (default 3.0). VOLUMEN: tick volume del exec TF para confirmar el sweep
  (el sweep con volumen alto es más válido; el volumen es dato, no indicador).

## Lógica (engine/execution.fine_execution)
1. Recorta exec TF a velas con `time <= t` (anti look-ahead).
2. Sin `sweep_ts`: entry/SL/TP desde swings del exec TF (fallback).
3. Con `sweep_ts`: SL anclado a la MECHA DEL SWEEP del exec TF (libro 18: SL
   estructural SIEMPRE en el TF más fino). El SETUP se detectó en LTF; aquí solo
   se reancla la entrada fina.
4. Si el SL por mecha de sweep queda inválido por compresión del TF fino →
   FALLBACK al último swing opuesto del exec TF (estructura real).
5. TP = RR 1:3 al objetivo de liquidez.

## Salidas
`{"ok", "exec_tf", "entry", "sl", "tp", "rr", "reason"}`. Si `ok=False` la señal
se SALTA (no opera) pero NO cuenta como veto.

## Integración
`engine/execution.py` es la única fuente. `ict_backtest/canonical.py` lo consume
(`fine_execution`) — NUNCA reimplementa swing/SL. Ley respetada: engine/ no
importa ict_backtest/.

## Verificación
`pytest tests/test_engine_execution_b2.py` → 15 passed (incl.
`test_b2_fallback_sweep_sl_invalid_uses_swing`). Cableado real confirmado por
`tests/test_b2_exec_tf_wiring.py`.
