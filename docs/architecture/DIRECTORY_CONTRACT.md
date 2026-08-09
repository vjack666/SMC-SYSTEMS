# DIRECTORY_CONTRACT.md — Contrato de carpetas

> **Constitución arquitectónica PROPUESTA — Revisión 2.1 (2026-08-09).** Regla fundamental:
> **UNA carpeta = UNA responsabilidad.** Incorpora los ajustes del Director: `docs/` =
> conocimiento, `results/` = evidencia; `research/` = preguntas fuera del producto;
> `RESULTS → ENGINE` automático prohibido. Estos contratos son propuesta; el guardrail
> (FASE 4) se construye SOLO tras aprobación del Director.

## Regla fundamental

> Cada carpeta debe responder UNA sola pregunta. Si una cosa no puede responder
> claramente a una de esas preguntas, NO se crea la carpeta todavía.

| Carpeta | Pregunta que responde |
|---------|-----------------------|
| `engine/` | ¿Dónde vive la lógica causal del mercado? |
| `backtest/` (hoy `ict_backtest/`) | ¿Cómo comprobamos históricamente? |
| `runtime/` | ¿Cómo ejecutamos y observamos en vivo? |
| `research/` | ¿Qué preguntas aún no pertenecen al producto? |
| `data/` | ¿Con qué datos trabajamos? |
| `results/` | **¿Qué evidencia obtuvimos?** |
| `docs/` | **¿Qué sabemos y decidimos? (conocimiento institucional)** |
| `tests/` | ¿Cómo sabemos que funciona? |
| `scripts/` | ¿Qué herramientas usamos para operar el proyecto? |
| `agents/` | ¿Quién analiza, coordina y gobierna? |
| `detectors/` `features/` `adapters/` etc. | ¿Qué librería de soporte reutilizamos? |

> Nota: `results/` contiene **evidencia**; `docs/` contiene el **conocimiento** derivado
> de esa evidencia. Una conclusión puede sobrevivir aunque el resultado concreto se archive.

## Procedimiento obligatorio antes de crear una carpeta nueva

Todo agente debe responder POR ESCRITO:

1. **¿Qué responsabilidad única tiene?** (una frase; si necesita "y", es mala señal)
2. **¿Por qué NO pertenece a una carpeta existente?** (citar la carpeta rechazada y por qué)
3. **¿Qué tipo de artefactos puede contener?** (.py / .md / .parquet / mixto, con límites)
4. **¿Quién es su propietario?** (rol de `agents/governance/ROLES_GOBERNANZA.md`)
5. **¿Qué dependencias puede tener?** (qué puede importar, qué NO — ver `DEPENDENCY_RULES.md`)

Sin las 5 respuestas, la carpeta no se crea.

## Contratos específicos (objetivo)

- `engine/` — solo geometría de mercado + volumen (confirmación). Cero indicadores.
  No importa backtest/research/results. **`engine/killzone.py` (TIME) es utilidad temporal
  NEUTRA**: ni `engine/` ni `detectors/` la consideran "del backtest". Regla: utilidad
  neutral jamás depende de `backtest/` (ver `DEPENDENCY_RULES.md` §4).
- `backtest/` — consume engine + detectors. No decide; mide.
- `research/` — `hypotheses/`, `experiments/EXP-NNN/`, `protocols/`, `validation/`. Hogar
  de lo que aún NO es producto. Cuando se promueve, el experimento queda para trazabilidad.
- `results/` — siempre con ID (`EXP-071`, `BT-2026-001`, `VAL-003`). Nunca `final_final.csv`.
- `data/manifests/` — cada dataset tiene manifest (origen, símbolo, TF, período, proveedor,
  versión, hash, transformaciones).
- `agents/` — `analysis/` (mercado), `orchestration/` (coordina), `governance/` (protege el
  proceso científico). Poderes distintos: detectar BOS ≠ rechazar una hipótesis.

## Modificaciones 2.1 (incorporadas)

1. `docs/` = conocimiento institucional; `results/` = evidencia. (Tabla arriba.)
2. `research/` = preguntas/hipótesis/experimentos que **aún no pertenecen al producto**.
3. **Prohibido `RESULTS → ENGINE` como feedback automático** (ver `DEPENDENCY_RULES.md`).
   La vuelta a `ENGINE` solo vía decisión explícita pre-registrada.
4. **Utilidades neutras NO pueden depender de `backtest`.** (ver `DEPENDENCY_RULES.md`.)

> **LEY CENTRAL:** El resultado de un experimento puede generar una nueva hipótesis, pero
> nunca modificar silenciosamente el sistema que produjo ese resultado.

## Prohibido (a nivel de contrato)

- Organizar por TIPO DE ARCHIVO (`markdown/`, `python/`, `csv/`) en lugar de responsabilidad.
- Carpetas de 5 niveles para una sola cosa.
- "Limpieza cosmética" sin justificación de responsabilidad.
- Mover `engine/` sin migración arquitectónica aprobada.
- `RESULTS → ENGINE` automático (autoengaño por optimización retrospectiva).

## Estado

Propuesto — Revisión 2.1. El guardrail que enforce esto se construye en FASE 4 tras aprobación.
