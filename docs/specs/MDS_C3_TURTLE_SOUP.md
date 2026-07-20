# MDS — Turtle Soup (contratendencia) (SPEC §18, libro 06)

**Clasificación:** OBLIGATORIO (1 de 3 setups del ciclo PO3) · **Fase:** C3 · **Estado:** ❌
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §18 · **Roadmap maestro:** §9 (Turtle Soup)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Setup contratendencia: el sweep manipula EN CONTRA del sesgo HTF y el BOS/CHOCH va CONTRA
la marea. Es reversión, no continuación (SPEC §18, tesis 20 §4).

## 1. Dependencias

- Sweep (§6) · BOS/CHOCH (§8) · Killzone (§15) · POI (§16) ·
  `top_down_allows_trade` con `counter_trend=True` (v2/context_mtf.py:136, ya existe).

## 2. Módulo (a crear/extender)

- `run_sequence` modo `setup="turtle_soup"` → llama `top_down_allows_trade(stack, direction,
  counter_trend=True)`. Esto EXIGE dirección CONTRA D1/H4 (ver SPEC §18 CRIT).
- Reusa misma sub-máquina SWEEP→DISPLACE→BOS→ENTRY, pero con flag contratendencia.

## 3. Firma propuesta

```python
def turtle_soup_ready(stack, direction) -> (bool, str):
    ok, reason = top_down_allows_trade(stack, direction, counter_trend=True)
    if not ok:
        return False, reason
    return True, "turtle_soup"
```

## 4. Reglas duras

- `direction == opuesta al sesgo HTF`; BOS/CHOCH va CONTRA la marea (SPEC §18 CRIT).
- Si está alineado al HTF → es PO3 (§19), NO Turtle Soup.
- Recomendación tesis §9: operar Turtle Soup solo en RANGO (régimen filter = decisión ing).

## 5. Criterios de aceptación (fidelidad)

- Subconjunto etiquetado: Turtle Soup solo se dispara cuando D1/H4 están en dirección
  opuesta a la entrada y hay CHOCH contrario.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §4 · §18 · §19 (PO3) · libro 06 · ROADMAP §9 (Turtle Soup) ·
PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md (counter_trend en top_down).
