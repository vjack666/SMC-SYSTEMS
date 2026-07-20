# MDS — Trade Management: BE / parciales / re-entry (SPEC §22, libros 15/17)

**Clasificación:** OBLIGATORIO · **Fase:** E1 · **Estado:** ❌ pendiente
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §22 · **Roadmap maestro:** §9 (Trade Mgmt)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Gestión activa post-entry: Break Even, cierre parcial en liquidez internal, re-entry en
nuevo POI. Hoy el motor solo tiene `hold_limit` (libro 20 §7, 16 velas M15).

## 1. Dependencias

- Entry (§11) · TP (§13) · Liquidez internal/external (§14, ❌) · POI (§16).

## 2. Módulo (a crear/extender)

- `ict_backtest/engine.py` `simulate_trade`: reemplazar `hold_limit` por máquina de Estados
  de gestión: `IN_TRADE → BE_MOVED → PARTIAL → CLOSED` (+ `RE_ENTRY` en nuevo POI).
- Niveles BE/parcial = decisión de ing (la tesis exige gestión activa, no el número);
  defaults propuestos: BE tras 1R, parcial en liquidez internal.

## 3. Firma propuesta

```python
def manage_trade(position, market, liquidity_internal) -> actions:
    # BE tras alcanzar 1R; parcial en liquidez internal; re-entry en nuevo POI
    ...
```

## 4. Reglas duras

- BE tras alcanzar 1R; parcial en liquidez internal; re-entry en nuevo POI (SPEC §22 CRIT).
- Sin estructura a favor → NO BE (dejar SL original).

## 5. Criterios de aceptación (fidelidad + calidad)

- Tests unitarios de la máquina de estados (BE/parcial/re-entry) aislada.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4); aquí se mide por fidelidad
  de la gestión, no por PF.

## 6. Trazabilidad

SPEC §9 (hold/ RR/ regimes) · §13 (TP) · §14 (internal/external) · §22 (Trade Mgmt) ·
libro 15/17 · ROADMAP §9 (Trade Mgmt).
