# Contexto SDD — SMC-SYSTEMS

Contexto detectado por inspección directa del repositorio el **2026-08-07** (rama `feature/backtest-ict`).
Este documento es la entrada obligatoria para toda fase SDD posterior. Donde el `README.md` o el
`harness/README.md` contradicen lo que sigue, **manda este documento**: fue verificado ejecutando
comandos, no leyendo documentación.

---

## Ruta rápida

1. Leer la sección **[Ley arquitectónica](#1-ley-arquitectónica-motor-vs-backtest)** — nada se decide sin ella.
2. Leer la sección **[Regla de procesos largos](#2-regla-de-procesos-largos-runner-monitor)**.
3. Usar el comando de test de `openspec/testing-capabilities.md`.
4. Consultar **[Trampas verificadas](#6-trampas-verificadas-documentación-obsoleta)** antes de confiar en cualquier README.

---

## 1. Ley arquitectónica: MOTOR vs BACKTEST

Fuente normativa: `AGENTS.md`, sección *LEY FUNDAMENTAL — MOTOR vs BACKTEST*.
Resumen fiel:

| # | Regla | Verificación en código |
|---|-------|------------------------|
| 1 | `engine/` es la **única** fuente de decisión. Bias, estructura, POI y ejecución viven en el motor. El motor es la tesis hecha código y debe responder en vivo sin el backtest. | `engine/` (16 módulos raíz + `bias/`, `bos/`), 3 319 líneas |
| 2 | `ict_backtest/` **no tiene lógica propia**. Su único rol es el reloj vela a vela más la llamada al motor y la medición de resultados. Está PROHIBIDO crear allí módulos de decisión o detección. | `ict_backtest/` importa `engine` en 8 módulos de primer nivel |
| 3 | `ict_backtest/` es **desechable**. Cuando el motor esté completo se borra sin pérdida funcional. | — |
| 4 | El backtest **demuestra la tesis**: sin indicadores, sólo matemática pura y geometría de mercado. Cualquier EMA/RSI/ATR en `engine/` es sospechoso y debe justificarse contra la tesis. | — |
| 5 | Regla técnica derivada: **`engine/` nunca importa `ict_backtest/`**. El backtest sí puede importar el motor. | ✅ 0 imports detectados por AST |

**Test guardián:** `tests/test_engine_no_backtest_import.py` — escanea por AST todo `engine/**/*.py`
buscando `import ict_backtest` / `from ict_backtest` y exige cero coincidencias. Toda fase `verify`
debe ejecutarlo.

### Backtest canónico (único)

| Aspecto | Valor |
|---------|-------|
| Entrada principal | `ict_backtest/run_backtest.run_sequence_backtest` (línea 193) |
| Paridad | `ict_backtest/v2/orchestrator.run_sequence_parity` (línea 89) |
| Motor invocado | `engine/sequence.run_sequence` (línea 641) |
| Secuencia top-down | `engine/plan.build_context_stack` + `top_down_allows_trade` vía `est_htf_ctx_fn` |
| Eliminados / prohibidos | `run_mtf_intraday`, `generate_mtf_signals` — ✅ verificado: 0 ocurrencias en el repo |

No existe «backtest v2» como ruta de decisión alternativa. Referencia: `docs/DECISION_BACKTEST_UNICO.md`.

---

## 2. Regla de procesos largos (Runner Monitor)

Umbral: **cualquier comando que pueda superar 60 segundos**.

```bat
python scripts\runner_monitor.py --window --title "NOMBRE" -- <comando>
```

| Obligatorio | Prohibido |
|-------------|-----------|
| `--window` para que el operador vea una consola nueva | Background silencioso o detached sin ventana |
| Una sola espera bloqueante hasta el exit del proceso | Polling en el chat («sigo esperando…», «vivo (73 s)…») |
| Tras el exit: leer stdout/stderr + `results/runner_monitor_last.json` y analizar **una vez** | Porcentajes de progreso inventados |
| Workers ~70-80 % de hilos vía `HERMES_WORKERS`; prioridad Above Normal | Saturar el 100 % de CPU o usar prioridad High/Realtime |
| Multi-símbolo: máximo 2 jobs concurrentes, una ventana por símbolo | Repartir el presupuesto completo de workers a cada job |

Trabajos de menos de 60 s pueden correr en la terminal principal sin monitor.

> El script existe y es la fuente de verdad: `scripts/runner_monitor.py`.
> El documento `docs/plan/RUNNER_MONITOR.md` que citan `AGENTS.md` y `opencode.json` **ya no existe**.

---

## 3. Stack detectado

| Aspecto | Valor verificado |
|---------|------------------|
| Lenguaje | Python |
| Intérprete real de trabajo | `C:\Python314\python.exe` → **Python 3.14.6** |
| Intérprete alterno | `C:\Users\v_jac\smc_probe\Scripts\python.exe` → Python 3.14.6 (venv fuera del repo, sin MetaTrader5 real) |
| Declarado en `pyproject.toml` | `requires-python = ">=3.11"` |
| Declarado en CI | Python 3.11 (`.github/workflows/ci.yml`) |
| Gestor de paquetes | `pip` + `setuptools>=68`; instalación editable `pip install -e .` |
| Lockfile | ❌ ninguno (`requirements.txt`, `poetry.lock`, `uv.lock` ausentes) |
| Dependencias clave | pandas 3.0.3, numpy, scikit-learn, xgboost, pyarrow, scipy, optuna, PySide6, MetaTrader5, pyzmq, langgraph |
| `MetaTrader5` | ✅ importable bajo `C:\Python314`; `conftest.py` inyecta un stub no-op sólo si falta |

> **Aviso de deriva:** `pyproject.toml` fija `>=3.11`, la CI usa 3.11, pero el entorno real corre 3.14.6
> con pandas 3.0.3. Ya aparecen `Pandas4Warning` en `engine/bias/narrative.py`. Cualquier spec que toque
> pandas debe considerar esta brecha.

---

## 4. Mapa del repositorio (dominios relevantes)

| Directorio | Rol | Estado |
|------------|-----|--------|
| `engine/` | **Motor de decisión.** Fuente permanente. 3 319 LOC | ✅ activo |
| `engine/bias/`, `engine/bos/` | Narrativa de sesgo y estructura BOS/CHOCH | ✅ activo |
| `engine/structure/` | Sólo directorios vacíos (`dependencies/v2`) | ⚠️ andamio vacío |
| `ict_backtest/` | Consumidor puro y desechable. 9 560 LOC | ✅ activo |
| `ict_backtest/v2/` | Orquestador de paridad (`run_sequence_parity`) | ✅ activo |
| `ict_backtest/sesgo/`, `diagnostics/`, `setups/` | Medición y diagnóstico | ✅ activo |
| `app_observador/` | UI PySide6 del observador FundedNext | ✅ producción |
| `scripts/` | 32 entrypoints CLI, incluye `runner_monitor.py` | ✅ activo |
| `tests/` | 161 archivos, 936 tests colectables | ⚠️ parcialmente rojo |
| `harness/` | **Sólo contiene `README.md`.** El framework no existe | ❌ obsoleto |
| `docs/specs/` | Convención previa `MDS_*.md` (19 archivos, español) | ✅ coexistir |
| `docs/tesis/`, `docs/ict/` | Tesis formal y biblioteca ICT | ✅ fuente de verdad |
| `docs/plan/` | **No existe** (purgado 2026-08-03) | ❌ eliminado |

---

## 5. Convenciones del proyecto

| Tema | Convención observada |
|------|----------------------|
| Idioma de documentación | Español (docs, docstrings, comentarios, mensajes de commit) |
| Idioma de código | Inglés en identificadores, rutas y símbolos |
| Specs previas | `docs/specs/MDS_<FASE>_<TEMA>.md` con secciones: Responsabilidad, Dependencias, Módulo, Firma propuesta, Reglas duras, Criterios de aceptación, Trazabilidad |
| Números de performance | **Única fuente**: `docs/METRICS_CANON.md`. Los demás documentos enlazan, no copian |
| Commits | Sin atribución a IA. **No commitear ni pushear sin OK expreso del operador** |
| Estilo de import | `from __future__ import annotations` en módulos nuevos |

---

## 6. Trampas verificadas (documentación obsoleta)

Todo esto fue comprobado ejecutando comandos. No confiar en la documentación que lo contradice.

| Afirmación de la documentación | Realidad verificada |
|--------------------------------|---------------------|
| `harness/README.md`: framework con 11 adapters, 14 escenarios, `python -m harness` | ❌ `harness/` contiene **sólo** `README.md`. `git ls-files harness` devuelve un único archivo. `python -m harness` falla con `No module named harness.__main__` |
| `pyproject.toml`: `testpaths = ["tests", "harness"]` | ⚠️ `harness` no aporta ningún test |
| `AGENTS.md`: fuente de verdad `docs/tesis/SPEC_TESIS_FORMAL.md` | ❌ no existe ahí. La ruta real es `docs/ict/SPEC_TESIS_FORMAL.md` |
| `AGENTS.md`: fuente de verdad `docs/tesis/TRUTH_SOURCES.md` | ❌ no existe en ninguna parte |
| `AGENTS.md` / `opencode.json`: `docs/plan/RUNNER_MONITOR.md` y demás `docs/plan/*` | ❌ `docs/plan/` fue purgado. `opencode.json` referencia 8 archivos inexistentes |
| `AGENTS.md` / `README.md` / `opencode.json`: leer `COMPLETION_REPORT.md` | ❌ borrado en el árbol de trabajo actual |
| `README.md`: venv `smc_probe` dentro del proyecto | ⚠️ está en `C:\Users\v_jac\smc_probe`, fuera del repo |
| `AGENTS.md`: POI anclado cerrado en `engine/poi_anchor.py`, consumido por `ict_backtest.poi_filter` | ⚠️ `ict_backtest/poi_filter.py`, `poi_anchor.py`, `poi_anchor_motor.py`, `htf_pd_index.py` y `zone_authority.py` están **borrados** en el árbol de trabajo; `engine/poi_anchor.py` está **sin versionar**. Migración en curso |

---

## 7. Estado del árbol de trabajo (2026-08-07)

Rama `feature/backtest-ict`, último commit `9842394`. El árbol está **sucio** por una migración en curso:

| Tipo | Rutas |
|------|-------|
| Modificados | `.atl/skill-registry.md`, `.atl/.skill-registry.cache.json`, `_data_legacy.py`, `app_observador/core/engine.py`, `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` |
| Borrados | `COMPLETION_REPORT.md`, `ict_backtest/htf_pd_index.py`, `ict_backtest/poi_anchor.py`, `ict_backtest/poi_anchor_motor.py`, `ict_backtest/poi_filter.py`, `ict_backtest/zone_authority.py` |
| Sin versionar | `engine/poi_anchor.py`, `scripts/request_daily_bias.py`, `tests/test_engine_plan_pd.py`, `tests/test_engine_poi_anchor.py`, `_audit_docstrings.py` |

**Lectura:** hay una migración deliberada de POI/zonas desde `ict_backtest/` hacia `engine/`, alineada con
la Ley. Está a medio camino: `tests/test_poi_anchor.py` (el test viejo) falla porque apunta al módulo
eliminado. Ninguna fase SDD debe mezclar su cambio con esta migración sin resolverla primero.

---

## 8. Persistencia

| Aspecto | Valor |
|---------|-------|
| Modo | `openspec` (basado en archivos) |
| Raíz | `openspec/` |
| Engram MCP | ❌ no disponible en esta sesión. Todo se persiste en archivos |
| Registro de skills | `.atl/skill-registry.md` (existente, generado 2026-08-04) |

---

## Siguiente paso

Ejecutar `/sdd-explore` sobre el área objetivo, o `/sdd-new` si el cambio ya está acotado.
Antes de cualquiera de los dos, decidir con el operador qué hacer con la migración
`poi_anchor` pendiente descrita en la sección 7.
