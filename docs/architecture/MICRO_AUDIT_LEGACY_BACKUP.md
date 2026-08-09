# MICRO_AUDIT_LEGACY_BACKUP.md — Auditoría de `legacy_smc_backup` (MATRIZ FINAL)

> **Micro-auditoría pura (2026-08-09).** Solo lectura, rastreo y clasificación.
> CERO movimientos, CERO Python, CERO commit, CERO push.
> Regla: *Un archivo no deja de ser producto por llamarse `_legacy`; primero se
> demuestra que no tiene consumidores vivos.* Y: *La ausencia de un import no
> demuestra muerte; demuestra únicamente ausencia de ese tipo de consumidor.*

## Matriz final de los 10 ítems

| # | Ítem | Evidencia de consumo | Estado | Acción |
|---|------|----------------------|--------|--------|
| 1 | `__init__.py` (raíz) | **0 bytes** en backup; NO trackeado en git; `pyproject` usa `packages.find` (no requiere __init__ raíz); nadie hace `import SMC_SYSTEMS`/`from . import`. Capacidad: ninguna. | **MUERTO (evidencia)** | NO restaurar |
| 2 | `_data_legacy.py` | 24 refs (`data/`, `adapters/`, `scripts/`); al sacarlo rompió `ict_backtest→signals→data`. | **VIVO** | RESTAURADO a raíz (pendiente commit B) |
| 3 | `_progress.py` | 21 refs (`data/mt5/connector.py`); igual rompió cadena al sacarlo. | **VIVO** | RESTAURADO a raíz (pendiente commit B) |
| 4 | `check_edge_progress.bat` | Solo citado en `docs/_archivo/avances/ESTADO_ACTUAL.md` (histórico). Es medidor de `edge_diagnosis`. | HISTÓRICO | MANTENER BACKUP |
| 5 | `reset_and_run_cortos.bat` | Llama `scripts/edge_diagnosis/run.py --all` (EXISTE, vivo). Invocado por `run_edge_diagnosis.vbs`. | **VIVO-OP** | MANTENER BACKUP (launcher harness) |
| 6 | `run_capa3_optuna.bat` | Solo `docs/_archivo/avances/...md` (histórico). | HISTÓRICO | MANTENER BACKUP |
| 7 | `run_edge_diagnosis.bat` | Llama `scripts/edge_diagnosis/run.py --all` (EXISTE). Citado por `scripts/windows/download_missing_data.bat` (VIVO). | **VIVO-OP** | MANTENER BACKUP (launcher harness) |
| 8 | `start_all_session.bat` | Launcher arranque de sesión: targets `run_app.py`, `scripts/loop_analisis.py`, `scripts/vigilante_riesgo.py`, MT5 — TODOS EXISTEN hoy. Citado en README:122. | **VIVO-OP** | INVESTIGADO → restaurar (decisión Director) |
| 9 | `start_all_session.vbs` | Lanza el .bat oculto vía Carpeta de Inicio de Windows. Coexiste con `start_hermes_session.ps1`. | **VIVO-OP** | INVESTIGADO → restaurar (decisión Director) |
| 10 | `src/_legacy_data/` | Solo en MD de auditoría. Datos legacy. | HISTÓRICO | MANTENER BACKUP |

## Frentes investigados (orden del Director)

### Frente 1 — `start_all_session.bat/.vbs` (INVESTIGAR →结果)
- `.bat` arranca: MT5 FundedNext + `scripts/loop_analisis.py` + `scripts/vigilante_riesgo.py`
  + `run_app.py` (PySide6 observador). Todos EXISTEN en repo vivo.
- `.vbs` = acceso directo de Carpeta de Inicio de Windows (arranque automático).
- Existe launcher más moderno `start_hermes_session.ps1` (arranque de Hermes) y `start_local.ps1`.
  `start_all_session` = arranque del observador/MT5; coexisten. README lo documenta como vivo.
- **Conclusión: VIVO-OPERACIONAL.** Debería restaurarse al repo (es el launcher de arranque
  de sesión del operador). Decisión de restauración pendiente del Director.

### Frente 2 — `__init__.py` raíz (INVESTIGAR →结果)
- Archivo en backup = **0 bytes**. No trackeado en git (`git ls-files` vacío para raíz).
  Borrado en commit `f5f50e7`. `pyproject.toml` usa `[tool.setuptools.packages.find]`
  (auto-descubre, no requiere __init__ raíz). Ningún `import SMC_SYSTEMS`/`from . import`.
- **Conclusión: MUERTO con evidencia.** Capacidad proveída = ninguna. NO restaurar.

### Frente 3 — cadena de launchers (NO declarar muertos)
```
download_missing_data.bat (VIVO scripts/windows/)
   └─> scripts/download_multiyear.py (EXISTE)
   recomienda run_edge_diagnosis.bat
run_edge_diagnosis.bat ─> scripts/edge_diagnosis/run.py --all (EXISTE, harness vivo)
reset_and_run_cortos.bat ─> scripts/edge_diagnosis/run.py --all (EXISTE)
run_edge_diagnosis.vbs ─> reset_and_run_cortos.bat
```
- `scripts/edge_diagnosis/` existe hoy con `run.py`, `_precache.py`, `status_edge.bat`, `_loop.sh`.
- **Conclusión: árbol de herramientas VIVO** (launchers del harness edge_diagnosis).
  No tocar ninguno.

## Veredicto de gobernanza

- **Restaurados (VIVOS, dependencias):** `_data_legacy.py`, `_progress.py` → ya en raíz.
- **Restaurar pendiente decisión:** `start_all_session.bat/.vbs` (launcher de arranque vivo).
- **Muerto con evidencia:** `__init__.py` raíz (0 bytes, no trackeado).
- **VIVO-OP (no tocar):** `reset_and_run_cortos.bat`, `run_edge_diagnosis.bat` (launchers harness).
- **Histórico (backup):** `check_edge_progress.bat`, `run_capa3_optuna.bat`, `src/_legacy_data/`.
- **Carpetas `legacy_*` en backup:** 0 refs vivas; `legacy_tests/` tiene 11 tests de regresión
  potencialmente útiles → MANTENER BACKUP + INVESTIGAR en FASE 3E.

## Plan de commits (separados, sin push)
- **A (hecho):** `b475023` `detectors/killzones.py`
- **B:** `_data_legacy.py` + `_progress.py` (restauración de dependencias vivas)
- **C:** constitución/documentación 2.2 (`docs/architecture/*.md`)
- **D:** micro-auditoría (`docs/architecture/MICRO_AUDIT_LEGACY_BACKUP.md`)
- `start_all_session.bat/.vbs` → commit propio solo tras decisión del Director.

Nada se movió ni borró. Matriz lista para revisión del Director antes de FASE 3A-1.
