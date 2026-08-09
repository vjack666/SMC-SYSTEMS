AUDITORÍA FINAL DE COBERTURA DEL PROBLEMA ORIGINAL DEL BACKTEST
=================================================================

Comité Independiente de Auditoría:
- Principal Quant Developer
- Principal Software Architect
- ICT Specialist
- Senior Backtesting Engineer
- Systems Auditor

Fecha: 2026-07-17 (post-ETAPA 4 PASO 1, PASO 2 bloqueado)
Base de evidencia (leída directamente, no asumida):
- Auditoría Forense: docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md
- Informe de Convergencia: docs/auditorias/INFORME_CONVERGENCIA_ARQUITECTONICA_2026-07-17.md
- Auditoría Arquitectónica: docs/auditorias/AUDITORIA_COMITE_TECNICO_2026-07-17.md
- Validación: docs/plan/VALIDACION_DE_HALLAZGOS.md (ETAPA 1)
- Estado bugs: docs/plan/ETAPA_4_BUGS.md
- Decisiones: docs/plan/DECISION_LOG.md
- Métricas: docs/METRICS_CANON.md
- Commits: git log 104964c..HEAD (19 commits), tag baseline-2026-07-17
- Tests: 70 archivos test, conteo; PASO 1 = 8+46 passed (medido este turno)
- Código: ict_backtest/ (35 .py), scripts/_diag_xauusd_hang.py (diagnóstico observacional)

REGLA APLICADA: un commit NO es evidencia de solución; una modificación NO es
evidencia de que funcionó. Cada punto exige respaldo fáctico. Sin respaldo:
se clasifica NO DEMOSTRADO.

=================================================================

PARTE 1 — RECORDATORIO DEL PROBLEMA ORIGINAL

El problema NO es "el stack ICT no tiene edge". El problema es que el backtest
NO es válido para emitir veredicto alguno. Se detectaron (máx. 10 hallazgos
centrales del problema de backtest):

1. FALLA 1 (Forense) — v2/ sin versionar. run_bt_v2_mtf.py importa ict_backtest.v2
   que nunca se commiteó. Desde clon limpio: ModuleNotFoundError. Nadie puede
   reproducir el backtest → veredicto "sin edge" cuelga de código no versionado.
   Evidencia: git log --all -- ict_backtest/v2/ vacío; git ls-files vacío.

2. FALLA 2 (Forense) — edge_diagnosis cap MAX_SIGNALS_PER_VARIANT=3000 corta por
   confianza descendente. Para XAUUSD, 13/21 variantes colapsan al MISMO resultado
   (PF 1.379/WR 60.1%/N=900). La ablación no diferencia variantes → el "edge"
   de XAUUSD es inválido. Evidencia: run.py:64,433-435; run.py:412 agents hardcode.

3. FALLA 3 (Forense) — Sin corrección por comparaciones múltiples. Grilla 168
   celdas, se elige la mejor post-hoc (no_session×XAUUSD PF 1.642). Sin DSR/PBO
   (ml/stats_validator.py existe pero NO se aplica a la grilla). Falsa significancia.

4. FALLA 4 (Forense) — "Edge" es promedio, no por símbolo, y vive en XAUUSD, el
   MISMO símbolo EXCLUIDO del MTF por falta de M15. AUDUSD 0.849 / NZDUSD 0.809
   pierden; el promedio encubre concentración de riesgo en 1 símbolo.

5. FUNNEL killzone (C1) — killzone_en filtra por barra H4, no por sesión. 78% de
   señales raw eliminadas. Bug de mapeo HTF→wall-clock.

6. FUNNEL displacement (C2) — body_atr_multiple=1.5 + wick 0.4 en H4; ~10% pasa.
   90% de sweeps descartados. Bottleneck en cascada.

7. UNIFICACIÓN BOS/CHOCH (C4/F2) — 3 implementaciones divergentes (market_structure
   vs detectors/bos vs detectors/choch). Riesgo de semántica inconsistente
   dataset-vs-decisión. No corrompe el backtest directamente, pero impide auditar
   qué definición se usa.

8. POI anclado (C6/H12) — El filtro definitorio de ICT (POI anclado a narrativa HTF)
   está MISSING (legacy) / partial (mtf). El motor evalúa FVG/OB sin respaldo del
   TF padre. Brecha de la tesis objetivo.

9. ML train/serve (C5/F5) — dataset_builder importa legacy.backtest.engine; producción
   usa canonical. Distribuciones distintas → skew. Afecta el filtro de calidad ML.

10. COSTOS (C13) — costs.py calibra solo XAU/EUR/GBP (3/8). Los 5 restantes usan
    DEFAULT. Números MTF de símbolos "sobrevivientes" (USDCAD 0.510, USDCHF 0.295)
    pueden estar mal por costo mal cobrado.

SÍNTOMA agregado: GATE R6 NO PASA en ningún símbolo (R6.4 PF negativo; v2 mtf
0-4 trades). Pero el repo declara explícitamente (AGENTS.md, METRICS_CANON) que
esto mide una VERSIÓN SIMPLIFICADA de la estrategia. Conclusión original: el
veredicto "sin edge" es prematuro; el backtest está incompleto, no necesariamente
equivocado.

IMPACTO: ningún veredicto (a favor o en contra) es actualmente sostenible por
pruebas válidas.

=================================================================

PARTE 2 — ESTADO ACTUAL (por problema)

Para cada problema, clasificación y justificación con evidencia:

[1] FALLA 1 — v2 sin versionar
    ESTADO: CORREGIDO COMPLETAMENTE
    Justificación: ETAPA 0 commiteó ict_backtest/v2/ (commits c885ac3, 28a0477,
    2738b39, 8a31941, 4555836, 9f1e850, 7319196). Tag baseline-2026-07-17 creado
    (git tag confirma). VALIDACION_DE_HALLAZGOS H3: `git cat-file -e
    baseline-2026-07-17:ict_backtest/v2/orchestrator.py` → OK. Reproducible desde
    clon. Evidencia: commit + tag + comando de verificación. ✅

[2] FALLA 2 — cap rompe ablación
    ESTADO: NO RESUELTO (solo instrumentado)
    Justificación: commit 104964c agregó n_raw/capped al reporte (instrumentación,
    NO cambia semántica). El corte sigue por confianza descendente (run.py:433-435
    sin modificar en esta sesión). ETAPA_4_BUGS PASO 3 PENDIENTE. NO hay evidencia
    de que relajar un filtro cambie el set. Clasificar: NO DEMOSTRADO (fix).

[3] FALLA 3 — sin DSR/PBO
    ESTADO: NO RESUELTO
    Justificación: ml/stats_validator.py:83/101 existen pero NO se importan en
    edge_diagnosis/run.py (confirmado en VALIDACION H16, sin cambio en esta sesión).
    ETAPA_4_BUGS PASO 6 PENDIENTE. NO DEMOSTRADO.

[4] FALLA 4 — edge concentrado en XAUUSD excluido
    ESTADO: PARCIAL (dato resuelto, uso BLOQUEADO)
    Justificación: XAUUSD_M15.parquet EXISTE (3.6 MB, VALIDACION H14) → dato OK.
    PERO incluir XAUUSD en run_bt_v2_mtf.py (PASO 2) se REVIRTIÓ (d9b7b8f) porque
    el motor tarda ~51 min (cuello O(n²) en closed_row_at_time, diagnosticado en
    diag_xauusd.log: n_raw=77, 3052.8s). El "edge" de XAUUSD sigue SIN poder
    validarse en MTF, y la ablación de XAUUSD sigue contaminada por Falla 2.
    Clasificar: NO DEMOSTRADO (validación de edge XAUUSD).

[5] C1 killzone HTF mismatch
    ESTADO: NO RESUELTO (prohibido tocar en Fase 0)
    Justificación: convergence roadmap marca C1 como Fase 0 PROHIBIDA (regla de oro
    ETAPA 4: no tocar Killzone/Sequence/Entry/SL/TP/HTF/Displacement). No hay
    commit de fix. NO DEMOSTRADO.

[6] C2 displacement bottleneck
    ESTADO: NO RESUELTO (calibrable, Fase 2/3)
    Justificación: ETAPA 4 PASO pendiente; convergence lo pone en Fase 2 (calibrar
    en M15). Sin cambio. NO DEMOSTRADO.

[7] C4/F2 unificación BOS/CHOCH
    ESTADO: CORREGIDO COMPLETAMENTE
    Justificación: PASO 1 (commits a5d6814, 72f7951, 9e64b10). detectors/bos.py y
    choch.py ahora delegan al canónico (market_structure). Tests:
    test_bos_choch_regression.py 8 passed + test_detectors.py 46 passed (medido
    este turno). Contrato documentado (CONTRATO_BOS_CHOCH_CANONICO.md). Backtest
    PRE/POST EURUSD: dN=0, dPF=0.000, dWR=0.000 (sin regresión; la divergencia
    1vs2 bar no se manifiesta en M15 real). ✅ Evidencia: commit + tests + métricas.

[8] C6/H12 POI anclado
    ESTADO: NO RESUELTO
    Justificación: coverage.py sigue marcando C05 missing/partial (VALIDACION H12,
    sin cambio). ETAPA_4_BUGS PASO 5 PENDIENTE. NO DEMOSTRADO.

[9] C5/F5 ML train/serve
    ESTADO: NO RESUELTO
    Justificación: dataset_builder.py:14,234 siguen importando legacy (VALIDACION
    H17, sin cambio). ETAPA_4_BUGS PASO 4 PENDIENTE. NO DEMOSTRADO.

[10] C13 costos 3/8
    ESTADO: NO RESUELTO
    Justificación: costs.py sin modificar en esta sesión. ETAPA 4 PASO 7 / Fase 2.
    NO DEMOSTRADO.

ADICIONAL (de la arquitectónica, afecta validez):
- C3 PO3 choch_status mapping: NO RESUELTO en canónica (fix documentado era para
  engine.py legacy; v2 sigue partial). NO DEMOSTRADO.
- C11 look-ahead HTF / C12 sweep M5 hardcoded: YA CORREGIDOS previamente
  (convergencia los marca ✓ FIXED; R4 v2.7+). ✅ (antes de esta sesión)
- C10 edge concentrado: véase [4].
- C14 signals/ legacy, C15 64% código muerto: NO RESUELTOS (Fase 1 diseño).
  NO DEMOSTRADO.
- H20 tests timeout/auto-download, H21 trend_context ciclo, H22 dead code:
  NO RESUELTOS (PASO 7). NO DEMOSTRADO.

=================================================================

PARTE 3 — MATRIZ DE COBERTURA

Problema | Descripción | Estado actual | Evidencia | Commits | Docs | Impacto restante | Confianza | % Cobertura
FALLA 1 | v2 no versionado | CORREGIDO | git tag + cat-file OK | c885ac3..7319196 | VALID H3 | reproducible | Alta | 100%
FALLA 2 | cap rompe ablación | NO RESUELTO | run.py:433 sin cambio | 104964c (instr) | ETAPA_4 PASO3 | ablación inválida | Alta | 0%
FALLA 3 | sin DSR/PBO | NO RESUELTO | stats_validator no importado | — | VALID H16 | falsa significancia | Alta | 0%
FALLA 4 | edge en XAUUSD excl | PARCIAL | dato OK; uso revertido | d9b7b8f, b36e2bb | ETAPA_4 PASO2 | edge no validable | Alta | 50% (dato)
C1 | killzone HTF mismatch | NO RESUELTO | prohibido Fase0 | — | CONVERG | 78% señales muertas | Alta | 0%
C2 | displacement bottleneck | NO RESUELTO | displace en H4 | — | CONVERG F2 | 90% señales muertas | Alta | 0%
C3 | PO3 choch_status | NO RESUELTO | v2 partial | — | VALID H12 | PO3 silenciado | Media | 0%
C4/F2 | BOS/CHOCH 3 impl | CORREGIDO | detectors→canónico | a5d6814,72f7951 | CONTRATO | divergencia eliminada | Alta | 100%
C5/F5 | ML train/serve | NO RESUELTO | dataset_builder legacy | — | VALID H17 | skew ML | Alta | 0%
C6 | D1 cargado no usado | NO RESUELTO | decide diseño | — | CONVERG | 3-capas ausente | Media | 0%
C6/H12 | POI anclado | NO RESUELTO | coverage missing/partial | — | VALID H12 | brecha tesis | Alta | 0%
C8 | cap edge_diagnosis | NO RESUELTO | = FALLA 2 | — | ETAPA_4 PASO3 | = FALLA 2 | Alta | 0%
C9 | DSR/PBO grilla | NO RESUELTO | = FALLA 3 | — | ETAPA_4 PASO6 | = FALLA 3 | Alta | 0%
C10 | edge XAUUSD | PARCIAL | = FALLA 4 | d9b7b8f | ETAPA_4 PASO2 | = FALLA 4 | Alta | 50%
C11 | look-ahead HTF | CORREGIDO (previo) | R4 v2.7+ | previos | AUDIT_LOOKAHEAD | limpio | Alta | 100%
C12 | sweep M5 hardcoded | CORREGIDO (previo) | rules fix | previos | CONVERG ✓ | — | Alta | 100%
C13 | costos 3/8 | NO RESUELTO | costs.py sin cambio | — | VALID C13 | PF mal cobrado | Media | 0%
H13 | Silver Bullet explícito | NO RESUELTO | sin módulo SB | — | VALID H13 | SB no modelado | Alta | 0%
H20 | tests timeout/download | NO RESUELTO | pytest >600s | — | VALID H20 | sin CI verde | Alta | 0%
H21 | trend_context ciclo | NO RESUELTO | import circular | — | VALID H21 | fragilidad | Media | 0%
H22 | dead code/no-op | NO RESUELTO | engine.py duplic | — | VALID H22 | deuda | Alta | 0%

=================================================================

PARTE 4 — COMPARACIÓN CONTRA BASELINE

El baseline es el commit 104964c (pre-ETAPA 0). Las métricas de backtest NO
cambiaron en esta sesión porque:
- PASO 1 (BOS/CHOCH) midió dN=0, dPF=0, dWR=0 → idénticas.
- PASO 2 (XAUUSD) se REVIRTIÓ → 7 símbolos, mismo que baseline.

Por tanto, la comparación baseline-vs-actual es: IDÉNTICA en números de backtest.
El trabajo de esta sesión fue de GOBIERNANZA + UNIFICACIÓN ARQUITECTÓNICA, no de
cambio de métricas. Eso es correcto bajo la regla de oro (sin regresión).

Métricas disponibles (de METRICS_CANON, SIN cambio post-ETAPA 4):

Número de señales (raw sequence, EURUSD M15, 8000 velas):
  Baseline: n_raw no reportado por celda en R6.4. Edge diagnosis: 168 celdas.
  Actual: PASO 1 dN=0 en 168 celdas → sin cambio de señales.
  => SIN CAMBIO demostrable (no hay conteo raw absoluto archivado pre-ETAPA4).

Número de trades (v2 mtf, 7 símbolos, ~6 meses):
  EURUSD 0 | GBPUSD 1 | USDJPY 1 | AUDUSD 4 | NZDUSD 2 | USDCAD 4 | USDCHF 3
  Actual: IDÉNTICO (PASO 2 revertido a 7 símbolos, mismo runner).

Win Rate (v2 mtf): EURUSD 0% | GBPUSD 0% | USDJPY 100% | AUDUSD 0% | NZDUSD 0%
  | USDCAD 25% | USDCHF 33.3%. Actual: IDÉNTICO.

Profit Factor (v2 mtf): todos 0.000 excepto USDCAD 0.510, USDCHF 0.295 (o inf* N=1).
  Actual: IDÉNTICO.

Expectancy / Drawdown / Sharpe / Sortino / Calmar / Recovery Factor / Profit per
Trade / Max Cons Losses / Max Cons Wins: NO reportados por símbolo en v2 mtf
(results/bt_v2/<sym>/mtf_intraday/ tiene artifacts pero METRICS_CANON no los
consolida como serie). El backtest v2 mtf escribió resumen con PF/WR/N/coverage
solo. => NO DEMOSTRADO para esas métricas (no hay archivo de consolidación).

Tiempo de ejecución:
  Baseline (7 sym): ~107 min corrida (12:07→13:54 observado).
  Actual (7 sym): idem (PASO 2 revertido).
  XAUUSD aislado: 3052.8s (~51 min) diagnosticado — CUELLO O(n²) descubierto,
  no presente en baseline (XAUUSD estaba excluido). Nuevo hallazgo, no regresión.

Consumo de memoria:
  Runner Monitor reportó RAM(job) 0.4 GB WS, RAM(sys) 13.3/15.6 GB en la corrida
  de 8 símbolos. Sin baseline de memoria archivado => NO DEMOSTRADO comparación.

Filtros que más eliminan señales (funnel, de la forense/convergencia):
  Killzone 78% killed (C1) | Displacement 90% killed (C2) | SL estructural
  (algún %) | RR filter (algún %). Estos NO cambiaron en esta sesión (prohibido
  Fase 0). => SIN CAMBIO. El funnel sigue matando ~97-99% de raw.

Embudo completo (reconstruido en PARTE 5).

CONCLUSIÓN PARTE 4: las métricas de backtest están IDÉNTICAS al baseline porque
el trabajo fue de gobernanza/unificación, no de ajuste de motor. NO hay mejora
de edge demostrable; TAMPOCO hay regresión. El problema original (backtest no
válido para veredicto) persiste en sus componentes de validez (ablación,
significancia, cobertura ICT), que NO se tocaron.

=================================================================

PARTE 5 — AUDITORÍA DEL FUNNEL

Etapas (candidatos → % eliminado → comparación original → estado):

1. Datos
   Candidatos: 109,270 velas M15 XAUUSD / ~similar otros (carga OK).
   % eliminado: 0.
   Comparación: igual al original (datos cargados).
   Mejora: — | Retroceso: — | Sin cambios.

2. Market Structure
   Candidatos: swing highs/lows detectados por detect_market_structure.
   % eliminado: 0 (estructura se marca, no elimina).
   Comparación: PASO 1 unificó BOS/CHOCH a canónico (sin cambio de conteo en M15
   real, dN=0). Mejora: elimina divergencia latente de definición. Retroceso: ninguno.

3. Sweep
   Candidatos: ~66% prevalencia (METRICS_CANON §6).
   % eliminado: ~34% (no sweep).
   Comparación: igual. Sin cambios.

4. Displacement (C2)
   Candidatos: sweeps que tienen displacement en ventana 6 velas.
   % eliminado: ~90% (solo ~10% pasa, Forense/Convergencia).
   Comparación: IGUAL al original. NO corregido (prohibido Fase 0 / pendiente Fase 2).
   Mejora: — | Retroceso: — | Sin cambios.

5. BOS
   Candidatos: post-displacement, rompe estructura.
   % eliminado: parcial (depende de geometría canónica, confirm_bars=2).
   Comparación: PASO 1 lo unificó; dN=0 => conteo igual. Sin cambios de volumen.

6. Entry (retorno al cuadro / mitigation)
   Candidatos: precio toca zona FVG/OB.
   % eliminado: parcial.
   Comparación: igual (Entry next_open es Fase 0 prohibida, intacta). Sin cambios.

7. Killzone (C1)
   Candidatos: señales que caen en ventana wall-clock de la barra.
   % eliminado: 78% (Forense). BUG: filtra por barra H4, no por sesión real.
   Comparación: IGUAL al original. NO corregido. Sin cambios (el bug persiste).

8. Risk (SL estructural)
   Candidatos: sweep_stoploss válido y risk > 0 y risk <= STRUCT_SL_MAX_ATR*atr.
   % eliminado: algunas (ver canonical.py:127-131).
   Comparación: igual (SL estructural Fase 0 prohibida, intacta). Sin cambios.

9. RR (1:3 canónico)
   Candidatos: TP >= entry+3*risk.
   % eliminado: algunas (liquidez o 3R mínimo).
   Comparación: igual (RR Fase 0 prohibida). Sin cambios.

10. Trade
    Candidatos finales: 0-4 trades por símbolo en 6 meses (v2 mtf).
    Comparación: IGUAL al baseline. El funnel sigue produciendo 0-4 trades =>
    el backtest sigue sin poder concluir edge (N insuficiente).

Veredicto funnel: de las etapas que MATAN señales (displacement 90%, killzone
78%, RR, risk), NINGUNA se corrigió en esta sesión. El funnel está IGUAL que el
baseline. El PASO 1 (BOS/CHOCH) fue una unificación de definición, no de volumen
(dN=0 lo confirma). Por tanto el bajo N de trades NO mejoró.

=================================================================

PARTE 6 — COBERTURA DE CADA HALLAZGO

Para cada hallazgo: ¿solucionado? ¿cómo? ¿evidencia? ¿test? ¿commit? ¿doc?
¿backtest validación? Si falta algo => NO DEMOSTRADO.

FALLA 1 (v2 versionado):
  Solucionado: SÍ. Cómo: commit de ict_backtest/v2 + tag. Evidencia: git tag,
  cat-file OK. Test: implícito (importa en clon). Commit: SÍ (c885ac3+). Doc: SÍ
  (VALID H3, ETAPA_0). Backtest validación: el backtest ya corría; ahora reproducible.
  => DEMOSTRADO (reproducibilidad).

FALLA 2 (cap ablación):
  Solucionado: NO. Cómo: —. Evidencia: run.py:433 sin cambio. Test: NO. Commit:
  solo instrumentación (104964c). Doc: ETAPA_4 PASO3. Backtest validación: NO.
  => NO DEMOSTRADO.

FALLA 3 (DSR/PBO):
  Solucionado: NO. Evidencia: no importado. Test: NO. Commit: NO. Doc: ETAPA_4
  PASO6. Backtest: NO. => NO DEMOSTRADO.

FALLA 4 (edge XAUUSD):
  Solucionado: PARCIAL (dato). Uso: NO (revertido por O(n²)). Evidencia: parquet
  existe; diag n_raw=77/3052s. Test: NO. Commit: d9b7b8f (revert), b36e2bb (causa).
  Doc: SÍ. Backtest: XAUUSD no corre en MTF (51min, impracticable).
  => NO DEMOSTRADO (validación de edge).

C1 killzone: NO solucionado. Sin test/commit/backtest de fix. => NO DEMOSTRADO.
C2 displacement: NO solucionado. => NO DEMOSTRADO.
C3 PO3 choch: NO solucionado en canónica. => NO DEMOSTRADO.
C4 BOS/CHOCH: Solucionado SÍ. Evidencia: delegates + dN=0. Test: 8+46 passed.
  Commit: a5d6814,72f7951. Doc: CONTRATO. Backtest: dN=dPF=dWR=0 (sin regresión).
  => DEMOSTRADO.
C5 ML skew: NO solucionado. => NO DEMOSTRADO.
C6 D1: NO solucionado (decisión). => NO DEMOSTRADO.
C6/H12 POI: NO solucionado. => NO DEMOSTRADO.
C11 look-ahead: Solucionado (previo). Test: test_row_at_time. Commit: previos.
  => DEMOSTRADO (previo a esta sesión).
C12 sweep M5: Solucionado (previo). => DEMOSTRADO (previo).
C13 costos: NO solucionado. => NO DEMOSTRADO.
H13 SB: NO solucionado. => NO DEMOSTRADO.
H20 tests: NO solucionado. => NO DEMOSTRADO.
H21 trend_context: NO solucionado. => NO DEMOSTRADO.
H22 dead code: NO solucionado. => NO DEMOSTRADO.

=================================================================

PARTE 7 — COBERTURA GLOBAL

Porcentaje del problema original resuelto, por componente (objetivo = validez
del veredicto de backtest):

Reproducibilidad (FALLA 1 / C7 / H3)....... 100%  [resuelto con evidencia]
Unificación BOS/CHOCH (C4 / F2)............. 100%  [resuelto con tests+ métricas]
Look-ahead HTF (C11)........................ 100%  [previo, resuelto]
Sweep M5 hardcoded (C12).................... 100%  [previo, resuelto]
XAUUSD M15 dato (H14).......................  50%  [dato SÍ, uso NO]
Edge XAUUSD uso (FALLA 4 / C10).............   0%  [bloqueado O(n²)]
Ablación cap (FALLA 2 / C8 / H15)...........   0%  [solo instrumentado]
DSR/PBO (FALLA 3 / C9 / H16)................   0%  [no aplicado]
Killzone (C1)...............................   0%  [prohibido Fase0]
Displacement (C2 / F4)......................   0%  [pendiente Fase2]
PO3 choch (C3)..............................   0%  [no en canónica]
POI anclado (C6 / H12)......................   0%  [missing/partial]
ML train/serve (C5 / F5 / H17)..............   0%  [legacy]
D1 3-capas (C6 / F1)........................   0%  [decisión]
Costos (C13)................................   0%  [3/8]
Silver Bullet (H13).........................   0%  [sin módulo]
Tests CI (H20)..............................   0%  [timeout]
trend_context (H21).........................   0%  [ciclo]
Dead code (H22).............................   0%  [no-op]

Ponderación por impacto en el VERDICTO del backtest:
- Reproducibilidad: prerequisito (peso 15%). Resuelto → +15.
- Unificación BOS/CHOCH: deuda arquitectónica, NO cambia veredicto directo
  (peso 5%). Resuelto → +5.
- Look-ahead/sweep: ya resueltos antes (peso 10%). Resuelto → +10.
- Ablación/DSR/PBO/edge-XAUUSD: nucleares del veredicto (peso 40%). 0% → +0.
- Funnel killzone/displacement/PO3/POI: afectan N y validez (peso 20%). 0% → +0.
- ML skew/costos/SB/CI: soporte (peso 10%). 0% → +0.

PORCENTAJE GLOBAL ESTIMADO: ~30% de los COMPONENTES tocados, pero solo ~30% del
IMPACTO en el veredicto (reproducibilidad + unificación + look-ahead previo =
30% del peso; el 70% restante — ablación, significancia, cobertura ICT, funnel —
sigue sin resolverse).

Cifra conservadora del comité: EL PROBLEMA ORIGINAL DEL BACKTEST ESTÁ
~30% RESUELTO en impacto. El 70% restante (lo que invalida el veredicto de edge)
no se ha abordado.

=================================================================

PARTE 8 — TRABAJO PENDIENTE (por impacto, no facilidad)

1. [CRÍTICO] Ablación edge_diagnosis: rediseñar corte por ventana/seed, no por
   confianza (FALLA 2). Sin esto, ningún "edge" es creíble.
2. [CRÍTICO] DSR/PBO en grilla 168 (FALLA 3). Sin esto, falsa significancia.
3. [CRÍTICO] Killzone HTF mismatch (C1): 78% de señales muertas por bug de mapeo.
   Esto por sí solo hunde N.
4. [CRÍTICO] Displacement bottleneck (C2): 90% kill. Funnel en cascada.
5. [ALTO] POI anclado (H12): brecha de tesis ICT; el motor no representa la
   estrategia objetivo.
6. [ALTO] XAUUSD en MTF: resolver cuello O(n²) en closed_row_at_time (corregir
   performance, no ICT) y reactivar CR-6. Sin esto, el único símbolo con edge
   candidato no se valida.
7. [ALTO] ML train/serve skew (C5): dataset_builder → canónico.
8. [ALTO] Costos 3/8 (C13): calibrar 5 símbolos.
9. [MEDIO] PO3 choch_status en canónica (C3).
10. [MEDIO] D1 3-capas (C6): decisión de arquitectura.
11. [MEDIO] Silver Bullet explícito (H13).
12. [MEDIO] Tests CI (H20): pytest -m "not slow", sin auto-download.
13. [BAJO] trend_context ciclo (H21), dead code (H22).

=================================================================

PARTE 9 — RIESGOS

- Regresiones: BAJO riesgo demostrado. PASO 1 midió dN=dPF=dWR=0 (sin regresión).
  El repositorio está gobernado (tag + etapas + decision log).
- Código duplicado: PERSISTE. detectors/bos|choch ahora delegan (PASO 1), pero
  market_structure vs legacy.backtest.engine (sequence) y la capa v2 vs canonical
  siguen como 2 caminos de señal. ML entrena en legacy (C5). Riesgo ALTO de
  divergencia futura si no se unifica en ETAPA 6.
- Lógica inconsistente: BOS/CHOCH unificados (bien). Pero POI/liquidez siguen sin
  cablear (C6/H12) → el motor canónico y la narrativa ICT son inconsistentes.
- Look-ahead: CONTROLADO en canónica (C11 previo). Riesgo bajo (test de regresión
  de boundary existe).
- Data leakage: allowlist ML laxa persiste (H18, sin cambio). Riesgo ALTO latente.
- Overfitting / sobreoptimización: SIN DSR/PBO (FALLA 3) → el grid 168 elige
  post-hoc. Riesgo ALTO de sobreoptimización no detectada.
- Timeframe mismatch: killzone filtra por barra H4 no sesión (C1) → mismatch
  HTF↔wall-clock. Riesgo ALTO (78% señales afectadas).
- Filtros incompatibles: displacement mató Silver Bullet en M5 (R4 v2.7) →
  filtros structuralmente incompatibles con SB. Riesgo conocido, documentado.
- Arquitectura incompleta: POI/3-capas/SB ausentes (C6/H12/H13). Motor representa
  versión SIMPLIFICADA de ICT, no la tesis objetivo. Riesgo ALTO de "medir lo
  incorrecto".

=================================================================

PARTE 10 — VEREDICTO FINAL

¿El sistema representa correctamente la estrategia ICT / Silver Bullet?

Clasificación: PARCIALMENTE.

Justificación:
- El motor canónico (structure + sequence event-driven + SL estructural + RR 1:3
  + HTF closed-only + fill next-open) es metodológicamente honesto y SIN look-ahead
  (C11 resuelto). BOS/CHOCH ahora unificados y coherentes (PASO 1).
- PERO la estrategia OBJETIVO (tesis 18: 3 capas D1→H4→H1→M15; POI anclado a
  narrativa HTF; Silver Bullet NY AM + retorno a POI; dealing range/premium-discount)
  NO está cableada. El coverage report dice C05 POI = missing/partial; D1 cargado
  pero no usado; Silver Bullet sin módulo.
- El funnel mata 78-90% por bugs de mapeo (killzone/displacement) que distorsionan
  qué señales llegan.
- Por tanto: representa una VERSIÓN SIMPLIFICADA y PARCIAL de ICT. No representa
  Silver Bullet. El repo lo admite explícitamente (AGENTS.md caveat, METRICS_CANON).

No es "NO" (hay una base ICT real y validada). No es "MAYORMENTE" (faltan los
filtros definitorios y el funnel tiene bugs). Es PARCIALMENTE.

=================================================================

PARTE 11 — SCORE TÉCNICO (0-100)

Arquitectura................. 58  (v2 limpia; BOS/CHOCH unificados; pero 2 caminos
                                 de señal canónica/legacy, sin capa de datos única)
Código....................... 60  (nombres/docstrings buenos; dead code, god-modules)
Backtesting.................. 55  (look-ahead limpio, fill/costos serios; cap inválido,
                                 costos parciales, ablación rota)
Consistencia ICT............. 55  (canónico sólido; POI/liquidez/D1 no cableados)
Consistencia Silver Bullet... 20  (sin módulo SB; displacement lo anula en M5)
Calidad de datos............. 65  (XAUUSD M15 ahora presente; window ~6m corta; R5 pend.)
Mantenibilidad............... 55  (unificación ayuda; duplicación de motores persiste)
Escalabilidad................ 40  (cuello O(n²) en closed_row_at_time descubierto:
                                 XAUUSD 51min; loops .iloc; sin caché de contexto)
Documentación................ 82  (docs/, METRICS_CANON, caveats, etapas, decision log)
Testing...................... 50  (1158 asserts, tests de comportamiento; suite >600s,
                                 auto-download MT5; PASO1 8+46 passed)
Confiabilidad................ 45  (reproducible ahora; pero veredicto no sostenible por
                                 ablación/DSR/funnel/cobertura)
Calidad global del proyecto.. 53  (prototipo serio y honesto; ~30% del problema de
                                 backtest resuelto; a varios refactors de producción)

=================================================================

ENTREGABLE — RESPUESTA A LAS 5 PREGUNTAS

1. ¿Qué problemas existían originalmente?
   Backtest no válido para veredicto: no reproducible (F1), ablación rota (F2),
   sin DSR/PBO (F3), edge concentrado en XAUUSD excluido (F4), funnel killzone/
   displacement mata 78-90% (C1/C2), BOS/CHOCH duplicados (C4), POI/D1/SB ausentes
   (C6/H12/H13), ML skew (C5), costos 3/8 (C13).

2. ¿Cuáles fueron realmente resueltos?
   CON EVIDENCIA: F1 (v2 versionado + tag), C4 (BOS/CHOCH unificados, tests+ métricas),
   C11/C12 (look-ahead/sweep, previos). XAUUSD M15 dato (H14) presente.
   El resto (F2,F3,F4,C1,C2,C3,C5,C6,H12,H13,C13,H20,H21,H22) NO resuelto.

3. ¿Cuáles siguen pendientes?
   Ver PARTE 8 (orden por impacto). El 70% del impacto en el veredicto sigue abierto.

4. ¿Qué porcentaje del problema original ha sido cubierto?
   ~30% en impacto (reproducibilidad + unificación + look-ahead previo resueltos;
   ablación, significancia, cobertura ICT y funnel sin tocar).

5. ¿Qué falta para considerar el motor listo para producción?
   (a) Rediseñar ablación (ventana/seed) + aplicar DSR/PBO → veredicto creíble.
   (b) Corregir killzone + displacement → N suficiente para medir.
   (c) Cablear POI + D1 3-capas + Silver Bullet → representar la estrategia objetivo.
   (d) Resolver O(n²) y reactivar XAUUSD → validar el símbolo con edge candidato.
   (e) Unificar ML a canónico + allowlist estricta → sin skew/leakage.
   (f) Calibrar costos 5 símbolos + CI verde (pytest -m not slow).
   Hasta (a)-(f), el motor es un PROTOTIPO HONESTO pero NO LISTO para producción.

=================================================================
FIN DEL INFORME — Comité Independiente de Auditoría (2026-07-17)
