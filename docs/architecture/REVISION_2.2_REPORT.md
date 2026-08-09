# REVISION_2.2_REPORT.md — Auditoría de fronteras antes de la constitución

> **FASE 2.2 (2026-08-09).** Auditoría pura. NO se movió, creó, renombró ni modificó
> código Python. NO guardrail. NO commit. Entregable pedido por el Director: informe que
> responde 7 preguntas y propone cambios a los 3 MD de FASE 2.1.

## 1. ¿La arquitectura 2.1 tiene alguna contradicción?

Sí, una: el diagnóstico de `killzones.py` en 2.1 estaba INCOMPLETO. Decía que la utilidad
temporal vivía solo en `ict_backtest/rules` y que había que decidir dónde ubicarla. La
auditoría real encontró que **`engine/killzone.py` YA es la fuente única** de
`server_to_utc` (l.50) y `_et_band_to_utc` (l.63), y que **`ict_backtest/rules.py:6` YA
importa desde `engine.killzone`** (`from engine.killzone import ... # noqa: F401`).

O sea la frontera ENGINE/TIME ya está resuelta en el código; solo `detectors/killzones.py`
quedó atrasado importando del backtest. La 2.1 proponía "no elegir ubicación todavía" —
correcto como prudencia, pero la evidencia ya muestra que `engine/killzone.py` es el sitio
natural (y actualmente la fuente de verdad). Esto NO contradice la regla "utilidad neutra
no depende de backtest"; al contrario, la confirma: el backtest ya consume engine, falta
que el detector haga lo mismo.

## 2. ¿Dónde está realmente la frontera ENGINE / DETECTORS / TIME / BACKTEST?

Evidencia:

- `detectors/` = 13 módulos de **detección geométrica** (bos, choch, displacement, fvg,
  gaps, liquidity, ob, trend, zones, killzones, liquidity_context, fib). Consumido por
  `engine/bos/structure.py`, `engine/htf_pd_index.py`, `ict_backtest/data_feed.py`,
  `ict_backtest/_cmp_bos.py`, `agents/ict_agent.py`, `signals/pipeline.py`, `adapters/`.
- `detectors/` NO importa `engine/` (0 hits) → es una **librería de dominio reutilizable**
  que vive CERCA de engine pero es independiente de él. Correcto según la arquitectura.
- `engine/killzone.py` = **subdominio temporal NEUTRO** ya existente (bandas de sesión,
  conversión servidor↔UTC, DST vía ZoneInfo). Docstring explícito: "Unica fuente de verdad
  del motor. El backtest LO CONSUME; nunca al revés."
- `ict_backtest/` = consumidor (12 archivos importan engine). `rules.py` importa de engine
  (es consumidor correcto) y además define `_dir_setup` (reglas propias del backtest).

**Frontera real:**
```
engine/killzone.py  (TIME, neutro, fuente de verdad)
        ↑ consumen
detectors/  (geometría)   +   ict_backtest/  (backtest)
```
El TIME ya está aislado en `engine/killzone.py`. No hace falta crear `detectors/_time_util.py`.

## 3. ¿Ubicación conceptual de las utilidades temporales y por qué?

Las 8 funciones sugeridas (`server_to_utc`, `_et_band_to_utc`, `session_to_utc`,
`utc_to_server`, `market_session`, `trading_day`, `timezone normalization`, `DST`) — de las
cuales ya existen `server_to_utc`/`_et_band_to_utc` en `engine/killzone.py` — constituyen
un **subdominio temporal real y transversal**, confirmando la intuición del Director.

**Veredicto:** pertenecen a `engine/killzone.py` (o a un futuro `engine/time/` si crece),
que es neutral respecto a backtest y a detectores. NUNCA a `ict_backtest/`. La regla queda:
> Una utilidad temporal (neutral) jamás puede depender de un consumidor como `backtest`.

El fix de FASE 3 es mínimo: `detectors/killzones.py` debe importar
`server_to_utc, _et_band_to_utc` desde `engine.killzone` (igual que ya hace
`ict_backtest/rules.py`), no desde `ict_backtest.rules`. Sin mover archivos, solo un import.

## 4. ¿Qué es `ict_backtest` realmente y qué debería ser?

`ict_backtest/` = 79 .py en subcarpetas: `diagnostics/`, `sesgo/` (medicion, motor_cable,
reloj), `setups/`, `v2/`, raíz (canonical, run_backtest, engine, object_adapter...).

- Es el **consumidor histórico del motor** (backtest canónico + v2 + sesgo + setups).
- Importa engine (12 archivos) → dirección correcta.
- Contiene partes que son genuinamente de backtesting: reloj vela-a-vela, fill, costs,
  runners, reports. Y partes que ya se delegaron a engine (killzone, POI, sequence).

**Veredicto:** `ict_backtest/` es el nombre histórico de la IMPLEMENTACIÓN del backtest. No
es conceptualmente incorrecto, pero es específico a ICT. Si el sistema termina soportando
SMC/Wyckoff/ML, el nombre se queda corto. Arquitectura futura posible (NO ejecutar):
```
backtest/
├── engine/      (orquestación del reloj)
├── runners/     (v2, canonical)
├── rules/       (sesgo, setups)
├── reports/     (diagnostics)
└── adapters/
```
Pero esto es indeciso hasta que existan otros motores. **Hoy: no renombrar.** Se documenta
como incertidumbre (ver §6).

## 5. ¿Qué riesgo arquitectónico existe en `legacy/` (in-repo)?

`legacy/` = 29 .py (subcarpetas: governance, harness, integration_mt5_bridge, monitoring,
orchestration, paper_trading).

Auditoría de referencias:
- **Código vivo que lo importa:** ninguno (los matches en `ict_backtest/engine.py` y
  `object_adapter.py` son módulos legacy-ish; los tests `test_data_legacy`,
  `test_r10c_semantic_vs_legacy` son de legacy). → En PRODUCCIÓN está muerto.
- **Scripts que lo referencian:** `download_data.py`, `download_h1_mtf.py`,
  `download_multiyear.py`, `live_market_read.py`, `runner_monitor.py` (rutas en strings,
  no imports rotos).
- **Tests que lo tocan:** `test_data_legacy.py`, `test_r10c_semantic_vs_legacy.py`,
  `test_r10c_adapter.py`, `test_a1_topdown_filter.py`, etc. → **si se borra, 4+ tests
  rompen** (deben migrarse o marcarse obsoletos primero).
- **Docs:** referenciado en bitácora e índices.

**Riesgo:** BAJO para runtime, MEDIO para CI (tests dependen de él). Decisión de FASE 3:
`archive/`, NO borrar. El backup de disco (`legacy_smc_backup`) es OTRA cosa y no se toca.

## 6. ¿Qué partes son incertidumbre y NO deben ser ley?

- Renombrar `ict_backtest/` → `backtest/` (depende de si habrá otros motores).
- Separar `runtime/` (app_observador + MQL5 + integration) (FASE 3, confirmado).
- Crear `data/manifests/` (FASE 3, confirmado).
- Si `engine/killzone.py` crece a `engine/time/` (solo si aparecen más funciones temporales).
- Si `legacy/` merece `archive/` o salida (FASE 3, tras migrar tests).

Esto NO se congela como ley en 2.2.

## 7. Cambios recomendados para los 3 MD (versión 2.2)

A. **ARCHITECTURE.md**: separar visualmente flujo FÍSICO de flujo EPISTEMOLÓGICO.
   - Físico: `DATA → ENGINE → BACKTEST → RESULTS`.
   - Epistemológico: `RESULTS → RESEARCH → HYPOTHESIS → [PUERTA: decisión pre-registrada] → ENGINE`.
   La puerta debe verse como una barrera, no como flecha.
B. **DEPENDENCY_RULES.md**: corregir el diagnóstico de `killzones.py` — ya no es "decidir
   dónde ubicar la utilidad" sino "el detector importa del backtest en lugar de
   `engine.killzone` que YA es la fuente". El fix FASE 3 es un import, no un movimiento.
C. **DIRECTORY_CONTRACT.md**: añadir que `engine/killzone.py` (TIME) es utilidad neutral que
   ni engine ni detectors consideran "del backtest"; reafirmar prohibición `RESULTS→ENGINE`
   automático y la LEY CENTRAL.
D. Mantener `legacy/` in-repo como incierto hasta FASE 3; diferenciarlo siempre del backup
   de disco.

## Conclusión

La 2.1 era correcta en intención; la 2.2 la hace PRECISA con evidencia. La frontera
ENGINE/DETECTORS/TIME/BACKTEST ya está mayormente resuelta en el código (engine/killzone es
la fuente temporal; ict_backtest la consume). La única violación real es un import atrasado
en `detectors/killzones.py`. `ict_backtest` es nombre de implementación, no conceptualmente
erróneo. `legacy/` está muerto en producción pero atado a tests → archive, no borrar.

**Sin movimientos. El plano está listo para aprobarse como constitución tras esta 2.2.**
