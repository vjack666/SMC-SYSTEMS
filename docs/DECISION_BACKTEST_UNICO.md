# DECISIÓN — Backtest único (motor canónico). NO recuperar el backtest de gate duplicado.

**Fecha:** 2026-08-05
**Autor:** Trader humano (Ruben) + Hermes
**Estado:** VIGENTE. Fuente de verdad para la arquitectura de backtest.

## Decisión

El proyecto tiene **UN SOLO backtest**. Ese backtest es un consumidor puro del
motor: corre el reloj vela a vela y llama a `engine/sequence.run_sequence`.
No contiene lógica de decisión propia.

El motor (`engine/`) ya ejerce la secuencia top-down COMPLETA
**D1 → H4 → H1 → M15 → M5 → M1** porque `ict_backtest/canonical.py` construye
`est_htf_ctx_fn` con `engine/plan.build_context_stack` (cadena entera) y se la
pasa a `run_sequence`. La compuerta de 4 capas vive en `engine/plan.top_down_allows_trade`
(dentro del motor), no en el backtest.

## PROHIBIDO — no recuperar el backtest B

Queda prohibido reintroducir `ict_backtest/v2/strategy_mtf.py`
(`generate_mtf_signals`, `mtf_signals_to_plan`, `explanation_mtf`) ni
`ict_backtest/v2/orchestrator.run_mtf_intraday`, ni los scripts
`scripts/run_bt_v2_mtf.py` / `scripts/run_htf_mtf_window.py`.

Motivo (Ley arquitectónica, AGENTS.md): "el motor es la ÚNICA fuente de
decisión; el backtest NO tiene lógica propia". El backtest B generaba el setup
con el motor (A) y luego LE APLICABA un gate top-down D1/H4/H1 propio +
`apply_nearest_tp_to_signals`. Eso es decisión duplicada en el backtest =
falsa señal de "dos backtests distintos" y superficie de bug (no se sabe si una
diferencia de métricas viene del motor o del filtro del backtest).

El gate D1/H4/H1 que B aplicaba YA ESTÁ en el motor (`engine/plan`). Borrar B
no pierde capacidad: el motor ya lo hace. B solo lo repetía mal.

## El backtest único CRECE CON EL MOTOR

Regla de oro para evitar que el backtest se quede atascado:

- Toda nueva capa / filtro / regla de la tesis va al **MOTOR** (`engine/`).
- El backtest único la consume automáticamente (vía `est_htf_ctx_fn` /
  `run_sequence`). No se toca el backtest para añadir lógica.
- Si algún día se quiere un filtro nuevo, se implementa en `engine/` y se mide
  con el backtest único. Nunca se crea un segundo backtest con lógica propia.

Así el backtest nunca se atasca: crece porque el motor crece, y hay una sola
definición de "señal válida" = la del motor. Cero falsos positivos por
definiciones de señal divergentes.

## Verificación de cumplimiento

- `engine/` no importa `ict_backtest/` (AST guard: `tests/test_engine_no_backtest_import.py`).
- El backtest único reporta el embudo de fases B2 (`funnel` en `run_summary.json`):
  SWEEP ≥ DISPLACE ≥ BOS ≥ ENTRY (monótono).
- `run_mtf_intraday` / `generate_mtf_signals` no existen en el árbol importable.

## Rastro

- Cerrado en sesión 2026-08-05: B1 (secuencia en motor + shim), B2 (embudo),
  B3 (invalidación, flag OFF), B4 (labels aislados), B5 (Expediente), B6 (test
  relajado). Backtest B eliminado por redundante/ley-arquitectónica.
