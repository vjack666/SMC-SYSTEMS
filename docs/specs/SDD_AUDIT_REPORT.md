# SDD_AUDIT_REPORT.md — Auditoría del SDD existente (FASE A/B, contrato CEO)

**Fecha:** 2026-08-11 · **CEO:** Hermes · **Baseline auditada:** HEAD `76a8faa`
**Dominio:** Forex / ICT-SMC exclusivo. (Ver contaminación §6.)
**Método:** lectura de archivos reales + inspección de árbol. NO se modificó `engine/` ni
`ict_backtest/` (contrato CEO §3).

---

## 1. MATRIZ DE AUDITORÍA (contrato CEO §19)

Cada celda: Estado / Evidencia (archivo real) / GAP / Acción.

| Área | Estado | Evidencia | GAP | Acción |
|------|--------|-----------|-----|--------|
| Requirements | PARCIAL | `docs/tesis/SDD_*.md` (contexto, decisión, límites, plan) | sin DoR formal | conservar + enlazar DoR (§1) |
| Design | PARCIAL | `SDD_RESCATE_POI_HTF.md` §2 contratos de módulo; `SDD_LTF_ENTRY_LAYER.md` | sin separación 4 conceptos | conservar + §8 |
| Tasks | BUENO | `SDD_*.md` §4 planes paso a paso con tests | — | conservar |
| Implementation | FUERA ALCANCE (prohibido) | `engine/` (no se toca) | — | — |
| Testing | PARCIAL | `py_compile`+`pytest`+smoke en contratos | solo técnico, sin semántico | añadir §4 |
| Semantic validation | AUSENTE del SDD | HYP-002 Fase5/6 inventó `phase*_validation.py` ad-hoc | no es regla SDD | añadir §4 |
| Audit | BUENO (parcial) | `agents/governance/auditor_independiente.md` (veto promoción) | no sellado en estado SDD | enlazar §3 AUDITED |
| Acceptance | DÉBIL | `ingeniero.md` "SDD alineado"; sin firma explícita | no DoD | añadir §2 |
| Traceability | PARCIAL | `INDICE_MDS.md` (comp↔SDD) | falta tramo tesis→código→evidencia | añadir §6 |
| Change impact | AUSENTE | `evidence-docs.md` DP-1/DP-2 lo insinúa | no formal | añadir §7 |
| Agent authority | BUENO | `ROLES_GOBERNANZA.md`, `ORQUESTADOR.md` | `PROTOCOLO_AGENTE` apunta a `docs/specs/` erróneo | corregir punteros |
| Research → engine | BUENO | `RESEARCH_CONTRACT.md` (HYP/EXP, puerta) | — | conservar |

---

## 2. DIAGNÓSTICO — qué estaba MAL / qué faltaba (contrato CEO §22.1/§22.2)

### CRÍTICO
- **C1 — Sin Definition of Ready ni Definition of Done.** "DONE" implícito = código
  existe. Viola §6/§7 del contrato. El `ingeniero.md` §3.4 dice "SDD alineado" pero no
  define estados ni verificación semántica. → Resuelto en `SDD_GOVERNANCE.md` §1/§2.
- **C2 — Sin máquina de estados formal del SDD.** El modelo "P0→P7 pisos" (`ROLES_
  GOBERNANZA.md`) existe para ideas, pero los specs de motor no tienen DRAFT→…→ACCEPTED
  con autoridad por estado. → Resuelto §3.
- **C3 — Sin verificación semántica en el SDD.** La separación IDENTITY/LINK/CAUSALITY
  que HYP-002 Fase 5/6 demostró funciona está en scripts ad-hoc, NO es regla SDD. Cualquier
  futura modificación de `engine/` podría romper el linaje sin que el SDD lo exija. → §4.
- **C4 — Sin matriz de trazabilidad.** `INDICE_MDS.md` es índice de componentes, no
  traza Tesis→SDD→Código→Test→Evidencia→Decisión. → §6.

### ALTO
- **A1 — Triple fuente de SDD (duplicación).** `docs/specs/` (MDS_*.md), `docs/tesis/
  SDD_*.md`, y `openspec/changes/` conviven. `openspec/README` dice "no reemplazan" pero
  viven en paralelo sin jerarquía → riesgo de divergencia (anti-patrón §18). → Resuelto
  con árbol de autoridad §0; `openspec/` congelado §12.
- **A2 — Punteros rotos de "SDD relevante".** `PROTOCOLO_AGENTE.md` §2 y `CONTRATO_ORDEN.
  md` §1/§5 citan `docs/specs/` como el SDD, pero los specs de estrategia viven en
  `docs/tesis/`. Un agente nuevo busca en el lugar equivocado. → Corregido en §0 + parches.
- **A3 — `AGENTS.md`/`README.md`/opencode.json con rutas muertas.** `evidence-docs.md`
  (SDD-00) documentó 16+ claims rotos (COMPLETION_REPORT borrado, docs/plan purgado,
  SPEC_TESIS_FORMAL en `docs/ict/` no `docs/tesis/`, etc.). Fuera de alcance de ESTA misión
  (es limpieza de docs, no SDD), pero se REPORTA como GAP de fuente de verdad. → Ver §5.

### MEDIO
- **M1 — Sin regresión semántica formal.** `evidence-docs.md` DP-1/DP-2 documenta flags de
  regresión cero pero como "decisiones protegidas", no como categoría del proceso SDD. → §5.
- **M2 — Sin plantilla de impact analysis.** → §7.
- **M3 — 4 conceptos no son regla SDD.** Están implícitos en HYP-002 pero no en el SDD. → §8.
- **M4 — Regla de no-invención no en gate SDD.** → §9.

### BAJO
- **B1 — Cero-indicadores:** presente en AGENTS.md y `INDICE_MDS.md` (regla dura). Bien,
  pero no cableado como aceptación del SDD más allá de la Ley. → §10 (refuerzo).

---

## 3. QUÉ ESTABA BIEN (conservar, no tocar)

- `RESEARCH_CONTRACT.md`: HYP/EXP, protocol.yaml, verdict.yaml, data_manifest → excelente
  maquinaria de reproducibilidad. Modelo a imitar para el lado producto.
- `ROLES_GOBERNANZA.md` + `ORQUESTADOR.md`: separación de roles, veto del Auditor, principio
  "quien propone ≠ construye ≠ audita ≠ aprueba".
- `INDICE_MDS.md`: índice de componentes auditado contra el motor real (2026-08-08).
- `SDD_RESCATE_POI_HTF.md` / `SDD_LTF_ENTRY_LAYER.md`: specs de diseño con contexto,
  decisión, límites, plan y riesgos — base sólida; solo faltaba el marco formal (DoR/DoD/
  estados/semántica) que este meta-SDD les da.
- `auditor_independiente.md`: veto de PROMOCIÓN, anti data-snooping, verdad estadística.

---

## 4. DISEÑO PROPUESTO (FASE C) — qué se conserva / modifica / fusiona / elimina

| Artefacto | Decisión | Motivo |
|-----------|----------|--------|
| `docs/specs/SDD_GOVERNANCE.md` | **CREAR** (este meta-SDD) | define DoR/DoD/estados/semántica/trazabilidad |
| `docs/tesis/SDD_*.md` | **CONSERVAR** | specs de diseño vigentes; ahora enlazados al meta-SDD |
| `docs/specs/INDICE_MDS.md` | **CONSERVAR** | índice de componentes; es la pieza de trazabilidad existente |
| `PROTOCOLO_AGENTE.md` §2 | **MODIFICAR** | apuntar "SDD relevante" a `docs/tesis/SDD_*.md` + `SDD_GOVERNANCE.md` |
| `CONTRATO_ORDEN.md` §1/§5 | **MODIFICAR** | aclarar que SDD vive en `docs/tesis/` y `docs/specs/` (índice+meta) |
| `openspec/` | **CONGELAR** (§12) | línea base forense histórica; no SDD vivo |
| `AGENTS.md` / `README.md` / opencode.json | **NO TOCAR** (fuera de alcance) | limpieza de docs es otra misión; se REPORTA en §5 |

---

## 5. CONTAMINACIÓN / FUENTES ROTAS REPORTADAS (no arregladas aquí)

- **Contaminación dominio (contrato §2):** varios docs históricos citan "QUOTEX"/"binarias"
  (ej. `openspec/README.md` "adaptado de backtest quotex"; `app_observador` = "Observador
  FundedNext"; `evidence-docs.md` "bot heredado"). SMC-SYSTEMS es Forex/ICT-SMC profesional.
  Estas referencias viven en `_descartado/` y historical, baja severidad, pero se marcan
  como contaminación arquitectónica a limpiar en misión de docs (no en esta).
- **Rutas muertas en AGENTS/README/opencode.json:** 16+ claims rotos documentados en
  `evidence-docs.md` (COMPLETION_REPORT borrado, docs/plan purgado, SPEC_TESIS_FORMAL en
  `docs/ict/` no `docs/tesis/`, opencode.json 7 instrucciones MISSING). Fuera del alcance
  de esta misión de SDD; se recomienda misión aparte de "limpieza de fuentes de verdad".

---

## 6. VERIFICACIÓN FINAL (contrato CEO §22.10)

- **Verificado:** árbol de autoridad (§0), DoR (§1), DoD (§2), estados (§3), verificación
  semántica (§4), regresión semántica (§5), trazabilidad (§6), impact (§7), 4 conceptos
  (§8), no-invención (§9), cero-indicadores (§10), investigación≠producción (§11),
  congelación openspec (§12). Todos los archivos citados existen y fueron leídos.
- **No verificado:** que los punteros corregidos no dejen referencias colgadas (se hace en
  FASE F por grep). Que `AGENTS.md`/README se limpien (fuera de alcance).
- **GAP persistente:** limpieza de fuentes de verdad (AGENTS/README/opencode.json) — misión
  aparte, recomendada.
- **BLOCKED:** nada bloquea; la implementación es solo documentación.
- **NO se tocó:** `engine/`, `ict_backtest/`, detectores, tesis, backtest, métricas.

---

## 7. LISTA DE ARCHIVOS (FASE E)

| Archivo | Cambio | Por qué |
|---------|--------|---------|
| `docs/specs/SDD_GOVERNANCE.md` | CREAR | meta-SDD (este informe lo materializa) |
| `docs/specs/SDD_AUDIT_REPORT.md` | CREAR | esta auditoría FASE A/B con evidencia |
| `agents/governance/PROTOCOLO_AGENTE.md` | PARCHE §2 | "SDD relevante" apunta a `docs/tesis/SDD_*.md` + meta-SDD |
| `agents/governance/CONTRATO_ORDEN.md` | PARCHE §1/§5 | aclarar ubicación del SDD |
| `openspec/README.md` | PARCHE nota | marcar `openspec/` como línea base forense congelada |
