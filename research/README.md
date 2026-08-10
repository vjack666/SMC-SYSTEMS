# research/ — Mundo CIENCIA (FASE 3B, esqueleto contractual)

Este directorio es la **frontera científica** del sistema. Es la fuente primaria e inmutable
de todo experimento controlado.

Contrato completo: `docs/architecture/RESEARCH_CONTRACT.md`.

## Estructura

```
research/
├── hypotheses/    ← HYP-NNN/ (pregunta + predicción falsable; texto, NO reproducible)
├── experiments/   ← EXP-NNN/ (unidad reproducible; arranca VACÍO)
├── protocols/     ← protocolos versionados reutilizables
└── validation/    ← validación independiente
```

## Reglas de hierro (del contrato)

1. HYP-NNN ≠ EXP-NNN. Una hipótesis NO es reproducible; un experimento SÍ.
2. Un EXP-NNN requiere: `experiment.md`, `protocol.yaml`, `config.yaml`, `code/`,
   `data_manifest.json`, `run/`, `results/`, `evidence/`, `verdict.yaml`.
3. Datos NO viven aquí: `data_manifest.json` los identifica por ID + hash.
4. `run/` registra commit SHA + seed + comando exacto (regla fundamental: reproducible
   desde el repo, no desde la memoria de una conversación).
5. EXP-NNN = FUENTE PRIMARIA. `results/experiments/EXP-NNN/` es publicación derivada, nunca
   segunda fuente de verdad.
6. Veredicto: REFUTADA | INCONCLUSIVA | PROMOVIDA. Sellado por hash, histórico aditivo.
7. `research/experiments/` CONSUME engine/backtest/data (✅); NO gobierna el backtest (❌).
8. `ict_backtest/diagnostics/` (FDR/Bonferroni) queda en backtest. No se mueve.

## Validación

`research/_contract.py` valida que un EXP cumple el contrato. No se crea ningún EXP hasta
que el laboratorio tenga una hipótesis real promovible (ver FASE 3B.2).
