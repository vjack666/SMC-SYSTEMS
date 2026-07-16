# 06 — Gap analysis: checklist profesional vs SMC-SYSTEMS

| Campo | Valor |
|-------|-------|
| **ID** | `13/06_GAP_SMC_SYSTEMS` |
| **Versión** | 1.1 |
| **Fecha** | 2026-07-16 |
| **Estado** | Actualizado (R6.1/2/3 implementados) |

---

## Respuesta primero

| Área | ¿Lo respeta el sistema? |
|------|-------------------------|
| Reloj LTF vela a vela (ICT sequence) | **Sí** |
| Features LTF causales (post-fix swing) | **Sí (mejorado)** |
| HTF solo cerradas | **Sí** ✅ (R6.1: `closed_row_at_time` + `closed_merge_asof`) |
| Fill next-open | **Sí** ✅ (R6.2: `fill_entry_price` default `next_open`) |
| Costos siempre ON | **Sí** ✅ (R6.3: `COST_BY_SYMBOL` + `resolve_cost` default en runners) |
| WF multi-fold dirección correcta | **Sí** (post #5) |
| PBO/DSR en pipeline ICT | **Parcial** (código en ML, no gate ICT) |
| Portafolio multi-símbolo + prop DD | **Parcial / legacy** |
| Mismo código decisión live↔BT | **Objetivo; aún islas** |

---

## Tabla gap (accionable)

| ID | Punto profesional | Estado | Evidencia en código | Acción R6 |
|----|-------------------|--------|---------------------|-----------|
| G1 | HTF closed-only | ✅ | `closed_row_at_time` + `closed_merge_asof` (R6.1, commit 9990390) | Hecho + test multi-TF |
| G2 | Next-bar open fill | ✅ | `fill_entry_price` default `next_open` (R6.2) | Hecho + test_r6_fill_next_open |
| G3 | Cost pack siempre | ✅ | `COST_BY_SYMBOL` + `resolve_cost` default en runners (R6.3) | Hecho + test_r6_costs_on |
| G4 | Gaps sesión/weekend | 🔴 | no modelado en `simulate_trade` | Regla open-gap vs SL |
| G5 | Swap overnight | ⚪ | n/a si hold corto | Solo si max_hold multi-día |
| G6 | DSR/PBO en ICT Optuna | 🟠 | `ml/stats_validator.py` existe | Reportar en optimize.py |
| G7 | Gate N OOS / peor fold | 🟠 | METRICS + veredictos manuales | Automatizar veredicto en runner |
| G8 | No contaminar OOS | 🟠 | proceso | Checklist humano en plan |
| G9 | Datos multi-año XAU | 🟠 | R5 | Download MT5 |
| G10 | Portafolio + DD prop | 🟠 | compliance tool aparte | Opcional post-G1–G3 |
| G11 | Métricas por régimen | ⚪ | parcial | Reporte |
| G12 | Replay M1 | ⚪ | data M1 corta | Solo si modelo lo exige |
| — | Swing no look-ahead | ✅ | fix #1 | Mantener tests |
| — | CHOCH ≠ BOS | ✅ | fix #2 | Mantener tests |
| — | SL antes que TP | ✅ | simulate_trade | Mantener |
| — | Sequence event memory | ✅ | sequence.py | Mantener |
| — | TZ killzone UTC | ✅ | R2 | Mantener |

Leyenda: 🔴 crítico · 🟠 importante · ⚪ opcional/deuda · ✅ ok

---

## Lo que **sí** está bien (no rehacer)

1. Motor **event-sequence** (sweep → displace → BOS → retorno) con memoria de fases.  
2. Corrección de look-ahead de swings y CHOCH real (auditoría 2026-07-11).  
3. Walk-forward multi-fold con dirección temporal correcta.  
4. Costos **implementados** (falta política de uso).  
5. Estadísticos avanzados en `ml/stats_validator.py` (aprovechar, no reescribir).  
6. Separación theory_mode vs producción en la **filosofía** del pack (este libro §0).

---

## Impacto esperado (cualitativo)

| Fix | Efecto típico en PF reportado |
|-----|-------------------------------|
| G1 HTF cerradas | Baja o reordena señales (menos “timing perfecto”) |
| G2 next-open | Empeora ligeramente expectancy (latencia 1 barra) |
| G3 costos ON | Empeora (ya visto en R4 E5) |
| G1+G2+G3 juntos | El PF “de marketing” se acerca al PF “de prop” |

**No se asume magnitud:** se mide y se escribe en METRICS_CANON.

---

## En resumen

El sistema **no es un backtest amateur puro** (tiene sequence, fixes de look-ahead, WF, stats, y desde R6.1/2/3: HTF cerradas, fill next-open y costos siempre ON).  
El GATE R6 **no pasa en EURUSD M15** (R6.4 M2: PF -4.89 producción, ver METRICS_CANON §0) — no por errores de implementación sino porque el motor ICT intradía no muestra edge en esa muestra. Pendientes reales: G4 (gaps sesión), G6/G7 (DSR/PBO gate), G9 (datos R5 para M3), G10/G11 (portafolio/régimen). Ver PLAN_BACKTEST_PROFESIONAL §06 y CRONOGRAMA.
