# Bitácora de Trabajo — SMC-SYSTEMS

Registro cronológico de sesiones, decisiones y estado del proyecto. Fuente de
verdad viviente junto con AGENTS.md y la tesis (docs/tesis/). El backtest es
desechable; el motor (engine/) es permanente.

## 2026-08-05 — Sesión: cierre de brechas B/A1 + orden de documentación

### Decisiones del trader humano (Ruben)
- Cuenta correcta del proyecto: **FundedNext** (ForexClub descartado).
- Auto-arranque con Windows **ELIMINADO**: el sistema corre solo bajo demanda
  (pedir "dame el bias de hoy" / "analiza la gráfica"). Hermes.lnk movido a
  `scripts/DisabledStartup/`.
- **Ley arquitectónica**: motor (engine/) = lectura del humano hecha código,
  PERMANENTE y autónoma; backtest (ict_backtest/) = desechable, solo demuestra
  la tesis. El backtest puede importar el motor; el motor NUNCA importa el
  backtest. El observador en vivo lee del motor, no del backtest.
- Ante duda: "qué camino escogería el trader humano y le diría al ingeniero que
  construya" — la lógica del humano va al MOTOR, el backtest solo la demuestra.

### Trabajo ejecutado (verificado con ejecución real)
1. **Recuperación de archivos**: 164 archivos borrados en la historia de git,
   de carpetas vivas (app_observador/, detectors/, ict_backtest/, scripts/,
   tests/, ml/, strategy/, adapters/), restaurados a su carpeta original vía
   `git checkout` del último commit donde existieron. 0 fallidos.
   - Fuera de alcance (purga probable de Ruben, no tocados): docs/ (91),
     modules/ (85), smc_successor/, automation/ — 176 archivos.
2. **Motor — brecha B (POI anclado) CERRADA**:
   - `engine/poi_anchor.py` (nuevo): `build_htf_structure_index` +
     `make_htf_poi_fn(i, target)->bool`. Ancla POI a BOS/CHOCH del TF padre ya
     cerrado, con anti look-ahead por timestamp. Solo importa `engine.bos`/
     `engine.bias` (Ley OK).
   - `engine/htf_narrative.py`: `build_htf_narrative` marca `poi["anchored"]`.
   - `tests/test_engine_poi_anchor.py`: 5 tests (passed).
3. **Motor — brecha A1 (3 capas reales) CERRADA**:
   - `engine/plan.py` (nuevo): `build_context_stack` + `top_down_allows_trade`
     + `snapshot_tf` + `dealing_range_pd`. Lectura top-down D1→H4→H1→M15 con
     premium/discount y anti look-ahead. Usa `engine.bos`, NO importa backtest.
   - `engine/data_feed.py` (nuevo): `load_frames` del motor (lee parquet crudos
     de data/raw). El motor carga sus propios datos.
   - `ict_backtest/v2/context_mtf.py`: re-exporta desde `engine.plan` (el
     backtest CONSUME el motor, sin duplicar).
4. **Observador desacoplado del backtest**:
   - `app_observador/core/engine.py::_canonical_plan` ahora lee del motor
     (`engine.data_feed` + `engine.plan` + `engine.htf_narrative`), no de
     `ict_backtest.canonical.latest_plan`. Verificado con ict_backtest BLOQUEADO:
     el observador corre sin tocar el backtest.
   - `grep -r ict_backtest app_observador/` → 0 imports reales.
5. **Datos**: `_data_legacy.py` tenía rango de descarga hardcodeado a 2026-07-07
   → corregido a `datetime.now()`. `update_mt5_data.py` (MERGE) subió EURUSD
   D1/H4/H1 a 2026-08-05. M15 sigue corto (ver pendiente).
6. **Tests**: `pytest tests/test_engine_*.py` → **79 passed, 0 failed**.

### Reordenamiento de documentación (esta sesión)
- AGENTS.md CAVEAT R6 corregido: brechas B y A1 ya CERRADAS en el motor.
- Creada `docs/bitacora/bitacora_trabajo.md` (este archivo).
- MD desactualizados movidos a `docs/_descartado/` (reversible): ver
  `docs/_descartado/INDICE_DESCARTE.md`. No se tocó la tesis.

### Estado actual del motor (permanente)
- COMPLETO: bias (D1/H4/H1), bos/structure, order_block, fvg_poi,
  liquidity_levels (BSL/SSL), dealing_range (EQ/premium-discount),
  htf_narrative, poi_anchor (ancla), plan (top-down 3 capas), data_feed.
- PENDIENTE en motor: exec fino M5/M1; fix sesgo NEUTRAL perpetuo en rangos
  (`engine/bias/narrative.py` `_bias_from_swings`, bug T8).

### Pendiente / bloqueos
- MT5 logueado en **MetaQuotes-Demo** (no cuenta real FundedNext). Hoy funcionó
  para velas de hoy; para histórico real del challenge hay que loguear FundedNext.
- EURUSD_M15.parquet no actualizado a 2026-08-05 (solo D1/H4/H1). Falta correr
  update de M15 para que el plan en vivo vea el día de hoy.
- Sin commit/push (regla Ruben).

### Roadmap recuperado y punto actual (agente humano → ingeniero)
- El repo NO tenía roadmap vivo (docs/plan/ purgado 2026-08-03). 21 roadmaps
  históricos recuperados selectivamente del commit d0a5f20 a
  `docs/planificacion/_roadmap_historico/` (solo hitos/fases/decisiones; SIN
  código de backtest ni libro 13), marcados HISTÓRICOS (no fuente de verdad).
- Diff honesto motor vs roadmap: `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.
- **Punto del roadmap (vista motor):** lectura completa (sesgo, estructura,
  OB/FVG, liquidez, dealing range, narrativa HTF, POI anclado, plan top-down 3
  capas) CERRADA. Ejecución fina PENDIENTE en motor: B2 (exec M5/M1), C2/C3/D1
  (setups), E1 (trade mgmt), y bug T8 (sesgo NEUTRAL en rango). El backtest
  estaba más adelantado en ejecución, pero es desechable; el motor es lo
  permanente y es donde falta subir esas capas.

## Registro de sesiones anteriores (resumido)
- 2026-08-03: purga intencional de roadmaps (docs/plan/). Fuente de verdad =
  AGENTS.md + docs/tesis/ + engine/.
- 2026-07-16..17: R6 cerrado en código; auditorías de fidelidad a tesis y
  cobertura de backtest. Ver docs/auditorias/ (vigentes) y docs/_descartado/
  (los que cruzaban roadmaps ya purgados).
