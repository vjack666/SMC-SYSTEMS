# MDS — OTE: Optimal Trade Entry 62-79% retrace (SPEC §21, libro 15)

**Clasificación:** OBLIGATORIO · **Fase:** D1 · **Estado:** ❌ pendiente
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §21 · **Roadmap maestro:** §9 (OTE)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Refinar la entry al nivel OTE = retrace 62-79% del swing, medido sobre el dealing range
(P-D). Estrecha la zona de entry (SPEC §11 retorno a zona → §21 OTE dentro de la zona).

## 1. Dependencias

- Dealing Range / P-D (§2) — módulo `dealing_range_motor` existe HOY pero como POSTPROCESO
  en `canonical.py` (anota `ICTSignal.zone_class`). Para OTE debe usarse EN el cálculo de
  entry, no solo anotar.
- Entry retorno a zona (§11) · BOS/CHOCH (§8) · PD Arrays (§3).

## 2. Módulo (a crear/extender)

- Nueva función en `ict_backtest/engine.py` / `canonical.py`: `compute_ote_level(swing,
  dealing_range)` → devuelve `ote_low, ote_high` (62-79% del retrace del swing).
- `build_signals_from_frames` / `run_sequence` usan OTE para afinar `entry_price` dentro
  de la zona POI (no el close del BOS).

## 3. Firma propuesta

```python
def compute_ote_level(swing_high, swing_low, eq) -> tuple[float, float]:
    # retrace 62-79% del swing medido desde el extremo, sobre el rango P-D
    ...
```

## 4. Reglas duras

- `entry_price ∈ [0.62, 0.79]` del retrace del swing (SPEC §21 CRIT).
- Caso límite: retrace <62% → entry en zona amplia; >79% → fuera de OTE.
- Medir el retrace desde el swing completo o desde el PD Array = decisión de ing (R3).

## 5. Criterios de aceptación (fidelidad)

- Subconjunto etiquetado: entry cae en banda OTE cuando el precio retorna.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §6 (entry retorno) · §21 (OTE) · libro 15 §2 · ROADMAP §9 (OTE) ·
closure_brecha_a1_opcionb (patrón: postproceso → usar en decisión).
