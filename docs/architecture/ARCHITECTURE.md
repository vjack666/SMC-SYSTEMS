# ARCHITECTURE.md — Arquitectura objetivo de SMC-SYSTEMS

> **Constitución arquitectónica PROPUESTA — Revisión 2.1 (2026-08-09).** Incorpora los
> ajustes del Director: `docs/` = conocimiento, `results/` = evidencia; `research/` =
> preguntas aún fuera del producto; `RESULTS` nunca alimenta causalmente a `ENGINE`;
> utilidades neutras no pueden depender del backtest. NO es aún la constitución definitiva
> (pendiente de aprobación del Director). El guardrail (FASE 4) se construye SOLO después.
> Inventario real en `ARCHITECTURE_MAP.md`.

## 1. Principio rector

SMC-SYSTEMS no es "un bot de trading". Es **un sistema de investigación que descubre,
falsa, valida y eventualmente convierte hipótesis de mercado en componentes operativos**.

Dos grandes mundos con un núcleo compartido:

```
                 SMC-SYSTEMS
                      │
          ┌───────────┴───────────┐
          │                       │
       PRODUCTO               CIENCIA
          │                       │
       engine/                research/
       backtest/              experiments/
       runtime/               hypotheses/
                              validation/
          │                       │
          └───────────┬───────────┘
                      ↓
                   RESULTS
                 (evidencia)
                      │
                      ↓
                    DOCS
            (conocimiento sobre
             esa evidencia)
```

`docs/` NO es evidencia: contiene el **conocimiento institucional** derivado de la
evidencia. Una conclusión puede sobrevivir aunque el resultado concreto esté archivado.

## 2. Dos flujos distintos: FÍSICO y EPISTEMOLÓGICO (Revisión 2.2)

### 2.1 Flujo FÍSICO (datos → producto) — flecha que nunca se invierte

```
DATA → ENGINE → BACKTEST → RESULTS
```

- `DATA`: materia prima (velas). Nunca importa nada de arriba.
- `ENGINE`: motor causal ICT, geometría pura, cero indicadores. Nunca importa
  `ict_backtest/`, `backtest/`, `research/`, `results/`.
- `BACKTEST`: consumidor puro del motor. Puede importar ENGINE y DETECTORS.
- `RESULTS`: evidencia. Hoja: no importa nada de arriba.

### 2.2 Flujo EPISTEMOLÓGICO (aprendizaje) — con PUERTA explícita

El aprendizaje NO es una flecha normal hacia ENGINE. Es:

```
RESULTS → RESEARCH → HYPOTHESIS → ║PUERTA: decisión pre-registrada║ → ENGINE
```

La `║PUERTA║` es una **barrera explícita**, no una flecha. Representa que la vuelta al
motor SOLO ocurre tras un experimento cerrado con veredicto y una decisión registrada de
antemano (no un ajuste reactivo al número del backtest).

> **LEY CENTRAL (anti autoengaño):** El resultado de un experimento puede generar una
> nueva hipótesis, pero **nunca modificar silenciosamente el sistema que produjo ese
> resultado**. Esto protege la separación entre descubrimiento y confirmación.

Ningún diagrama de este documento debe interpretarse como `RESULTS → ENGINE` directo.

## 3. Mundo PRODUCTO

| Carpeta | Responsabilidad (una sola) |
|---------|----------------------------|
| `engine/` | Lógica causal del mercado (motor ICT permanente). En RAÍZ por ahora. |
| `backtest/` (hoy `ict_backtest/`) | Consumidor histórico del motor. |
| `runtime/` (hoy `app_observador/` + `MQL5/` + `integration/`) | Ejecución y observación en vivo. |

**Decisión futura (no ahora):** `ict_backtest/` puede ser un nombre de implementación
histórica demasiado específico si el sistema termina soportando ICT/SMC/Wyckoff/ML. A
largo plazo podría ser `backtest/{engine,runners,rules,reports,adapters}`. Renombrar es
migración arquitectónica, no limpieza — se decide en FASE 3+, no hoy.

## 4. Mundo CIENCIA — `research/`

`research/` es el hogar de las **preguntas que todavía no pertenecen al producto**.

```
research/
├── hypotheses/      ← preguntas formuladas como hipótesis comprobables
├── experiments/     ← EXP-NNN/ (unidad autónoma reproducible)
├── protocols/       ← protocolos de experimentación
└── validation/      ← validación independiente
```

Cada `research/experiments/EXP-NNN/` contiene: `hypothesis.md`, `protocol.md`, `config/`,
`code/`, `results/`, `evidence/`, `verdict.md`.

**Regla de tránsito:** cuando una investigación demuestra que algo merece entrar al
producto, deja de pertenecer *exclusivamente* a `research/` — pero el experimento NO
desaparece. Queda su historial para trazabilidad:

```
research/experiments/EXP-071/
       ↓ (evidencia suficiente, decisión pre-registrada)
results/experiments/EXP-071/
       ↓
engine/...  (el componente promovido)
```

Estados epistemológicos (subir de piso = cambiar estado, NO mover carpeta):
`P0 IDEA → P1 HIPÓTESIS → P2 EXPERIMENTO → P3 EVIDENCIA → P4 VALIDACIÓN → P5 CANDIDATO → P6 PROMOVIDO → P7 PRODUCCIÓN`.

## 5. EVIDENCIA y CONOCIMIENTO

| Carpeta | Responsabilidad (una sola) |
|---------|----------------------------|
| `results/` | **Evidencia** en bruto con IDs (`EXP-071`, `BT-2026-001`, `VAL-003`). Nunca `final_final.csv`. |
| `docs/` | **Conocimiento institucional** sobre esa evidencia (SDD, tesis, lab, architecture/, decisiones). |

## 6. Servicios transversales

| Carpeta | Responsabilidad (una sola) |
|---------|----------------------------|
| `agents/` | `analysis/` (piensa sobre el mercado: ict/wyckoff/structure/decision), `orchestration/` (coordina agentes), `governance/` (protege el proceso científico). **Dirección aprobada.** |
| `tests/` | Verificación. |
| `scripts/` | Herramientas de operación. |
| `detectors/` `features/` `adapters/` `strategy/` `risk/` `signals/` `ml/` `indicators/` | Librería de soporte (cada uno UNA responsabilidad). |
| `knowledge/` `mcps/` | IA / personalidad de los agentes (no se mueven). |

## 7. Lo que NO se hace hoy (decisiones firmes)

- `engine/` se queda en la raíz. No se mete en `src/` aún.
- `src/` (vacío) no se usa hasta migración arquitectónica futura explícita.
- `research/`, `runtime/`, `data/manifests/`, separación de `agents/` → documentados como
  objetivo, NO creados/movidos hasta FASE 3 (aprobación del Director).
- **Legacy — dos cosas distintas, no confundir:**
  - `C:\Users\v_jac\Desktop\legacy_smc_backup` (DISCO) = backup **reversible** creado
    esta sesión (10 ítems movidos de raíz/src). SEGURO, se mantiene fuera del repo.
  - `legacy/` (EN EL REPO, 29 .py) = código muerto detectado dentro del repo, NO importado
    por nada vivo. Se investiga en FASE 3 (¿usado? ¿referencia? ¿recuperable?) antes de
    decidir `archive/` o salida del repo. "Parece viejo" no basta para borrarlo.
- `ict_backtest/` no se renombra hoy (ver §3).

## 8. Estado de este documento

Propuesta — Revisión 2.1. Pendiente de aprobación del Director para congelarse como
constitución y habilitar el guardrail (FASE 4). Mientras tanto `ARCHITECTURE_MAP.md` es
la foto real del repo.
