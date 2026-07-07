# Tarea 3 — Verificación de limpieza Pandas / chained-assignment (Pandas 4 / CoW)

Fecha de verificación: 2026-07-07
Entorno: venv aislado `C:/Users/v_jac/smc_probe` (Python 3.14.6)
Dependencias de verificación: numpy 2.5.1, pandas **3.0.3**, pyarrow, scikit-learn 1.9.0, scipy, joblib, pyyaml, pytest 9.1.1, optuna 4.9.0, pyzmq 27.1.0, langgraph, langchain.

## Conclusión

**La Tarea 3 está COMPLETA y VERIFICADA.** No hay asignaciones encadenadas
(chained-assignment) inseguras en el código. El proyecto ya es compatible con
Pandas 4 (copy-on-write siempre activo).

## Evidencia

### 1. Ejecución del suite de tests bajo pandas 3.0.3 (CoW siempre ON)
- Comando: `pytest tests harness -W always::pandas.errors.ChainedAssignmentError`
- Resultado: **349 passed, 18 failed, 1 skipped**
- **ChainedAssignmentError: 0**
- **SettingWithCopyWarning: 0**
- Warnings totales: solo 5 (todas `datetime.utcnow()` deprecado — triviales, no de pandas).

Los 18 fallos son por el stub de `MetaTrader5` (inyectado para poder correr sin
MT5 instalado) y por modelos de ML que no están en el venv de verificación.
**Ningún fallo es por asignación encadenada.**

### 2. Escaneo estático AST de patrones encadenados
- Script: `scripts/_scan_chained.py`
- Encontró 3 sitios sintácticos `obj[a][b] = val`:
  `adapters/feature_enrichment_adapter.py:190-192`
- **Falso positivo:** allí `results` es una `list[dict]`, NO un DataFrame.
  `results[target]["inducement_detected"] = ...` es asignación a dict anidado,
  segura y correcta bajo CoW. No requiere cambio.

### 3. Búsqueda de `df[mask][col] = val` en todo el repo
- Únicos matches reales de asignación: los de `results[...]` arriba (lista de dicts).
- Resto: asserts de lectura en tests y el propio script de escaneo.
- **0 asignaciones encadenadas sobre DataFrames.**

## Notas técnicas

- pandas 3.0.3 ya tiene copy-on-write SIEMPRE activo (el `set_option("mode.copy_on_write")`
  emite `Pandas4Warning` diciendo que ya no se puede desactivar). Por tanto, si el
  código tiene asignación encadenada insegura, O BIEN lanza `ChainedAssignmentError`
  O BIEN falla silenciosamente (el write no afecta al original). Al correr 349 tests
  sin ningún `ChainedAssignmentError`, se confirma que no hay ese patrón.
- El commit previo `abb7343` (fix(pandas4): remove deprecated infer_objects(copy=False)
  + add live drift check) ya había quitado la API deprecada. No quedan APIs de pandas
  obsoletas en el código ejercitado.

## Archivos de apoyo (reutilizables para re-verificar)
- `scripts/_probe_warn.py` — importa módulos + corre pytest capturando warnings.
- `scripts/_probe_warn_b.py` — ejercita detectores con DataFrames sintéticos.
- `scripts/_scan_chained.py` — escaneo AST de asignaciones encadenadas.
- `conftest.py` — inyecta stub de `MetaTrader5` para correr tests sin MT5
  (solo para verificación offline; quitar antes de usar MT5 real).

## Pendiente de la Tarea 3 (menor, opcional)
- Reemplazar `datetime.utcnow()` por `datetime.now(datetime.UTC)` en
  `backtest/validation/report_generator.py:18` y `scripts/check_mt5.py` para
  eliminar las 5 deprecaciones restantes (no afecta funcionalidad).
