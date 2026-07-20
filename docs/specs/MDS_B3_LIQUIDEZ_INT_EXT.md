# MDS — Liquidez internal vs external (jerarquía TP) (SPEC §14, libros 05/15/16)

**Clasificación:** OBLIGATORIO · **Fase:** B3 · **Estado:** ❌ pendiente
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §14 · **Roadmap maestro:** §9 (internal/external)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Jerarquía de targets de TP: primero liquidez INTERNAL (swing reciente de la sesión), luego
EXTERNAL (PDH/PDL/EQ highs-lows). Hoy `_tp_liquidity` usa clusters lejanos (libro 20 §8).

## 1. Dependencias

- Liquidez (§6) · TP (§13) · 3 capas (§9).

## 2. Módulo (a crear/extender)

- `ict_backtest/engine.py` `_tp_liquidity`: distinguir `internal` (swing sesión/estructura
  reciente) de `external` (PDH/PDL/EQ high-low) y devolver ambos; el TP primario = internal
  más cercano; objetivo macro = external.

## 3. Firma propuesta

```python
def tp_hierarchy(row_exec, structure) -> dict:
    return {"internal": bsl_ssl_mas_cercano, "external": pdh_pdl_eq}
```

## 4. Reglas duras

- internal = swing de la sesión/estructura reciente; external = máximos/mínimos de
  día/semana (PDH/PDL, EQ high-low) (SPEC §14 CRIT).
- Sin external claro → solo internal.

## 5. Criterios de aceptación (fidelidad)

- Subconjunto etiquetado: el TP primario cae en liquidez internal cuando existe.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §3 (sweep) · §8 (BOS) · §13 (TP cercano) · §14 (internal/external) · libro 05/15/16 ·
ROADMAP §9 (Liquidez internal vs external).
