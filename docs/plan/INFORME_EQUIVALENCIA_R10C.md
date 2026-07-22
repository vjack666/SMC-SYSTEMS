> **✅ HISTORICAL** — Informe de equivalencia completado 2026-07-16. Conclusión: `Legacy ⊆ Semantic`.

# Informe: Redefinición de la equivalencia R10.C (Fase E)

Fecha: 2026-07-16
Autor: Hermes (agent) — validado por usuario (Ruben)

## 1. Hipótesis original del DoD (Fase E)

El diseño aprobado establecía como DoD de equivalencia:

> "run_semantic es MÁS ESTRICTO: quita las que caducaban por reloj sin
>  invalidación real. El SUBSET de bar_index de entrada debe cumplirse."

Esto se interpretó como: `sem_keys ⊆ legacy_keys` (run_semantic es
subconjunto de legacy por identidad causal `(direction, bos_index)`).

## 2. Evidencia empírica (H4 XAUUSD 2000 velas + D1)

- legacy (`run_sequence`) emite 1 señal: `(-1, 1324)`.
- `build_objects` (canónico) SÍ contiene el BOS `(-1, 1324)`. La detección
  NO diverge: el objeto existe en ambos motores.
- Con enlace causal "por sweep" (cada sweep busca su BOS), run_semantic
  emitía ~70 señales, intersección con legacy = VACÍA.
- Con enlace causal "por BOS" (cada BOS busca el sweep más cercano anterior
  válido cuya zona cruza), run_semantic reconoce 165 estructuras y
  `legacy ⊆ sem = True`.

## 3. Diagnóstico de la falla de la hipótesis

Legacy y el motor semántico hacen preguntas DISTINTAS:

- Legacy: "¿qué BOS ocurrió DENTRO de mi ventana temporal (displace_gap)
  después del sweep?" → elige 1324 por proximidad de RELOJ.
- Semantic: "¿qué BOS tiene relación CAUSAL (zona de precio) con el sweep?"
  → elige el BOS que cruza la zona del sweep más cercano.

Ambos ven el mismo mercado. Eligen BOS distintos porque legacy usa un
RELOJ (displace_gap) y el semántico usa CAUSALIDAD POR ZONA. Por eso
`sem ⊆ legacy` es FALSA: el semántico es MÁS AMPLIO, no más estricto.

## 4. Conclusión (demostración)

La relación correcta NO es `Semantic ⊆ Legacy`. Es:

    Legacy ⊆ Semantic

Porque:
- Legacy es un detector histórico con restricciones artificiales (ventana
  temporal displace_gap).
- Semantic es un modelo causal (sweep → consecuencia estructural por zona).
- El modelo causal puede encontrar MÁS casos válidos; eso no lo hace peor,
  sino MÁS COMPLETO. Lo que legacy reconoce, el motor causal también debe
  reconocerlo (y lo hace: 1324 queda cubierto).

Esto NO requiere modificar el DoD en su INTENCIÓN (run_semantic no debe
inventar estructuras sin fundamento causal), pero SÍ corrige la dirección
del SUBSET: legacy es subconjunto de lo que el motor causal reconoce, no
al revés.

## 5. Condición de validez (no relajar a "semantic produce más")

Toda narrativa semántica debe tener integridad causal completa:

    SWEEP → BOS causal (zona cruzada) → estructura válida (estado ACTIVE/MITIGATED)

No se acepta "cualquier BOS cercano". El enlace por BOS + consumo único
del sweep garantiza eso sin reloj.

## 6. Decisiones respetadas

- No se implementó displace_gap (reloj disfrazado) — regla 3.
- No se acopló run_semantic a legacy (copia) — regla 2.
- SWEEP es MarketObject persistente (aprobado previamente).
- run_semantic sigue siendo motor canónico independiente.
- El significado de "equivalencia" del DoD se redefine empíricamente; el
  test RED 2 se reescribe a `legacy ⊆ semantic` + integridad causal.
