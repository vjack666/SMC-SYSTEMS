# DISEÑO — GATE DE GOBERNANZA DE AGENTES

**Versión:** 2.1 (corregido: sin states.json ni hypothesis_gate separado)  
**Autor:** Hermes (orquestador)  
**Estado:** ✅ APROBADO PARA IMPLEMENTACIÓN

---

## 1. PROBLEMA

La arquitectura documentada de agentes (ROLES_GOBERNANZA.md) declara una cadena de autoridad:

```
HIPÓTESIS → PROMOCIÓN → DoR → INGENIERO → IMPLEMENTACIÓN → AUDITOR → PASS/VETO → ACEPTACIÓN
```

Las 5 violaciones documentadas son:

1. No existe gate de promoción formal para hipótesis
2. No existe verificación automática de DoR antes de permitir al ingeniero trabajar
3. El ingeniero puede auto-aprobar su trabajo
4. El audtor puede auto-auditar
5. El veto no es automatizado

**Objetivo:** Convertir las reglas institucionales documentadas en invariantes verificables, usando **mínimos componentes** y reutilizando la infraestructura existente.

---

## 2. AUTORIDAD EXISTENTE

| Archivo | Autoridad | Ubicación |
|---------|-----------|-----------|
| `AGENTS.md` | Ley Fundamental | Raíz |
| `ROLES_GOBERNANZA.md` | Organigrama de roles | `agents/governance/` |
| `ORQUESTADOR.md` | Matriz de enrutamiento | `agents/governance/` |
| `PROTOCOLO_AGENTE.md` | Protocolo obligatorio de agentes | `agents/governance/` |
| `CONTRATO_ORDEN.md` | Disciplina de edición | `agents/governance/` |
| `SDD_GOVERNANCE.md` | DoR/DoD, estados, verificación semántica | `docs/specs/` |
| `auditor_independiente.md` | Veto de promoción | `agents/governance/` |
| `memoria_institucional.md` | Autoridad del registro | `agents/governance/` |

**Nota:** `RESEARCH_CONTRACT.md` NO EXISTE como autoridad válida - solo menciones huérfanas en documentos. La frontera hipótesis↔código se define por:
- SDD_GOVERNANCE.md §11 ("INVESTIGACIÓN ≠ PRODUCCIÓN")
- AGENTS.md §85 ("engine/ es única fuente de decisión")

---

## 3. COMPONENTES ARCHITECTURALES

```
EXISTENTES REUTILIZADOS:
  - SDD_GOVERNANCE.md §44-64 (DoR checklist)
  - PROTOCOLO_AGENTE.md §0 (estados operacionales)
  - auditor_independiente.md §3.1, §5 (veto, independencia)
  - AGENTS.md §85 (Ley Fundamental: engine≠backtest)
  - docs/bitacora/ (registro histórico inmutable)

EXISTENTES MODIFICADOS:
  - ORQUESTADOR.md (añadido referencia al gate)

NUEVOS:
  - gate/orchestrator_enforcer.py (validate DoR + state transitions)
  - gate/audit_isolation_service.py (tracking: creator≠auditor)
  - gate/veto_registry.py (registry mínimo de vetos)
  - gate/states.py (representación ejecutable de estados documentados)
  - gate/config.py (modo advisory/enforcement)
  - gate/hypotheses_registry.json (registro inicial vacío)
```

**ANULADO:** `hypothesis_gate.py` separado y `states.json` - integrados en los componentes existentes.

---

## 4. INVARIANTES

```
I1: Hipótesis no promovida NO puede generar código que modifique engine/
    → Protegido por: promoción formal explícita requerida

I2: Ingeniero NO puede implementar sin DoR cumplido
    → Protegido por: gate/orchestrator_enforcer.validate_dor()

I3: Ingeniero NO puede aprobar su propio trabajo
    → Protegido por: gate/veto_registry.check_veto()

I4: Auditor NO puede auditar trabajo producido por él mismo
    → Protegido por: gate/audit_isolation_service (creator≠auditor)

I5: VETO activo IMPIDE promoción
    → Protegido por: gate/veto_registry.has_active_veto()

I6: Ningún cambio puede saltarse una etapa de autoridad
    → Protegido por: gate/orchestrator_enforcer.can_transition()

I7: Los mecanismos se integran con la gobernanza existente
    → Protegido por: uso de estados/documentos existentes
```

---

## 5. TRANSICIONES PROTEGIDAS

**Estados documentados (PROTOCOLO_AGENTE.md + SDD_GOVERNANCE.md):**

| De | A | Requerimiento | Archivo enfocado |
|---|---|---------------|------------------|
| READY | IMPLEMENTING | `validate_dor().passed = TRUE` | `gate/orchestrator_enforcer.py` |
| TESTED | AUDITED | `audit_isolation.verify(creator≠auditor)` | `gate/audit_isolation_service.py` |
| AUDITED | ACCEPTED | `veto_registry.has_active_veto() = FALSE` | `gate/veto_registry.py` |
| cualquier | BLOCKED | detención explícita | `gate/orchestrator_enforcer.py` |

---

## 6. QUÉ SE BLOQUEA Y DÓNDE

```
qué se bloquea:
  - Transición READY → IMPLEMENTING sin DoR
  - Asignación de auditor = creador
  - Promoción a ACCEPTED con veto activo

dónde se bloquea:
  - orquestador_enforcer.can_transition() (punto único)
  - audit_isolation_service.assign_auditor()
  - veto_registry.has_active_veto()

quién puede desbloquear:
  - Investigador corrige DoR / Director (override)
  - Auditor retira veto / Director (sobrescribe veto)
  - Memoria reasigna auditor

qué evidencia queda:
  - results/gate_dor_violations.json
  - results/gate_veto_blocked.json
  - results/gate_state_violations.json
```

---

## 7. INTEGRACIÓN CON SDD

```
SDD_GOVERNANCE.md §91-108 (ESTADOS):

TaskState.can_transition() codifica:
  READY → IMPLEMENTING → TESTED → AUDITED → ACCEPTED
  Los estados son strings que coinciden con PROTOCOLO_AGENTE.md
  No states.json - solo representación ejecutable de la autoridad documental
```

---

## 8. ARCHIVOS A MODIFICAR

| Archivo | Cambio |
|---------|--------|
| `ORQUESTADOR.md` | Añadir: "El orquestador consulta gate.orchestrator_enforcer antes de enrutar" |

**NO MODIFICAR:**
- `SDD_GOVERNANCE.md` (solo referencias)
- `PROTOCOLO_AGENTE.md` (solo referencias)
- `auditor_independiente.md` (solo referencias)

---

## 9. ARCHIVOS PROHIBIDOS

```
engine/ — Ley Fundamental
ict_backtest/ — Backtest canónico solo consumidor
docs/ict/SPEC_TESIS_FORMAL.md — Contrato técnico sagrado
AGENTS.md — Ley Fundamental
docs/specs/INDICE_MDS.md — Solo índice
agents/governance/*.md — Documentos, no código
```

---

## 10. RIESGOS Y MITIGACIÓN

| Riesgo | Mitigación |
|--------|------------|
| Over-engineering | 3 archivos nuevos mínimos |
| Breaking existing flow | Modo ADVISORY por defecto |
| False positives | Logging detallado, escalación automática |
| DoR muy estricto | Threshold configurable por Director |

---

## 11. COMPATIBILIDAD HACIA ATRÁS

```
Modo ADVISORY (default):
- Gate emite alerts en results/
- No bloquea flujo actual
- Documenta violaciones

Modo ENFORCEMENT (configurable):
- Gate bloquea transiciones críticas
- Requiere DoR, veto libre, auditor diferente
```

---

---

## 12. FASE 7.x — CIERRE DE LA FRONTERA (ENFORCEMENT REAL)

La arquitectura V2.1 + Opción C se completó con la integración en la frontera
de cambio del repositorio. El gate ya no es advertorial: es obligatorio.

### Mecanismo

```text
write_file(engine/...)
    ↓
git add
    ↓
git commit
    ↓
scripts/git_hooks/pre-commit  ← invoca ChangeGateValidator.validate_diff
    ↓
  BLOCK (exit 1)           ALLOW (exit 0)
    │                            │
  commit CANCELADO          commit permitido
```

### Componentes

- `scripts/change_gate_hook.py` — pre-commit hook (invoca el validador)
- `scripts/git_hooks/pre-commit` — copia instalada (core.hooksPath = scripts/git_hooks)
- `gate/change_validator.py` — `ChangeGateValidator.validate_diff(diff, ctx)`
- `gate/task_registry.json` — contexto de tareas (promoted / dor_passed / auditor)

### Derivación de contexto

- `task_id`: del branch actual (`feature/TASK-XXX` → `TASK-XXX`)
- `ctx`: de `gate/task_registry.json` (si no existe/entrada ausente → no promovido → BLOCK)

### Invariantes forzados en commit

- I1: hipótesis no promovida NO modifica engine/backtest/tesis
- DoR: requerido para READY→IMPLEMENTING
- Estado: transición válida según PROTOCOLO_AGENTE.md
- Auditor: creator != auditor
- Veto: ausencia de veto activo

### Verificación end-to-end (real)

```text
$ git add engine/_gate_probe.tmp
$ git commit -m "probe"
CHANGE GATE: COMMIT RECHAZADO
Razón: I1: hipótesis no promovida no puede modificar engine/backtest/tesis
→ exit code 1 (commit cancelado)
```

### Estado

- `GateConfig.mode = "enforcement"` (default desde este commit)
- Hook instalado vía `git config core.hooksPath scripts/git_hooks`
- Tests: 36 pasan (7 A-F + 6 G-K + 5 hook + 18 originales)

### Lo que NO cambió (Ley Fundamental respetada)

- `engine/` NO importa `gate/` (motor ignorante de gobernanza)
- NO se creó `hypothesis_gate.py` (I1 cubierto por Change Gate)
- NO se tocó `engine/`, tesis, ni backtest canónico
- Gobernanza = autoridad de CAMBIO; engine = autoridad de DECISIÓN

---

CEO, el gate de gobernanza del cambio está en ENFORCEMENT. La frontera de
promoción del repositorio está cerrada: no se puede modificar `engine/` sin
promoción, DoR, auditor independiente y ausencia de veto. El motor sigue
siendo la única fuente de decisión de mercado, completamente ignorante del gate.