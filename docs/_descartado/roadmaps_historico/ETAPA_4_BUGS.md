> ⚠️ **DOCUMENTO HISTÓRICO (recuperado 2026-08-05 del commit d0a5f20).**
>
> NO es fuente de verdad. La fuente de verdad viviente es:
> `AGENTS.md` + `docs/tesis/` (tesis del trader humano) + `engine/` (motor permanente)
> + `docs/bitacora/bitacora_trabajo.md` (estado real verificado).
>
> Este roadmap describe el estado al 2026-07-21, cuando el trabajo estaba medido
> en el **backtest** (`ict_backtest/`). El motor (`engine/`) se construyó DESPUÉS
> y está en otro punto. Ver `docs/planificacion/INDICE_PLANES.md` y el diff en
> `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.
>
> Recuperado selectivamente (solo hitos/fases/decisiones, SIN código de backtest
> ni libro 13) por petición del trader humano para ubicar el punto actual.

> **⚠️ STALE** — Paso 1 (killzone) completado; Paso 2 (revertido); Pasos 3–7 nunca ejecutados.
> Estos bugs predata el pivot a R7/R9/R10/thesis-driven. El motor legacy fue suprimido.
> No es fuente de verdad vigente para bugs activos.

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

## PASO 2 — Incluir XAUUSD en MTF (CR-6) — BLOQUEADO por cuello de botella O(n^2)

### Estado: REVERTIDO (no cerrado). Commit d9b7b8f. CAUSA RAIZ AISLADA 2026-07-17.

### CAUSA RAIZ (diagnostico forense aislado, sin modificar src)
- NO es bucle infinito. `run_mtf_intraday('XAUUSD')` TERMINA en ~3053s (~51 min)
  con n_raw=77 senales. El "cuelgue" del Runner Monitor era lentitud extrema
  (~1000x EURUSD), no parada.
- Funcion exacta: `ict_backtest/_util.py::closed_row_at_time` (lineas 113-122).
  Por CADA llamada reconvierte TODO el array HTF a datetime y compara el array
  completo (O(n_HTF) por llamada). Se invoca UNA vez por vela LTF via
  `est_htf_fn(i)` en `run_sequence` (sequence.py:342).
- Complejidad: O(n_LTF * n_HTF). XAUUSD = 109270 M15 * 10066 H4 ~= 1.1e9 ops.
  EURUSD tiene menos velas M15 => segundos. Por eso solo oro lo dispara.
- Diagnostico: scripts/_diag_xauusd_hang.py (v3, monkeypatch observacional).
  Log: results/diag_xauusd.log (n_raw=77, total 3052.8s).

### FIX PROPUESTO (performance, NO altera ICT => cumple regla de oro)
1. Cachear `times = pd.to_datetime(df["time"])` UNA vez por run_sequence, no por llamada.
2. O mejor: merge_asof por tiempo (O(log n_HTF) por vela) en lugar de scan lineal.
3. O cachear resultado por `cutoff` (los t LTF son monotonicos).
Cualquiera es deterministicamente identico en senales => backtest vs baseline
debe dar igual (solo cambia el tiempo de ejecucion). Requiere OK de Ruben antes
de implementar (es cambio de codigo).

### Siguiente paso
Esperar direccion de Ruben: (a) aplicar fix de perf y reactivar CR-6, o
(b) diferir y seguir con PASO 3. NO avanzar sin OK.

================================================================================

## PASO 3 — Cap por ventana/seed + sacar w0_agents (CR-3) — PENDIENTE

## PASO 4 — ML sobre stack canónico + allowlist (CR-4) — PENDIENTE

## PASO 5 — POI anclado + módulo Silver Bullet (CR-2) — PENDIENTE

## PASO 6 — DSR/PBO en grilla (H16) — PENDIENTE

## PASO 7 — Tests sin auto-download, ciclo trend_context, dead code (CR-5) — PENDIENTE
