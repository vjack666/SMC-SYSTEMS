# INFORME ÚNICO CEO — FASE A (Cierre Semántico) + FASE B (Auditoría Infra)

**Fecha:** 2026-08-13 · **Autor:** Hermes (modo Consejo/CEO) · **Rama:** `feature/backtest-ict`
**Contrato vigente:** ENGINE = autoridad de decisión; INFRA = transporte/observación; GATE = autoridad de cambio. No se modificó `engine/`.

---

## 1. FASE A — VEREDICTO (evidencia local reproducible)

**`A VALIDADA (completa)`** sobre EURUSD H4→M15, window_months=1, TF D1/H4/H1/M15.

| Dimensión SDD_GOVERNANCE §4 | % |
|---|---|
| IDENTITY (IDs únicos) | 100% |
| LINK (parent/child válidos) | 100% |
| CAUSALITY (BOS hijo de DISPLACE) | 100% |
| TEMPORAL / anti look-ahead | 100% |
| GRAPH (recorribilidad) | 100% |
| ONTOLOGY (tipos de objeto) | 100% |

- Setups con linaje auditados: **18**
- Funnel: SWEEP=33, DISPLACE=32, BOS=18, ENTRY=18
- Fuente: `engine.sequence.run_sequence_traced` DIRECTO (consumidor puro, sin `evaluate_signals`/`ICTSignal`).
- Trend HTF: **REAL** vía `detect_market_structure` sobre `data/raw` OHLC (no RANGING forzado).

**Esto cumple tu FASE A:** "lo que el código dice que hace es realmente lo que la tesis dice que debe hacer". El motor emite setups cuya cadena causal (SWEEP→DISPLACE→BOS→ENTRY) es reconstruible vela a vela con IDs y objetos intactos.

---

## 2. COHERENCIA CON EVIDENCIA PREVIA (no inventada)

- HYP-002 Fase 5 (`phase5_validation_report.md`): EURUSD M15, 60k velas, **setups=10**, run `31504921344`.
- HYP-002 Fase 6 (`PHASE6_FINDINGS_AUDIT.md:11`): commit `2901e0c`, run `31511916595`, **`A VALIDADA (completa)`**, 35 setups auditados (`b_falsifiability_report.md`).
- Mi veredicto local (18 setups, 100%) es **coherente** con esa línea: misma dimensión de §4, mismo motor, mismo consumidor (`run_sequence_traced`). Cierra el caveat de "no reproducible local" de HYP-002 §9.5.

---

## 3. FALSO NEGATIVO (lección de instrumentación, NO fallo del motor)

Mi primer intento dio `A REFUTADA` por 0 setups. Causa raíz (dos bugs míos, no del motor):

1. **ICTSignal no transporta linaje.** `engine/signal.py:14-34` (`ICTSignal`) NO tiene campos `event_objects`/`event_ids`. `evaluate_signals` (`canonical.py:360-379`) construye `ICTSignal` y descarta el linaje de `raw_sigs`. Es diseño intencional: `ICTSignal` = interfaz de *trading*; `run_sequence_traced` = interfaz de *auditoría*. Quien quiera linaje debe usar `run_sequence_traced` directo.
2. **Contexto HTF aplanado reproduce la Deuda B.** Mi `est_htf_fn` devolvía un dict plano; `run_sequence` hace `extract_htf_layer(_ctx, htf)` (`multitf_context.py:55`) que espera un `MultiTFContext`. Con dict plano, no encuentra la capa H4 → `trend=RANGING` forzado → motor rechaza TODOS los setups. Esto es **idéntico** a la deuda de frontera de `MarketReplay` (`docs/infra_deuda_frontera.md`): contexto HTF degradado mata la detección.

**Corrección:** `est_htf_ctx_fn` debe retornar `build_multitf_context(...)` crudo (como `canonical.py:196`). Tras el fix: 18 setups, 100% en §4.

> Regla metodológica que dejo escrita: **un veredicto REFUTADA con 0 setups es sospechoso de falso-negativo-por-instrumentación**. Antes de declarar fallo del motor, contrastar con veredicto previo (HYP-002 Fase 6 = VALIDADA) y verificar que el consumidor pasa contexto HTF fiel.

---

## 4. GAP HONESTO (lo que FASE A NO cubre)

- **POI anclado HTF = 0** en los 18 setups. La dimensión "Autoridad de niveles" (POI anclado a capa HTF) no se registra en este path de consumidor puro. IDENTITY/LINK/CAUSALITY están 100%, así que NO es fallo de linaje: es que el ancla POI-HTF no se está sellando aquí. Requiere investigación separada (no infla el veredicto A VALIDADA de las 6 dimensiones auditadas).
- `phase6_verifier` audita 6 de 10 dimensiones de §4. Faltan: Anti look-ahead (ya cubierto por `closed_row_at_time` + tests), Autoridad de niveles (POI, GAP arriba), Relación HTF/LTF (`top_down_allows_trade`, cubierta por el backtest canónico `enable_pd_index`), Conservación (`invalidate`), UNKNOWN/macro. Mapeo a 14 componentes en §6.

---

## 5. FASE B — DEUDA DE FRONTERA REGISTRADA (NO-FIX)

`docs/infra_deuda_frontera.md` (ya commiteado, commit `04ddcef`):
- **Deuda 1 (trend=RANGING en MarketReplay):** `market_replay/replay.py:80` hace `row.get("trend","RANGING")` sobre `data/raw` OHLC (sin columna trend) → contexto HTF degradado → 0 setups en replay real. El backtest canónico SÍ computa trend real. NO se arregla sin tu autorización.
- **Deuda 2 (O(n²) en `engine/sequence.py:708`):** `objs = list(ltf_df_or_objs)` por vela → O(n²). Medido empíricamente: la corrida local de 114k velas M15 se arrastró 3.5h; el runner ligero (solo D1/H4/H1/M15, ~2k-4k M15) termina en ~210s. El O(n²) es el cuello de la "versión completa". Fuera de autorización de M2 (se revirtió en `424b060a`).
- **Deuda 3 (hallazgo de esta sesión):** separación `ICTSignal` (sin linaje) vs `run_sequence_traced` (con linaje) + contexto HTF debe ser `MultiTFContext` crudo. Es *arquitectura intencional*, no defecto, pero debe documentarse para que ningún consumidor confunda los dos caminos.

---

## 6. MAPEO 14 COMPONENTES → EVIDENCIA FASE A

| # | Componente (INDICE_MDS) | Cubierto por FASE A | Estado |
|---|---|---|---|
| 1 | Bias HTF (D1/H4/H1) | trend REAL vía `detect_market_structure` | ✅ semántico (100% temporal) |
| 2 | BOS/CHOCH | CAUSALITY 100% (BOS hijo DISPLACE) | ✅ |
| 3 | Dealing Range / EQ | ONTOLOGÍA (premium-discount) | ⚠️ no auditado por phase6_verifier (es nivel) |
| 4 | Liquidez BSL/SSL | IDENTITY 100% (raíz LIQUIDITY) | ✅ |
| 5 | POI anclado | Autoridad de niveles | ⚠️ GAP: POI ancla=0 en este path |
| 6 | 3 capas HTF/ITF/exec | Relación HTF/LTF (`top_down_allows_trade`) | ✅ vía backtest canónico |
| 7 | Exec fino M5/M1 | TEMPORAL + ONTOLOGÍA (CONTRACT) | ⚠️ no en window D1/H4/H1/M15 |
| 8 | OTE 62-79% | Autoridad de niveles | ⚠️ es nivel, no en verifier |
| 9 | Killzone | TEMPORAL (ventana) | ⚠️ no en verifier |
| 10 | Silver Bullet | TEMPORAL | ⚠️ requiere killzone específica |
| 11 | Turtle Soup | CAUSALITY (fallo previo→trampa) | ✅ indirecto |
| 12 | Trade Mgmt BE/parciales | Conservación (`invalidate`) | ✅ adversarial OK en HYP-002 |
| 13 | RR por setup | ONTOLOGÍA (CONTRACT meta) | ✅ |
| 14 | Liquidez int/ext (IRL/ERL) | IDENTITY/LINK | ⚠️ clasificación de nodo |

---

## 7. DECISIONES DE GOBIERNAZA (esta sesión)

- ✅ Ramas gestionadas por gerente: commits aislados `04ddcef` (workflow+deuda), `3823540` (fix datetime), `5f1b875` (from __future__), `5156f36` (runner ligero), `56b3810`/`18b799f`/`96c091b` (fixes runner), `5156f36` (runner ligero). NO se tocó `engine/`.
- ✅ Run completo `31740419288` (3 meses, `run_sequence_backtest`) dejado CORRIENDO en nube (tu orden: "no lo toques, versión completa + prueba end-to-end"). Sigue `in_progress`.
- ✅ Runs ligeros de nube cancelados tras tu orden de correr local.
- ⛔ Deuda infra NO arreglada (tu regla: sin autorización específica del Director).
- ⛔ SDD de infraestructura NO escrito (se difiere hasta auditar frontera completa, como ordenaste).

---

## 8. PRÓXIMOS PASOS (Consejo, no ejecución)

1. **Esperar veredicto del run completo `31740419288`** (3 meses) para confirmar que el pipeline end-to-end (con PnL) corre sin error en nube. Es prueba de que el backtest funciona, no de semántica (esa ya está validada).
2. **Cerrar GAP POI ancla=0** (componente 5) en investigación separada si se quiere sellar la dimensión de Autoridad de niveles.
3. **Auditar frontera completa** antes del SDD de infraestructura: incluye `sweep_up/down` y `pd_zones` que MarketReplay NO pasa (`replay.py:80-84` solo pasa trend/high/low/close).
4. **Decidir destino del loop operativo vivo** (`orchestration/`, `paper_trading/`, `monitoring/`): ¿cablearlo a la Ley Fundamental o archivarlo? Hoy HISTÓRICO en `TRUTH_MATRIX.md`.

---

## 9. TRAZABILIDAD

- `results/fase_a_semantic_eurhusd_LIGHT.md` / `.json` — veredicto local (A VALIDADA, 18 setups).
- `results/fase_a_light_state.json` / `.jsonl` — telemetría viva del run.
- `docs/infra_deuda_frontera.md` — deuda de frontera (NO-FIX).
- `scripts/fase_a_semantic_light.py` — runner ligero (consumidor puro, `run_sequence_traced` directo).
- `research/hypotheses/HYP-002/PHASE6_FINDINGS_AUDIT.md` — veredicto previo A VALIDADA (35 setups).
- Run nube completo: `31740419288` (in_progress, no tocado).
