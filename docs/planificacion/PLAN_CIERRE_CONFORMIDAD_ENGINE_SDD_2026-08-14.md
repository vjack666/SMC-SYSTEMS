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
- [x] **F0 Reality Map** — working tree mapeado (25 archivos; 23 sucios tras commits FIX pusheados).
- [x] **F1 Contract Reconciliation** — SDD↔engine↔tests cruzado. 0 bugs ciegos. 3 AMBIGUOUS CONTRACT + 2 DOC GAP resueltos por aprobación del Director.
- [ ] **F2 Shadow Verification OTE/OB** — comparación OLD vs NEW antes de tocar semántica.
- [ ] **F3 Correcciones técnicas** — quarantine tests/_broken; fachada detectors/ob.py; índices OB.
- [ ] **F4 Perímetro oficial de pruebas** — gates declarados.
- [ ] **F5 Replay y verificación semántica** — escalado 100→2000 velas con runner_monitor.
- [ ] **F6 Auditoría independiente** — paquete congelado + informe AUDITED.
- [ ] **F7 Aceptación final** — decisión fechada del Director (ACCEPTED).

## Reglas de ejecución
- Nunca "corregir" sin evidencia; shadow comparison previo a cambio de semántica.
- Timeout/cancelación/datos faltantes = INCONCLUSIVE/BLOCKED_DATA, nunca PASS.
- Commits acotados; push a origin/feature/backtest-ict tras cada unidad.
- Bitácora actualizada en cada paso.
