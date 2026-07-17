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

## PASO 2 — Incluir XAUUSD en MTF (CR-6) — PENDIENTE (aprobación)

## PASO 3 — Cap por ventana/seed + sacar w0_agents (CR-3) — PENDIENTE

## PASO 4 — ML sobre stack canónico + allowlist (CR-4) — PENDIENTE

## PASO 5 — POI anclado + módulo Silver Bullet (CR-2) — PENDIENTE

## PASO 6 — DSR/PBO en grilla (H16) — PENDIENTE

## PASO 7 — Tests sin auto-download, ciclo trend_context, dead code (CR-5) — PENDIENTE
