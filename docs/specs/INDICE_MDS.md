# ÍNDICE MDS — Diseño de módulo por componente (R2 del roadmap maestro)

**Estado:** 2026-07-20 · SPEC_TESIS_FORMAL FIRMADA ✅ (R1 cumplida)
Cada regla de la SPEC tiene su MDS aquí (sincronía SPEC↔MDS exigida por R2).

| Componente | SPEC | Clasificación | Fase | Estado | MDS |
|------------|------|---------------|------|--------|-----|
| Narrativa HTF | §1 | OBLIGATORIO | Base ✅ | ✅ | (en SPEC; no requiere MDS nuevo) |
| Dealing Range P-D | §2 | OBLIGATORIO | Base ✅ | ✅ módulo existe | (postproceso canonical) |
| PD Arrays FVG/OB | §3 | OBLIGATORIO | Base ✅ | ✅ | — |
| PD Arrays completos | §4 | OBLIGATORIO | B1 ✅ | ✅ metadatos | — |
| Stacking multi-TF | §5 | OBLIGATORIO | B1 ✅ | ✅ metadatos | — |
| Liquidez (Sweep) | §6 | OBLIGATORIO | Base ✅ | ✅ | — |
| Displacement | §7 | OBLIGATORIO | Base ✅ | ✅ | — |
| Market Structure | §8 | OBLIGATORIO | Base ✅ | ✅ (PASO 1) | — |
| 3 capas HTF/ITF/exec | §9 | OBLIGATORIO | B2 | ❌ | MDS_B2_EXEC_M5_M1.md |
| Exec fino M5 + M1 | §10 | OBLIGATORIO | B2 | ❌ | MDS_B2_EXEC_M5_M1.md |
| Entry retorno zona | §11 | OBLIGATORIO | Base ✅ | ✅ | — |
| SL estructural | §12 | OBLIGATORIO | Base ✅ | ✅ medido v29 | — |
| TP liquidez cercana | §13 | OBLIGATORIO | Base ✅ | ✅ | — |
| Liquidez internal/external | §14 | OBLIGATORIO | B3 | ❌ | MDS_B3_LIQUIDEZ_INT_EXT.md |
| Killzone L/NY PM | §15 | OBLIGATORIO | B2 | ❌ | MDS_KILLZONES_L_NYPM.md |
| POI anclado (bonus) | §16 | OBLIGATORIO (bonus) | C1 ✅ | ✅ percepción | (Fase C DONE) |
| Silver Bullet | §17 | OBLIGATORIO | C2 | ❌ | MDS_C2_SILVER_BULLET.md |
| Turtle Soup | §18 | OBLIGATORIO | C3 | ❌ | MDS_C3_TURTLE_SOUP.md |
| PO3 / AMD | §19 | OBLIGATORIO (base) | Base ✅ | ✅ (sequence) | — |
| RR por setup | §20 | OBLIGATORIO | C2 | ❌ | MDS_RR_POR_SETUP.md |
| OTE 62-79% | §21 | OBLIGATORIO | D1 | ❌ | MDS_D1_OTE.md |
| Trade Management | §22 | OBLIGATORIO | E1 | ❌ | MDS_E1_TRADE_MANAGEMENT.md |

**Conteo:** 8 componentes ❌ con MDS nuevo (B2 exec, internal/external liq, killzones
L/NY PM, SB, Turtle, RR por setup, OTE, Trade Mgmt). El resto ✅ o ya cubierto por Fase
C/B1. Backtest de PF bloqueado hasta Fase G (R4).

Orden de implementación sugerido (por dependencia, ROADMAP §4):
B2 (exec M5/M1) + Killzones L/NY PM → B3 (internal/external liq) → C2 (SB + RR por setup)
→ C3 (Turtle) → D1 (OTE) → E1 (Trade Mgmt).
