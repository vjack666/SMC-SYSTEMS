# openspec — Almacén SDD de SMC-SYSTEMS

> ⚠️ **LÍNEA BASE FORENSE CONGELADA (2026-08-07, baseline `9842394`).** Hoy el HEAD es
> `76a8faa`; varios "riesgos" de esta auditoría ya se resolvieron (ej. `engine/poi_anchor.py`
> ya está trackeado). `openspec/` es **evidencia histórica de la auditoría SDD-00**, NO el SDD
> vivo del proyecto. El SDD vivo y su árbol de autoridad están en
> `docs/specs/SDD_GOVERNANCE.md`. No competir con él; si se reabre, nuevo spec.

Contexto y artefactos del flujo Spec-Driven Development. Inicializado el **2026-08-07** sobre la
rama `feature/backtest-ict`. Modo de persistencia: **archivos** (Engram MCP no disponible).

## Ruta rápida

1. **`project-context.md`** — stack, Ley arquitectónica, regla de procesos largos y trampas de documentación obsoleta. **Leer primero.**
2. **`testing-capabilities.md`** — comandos de test exactos y las condiciones del modo Strict TDD.
3. **`config.yaml`** — configuración legible por máquina: reglas por fase, ley, umbral de procesos largos.

## Estructura

```
openspec/
├── README.md                 <- este índice
├── config.yaml               <- configuración SDD del proyecto
├── project-context.md        <- contexto detectado (fuente de verdad sobre el README del repo)
├── testing-capabilities.md   <- runner, comandos y veredicto Strict TDD
├── specs/                    <- specs fuente de verdad, por dominio
└── changes/                  <- cambios activos
    └── archive/              <- cambios completados (AAAA-MM-DD-{nombre})
```

## Reglas no negociables

| Regla | Detalle |
|-------|---------|
| **Ley MOTOR vs BACKTEST** | Toda lógica de estrategia va a `engine/`. `ict_backtest/` es consumidor puro y desechable. `engine/` nunca importa `ict_backtest/`. Guardián: `tests/test_engine_no_backtest_import.py` |
| **Procesos > 60 s** | `python scripts\runner_monitor.py --window --title "NAME" -- <comando>`. Sin background oculto, sin polling en el chat |
| **Commits** | No commitear ni pushear sin OK expreso del operador |
| **Números de performance** | Única fuente: `docs/METRICS_CANON.md`. No copiar cifras |
| **Idioma** | Prosa en español neutro. Identificadores, rutas, símbolos y comandos en su forma original |

## Convivencia con documentación previa

`docs/specs/MDS_*.md` es una convención de especificación anterior, viva y en español.
Los artefactos SDD **no la reemplazan**: deben referenciarla y no contradecirla.
Trazabilidad de tesis: `docs/ict/SPEC_TESIS_FORMAL.md`.

## Siguiente paso

`/sdd-explore` sobre el área objetivo, o `/sdd-new` si el cambio ya está acotado.
Antes: resolver con el operador la migración `poi_anchor` pendiente
(`project-context.md`, sección 7).
