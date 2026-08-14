# Perímetro Oficial de Pruebas — Conformidad `engine/` vs SDD

**Fecha:** 2026-08-14 · **Estado:** VIGENTE (aprobado por Director)

Este archivo declara el gate oficial de conformidad del motor. Solo lo listado aquí
cuenta para `TESTED` / `SEMANTICALLY_VERIFIED`. Lo externo se trata como se indica.

## Gate oficial (debe pasar para conformidad)

1. **Verificación de fuentes:** `python scripts/check_truth_sources.py`
   → criterio: `BROKEN ACTIVE=0`, `CROSS-PROJECT=0`.
2. **Compilación:** `python -m compileall -q engine ict_backtest market_replay app_observador/core`
   → exit 0.
3. **Separación:** `engine/` NO importa `ict_backtest/` (auditado estático: 0 coincidencias).
4. **Pruebas vigentes del motor:**
   - estructura (`test_market_structure.py`)
   - secuencia / linaje (`test_m2_lineage.py`, `test_phase6_lineage.py`)
   - POI (`test_poi_*.py`)
   - contexto MTF (`test_multitf_context.py`)
   - ejecución B2 (`test_*_execution*.py`)
   - OTE (`test_engine_ote.py`, `test_engine_dealing_range.py`)
   - liquidez (`test_liquidity_*.py`)
   - zonas (`test_*_zones*.py`)
   - anti-look-ahead (`test_labels_isolation.py` con contrato ajustado)
5. **Batería rápida de replay:** `tests/test_market_replay_audit_battery.py` (12 tests).
6. **Equivalencia sintética y real escalada** (F5): perfiles 100/200/400/800/1600 velas.

## Tratamiento fuera del perímetro

- `tests/_broken/`: **QUARANTINED** (causa documentada en `tests/QUARANTINE.md`).
  No se resucitan APIs eliminadas solo para hacer pasar pruebas.
- Datasets inexistentes: resultado **BLOCKED_DATA** (no PASS, no FAIL).
- Timeout / interrupción (ej. GitHub 6h limit): resultado **INCONCLUSIVE_OPERATIONAL**.
- APIs eliminadas: no se reimplementan para satisfacer pruebas muertas.

## Criterio de PASS (estricto)

- exit code 0 en todas las suites del gate.
- trazas/eventos coincidentes en equivalencia (índices, timestamps, tf, dirección, niveles).
- relaciones padre-hijo preservadas.
- dos ejecuciones consecutivas idénticas.
- cero look-ahead demostrable.
- ningún dato sustituido/imputado.

INCONCLUSIVE ≠ PASS. BLOCKED_DATA ≠ FAIL.
