# MDS — RR mínimo POR SETUP (SPEC §20, libro 07 #5 / tesis 20 §9)

**Clasificación:** OBLIGATORIO (por setup) · **Fase:** C2 · **Estado:** ❌ pendiente
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §20 · **Roadmap maestro:** §9 (RR por setup)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Parametrizar el filtro RR POR SETUP: SB = 1:2 (libro 07 #5), resto (PO3/Turtle) = 1:3
(tesis 20 §9 / libro 18). Hoy el motor fuerza 1:2 (fixed2r) o 1:3 global sin distinguir.

## 1. Dependencias

- SL (§12) · TP (§13) · setup actual.

## 2. Módulo (a crear/extender)

- `ict_backtest/engine.py` / `rules.py`: `rr_ok(direction, sl, tp, setup) -> bool` con
  umbral según setup.
- `run_sequence` / `evaluate_signals` pasan `setup` para elegir umbral.

## 3. Firma propuesta

```python
RR_MIN = {"silver_bullet": 2, "po3": 3, "turtle_soup": 3}
def rr_ok(direction, sl, tp, setup) -> bool:
    need = RR_MIN.get(setup, 3)
    return (tp - entry) / (entry - sl) >= need
```

## 4. Reglas duras

- RR mínimo = 1:3 para PO3/Turtle Soup; 1:2 para Silver Bullet (SPEC §20 CRIT, resuelto).
- TP en liquidez cercana no alcanza 1:3 → setup no pasa filtro (caso límite).

## 5. Criterios de aceptación

- Tests: SB con RR 1:2 pasa; PO3 con RR 1:2 falla; todos con RR≥umbral pasan.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §9 (RR 1:3) · §17 (SB 1:2) · §20 (RR por setup) · libro 07 #5 · ROADMAP §9 (RR) ·
ambigüedad resuelta en §25 del SPEC.
