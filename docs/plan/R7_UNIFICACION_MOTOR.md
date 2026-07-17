# R7 — Unificación del motor de decisión ICT (single source of truth)

ESTADO: FASE 1 y FASE 2 **CERRADAS Y CONGELADAS** (2026-07-15).
**Implementación R7 (2026-07-16, autorización usuario "unificalo"):**
- `ict_backtest/canonical.py` = API única `evaluate_signals` / `latest_plan`
- `run_backtest.generate_sequence_signals` = thin wrapper a canonical
- `build_signals_from_frames` eliminada (T3.2B previo)
- `agents/ict_agent.py` ya no reimplementa geometría; lee columnas + `decision_engine=sequence`
- observador `run_cycle` adjunta `canonical` plan y LIMIT/Lab lo prefieren
- Deuda explícita: `legacy/backtest`, `ml/dataset_builder` (R7_DOCUMENTED_DEBT)
Fases 3-6 DoD parcial: motor único en alcance vivo + backtest default; legacy/ML documentados fuera.

**JERARQUÍA DOCUMENTAL (regla de oro, post-alineación 2026-07-15):** ante
cualquier conflicto entre documentos oficiales, este contrato R7 es la
autoridad para implementación. Orden de precedencia:
1. `R7_UNIFICACION_MOTOR.md` — contrato de implementación (autoridad).
2. `MARKET_OBJECT_MODEL.md` — ontología (visión de largo plazo; sus partes
   fuera de alcance de R7/R9 se aclaran, no se cambian).
3. `DISENO_ARQUITECTURA_OBJETOS_MERCADO.md` — arquitectura.
4. `REVISION_ARQUITECTURA_CONVIVENCIA.md` — estrategia de migración.
5. `ROADMAP_BIBLIOTECA_Y_APLICACION.md` / `CRONOGRAMA_Y_ROADMAP.md` —
   planificación (se alinean al contrato, no al revés).
Los documentos de menor jerarquía NUNCA deben contradecir a los superiores;
si hay conflicto, se actualiza el de menor jerarquía.

────────────────────────────────────────────────────────
## 0. Contrato arquitectónico (alcance de la congelación)
────────────────────────────────────────────────────────
R7 NO es una mejora de estrategia. R7 es la eliminación de la duplicidad de
motores de decisión. El objetivo medible es UNA sola función de evaluación ICT
que produzca idénticas señales en backtest, UI y agente.

Las Fases 1 y 2 definen QUÉ es el sistema resultante y QUIÉN hace QUÉ. Las
reglas ICT (POI, quality_score, narrativa, sweep, BOS, CHOCH, MSS, entry,
risk) NO se cambian: solo se unifican los caminos que hoy las evalúan de
forma divergente.

NOTA POST-AUDITORÍA: el inventario original (engine vs sequence) era
INCOMPLETO. La auditoría crítica reveló motores ICT paralelos vivos que NO
estaban documentados (`agents/ict_agent.py`, `legacy/backtest`, `ml`). El
contrato se amplía para hacerlos VISIBLES (no para migrarlos todas en R7),
evitando que el "Definition of Done" se declare falsamente cumplido.

══════════════════════════════════════════════
## FASE 1 — Inventario de diferencias (CERRADA · CONGELADA · AMPLIADA)
══════════════════════════════════════════════
Medido contra código real (engine.py / rules.py / sequence.py / ict_agent.py /
legacy/backtest / ml / scripts, 2026-07-15). Clasificación: ARQ=arquitectura,
REGLA=regla ICT, SIM=simulación, RIES=riesgo, COMPAT=compatibilidad,
DOC=documentación (no impl).

### 1.1 Flujo de decisión (engine.py vs sequence.py)
| Ítem | engine.py (checklist, DEFAULT en run_backtest.run) | sequence.py (event-sequence, --engine sequence) | Clase |
|---|---|---|---|
| Unidad de iteración | barra a barra, evalúa mini-check en LA MISMA vela | eventos en SECUENCIA (sweep→displace→BOS→retorno) con memoria | ARQ |
| Entry | `entry = row["close"]` (entra en el CIERRE de la vela del check) | `entry = obj.meta["close"]` SOLO cuando el precio RETORNA al cuadro (mitigation) | REGLA |
| RR | 1:2 fijo (`entry ± 2.0*risk`, RR 1:2 Stellar) | 1:3 (`entry ± 3.0*risk`) en el backtest run_sequence_backtest | RIES |
| SL | `calc_structural_sl` (mecha sweep / swing, buffer 0.3 ATR, MAX 6 ATR) | `calc_structural_sl` MISMA función (reusada) | RIES (compartido) |
| TP | `tp_mode`: 2R o liquidez opuesta (BSL/SSL) | 2R o liquidez opuesta (misma `_tp_liquidity`) | RIES (compartido) |
| Displacement | requerido OPCIONAL (`require_displacement` default False en build_signals) | requerido por default (`require_displacement=True`) + ventana `displace_gap` | REGLA |
| Killzone | SÍ exige KZ (London/NY AM/PM) en checklist_intradia/scalping | NO mira killzone (solo sesgo HTF + secuencia) | REGLA |
| Sesgo | desde `htf_trend` D1/H4; votes opcionales | desde `htf_trend` (est_htf_fn) D1; NO votes | REGLA |
| POI HTF | NO cableado en build_signals | `htf_poi_fn` OPCIONAL (default None = histórico) | REGLA |
| Counter-trend | SÍ (`counter_trend=True`, dir opuesta al sesgo) | SÍ (`counter_trend=True`, exige CHOCH antes de BOS) | REGLA |
| Modelos | intradia / scalping (Silver Bullet M1/M5) / po3 | solo event-sequence (PO3/Turtle Soup estilo) | REGLA |

### 1.2 Representación de datos
| Ítem | engine.py | sequence.py | Clase |
|---|---|---|---|
| Input | `dict[str, DataFrame]` (frames por TF) | `list[MarketObject(CANDLE)]` (R9 Paso 3) o DataFrame | ARQ |
| Lectura de señal | `ltf_df.iloc[i]` + `row.get(col)` DIRECTO | `obj.meta[col]` (objeto) | ARQ |
| Contexto HTF | `_build_estructura` arma dict por TF desde `frames[tf].iloc` | `est_htf_fn(i)` devuelve dict del HTF (equivalente) | ARQ |
| Simulación | `simulate_trade(frame, signal, max_hold)` lee `frame.iloc` (DataFrame) | `simulate_trade` MISMA función (compartida, post-decisión) | SIM (compartido) |

### 1.3 Motores ICT paralelos (HALLAZGOS H1 / H2 / H3 — post-auditoría)
Estos NO estaban en el inventario original. Son decisiones ICT vivas aparte de
engine/sequence. Se documentan para que el DoD no las ignore.

- **H1 — `agents/ict_agent.py` (TERCER motor ICT, isla total).**
  `ICTAgent.analyze` (agents/ict_agent.py:11-50) reimplementa por su cuenta
  _detect_trend/_detect_bos/_detect_choch/_detect_sweep/_detect_fvg/_detect_ob
  sobre el DataFrame. NO importa engine, sequence ni rules. Lo invocan
  AgentOrchestrator → paper_trading/runner.py:21 y ml/validator.py:9.
  Si sequence es la única fuente, ict_agent NO puede seguir evaluando ICT
  aparte. DEBE aparecer en el inventario y en el DoD (delegar en sequence, no
  reimplementar). **Bloqueante.**

- **H2 — `legacy/backtest/engine.py` (motor backtest legacy, isla).**
  exporta run_combined_backtest etc. (legacy/backtest/__init__.py:1-7); tests
  legacy usan _build_signals_from_context / _simulate_trade_with_stats
  (legacy/tests/test_backtest_engine.py, test_e2e_backtest.py). Es un TERCER
  motor de señales/backtest. **No se migra en R7** (limpiar legacy es otra
  deuda), pero queda REGISTRADO y fuera de la afirmación "una sola fuente"
  hasta decidirse. **Documentado, no bloquea implementación R7.**

- **H3 — `ml/dataset_builder.py` usa el motor LEGACY, no el canónico.**
  ml/dataset_builder.py:14 →
  `from legacy.backtest.engine import _build_signals_from_context, _simulate_trade_with_stats`
  (usado en :265). O sea la capa ML genera su dataset de trades desde el motor
  legacy, NO desde ict_backtest.engine ni sequence. Aunque R7 unifique
  ict_backtest.engine→sequence, ML queda desacoplado. **El contrato DEBE decir
  explícitamente** si ML es (a) fuera de alcance inicial y migrado después, o
  (b) también redirigido al motor canónico. No puede quedar invisible.
  **Bloqueante (decisión de alcance, no de código).**

### 1.4 Consumidores secundarios de `build_signals_from_frames` (HALLAZGO H9)
Además de run_backtest.run (default, L183) y la suite pytest, dependen de
`build_signals_from_frames` (ict_backtest.engine):
- `ict_backtest/_smoke.py:15,69`
- `scripts/plot_trade_structsl.py:28,51`
- `scripts/fase0_one.py:31,50,61`
- `scripts/fase0_baseline.py:32`
- `ict_backtest/plot_equity_curve.py:26,76` (vía simulate_trade)
- `tests/test_r4_po3_isolated.py:13,50,61`
- `ict_backtest/__init__.py:11,16` lo re-exporta en `__all__` (API PÚBLICA del paquete)

Eliminar `build_signals_from_frames` tiene MÁS superficie de ruptura de la
documentada. Quién depende debe quedar explícito ANTES de programar (arquitectura,
no implementación). **Bloqueante (superficie de eliminación).**

### 1.5 Restricción arquitectónica anti-lookahead HTF (HALLAZGO H8)
`engine._build_estructura` (engine.py:242-277) arma el join cross-TF con una
guarda de cierre de barra (TF_FREQ + `_row_at_time` con `freq`, engine.py:249-260)
para NO leer indicadores de una barra HTF aún en formación (ver
AUDIT_LOOKAHEAD_HTF.md). Esta SEMÁNTICA es parte del comportamiento canónico y
DEBE preservarse al portar el contexto HTF a sequence. No es un bug, es una
restricción de arquitectura que el contrato debe exigir. **Aclaración
arquitectónica (no bloquea, pero exigible en DoD).**

══════════════════════════════════════════════
## FASE 2 — Fuente única de verdad (CERRADA · CONGELADA)
══════════════════════════════════════════════
DECISIÓN OFICIAL: el motor canónico de decisión ICT es **sequence.py**.

Fundamento (medido, no opinado):
1. Es el único ya migrado a `MarketObject[]` (R9 cerrado).
2. Modela la SECUENCIA ICT real (sweep→displace→BOS→retorno), no el mini-check
   de una sola vela. Es más fiel a la tesis 18.
3. `simulate_trade`, `calc_structural_sl`, `_tp_liquidity` YA son compartidos →
   la divergencia real está en ENTRY (retorno vs close), RR (1:3 vs 1:2) y
   killzone (no vs sí), no en la simulación.
4. La auditoría tesis-código (14-jul) determinó que el camino sequence (retorno,
   RR 1:3, SL estructural) es el ALINEADO a la tesis 18; engine (close, RR 1:2)
   es la isla divergente.

RESOLUCIÓN DE DIVERGENCIAS (congelada, vinculante para Fases 3+):
- Entry: canonical = EN RETORNO al cuadro (sequence). El entry en close de
  engine se elimina.
- RR: canonical = 1:3 (sequence). El RR 1:2 de engine se elimina.
- SL/TP estructural: canonical = las funciones YA compartidas
  (`calc_structural_sl`, `_tp_liquidity`). Sin cambios.
- Killzone / scalping(M1/M5) / po3 / votes: capacidades de engine que se
  PORTAN a sequence como modos de configuración (SequenceConfig), sin alterar
  la ontología de objetos. NO se eliminan las reglas, se reubican.

══════════════════════════════════════════════
## CONTRATO OFICIAL DE R7 (AMPLIADO POST-AUDITORÍA)
══════════════════════════════════════════════

### A. Fuente única de verdad
Una sola función de evaluación ICT — `sequence.run_sequence` (sobre
`MarketObject[]`) — es invocada por backtest, UI observador y agente. No hay
segundo motor de decisión EN EL ALCANCE DE R7. Los motores paralelos documentados
en 1.3 (ict_agent, legacy) deben quedar resueltos (redirigidos o declarados
deuda fuera de R7) y NO pueden quedar invisibles.

### B. Responsabilidades de cada módulo (post-unificación)
| Módulo | Responsabilidad oficial | Estado tras R7 |
|---|---|---|
| `sequence.py` | ÚNICO motor de decisión. Consume `MarketObject[]`. Expone modos (intradia / scalping / po3 / counter_trend) vía `SequenceConfig`. Emite señales canónicas. | Canónico |
| `engine.py` | Eliminado como motor. **T3.2B (2026-07-15): `build_signals_from_frames` BORRADA (isla).** Sobreviven SOLO sus helpers PUROS y compartidos: `simulate_trade`, `calc_structural_sl`, `_tp_liquidity`, `ICTSignal`, `ICTTrade`. | Degradado a helpers |
| `rules.py` | Funciones PURAS de checklist (intradia/scalping/po3) consumidas POR sequence como definición de reglas (no como motor independiente). | Biblioteca de reglas |
| `translation.py` | Capa de compatibilidad DataFrame↔MarketObject. INTACTA. | Congelada |
| `object_adapter.py` | Puente `objects_view`. INTACTA. | Congelada |
| `run_backtest.run` (default) | Debe invocar `run_sequence` (sequence), NO `build_signals_from_frames`. **El camino por defecto (sin --engine) debe usar el motor canónico.** | Redirigido |
| `pipeline.py` (vivo) | Debe invocar `run_sequence` (sequence), no `build_signals_from_frames`. | Redirigido |
| `ict_agent.py` | DEBE delegar la evaluación ICT en `sequence` (no reimplementar BOS/CHOCH/sweep/FVG/OB). Es un consumidor del motor canónico, no un motor. | Redirigido (H1) |
| `legacy/backtest/engine.py` | FUERA del alcance de implementación de R7. Se registra como motor legacy y requiere DECISIÓN documentada (migrar o aceptar como deuda). No puede invisibilizarse. | Documentado (fuera alcance impl) |
| `ml/dataset_builder.py` | FUERA del alcance de implementación de R7. Requiere DECISIÓN documentada explícita: (a) migrar a sequence posteriormente, o (b) redirigir al motor canónico. No puede quedar invisible en el contrato. | Documentado (fuera alcance impl) |
| `optimize.py` | Ya usa `run_sequence`. | Alineado |
| `app_observador/ui/*` | Usa `rules.py` (checklist) para VISUALIZACIÓN; la generación de señales real pasa por sequence. (Nota: `app_observador/core/engine.py` es módulo distinto de `ict_backtest/engine.py`; NO se confunde.) | Vista, no motor |
| `scripts/` (_smoke, fase0_*, plot_*) | Consumidores secundarios de `build_signals_from_frames`/`simulate_trade`. **T3.2A: redirigidos al motor canónico. T3.2B: `build_signals_from_frames` eliminada.** `simulate_trade` permanece como helper puro. | Redirigidos |

### C. Alcance (scope)
- Unificar los dos motores de decisión principales (engine ↔ sequence) en uno solo.
- Portar a sequence las reglas que hoy solo tiene engine (killzone, scalping,
  po3, votes) como configuración, sin cambiar su semántica ICT.
- Redirigir todos los consumidores principales (runner default, pipeline, agente)
  a sequence.
- Eliminar `build_signals_from_frames` y la rama `checklist` del runner, sabiendo
  la superficie de consumidores de 1.4.
- Mantener la representación canónica `MarketObject[]` (R9).
- **DOCUMENTAR (no migrar en R7)** los motores paralelos `legacy/backtest` y
  `ml/dataset_builder`, con decisión explícita escrita sobre cada uno.

### D. Exclusiones (explicitas — NO son R7)
- NO cambiar ninguna regla ICT (POI, quality_score, narrativa, sweep, BOS,
  CHOCH, MSS, displacement, entry, risk). Solo se unifica el motor que las lee.
- NO migrar `MarketNarrative` / inteligencia narrativa (es trabajo posterior,
  fuera de R7).
- NO tocar `translation.py` / `object_adapter.py` (capa de compatibilidad
  congelada).
- NO migrar `legacy/backtest` ni `ml/dataset_builder` en R7 (se documentan;
  su migración es deuda aparte).
- NO optimizar ni limpiar código ajeno al motor de decisión.
- NO alterar el comportamiento de `simulate_trade` / `calc_structural_sl` /
  `_tp_liquidity` (ya compartidos y correctos).

### E. Principios de migración (vinculantes para Fases 3+)
1. TDD: cada porte de regla va acompañado de un test que pruebe equivalencia
   contra el comportamiento engine documentado en Fase 1.
2. Congelar primero, programar después: este contrato está firmado antes de
   escribir código.
3. Portar, no reimplementar: las reglas de `rules.py`/engine se reutilizan;
   no se reescriben desde cero.
4. Sin cambio de behavior más allá de las divergencias resueltas en Fase 2
   (entry retorno, RR 1:3). Cualquier otro cambio de métricas debe ser
   documentado y justificado antes de código.
5. Una sola fuente: tras R7, `build_signals_from_frames` deja de existir; no
   quedan dos caminos de decisión EN EL ALCANCE DE R7.
6. Compatibilidad preservada: las columnas legacy del DataFrame siguen
   disponibles para los consumidores que las necesiten (simulación, UI).
7. **Preservación anti-lookahead HTF (H8):** la semántica de join cross-TF con
   cierre de barra (TF_FREQ + `_row_at_time(freq)`) es comportamiento canónico;
   al portar el contexto HTF a sequence debe mantenerse idéntica para no introducir
   look-ahead. Exigible en el DoD.

### F. Definition of Done (R7) — FORTALECIDO (H10)
Para declarar "una sola fuente de verdad" NO basta con que sequence y rules se
tociquen. El DoD es evadible si ignora los motores paralelos. Por tanto:

- [ ] `run_sequence` (sobre `MarketObject[]`) es la ÚNICA función de
      evaluación ICT en el alcance de R7; backtest, UI y agente la invocan.
- [ ] **`run_backtest.run` por DEFECTO (sin --engine) invoca `run_sequence`,
      no `build_signals_from_frames` (H12).** La migración no está terminada
      si el usuario corre el backtest por defecto y sigue entrando por engine.
- [ ] `agents/ict_agent.py` delega la evaluación ICT en `sequence` (no
      reimplementa BOS/CHOCH/sweep/FVG/OB) — H1 resuelto.
- [ ] `build_signals_from_frames` y la rama `checklist` del runner ELIMINADOS,
      y todos los consumidores de 1.4 actualizados o reemplazados (sin import
      roto en `__init__.py` ni scripts).
- [ ] Los modos scalping / po3 / killzone / votes de engine existen en sequence
      como `SequenceConfig`, con tests de equivalencia vs Fase 1.
- [ ] **Decisión documentada y explícita sobre `legacy/backtest` y
      `ml/dataset_builder.py` (H2/H3): redirigir o aceptar como deuda fuera de
      R7. No pueden quedar invisibles en el repo ni en este contrato.**
- [ ] `scripts/check_separation.py` (o equivalente) reporta el grafo de motores
      ICT incluyendo `ict_agent`, `legacy/backtest` y `ml`; no se declara
      "done" mientras existaMotor ICT paralelo o consumidor no redirigido
      (H10).
- [ ] La semántica anti-lookahead HTF (H8) se preserva en sequence (test de
      regresión de no-look-ahead).
- [ ] Ninguna métrica de baseline (PF / WR / expectancy) cambia por la
      unificación más allá de lo documentado en Fase 2 (entry retorno vs close,
      RR 1:3 vs 1:2).
- [ ] Todo el camino de decisión corre sobre `MarketObject[]` (sin `.iloc[col]`
      en la lógica de señal dentro del alcance de R7).
- [ ] Roadmap R7 marcado como ✅ Cerrado y grafo regenerado.

══════════════════════════════════════════════
## FASES 3-6 — IMPLEMENTACIÓN / TDD (NO AUTORIZADAS)
══════════════════════════════════════════════
Pendientes de firma posterior. NO se definen aquí para no anticipar código
antes de congelar la arquitectura. Se autorizarán sólo tras aprobar este
contrato Fase 1+2 ampliado.

══════════════════════════════════════════════
## R9 — CERRADO (2026-07-15, referencia)
══════════════════════════════════════════════
R9 cumplió su contrato: representación canónica MarketObject; sequence 100%
migrado; equivalencia 15/15 tests; compatibilidad vía adapter intacta. R9 NO
incluía eliminar engine.py (deuda arquitectónica R7, no de representación).
Por tanto R9 está COMPLETADO y engine.py pasó a R7.
