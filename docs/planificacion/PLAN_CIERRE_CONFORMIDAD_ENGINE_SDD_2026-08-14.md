# Plan de Cierre de Conformidad — `engine/` vs SDD vigente

**Fecha:** 2026-08-14 · **Estado:** EN EJECUCIÓN (autónoma, con aprobación del Director)
**Responsable:** Hermes (orquestador) bajo Consejo de Agentes activo.
**Objetivo:** llevar `engine/` de IMPLEMENTED→TESTED→SEMANTICALLY_VERIFIED→AUDITED, y dejar evidencia para ACCEPTED (Director).

## Decisiones de autoridad YA APROBADAS por el Director
1. OTE = metadata/calidad, NO gate duro en `fine_execution`. API canónica: `engine.ote.ote_zone` / `is_ote_entry` / `flag_ote`.
2. Order Block = única semántica canónica con `origin_index` + `confirmed_index`; activación solo desde confirmación cerrada; zona por cuerpo; mechas separadas para invalidación.
3. `detectors/ob.py` = fachada compatible que delega en `engine/order_block.py`.
4. `tests/_broken/` = QUARANTINED (causa documentada), fuera del gate oficial.
5. Metadatos descriptivos ERL/IRL se separan de etiquetas decisionales.
6. `.hermes.md` / `engineering.md` ausentes → se eliminan sus referencias del protocolo (no se crean).

## Fases
- [x] **F0 Reality Map** — working tree mapeado (HEAD=b3fa2c7; commits FIX en origin).
- [x] **F1 Contract Reconciliation** — SDD↔engine↔tests: OTE sin inversión, OB ya canónico, POI fail-open EXPECTED BY DESIGN.
- [x] **F2 Shadow Verification OTE/OB** — OB 27/2000 velas, status event-driven; añadir índices = trazabilidad.
- [x] **F3a Quarantine tests/_broken** — tests/QUARANTINE.md (fuera del gate).
- [ ] **F3b/c Correcciones OB** — BLOQUEADO autoridad: confirmación vela siguiente (engine) vs anterior (detectors/ob.py:20-26). Requiere fallo Director.
- [x] **F4 Perímetro oficial de pruebas** — docs/planificacion/PERIMETRO_PRUEBAS_CONFORMIDAD.md.
- [~] **F5 Replay y verificación semántica** — N=100 PASS aislado; N>=400 INCONCLUSIVE_OPERATIONAL (timeout O(n²) MarketReplay). No se declara PASS escalado.
- [x] **F6 Auditoría independiente** — docs/auditoria_cierre_conformidad_engine_sdd_2026-08-14.md → AUDITED.
- [ ] **F7 Aceptación final** — DECISIÓN DEL DIRECTOR (ACCEPTED). Fuera del alcance de Hermes.

## Reglas de ejecución
- Nunca "corregir" sin evidencia; shadow comparison previo a cambio de semántica.
- Timeout/cancelación/datos faltantes = INCONCLUSIVE/BLOCKED_DATA, nunca PASS.
- Commits acotados; push a origin/feature/backtest-ict tras cada unidad.
- Bitácora actualizada en cada paso.
