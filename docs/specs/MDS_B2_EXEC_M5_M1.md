# MDS — B2: Ejecución fina M5 + Confirmación M1 (SPEC §10, libro 18)

**Clasificación:** OBLIGATORIO · **Fase:** B2 · **Estado:** ❌ pendiente de implementar
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §10 · **Roadmap maestro:** §9 (B2)
**R1:** requiere SPEC firmada ✅ (2026-07-20) + este MDS antes de código.

---

## 0. Responsabilidad (CON QUÉ se implementa)

Bajar la **entry / SL / TP** al exec TF fino (M5) y la confirmación a M1, separados de
`htf`/`itf`. Hoy el motor itera `ltf` y `exec_tf == ltf` por coincidencia (libro 18 §4
cadena de falla). Este MDS rompe ese acoplamiento.

## 1. Módulos y funciones

| Pieza | Ruta | Rol | Gap |
|-------|------|-----|-----|
| `build_signals_from_frames` | `ict_backtest/engine.py` | genera entry/SL/TP por señal | 🔴 agregar param `exec_tf` (hoy solo `ltf`) |
| `calc_structural_sl` | `ict_backtest/engine.py` | SL estructural | 🔴 recibir el `row` del **EXEC_TF** (no del ltf) |
| `checklist_scalping` | `ict_backtest/rules.py` | valida setup | ✅ ya pasa `exec_tf` explícito (reusable) |
| `emit_m5` | `ict_backtest/plan_emitters.py` | ENTRY_READY en M5 misma dir | ✅ existe (Fase 3); usarlo para confirmación |
| `multitf_context.py` | `ict_backtest/multitf_context.py` | carga M5/M1 cerrado-only | ✅ ya carga la cadena TF |

## 2. Firma propuesta

```python
def build_signals_from_frames(htf, itf, exec_tf, ...):
    # 1) bias  = trend del HTF (vela cerrada)
    # 2) zona  = BOS/CHOCH/FVG/OB en ITF
    # 3) entry = retorno a zona en EXEC_TF
    # 4) sl    = calc_structural_sl(row_exec, direction)  # row_exec del EXEC_TF
    # 5) tp    = liquidez opuesta MÁS CERCANA del EXEC_TF
    # 6) if RR(tp, sl) < umbral_por_setup: NO operar
```

`calc_structural_sl` pasa a recibir `row_exec` (vela del exec TF), no `row_ltf`.

## 3. Reglas duras (libro 18 §0)

- SL y entry SIEMPRE en exec TF. Nunca en TF mayor.
- Exec TF default = M15 hoy; M5/M1 objetivo de esta fase.
- M1 no disponible → confirmar en M5 (sin M1). Nunca degradar a H4.

## 4. Integración

- Desbloquea Silver Bullet (§17) y Turtle Soup (§18): ambos requieren exec M5/M1.
- `run_sequence` consume `exec_tf` desde `MultiTFContext` (ya cerrado-only, anti look-ahead R6).
- No crea señal nueva: refina dónde se ancla entry/SL/TP.

## 5. Criterios de aceptación (tests)

- TDD RED→GREEN: long tras sweep SSL en exec_tf → SL bajo mecha de ESE tf; scalping con
  `exec_tf=M1` ≠ SL de M5.
- Regresión: modo `exec_tf==ltf` (M15) produce mismas señales que hoy (no rompe legacy).
- `scripts/diag_etapas.py` con datos chicos (800-1500 velas), NO backtest de PF (R4).

## 6. Trazabilidad

SPEC §9 (3 capas) → §10 (exec M5/M1) · libro 18 §0/#4/#5 · ROADMAP_TESIS_DRIVEN §9 (B2) ·
ROADMAP_CAPACIDADES §3 (Exec TF M5 = Pendiente).
