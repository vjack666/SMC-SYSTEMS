# AUDITORÍA COMPARATIVA — Tesis ↔ Motor ↔ Dashboard ↔ Planes
## SMC-SYSTEMS — Parte II: reconciliación documental

**Fecha:** 2026-07-25
**Autor:** Auditoría interna (Hermes) — subagente de reconciliación documental
**Fuente primaria de fidelidad:** `docs/auditorias/AUDITORIA_FIDELIDAD_TESIS_SMC_SYSTEMS.md` (2026-07-22)
**Otras fuentes:** `SPEC_TESIS_FORMAL.md`, `AUDIT_R6_FORMAL_2026-07-23.md`, `AUDITORIA_DASHBOARD_OPERACIONAL_2026-07-22.md`, `CRONOGRAMA_Y_ROADMAP.md`, `docs/specs/INDICE_MDS.md`
**Alcance:** solo documentación (`docs/`). No se toca código, datos, ni git.

> **Principio rector de esta auditoría:** distinguir **"módulo cableado (anota flag)"** de **"regla de tesis EJECUTADA en el edge"**. El cronograma marca muchas filas como 🟢 CERRADO porque el módulo existe, está testeado y está cableado como PASO POST con knob apagado. Eso NO significa que la regla de la tesis se ejecute en la decisión real del backtest. Esta auditoría separa ambos estados.

---

## (a) Mapa tesis vs motor vs dashboard vs planes de trabajo

| Perspectiva | Qué dice / qué hace | Estado global |
|---|---|---|
| **Tesis (SPEC_TESIS_FORMAL)** | Contrato fuente firmado 2026-07-20. 25 secciones obligatorias. PO3/Turtle Soup/Silver Bullet = MISMO ciclo (§23). Entry en retorno a zona, TP en liquidez LTF cercana, RR mín 1:3, exec TF fino, 3 killzones. | ✅ Contrato claro y trazable |
| **Motor (ict_backtest/)** | Columna vertebral implantada (sweep, BOS/CHOCH, displacement, PD arrays, SL estructural, costs, fill). Setups nuevos cableados como anotadores. Entry real = close del BOS; TP real = cluster promedio HTF; RR default 1:2. | ⚠️ 62–70% de la tesis (fidelidad 2026-07-22) |
| **Dashboard (app_observador/)** | Panel operacional, separado de backtest. Muestra bias/estructura/sweep/OTE/killzone/Turtle/SB/PO3. FALTAN SMT, régimen, premium-discount como campos calculados. | ⚠️ Cobertura alta de lectura, lag en campos nuevos |
| **Planes (CRONOGRAMA + ROADMAP)** | Marca C2/C3/D1/E1/B3/RR/KZ-2 como 🟢 CERRADO (módulo cableado). R1/R2/R3.5/R7/Fase1/G1+G2+G3 genuinamente cerrados. | ⚠️ Mezcla "módulo cerrado" con "regla ejecutada" sin distinguir |

**Conclusión del mapa:** hay una asimetría documental. El motor y el dashboard "saben" de los setups (los anotan), pero el edge real sigue gobernado por el pipeline sequence base, que diverge de la tesis en entry, TP, RR y temporalidad fina. El cronograma no hace visible esa asimetría en las filas de setups.

---

## (b) Por estrategia — PO3 / Turtle Soup / Silver Bullet (MISMO ciclo, tesis §23)

La tesis §23 es explícita: PO3, Turtle Soup y Silver Bullet son el MISMO ciclo PO3 visto desde distinto ángulo (a favor / contra / ventana NY). Comparten: Sweep → Displacement → BOS/CHOCH → POI → Entry → SL → TP → RR → Trade Mgmt.

| Setup (ciclo) | Estado real en motor | Deuda |
|---|---|---|
| **PO3 / AMD** (§19, base sequence) | `sequence.py` calcula A+M+D; flag `po3_complete` existe. Filtro real solo si `--model po3` (fork a implementado 2026-07-23). PERO entry=close BOS (bug#1), TP=cluster HTF (bug#2), RR=1:2 (no 1:3). | ❌ La regla del ciclo NO se ejecuta en el edge: entry/TP/RR divergen de tesis. El flag po3_complete no fuerza retorno a zona ni TP cercano. |
| **Turtle Soup** (§18) | `setups/turtle_soup.py` cableado en `evaluate_signals` como PASO POST, **knob apagado**: solo anota `turtle_confirmed`/`turtle_broke`, NO filtra. | ⚠️ Módulo cableado (anota flag) ✅ vs regla de tesis EJECUTADA ❌. No cambia señales ni edge. |
| **Silver Bullet** (§17) | `setups/silver_bullet.py` cableado como PASO POST, **knob apagado**: anota `sb_confirmed`/`sb_killzone`, NO filtra. Además killzones L/NY PM NO cableadas en el edge (solo NY AM en `checklist_scalping`). | ⚠️ Módulo cableado ✅ vs regla ejecutada ❌. El flag SB no veta; el RR 1:2 del SB no se aplica salvo que no haya liquidez internal. |

**Deuda transversal del ciclo PO3:** los 3 setups comparten el pipeline sequence defectuoso (entry/TP/RR/capas). Cerrar bug#1 (entry retorno) + bug#2 (TP cercano) + RR 1:3 + capas exec/itf + killzones L/NY PM = ejecutar la regla de tesis para los 3 a la vez. Hasta entonces, "setup detectado" es información, no filtro de edge.

---

## (c) Tabla de capas transversales — estado por lado

Leyenda: ✅ completo/ejecutado · ⚠️ parcial/anotador · ❌ ausente/no ejecutado en edge
Columnas: Tesis (SPEC §) · Motor (código real) · Dashboard · Planes (cronograma)

| Capa transversal | Tesis (SPEC §) | Motor (código) | Dashboard | Planes (cronograma) | Estado real |
|---|---|---|---|---|---|
| 3 capas HTF/ITF/exec | §9 OBLIG | ⚠️ `exec_tf == ltf`; ITF/exec no separados; top_down anota `htf_aligned` pero no ejecuta capa fina | ⚠️ usa M15 como todo | B2 🟢 CERRADO (módulo `exec_tf` existe) | ⚠️ módulo existe, capa fina no ejecutada en edge |
| Entry (retorno a zona) | §11 OBLIG | ❌ entra en `close` del BOS, no en retorno a FVG/OB (bug#1) | ✅ muestra entry OTE/killzone | no fila propia; implícito en B2/Fase1 | ❌ diverge de tesis (en corrección por otro agente) |
| SL estructural | §12 OBLIG | ✅ `calc_structural_sl` anclado a mecha sweep, medido v29 | ✅ | Fase1/SL estructural ✅ CERRADO | ✅ genuinamente alineado |
| TP (liquidez cercana) | §13 OBLIG | ❌ usa cluster promedio HTF, no swing opuesto LTF más cercano (bug#2) | ✅ muestra TP liquidez | no fila propia; implícito en B3 | ❌ diverge de tesis (en corrección por otro agente) |
| RR mínimo 1:3 | §20 OBLIG | ❌ default `fixed2r` = 1:2; filtro 1:3 no aplicado salvo fallback sin liquidez | ✅ muestra RR del setup | RR por setup 🟢 CERRADO (aplica solo sin liquidez) | ❌ regla 1:3 no ejecutada en edge |
| Killzones L/NY PM | §15 OBLIG | ⚠️ TZ corregida (KZ-2) pero solo NY AM lógica cableada; London/NY PM no en edge | ✅ `killzone_activa_ahora` | KZ-2 🟢 CERRADA | ⚠️ TZ OK, ventanas L/NY PM no ejecutadas en edge |
| POI anclado (bonus) | §16 OBLIG bonus | ⚠️ `enable_pd_index=False` por defecto → bonus ni se calcula; hook existe | ✅ PO3 complete | Fase C/B1 🟢 CERRADO | ⚠️ módulo existe, desactivado por defecto |
| Dealing range / P-D | §2 OBLIG | ⚠️ módulos sueltos, NO integrados en `evaluate_signals` | ❌ no campo calculado | no fila; implícito Fase1 | ⚠️ fuera del pipeline canónico |
| SMT Divergence | §25 (libro 25) OBLIG | ⚠️ detector `smt_divergence()` existe, cableado como post-flag Opción B (anota, no filtra) | ❌ no campo en observador (Opción B pendiente) | R3.5 🟢 CERRADO (detector+tests) | ⚠️ detector existe, no es regla de edge ni dashboard |
| Régimen de mercado | (libro 21 / derivado rango) | ⚠️ `avg_candle_range` existe en backtest; no deriva régimen en edge | ❌ no indicador en observador | no fila | ⚠️ disponible, no ejecutado como filtro |
| Trade Mgmt (BE/parcial/trailing) | §22 OBLIG | ⚠️ `trade_mgmt.py` cableado pero `trade_mgmt=False` por defecto (regresión cero = SL/TP simples) | ❌ no gestión en vivo | E1 🟢 CERRADA (módulo+wire) | ⚠️ módulo cableado, apagado por defecto en edge |
| Stacking multi-TF | §5 OBLIG | ⚠️ `tier_engine.py` existe, no consumido por sequence como regla de tier | ⚠️ PO3 complete parcial | R3.5/B1 🟢 CERRADO | ⚠️ infra existe, no eleva tier en edge |

---

## (d) Deuda priorizada

### 🔴 ROJA — afecta el edge real (decisión de entrada/salida)
1. **bug#1 — Entry = close del BOS** (tesis §11 ❌). El motor entra en el close de la vela de estructura, no en el retorno a la zona. Impacto alto: mitad del bug que mató v28/v29. *En corrección por otro agente en código.*
2. **bug#2 — TP = cluster promedio HTF** (tesis §13 ❌). Usa `bsl/ssl` como cluster promedio; si el rango es amplio, TP lejano → sale por `hold_limit` (44/258 EURUSD, 7/11 y 11/13 v29). Impacto alto. *En corrección por otro agente en código.*
3. **RR mínimo 1:3 no ejecutado** (tesis §20 ❌). Default `fixed2r` = 1:2; el filtro 1:3 solo aplica al fallback sin liquidez internal. El edge vive del hold, no del TP real.
4. **Capas exec/itf no separadas** (tesis §9 ⚠️→🔴). `exec_tf == ltf`; no hay confirmación fina M5/M1 en el edge del sequence. Falta la capa de confirmación fina que la tesis exige.
5. **Killzones L/NY PM no cableadas en edge** (tesis §15 ⚠️). Solo NY AM lógica en `checklist_scalping`; TZ corregida (KZ-2) pero ventanas London/NY PM no filtran en el pipeline canónico.

### 🟡 AMARILLA — módulos cableados como anotadores, no ejecutados en el edge
6. **C2 Silver Bullet** — módulo cableado (anota `sb_confirmed`/`sb_killzone`), knob apagado, no filtra duro. Regla de tesis no ejecutada.
7. **C3 Turtle Soup** — módulo cableado (anota `turtle_confirmed`/`turtle_broke`), knob apagado, no filtra.
8. **D1 OTE** — módulo cableado (anota `ote_confirmed`/`ote_zone`); la auditoría de fidelidad lo marca ⚠️ "no-op en producción real".
9. **E1 Trade Mgmt** — cableado pero `trade_mgmt=False` por defecto; el trade real usa SL/TP simples.
10. **B3 internal/external liq** — `external_tp` es metadato (`ICTSignal`); el TP primario sigue siendo internal cluster (ver bug#2).
11. **RR por setup** — aplica `rr_target` al TP solo cuando NO hay liquidez internal (casi siempre hay), así que en la práctica no se aplica.
12. **POI anclado** — `enable_pd_index=False` por defecto → el bonus ni se calcula (aunque `as_gate=False` es correcto por evidencia Fase E).
13. **Dealing range / premium-discount** — módulos fuera del pipeline canónico `evaluate_signals`.
14. **SMT Divergence** — detector existe y está cableado como post-flag Opción B, pero no es regla de tier ni aparece en el dashboard.
15. **Stacking multi-TF** — `tier_engine.py` no consumido por `sequence` como regla de tier.

### 🟢 VERDE — genuinamente alineado / cerrado
- Sweep manipulación, BOS/CHOCH/MSS, Displacement, PD Arrays FVG/OB (✅ motor).
- SL estructural medido (v29 EURUSD PF 1.128 / GBPUSD 2.101) (✅).
- R6 sello v1: G1 closed-only + G2 fill next-open + G3 costs ON (✅ 15/15 tests).
- R7 unificación de motor (✅ motor único `market_structure.py`).
- Fase 1 ATR→RANGO (✅ volatilidad sin indicadores).
- R5 datos multi-año M15 (✅ en disco).
- ML quality filter opcional (✅).
- Hitos R1/R2/R3/R3.5/R4/R9/Fase1/SL estructural/G1+G2+G3 (✅ cerrados de verdad, no tocar).

---

## (e) Recomendación

1. **No revertir el estado 🟢 CERRADO de los módulos** (C2/C3/D1/E1/B3/RR/KZ-2): el cableado existe, está testeado y es real. Pero el cronograma debe documentar explícitamente que "CERRADO" = *módulo cableado / anota flag*, NO = *regla de tesis EJECUTADA en el edge*. Ver notas de deuda agregadas en `CRONOGRAMA_Y_ROADMAP.md`.
2. **Prioridad 1 (en curso, código):** cerrar bug#1 (entry retorno a zona) y bug#2 (TP liquidez LTF cercana). Sin esto, el edge del sequence no representa la tesis.
3. **Prioridad 2 (decisión de diseño):** definir si los setups (SB/Turtle/OTE) deben activarse como **filtros duros opcionales** (knob encendido por `--setup-filter`) o quedarse como anotadores informativos. Hoy el knob apagado hace que "setup detectado" no cambie el edge.
4. **Prioridad 3 (edge):** ejecutar RR mín 1:3 (no solo fallback), separar capas exec/itf (`exec_tf` ya viaja al runner desde 2026-07-22 pero `sequence` sigue `exec_tf==ltf`), y cablear killzones L/NY PM en el pipeline canónico.
5. **No declarar "edge" hasta** que bug#1/#2 + RR + capas + killzones estén ejecutados Y corra A12 walk-forward OOS multi-fold (R6 veredicto sigue 🔴 pendiente de A12, no de datos).
6. **Dashboard:** cerrar la brecha SMT / régimen / premium-discount como campos calculados (Opción B, "EN CONSTRUCCIÓN" si falta) para que el panel operacional refleje el mismo ciclo PO3 que el motor anota.

---

*Auditoría documental generada 2026-07-25. Complementa `AUDITORIA_FIDELIDAD_TESIS_SMC_SYSTEMS.md` (2026-07-22) separando "módulo cableado" de "regla ejecutada". No altera código, datos ni git.*
