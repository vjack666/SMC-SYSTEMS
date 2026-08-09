# Capacidades de testing — SMC-SYSTEMS

**Modo Strict TDD:** ✅ **habilitado**
**Detectado:** 2026-08-07 (verificado por ejecución, no por lectura de documentación)
**Intérprete:** `C:\Python314\python.exe` (Python 3.14.6)

---

## Ruta rápida

```powershell
# Loop RED-GREEN-REFACTOR por defecto (rápido y verde: 116 passed en 3.77 s)
C:\Python314\python.exe -m pytest -q tests/test_engine_bias.py tests/test_engine_bos.py `
  tests/test_engine_dealing_range.py tests/test_engine_execution_b2.py `
  tests/test_engine_fvg_poi.py tests/test_engine_htf_narrative.py `
  tests/test_engine_liquidity_levels.py tests/test_engine_micro.py `
  tests/test_engine_no_backtest_import.py tests/test_engine_order_block.py `
  tests/test_engine_plan.py tests/test_engine_plan_ltf.py `
  tests/test_engine_plan_pd.py tests/test_engine_poi_anchor.py
```

```powershell
# Guardián de la Ley arquitectónica (obligatorio en toda fase verify)
C:\Python314\python.exe -m pytest -q tests/test_engine_no_backtest_import.py
```

---

## Test runner

| Campo | Valor |
|-------|-------|
| Framework | pytest **9.1.1** |
| Configuración | `pyproject.toml` → `[tool.pytest.ini_options]` |
| `testpaths` | `["tests", "harness"]` — `harness` no aporta tests (ver aviso abajo) |
| `pythonpath` | `["."]` |
| `conftest.py` raíz | Inyecta stub no-op de `MetaTrader5` sólo si el paquete real falta |
| Archivos de test | 161 en `tests/` |
| Tests colectables | **936** (con los `--ignore` obligatorios) |

---

## Comandos

### 1. Comando TDD (recomendado, verificado verde)

```
C:\Python314\python.exe -m pytest -q <archivos tests/test_engine_*.py>
```

| Métrica | Valor |
|---------|-------|
| Resultado | **116 passed**, 3 warnings |
| Duración | 3.77 s (5.6 s de pared) |
| Archivos | 14 |

Es el subconjunto que cubre `engine/`, es decir la única fuente de decisión según la Ley.
Para trabajo fuera del motor, ampliar con los archivos concretos del área tocada.

### 2. Suite completa local

La colección **aborta** sin los `--ignore`: 12 errores de importación (5 en `tests/`, 7 en el
directorio local `tests/_broken/`). Puede superar 60 s, por lo que debe ir por `runner_monitor`.

```bat
python scripts\runner_monitor.py --window --title "pytest-full" -- C:\Python314\python.exe -m pytest tests -q --ignore=tests/_broken --ignore=tests/test_r4_po3_isolated.py --ignore=tests/test_r7_divergence_investigation.py --ignore=tests/test_semaforo_rr.py --ignore=tests/test_structure_medicion.py --ignore=tests/test_structure_run.py
```

Con esos `--ignore`: **936 tests colectados, 0 errores de colección, en 3.79 s**.

### 3. CI

```yaml
# .github/workflows/ci.yml — Python 3.11, ubuntu-latest, sólo push/PR a main
pytest tests/ -q
```

Sobre un checkout limpio la CI no ve `tests/_broken/` (está en `.gitignore`), pero **sí** ve los
5 módulos rotos versionados. La CI no corre en `feature/backtest-ict`.

### 4. Harness — NO DISPONIBLE

```
python -m harness      # ❌ No module named harness.__main__
```

`harness/` contiene únicamente `README.md`. El framework descrito allí (11 adapters, 14 escenarios,
`adapters/`, `fixtures/`, `scenarios/`, `runners/`) **no existe en el repositorio ni en git**.
`harness/README.md` es documentación obsoleta y no debe usarse como contrato.

---

## Capas de test

| Capa | Disponible | Herramienta |
|------|-----------|-------------|
| Unit | ✅ | pytest |
| Integración | ✅ | pytest sobre datos reales en `data/raw` (`test_backtest_full_stack.py`, `test_pipeline_integration.py`) |
| Arquitectura | ✅ | `tests/test_engine_no_backtest_import.py` (AST scan, guardián de la Ley) |
| E2E / UI | ❌ | — |
| Harness por escenarios | ❌ | eliminado |

Marcadores en uso: `pytest.mark.skipif` ×7, `pytest.mark.parametrize` ×3, `pytest.mark.slow` ×2,
`pytest.mark.xfail` ×1. Ninguno está registrado en `pyproject.toml`.

---

## Cobertura y herramientas de calidad

| Herramienta | Disponible | Comando |
|-------------|-----------|---------|
| Cobertura | ❌ | `pytest-cov` no declarado ni configurado |
| Linter | ❌ | sin `ruff.toml`, `.flake8`, `setup.cfg`, `.pylintrc` |
| Type checker | ❌ | sin `mypy.ini` ni sección `[tool.mypy]` |
| Formatter | ❌ | sin `black`/`ruff format` configurado |
| Pre-commit | ❌ | sin `.pre-commit-config.yaml` |

`.gitignore` menciona `.mypy_cache/` y `.ruff_cache/`, señal de uso puntual histórico, pero
no hay configuración versionada.

---

## Veredicto Strict TDD

**`strict_tdd: true`**

### Justificación a favor

1. Existe un runner real y estándar (pytest 9.1.1) con configuración versionada en `pyproject.toml`.
2. Existe un comando **rápido y verde verificado en esta sesión**: 116 tests en 3.77 s sobre
   `engine/`, que es exactamente el dominio donde la Ley obliga a escribir toda la lógica nueva.
3. La colección completa es rápida (3.79 s), así que un agente escritor puede acotar el subconjunto
   afectado sin coste apreciable.
4. El repositorio ya practica TDD de facto: 936 tests para ~13 000 LOC de motor y backtest, con
   tests dedicados a invariantes arquitectónicas y anti look-ahead.

### Condiciones obligatorias (no negociables)

La suite **global no está verde**. Por eso Strict TDD aquí significa TDD **acotado**, no «correr todo».

1. **Capturar baseline RED antes de tocar código.** Ejecutar el subconjunto que se va a tocar y
   registrar qué falla ya. Un fallo preexistente no es una regresión.
2. **Nunca usar la suite completa como criterio GREEN.** Sobre la selección amplia
   `-k "engine or plan or poi or bos"` hay **25 failed + 7 errors** preexistentes en
   `test_r10c_semantic_vs_legacy.py`, `test_autopilot_from_engine.py`, `test_poi_anchor.py`,
   `test_dashboard_regime_and_votes.py`, `test_r10_bos_gap_dynamic.py`,
   `test_run_backtest_attach_plan.py`, `test_poi_engine_book21.py` y varios `test_plan_*`.
3. **`tests/test_poi_anchor.py` está roto a propósito**: apunta a `ict_backtest/poi_anchor.py`, que fue
   eliminado en la migración hacia `engine/poi_anchor.py`. No «arreglarlo» sin decisión del operador.
4. **Toda corrida que pueda superar 60 s va por `scripts/runner_monitor.py --window`.**
5. **El guardián de la Ley se ejecuta siempre** antes de cerrar un cambio:
   `pytest -q tests/test_engine_no_backtest_import.py`.

---

## Módulos con colección rota (excluir siempre)

| Módulo | Causa |
|--------|-------|
| `tests/test_r4_po3_isolated.py` | `ImportError: cannot import name 'build_signals_from_frames' from 'ict_backtest.engine'` |
| `tests/test_r7_divergence_investigation.py` | `FileNotFoundError` (dato ausente) |
| `tests/test_semaforo_rr.py` | `ModuleNotFoundError: scripts.semaforo_fundednext` |
| `tests/test_structure_medicion.py` | `ModuleNotFoundError: scripts.measure_structure` |
| `tests/test_structure_run.py` | `ModuleNotFoundError: scripts.measure_structure` |
| `tests/_broken/` (7 módulos) | Huérfanos locales, gitignored desde 2026-08-06 |

Los tres `ModuleNotFoundError` responden al mismo hecho: `scripts/_legacy/` está gitignored y esos
entrypoints ya no existen en `scripts/`.

---

## Siguiente paso

Registrar en la fase `sdd-tasks` qué subconjunto de tests define el GREEN de cada tarea,
y capturar su baseline RED en `sdd-apply`.
