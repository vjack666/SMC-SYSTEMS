# ETAPA 4 — CORRECCIÓN DE BUGS (un commit = un bug)

Objetivo: cerrar los hallazgos A de la matriz de convergencia, un cambio
estructural a la vez, con tests + backtest tras cada uno. Fase 0 (Killzone,
Sequence, Entry, SL, TP RR 1:3, HTF, Displacement) PROHIBIDA.

## PASO 1 — Unificar BOS/CHOCH (CR-1) ✅ COMPLETADO

### Archivos modificados
- `detectors/bos.py` — `detect_bos` delega a `ict_backtest.market_structure`
  (confirm_bars=2). Mapea `bos_dir`→`bos_direction`; re-agrega sweep/atr.
- `detectors/choch.py` — `detect_choch` adopta semántica canónica (rompe el
  ÚLTIMO BOS en dirección opuesta, 2 cuerpos de confirmación).
- `tests/test_bos_choch_regression.py` — suite de regresión (8 tests).

### Diferencias funcionales detectadas
- Antes: `detectors` tenía su PROPIA geometría BOS (1 vela rompe) y CHOCH
  (medias 20/50). El motor canónico (`market_structure`) usaba confirm_bars=2
  y "último BOS". DOS implementaciones divergentes.
- Ahora: `detectors` llama al canónico. Una sola fuente de verdad.
- Import perezoso para evitar ciclo: `ict_backtest.__init__` → `signals` →
  `detectors` → `ict_backtest.market_structure`.

### Métricas antes/después (backtest PRE vs POST, EURUSD, 168 celdas)
- `dN = 0`, `dPF = 0.000`, `dWR = 0.000` en TODAS las celdas.
- SIN REGRESIÓN. La divergencia 1-bar vs 2-bar del detectors viejo NO se
  manifiesta en M15 real (no hay fakeouts de 1 barra que cambien N). La
  inconsistencia latente queda eliminada y cubierta por la suite para casos
  sintéticos/fakeout.

### Evidencia de no-regresión
- `tests/test_bos_choch_regression.py`: 8 passed (incl. `test_post_unification_equivalence`
  exige 0 divergencia bos_direction/bos_status/choch_signal vs canónico).
- `tests/test_detectors.py`: 46 passed (consumidores intactos).
- `signals/pipeline.py` USA `bos_direction`/`choch_signal` en confluencia
  (líneas 170-174, 227-232, 301-302, 360) → el dispatch es REAL, no muerto.

## PASO 2 — Incluir XAUUSD en MTF (CR-6) — BLOQUEADO por bug del motor

### Estado: REVERTIDO (no cerrado). Commit d9b7b8f.

### Hallazgo (2026-07-17)
- Al activar XAUUSD en `run_bt_v2_mtf.py`, `run_mtf_intraday('XAUUSD', ...)`
  ESCRIBIÓ `live_structure.csv` (53 bytes) y entró en **loop/deadlock**: nunca
  produjo trades/metrics/coverage/OOS ni reescribió `results/bt_v2_mtf_resumen.txt`.
  El proceso quedó vivo ~2h hasta ser matado (PID 25344).
- Los otros 7 símbolos corren y terminan (la corrida de 7 escribió su resumen).
- `load_frames('XAUUSD', ('M15','H4','D1'))` CARGA OK (109,270 velas M15).
  El problema NO es el dato: es el motor canónico que no soporta oro
  (gaps/horario/volatilidad). Confirma la "bomba de tiempo ajustada a EURUSD".

### Decisión
- Regla de oro: cambio que rompe → REVERTIR. Vuelve a 7 símbolos, XAUUSD excluido.
- CR-6 QUEDA PENDIENTE hasta diagnosticar y corregir el cuelgue en
  `ict_backtest/v2/orchestrator.py` / `run_mtf_intraday` para XAUUSD.
- No es un fallo de la unificación BOS/CHOCH (PASO 1): el motor canonico ya
  usaba `market_structure`; el cuelgue es previo y específico de oro.

### Siguiente paso sugerido
- Nuevo bug aislado: diagnosticar dónde se cuelga `run_mtf_intraday` con XAUUSD
  (fase post-live_structure: simulate/coverage/OOS o bucle en estructura).
  Tratarlo como su propio commit, NO dentro de CR-6 tal como estaba planteado.

================================================================================

## PASO 3 — Cap por ventana/seed + sacar w0_agents (CR-3) — PENDIENTE

## PASO 4 — ML sobre stack canónico + allowlist (CR-4) — PENDIENTE

## PASO 5 — POI anclado + módulo Silver Bullet (CR-2) — PENDIENTE

## PASO 6 — DSR/PBO en grilla (H16) — PENDIENTE

## PASO 7 — Tests sin auto-download, ciclo trend_context, dead code (CR-5) — PENDIENTE
