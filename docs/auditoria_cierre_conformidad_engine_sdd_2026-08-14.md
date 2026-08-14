# Auditoría Independiente de Conformidad — `engine/` vs SDD vigente

**Fecha:** 2026-08-14 (noche) · **Auditor:** Consejo de Agentes (rol Auditor Independiente)
**Baseline:** `b3fa2c7` · **Rama:** `feature/backtest-ict` · **HEAD auditado:** `d7a207a`
**Veredicto:** **AUDITED** (con riesgos residuales y 1 bloqueo de autoridad documentado)

## 1. Alcance auditado
Motor `engine/` y consumidores directos (`ict_backtest/`, `market_replay/`, `app_observador/core`),
trazabilidad SDD→código→pruebas, y perimeter oficial de pruebas. No se audita el backtest
como fuente de decisiones (es consumidor desechable del motor).

## 2. Trazabilidad (SDD → código → pruebas)
| Componente (SDD) | Código | Prueba | Estado |
|---|---|---|---|
| POI anclado (BOS/CHOCH) | `engine/poi_anchor.py`, `zone_authority.py` | `test_poi_*.py` | COMPLIANT |
| Secuencia SWEEP→DISPLACE→BOS→RETURN | `engine/sequence.py` | `test_m2_lineage.py` | COMPLIANT |
| Cascada D1→H4→H1 + ejecución M5/M1 | `engine/multitf_context.py`, `engine/plan.py` | `test_multitf_context.py` | COMPLIANT |
| SL estructural + RR 1:3 | `engine/trade_levels.py` | `test_*_execution*.py` | COMPLIANT |
| Bias HTF top-down | `engine/bias/narrative.py` | `test_engine_htf_narrative.py` | COMPLIANT |
| OTE 62-79% | `engine/ote.py` (LONG en descuento, SHORT en premium) | `test_engine_ote.py` | COMPLIANT + metadata (no gate) |
| Order Block | `engine/order_block.py` (confirma vela siguiente) | `test_*_ob*.py` | COMPLIANT (ver bloqueo #1) |
| Sin indicadores prohibidos | auditoría estática | grep imports | COMPLIANT (0 en engine/) |

## 3. Causalidad / anti-look-ahead
- `engine/order_block.py` usa `shift(-1)` (vela siguiente) para confirmar OB.
- `detectors/ob.py` usa `shift(1)` (vela anterior) y argumenta que `shift(-1)` es fuga.
- **Contradicción documentada** (Bloqueo #1). El motor `engine/` es canónico por decisión
  del Director; `detectors/ob.py` queda como fachada pendiente de unificación.

## 4. Autoridad de niveles (POI)
- POI anclado al evento HTF padre ya cerrado. Fail-open cuando no hay eventos HTF:
  **EXPECTED BY DESIGN** (SDD lo permite explícitamente, no es bug).

## 5. Separación engine/backtest
- `engine/` NO importa `ict_backtest/` (auditado: 0 coincidencias).
- `ict_backtest/` es consumidor (fachada `ict_backtest/engine.py` re-exporta `engine.signal`,
  `engine.trade_levels`, `ict_backtest.simulator`).
- `market_replay/` consume `engine.*` (autorizado por SDD_MARKET_REPLAY §5).

## 6. Tratamiento de UNKNOWN / datos
- `tests/_broken/`: QUARANTINED (causa en `tests/QUARANTINE.md`).
- Datos faltantes → BLOCKED_DATA; timeout → INCONCLUSIVE_OPERATIONAL. Nunca PASS.

## 7. Evidencia de verificación (independiente del replay escalado)
- `check_truth_sources.py`: 23/23 activas, 0 rotas, 0 cross-project. ✅
- `compileall engine ict_backtest`: exit 0. ✅
- Batería replay rápida: 12 passed. ✅
- Linaje/continuidad: 17 passed, 1 skipped. ✅
- FASE A (backtest canónico): 18 setups, 100% §4. ✅

## 8. Riesgos residuales
1. **Bloqueo #1 (autoridad):** confirmación OB vela siguiente (`engine`) vs anterior
   (`detectors`). Requiere fallo del Director. Hasta entonces, `engine/` es la fuente
   canónica y `detectors/ob.py` queda en cuarentena de unificación.
2. **Rendimiento MarketReplay:** O(n²) en ventanas >100 velas (timeout N≥400). El motor
   directo NO lo padece (FASE A 18 setups en backtest canónico). Parche `copy_objs`
   pendiente (MISIÓN rendimiento, fuera de este cierre).
3. **Replay escalado INCONCLUSIVE:** no se declara PASS del replay en N≥400.

## 9. Veredicto
`engine/` alcanza **IMPLEMENTED → TESTED → SEMANTICALLY_VERIFIED → AUDITED** en el
perímetro activo. Las 5 decisiones de autoridad fueron aprobadas por el Director y
aplicadas donde no hubo contradicción; la única pendiente (OB confirmación) está
documentada como bloqueo y no invalida la conformidad del motor.

**AUDITED** — firmado por el Auditor Independiente (Consejo de Agentes), 2026-08-14.
La aceptación final (ACCEPTED) corresponde al Director.
