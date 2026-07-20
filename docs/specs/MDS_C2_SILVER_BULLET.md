# MDS — Silver Bullet (SB) (SPEC §17, libro 07)

**Clasificación:** OBLIGATORIO · **Fase:** C2 (post B2) · **Estado:** ❌ pendiente
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §17 · **Roadmap maestro:** §9 (SB)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.

---

## 0. Responsabilidad

Setup SB = M + FVG en ventana NY + a favor del sesgo. Reusa el ciclo PO3 pero acotado a
killzone NY y con **RR 1:2** (libro 07 #5), distinto del 1:3 global.

## 1. Dependencias (deben existir primero)

- Killzone NY AM 10-11 ET / NY PM 14-15 ET (§15) — NY AM ✅ hoy, NY PM 🔴 pendiente.
- Sweep (§6) · PD Arrays (§3) · POI anclado (§16, Fase C DONE como percepción) ·
  Exec M5/M1 (§10, B2 ❌) · RR por setup (§20, ❌).

## 2. Módulo (a crear/extender)

- Nuevo modo en `run_sequence` / `canonical.evaluate_signals`: `setup="silver_bullet"`.
- Reusa `top_down_allows_trade(stack, direction, counter_trend=False)` para alineación.
- Reusa `emit_m5` (plan_emitters) para confirmación en M5.

## 3. Firma propuesta

```python
def silver_bullet_ready(stack, est_htf, m5_zone, kz) -> bool:
    return (in_killzone(kz, ("NY_AM","NY_PM"))
            and sweep_valid(m5_zone)
            and fvg_after_sweep(m5_zone)
            and aligned_bias(stack, direction)
            and rr_ok(direction, sl, tp, rr=2))   # 1:2 SB
```

## 4. Reglas duras (libro 07)

- RR SB = 1:2 (NO 1:3). Resuelto como RR POR SETUP (SPEC §20, ambigüedad resuelta).
- Fuera de ventana NY → NO SB (aunque haya setup estructural).
- Entry en retorno a POI en exec fino (M5/M1).

## 5. Criterios de aceptación (fidelidad, no PF)

- Subconjunto etiquetado: % de setups SB coinciden con decisión humana (dir/entry/SL/TP).
- `scripts/diag_etapas.py` datos chicos. Backtest PF bloqueado hasta Fase G (R4).

## 6. Trazabilidad

SPEC §4 (3 setups PO3) · §17 (SB) · §20 (RR por setup) · libro 07 · ROADMAP §9 (SB) ·
PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md (top_down como filtro).
