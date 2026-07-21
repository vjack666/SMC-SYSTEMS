# DECISION_LOG — Memoria técnica de SMC-SYSTEMS

================================================================================

## DEC-009 — Nueva estrategia de proyecto: roadmap orientado a la tesis, suspensión de backtests de rendimiento (2026-07-17)

- Problema: las 3 auditorías (cobertura backtest ~30%, fidelidad tesis ~65% PARCIAL,
  cruzada del roadmap) + R4 (ICT mecánico SIN edge — REJECT_NO_EDGE) mostraron que
  el roadmap vigente ya no refleja el conocimiento adquirido. Faltan OTE, M5/M1,
  POI con tiers/stacking, Silver Bullet completo, Trade Management; y el roadmap viejo
  medía PASO 5 por PF (riesgo de trampa inversa: concluir "tesis falla" cuando falta
  completar capas operativas).
- Evidencia: AUDITORIA_FINAL_COBERTURA_BACKTEST_2026-07-17.md, AUDITORIA_FIDELIDAD_
  TESIS_ICT_2026-07-17.md, AUDITORIA_CRUZADA_ROADMAP_2026-07-17.md; CRONOGRAMA_Y_
  ROADMAP.md línea 7 (R4 NO_EDGE).
- Alternativas consideradas: (a) seguir ETAPA 4 heredada (rechazado: mide por PF,
  omite capas operativas); (b) parchear el roadmap (rechazado: conocimiento ya no
  cabe); (c) replantear desde cero orientado a tesis (elegido, con libertad explícita).
- Decisión tomada: ROADMAP_TESIS_DRIVEN_2026-07-17.md. Suspender backtests de
  rendimiento hasta cobertura mínima obligatoria de tesis. Tres dimensiones separadas
  (fidelidad / calidad / rendimiento). OTE, M5/M1, Trade Management suben de
  opcionales a OBLIGATORIOS. Orden por dependencia de tesis (B geometría fina → C
  POI+SB → D OTE → E trade mgmt → F deuda software → G gate fidelidad → backtest único).
  Gate de aceptación = checklist de fidelidad (no PF). Backtest integral SOLO al final.
- Justificación: el backtest ya cumplió su función (revelar deudas); medir PF sobre
  tesis incompleta es ruido. Priorizar coherencia con la tesis sobre mantener el
  plan anterior.
- Impacto esperado: cierre de deudas conceptuales antes de any performance claim;
  sin trampa de interpretar PF como veredicto de tesis.
- Cómo verificarla: ROADMAP_TESIS_DRIVEN_2026-07-17.md existe y es el plan de avance;
  checklist §5 cableado como tests/test_fidelity_thesis.py (SOLO tras definir→
  validar→automatizar); sin backtests de PF hasta Fase G.

## DEC-009b — Auditoría del plan + Fase 0 formalización (2026-07-17, post-revisión)

- Problema: antes del commit, Ruben pidió una última auditoría del PROPIO roadmap
  (no de la implementación) asumiendo rol de auditor externo. Se encontraron huecos
  reales del nuevo roadmap vs la tesis: faltaban Turtle Soup (tesis 20 §4, 1 de 3
  setups PO3), PD Arrays completos (Breaker/Rejection/Mitigation/Propulsion, 21_POI
  §2), liquidez internal vs external (tesis 15/16), ambigüedad RR (SB 1:2 libro 07
  #5 vs 1:3 global tesis 18), y una Fase 0 de formalización de la tesis.
- Evidencia: libro 07_SILVER_BULLET.md contrato #5 (RR≥1:2); 20_TESIS_ICT.md §4
  (3 setups PO3: Turtle Soup/PO3/SB); 21_POI.md §2 (tipos de PD Array); re-lectura
  de 07/20/21/15/18.
- Alternativas: (a) commitear el roadmap sin la auditoría (rechazado: Ruben exigió
  validación previa); (b) auditar y dejar huecos (rechazado: "incorpóralo antes del
  commit"); (c) auditar, incorporar y luego commitear (elegido).
- Decisión tomada: incorporar los hallazgos al ROADMAP_TESIS_DRIVEN_2026-07-17.md:
  Fase 0 (Formalización → SPEC_TESIS_FORMAL.md como contrato), B1 PD Arrays
  completos, B3 liquidez internal/external, C3 Turtle Soup, RR por setup (SB 1:2),
  checklist §5 con 14 ítems y separado en definir→validar→automatizar. Veredicto de
  la auditoría del plan: ✅ listo para roadmap maestro tras la revisión.
- Justificación: cerrar deuda conceptual ANTES del commit evita reabrir arquitectura
  en 2 semanas. Fase 0 previene que cada fase "reinterprete" los libros ICT.
- Impacto: roadmap maestro completo en lo obligatorio de la tesis; opcionales
  (SMT/MMXM/noticias/walk-forward) fuera del corte, correctamente.
- Cómo verificarla: ROADMAP_TESIS_DRIVEN_2026-07-17.md §9 con veredicto ✅; Fase 0
  como puerta dura antes de B.

## DEC-009c — Salvaguarda metodológica: matriz de trazabilidad + clasificación (2026-07-17)

- Problema: Ruben exigió verificar, antes del commit, que el roadmap NO sea una
  reinterpretación de ICT sino una representación fiel, y que ningún elemento
  quedara sin clasificar (OBLIGATORIO con referencia / OPCIONAL con justificación
  / DECISIÓN DE INGENIERÍA cuando no proviene de ICT). También cuestionó que
  "noticias" estuviera como opcional: si la tesis dice que un evento invalida el
  setup, es regla de invalidez, no extra.
- Evidencia: re-lectura de 20_TESIS_ICT.md (§1-§12), 08_POWER_OF_THREE.md (PO3 vs
  Turtle Soup por alineación), 07_SILVER_BULLET.md (#5 RR≥1:2), 21_POI.md (tiers),
  05/15/16 (liquidez internal/external). MATRIZ §9 del roadmap.
- Alternativas: (a) dejar noticias como opcional (rechazado: Ruben lo marcó como
  deuda funcional); (b) clasificar cada elemento (elegido).
- Decisión tomada: MATRIZ DE TRAZABILIDAD §9 con 33 filas, cada una con fuente
  exacta y clasificación. Conteo: 24 OBLIGATORIOS, 4 DECISIÓN DE INGENIERÍA de
  soporte, 3 OPCIONALES (SMT/MMXM/walk-forward), 1 DEUDA FUNCIONAL (noticias,
  tesis 21 §5). CERO sin clasificar. Noticias reclasificada de opcional a DEUDA
  FUNCIONAL (regla de invalidez real, no implementable hoy → documentada en hook
  de Fase C, no olvidada). La afirmación "no quedan obligatorios fuera" se sostiene
  y está respaldada por la matriz.
- Justificación: la matriz impide que una decisión de ingeniería (cap, ML, XAUUSD
  fix, DSR/PBO, RR-por-setup, Fase 0) se disfraze de regla de tesis. En 6 meses
  cualquiera ve si un concepto está implementado o documentado como deuda.
- Impacto: roadmap maestro con trazabilidad total; metodología sólida para el commit.
- Cómo verificarla: ROADMAP_TESIS_DRIVEN_2026-07-17.md §9 (matriz) + salvaguarda al
  final del §10. DEC-009c registra la decisión.

## DEC-009d — Reglas de gobernanza del roadmap maestro (2026-07-17)

- Problema: antes del commit único, Ruben exigió 4 criterios finales verificables:
  (1) Fase 0/SPEC es contrato fuente, nada sin SPEC; (2) matriz sincronizada con
  SPEC en el mismo cambio; (3) todo cambio futuro etiqueta si modifica tesis/
  implementación/ingeniería sin mezclar; (4) backtest bloqueado hasta Fase G, sin
  excepciones salvo validar infraestructura (nunca rendimiento).
- Evidencia: review del ROADMAP_TESIS_DRIVEN_2026-07-17.md pre-commit. (1) y (4)
  implícitos; (2) y (3) faltaban → se añadió sección 11 REGLAS DE GOBERNANZA
  (R1-R4) como duras y vinculantes.
- Alternativas: (a) dejar implícito (rechazado: Ruben pidió explícito); (b) fijar
  R1-R4 como sección 11 (elegido).
- Decisión tomada: sección 11 con R1 (SPEC precede código), R2 (matriz↔SPEC
  sincronizadas en mismo cambio), R3 (etiqueta de capa en todo commit, sin mezclar
  sin documentar), R4 (backtest rendimiento bloqueado hasta Fase G; excepción solo
  infraestructura, nunca rendimiento). Los 4 criterios quedan reflejados.
- Justificación: evita deriva futura (implementar sin SPEC, mezclar capas, medir
  PF prematuramente). Cumple la aprobación condicional del commit.
- Impacto: roadmap maestro con gobernanza dura; commit único procede.
- Cómo verificarla: ROADMAP_TESIS_DRIVEN_2026-07-17.md §11 (R1-R4).

## DEC-009e — Nomenclatura documental SPEC → ADS → MDS → CÓDIGO (2026-07-17)

- Problema: el commit maestro usaba "SPEC" como contrato fuente (Fase 0) pero no
  fijaba la cadena documental completa ni sus alias respecto a la convención SDD/SAD
  YA VIGENTE en el repo (SDD_ICT_BACKTEST.md, SAD.md, docs/specs/*.md, ADR-021,
  DOCUMENTATION_INDEX). Ruben propuso SPEC→ADS→MDS→CÓDIGO (qué/cómo/con-qué).
- Evidencia: search de "SDD" arrojó 40 matches en docs/ (SDD_ICT_BACKTEST, SAD.md,
  9 SDD en docs/specs/, ADR-021, DOCUMENTATION_INDEX, VISION/PRD/SRS/SAD/SDD/TEST).
  La convención SDD/SAD es estándar del proyecto, no solo etiqueta suelta.
- Alternativas: (a) renombrar SDD→MDS masivamente (rechazado: rompería convención
  vigente y ~40 refs); (b) adoptar SPEC como capa fuente y tratar SAD=ADS, SDD=MDS
  como alias, sin renombrar (elegido).
- Decisión tomada: cadena SPEC (docs/ict/SPEC_TESIS_FORMAL.md, QUÉ) → ADS
  (=SAD.md, CÓMO) → MDS (=docs/specs/*.md SDD, CON QUÉ) → CÓDIGO. Actualizados:
  ROADMAP_TESIS_DRIVEN_2026-07-17.md §4 Fase 0 (muestra la cadena + alias) y
  DOCUMENTATION_INDEX.md (nota de capa fuente SPEC). SDD y MDS son lo mismo; no se
  renombra nada existente.
- Justificación: completa la cadena documental del repo (que ya tenía VISION→PRD→
  SRS→SAD→SDD→TEST) añadiendo SPEC arriba como fuente de la estrategia, sin romper
  lo existente. Separa QUÉ/CÓMO/CON QUÉ explícitamente.
- Impacto: nomenclatura coherente y escalable; Fase 0 producirá SPEC_TESIS_FORMAL.md
  como contrato, luego ADS/MDS existentes se amplían por módulo.
- Cómo verificarla: ROADMAP_TESIS_DRIVEN §4 Fase 0 (cadena SPEC→ADS→MDS→CÓDIGO) +
  DOCUMENTATION_INDEX.md (nota capa SPEC). DEC-009e registra la decisión.

## DEC-009g — Fase B1: PD Arrays completos + tiers/stacking (metadatos) (2026-07-18)

- Problema: la SPEC §4/§5 exige tipos finos de PD Array (BREAKER/REJECTION/
  MITIGATION/PROPULSION) y jerarquía T1/T2/T3 + stacking, pero el motor solo
  detectaba FVG/OB genéricos. La POI anclada (§16) y el stacking (§5) no tenían
  información para operar.
- Decisión: añadir metadatos `pd_type`/`pd_tier` en detectores/fvg.py, ob.py,
  data_feed.py (cruce BPR/BREAKER/MITIGATION) y propagarlos vía translation.py
  al MarketObject; sequence.py los congela en el state de la zona. NO se cambia
  la lógica de decisión de run_sequence (fuente única R7 intacta).
- Por qué: geometría fina de la tesis sin riesgo a la fuente única; desbloquea
  POI/stacking (Fase C) y exec M5/M1 (Fase B2).
- Dónde: detectors/fvg.py, detectors/ob.py, ict_backtest/data_feed.py,
  ict_backtest/translation.py, ict_backtest/sequence.py,
  tests/test_fase_b1_pd_arrays.py, tests/_smoke_b1_stash.py.
- Verificación empírica (Ruben rule): tests B1 5 passed; smoke EURUSD M15 real
  B1=2 == baseline=2 señales (metadatos no alteran decisión); regresión 53 passed.
  test_detectors_now_requires_2_bars ya falla en baseline (no es regresión B1).

## DEC-009f — Fase 0: SPEC_TESIS_FORMAL.md (borrador de contrato fuente)

- Problema: la Fase 0 del roadmap maestro exigía formalizar la tesis en SPEC antes
  de código (R1). El commit DEC-009e fijó la nomenclatura pero NO escribía la SPEC.
- Evidencia: ROADMAP_TESIS_DRIVEN §4 Fase 0 + §9 matriz (24 obligatorios). SPEC
  redactada en docs/ict/SPEC_TESIS_FORMAL.md v1.0 DRAFT (26 secciones, ~22KB).
- Alternativas: (a) dejar SPEC como pendiente (rechazado: Fase 0 es puerta dura,
  debe existir el borrador); (b) redactar SPEC cubriendo los 24 componentes de la
  matriz con formato ENT/SAL/PRE/POST/DEP/CRIT/CASOS-LÍMITE/AMBIG (elegido).
- Decisión tomada: SPEC_TESIS_FORMAL.md con los 24 componentes obligatorios (más
  setups como composición §23, noticias como deuda funcional §24, ambigüedades
  resueltas y etiquetadas como ingeniería §25, contrato R2 §26). Cada componente
  cita referencia exacta (tesis 20 / libros 07/08/21). Estado: DRAFT pendiente de
  firma del comité; al firmarse pasa a CONTRATO FUENTE (R1).
- Justificación: cumple R1 (SPEC precede código) y R2 (§26 declara sincronía
  SPEC↔matriz §9). Las decisiones de ingeniería están etiquetadas (R3). No se
  ejecutó backtest (R4). El §23 evita reinterpretación: PO3/Turtle Soup/SB son un
  motor de liquidez en 3 modos, no 3 estrategias.
- Impacto: Fase 0 tiene su borrador; las Fases B-E pueden arrancar contra este
  contrato. Falta firma del comité para ser CONTRATO FUENTE formal.
- Cómo verificarla: docs/ict/SPEC_TESIS_FORMAL.md existe y cubre los 24 de la matriz
  §9. DEC-009f registra la decisión.

================================================================================

Base de conocimiento viva del proyecto (ETAPA 11). Cada decisión importante se registra con
el formato definido en PLAN_IMPLEMENTACION_ETAPAS.md. Orden cronológico inverso (más reciente
arriba). Cuando dentro de meses te preguntes "¿por qué hicimos X?", está aquí con su evidencia.

Formato por entrada:
- Problema · Evidencia · Alternativas consideradas · Decisión tomada · Justificación ·
  Impacto esperado · Cómo verificarla

================================================================================

## DEC-005 — ETAPA 2 cerrada: árbol de dependencias / causa raíz (2026-07-17)

- Problema: tras validar, hace falta saber QUÉ causa cada hallazgo para ordenar la
  implementación por dependencia (no por gravedad).
- Evidencia: `signals/pipeline.py:12` importa `detectors` (Stack A, usado en edge_diagnosis);
  `run_backtest.py:103` usa canónico (Stack B). Bifurcación real de dos stacks confirmada.
  `run_bt_v2_mtf.py:16` excluye XAUUSD pese a existir el parquet (H14 resuelto).
- Alternativas consideradas: listar por prioridad (rechazado: oculta dependencias); árbol por
  causa raíz (elegido).
- Decisión tomada: 6 causas raíz (CR-1..CR-6) trazadas en DEPENDENCY_TREE.md. CR-1 = ausencia de
  fuente única de verdad para geometría (raíz de H4/H5/H17). Hallazgo nuevo: el filtro XAUUSD en
  el runner MTF es obsoleto, no falta de datos.
- Justificación: el orden de ETAPA 4 debe seguir el árbol; corregir H4 antes que H17 porque H17
  depende de saber cuál es la verdad.
- Impacto esperado: ETAPA 4 corrige de raíz, no síntomas; sin ciclos de retrabajo.
- Cómo verificarla: DEPENDENCY_TREE.md existe con árbol por componente + CR-1..CR-6.

## DEC-008 — ETAPA 4 PASO 2 (CR-6) BLOQUEADO: cuello de botella O(n^2) con XAUUSD (2026-07-17, causa raiz aislada)

- Hecho original: activar XAUUSD en run_bt_v2_mtf.py -> run_mtf_intraday parecia
  colgarse (proceso vivo ~2h, solo live_structure.csv 53b escrito).
- DIAGNOSTICO FORENSE (scripts/_diag_xauusd_hang.py v3, monkeypatch observacional,
  sin modificar src): NO es bucle infinito. TERMINA en 3052.8s (~51 min) con
  n_raw=77 senales. Es lentitud extrema (~1000x EURUSD), no parada.
- CAUSA RAIZ EXACTA: `ict_backtest/_util.py::closed_row_at_time` (lineas 113-122)
  reconvierte y compara el array HTF COMPLETO por CADA llamada (O(n_HTF)). Se invoca
  una vez por vela LTF via est_htf_fn en run_sequence (sequence.py:342).
  Complejidad O(n_LTF * n_HTF) = 109270 M15 * 10066 H4 ~= 1.1e9 ops => ~51 min.
  EURUSD tiene menos velas M15 => segundos. Por eso solo oro lo dispara.
- Regla de oro aplicada: cambio que rompe -> REVERTIR (commit d9b7b8f). Vuelve a 7.
- FIX PROPUESTO (performance, deterministicamente identico en senales => cumple
  regla de oro): cachear conversion HTF fuera del loop / merge_asof / cache por cutoff.
- CR-6 QUEDA PENDIENTE hasta OK de Ruben para aplicar el fix de perf y reactivar.
- No es fallo de la unificacion BOS/CHOCH (PASO 1): motor ya usaba market_structure.

================================================================================

## DEC-007 — ETAPA 4 PASO 1 cerrado: BOS/CHOCH unificados (2026-07-17)

- Problema: dos implementaciones divergentes de BOS/CHOCH (detectors vs market_structure).
- Decisión: detectors.bos/choch delegan al canónico (fuente única de verdad).
- Evidencia: 8+46 tests passed; backtest PRE vs POST idéntico (dN=dPF=dWR=0) → sin regresión.
  Dispatch confirmado REAL en signals/pipeline.py (usa bos_direction/choch_signal).
- Regla respetada: Fase 0 prohibida; no se tocó ICT/SB. Un commit = un bug (72f7951).

================================================================================

## DEC-006 — ETAPA 3 cerrada: plan de implementación por dependencia (2026-07-17)

- Problema: definir el ORDEN de corrección sin violar "un cambio a la vez" ni la regla de oro.
- Evidencia: árbol de ETAPA 2 (CR-1..CR-6).
- Alternativas consideradas: ordenar por impacto (rechazado); ordenar por dependencia (elegido).
- Decisión tomada: 7 pasos en IMPLEMENTATION_PLAN.md. CR-1 primero (desbloquea H4/H5/H17);
  CR-6, CR-3, CR-4, CR-2, H16, CR-5. Cada paso = 1 commit = 1 bug, con tests+backtest+reversión
  si >5-10% de desvío. Fase 0 (ICT/SB/Killzone/Sequence/SL/TP/HTF/Entry) prohibida.
- Justificación: el orden evita corregir sobre base ambigua y aisla el efecto de cada filtro.
- Impacto esperado: implementación trazable; cada commit mide su impacto contra baseline.
- Cómo verificarla: IMPLEMENTATION_PLAN.md existe con pasos, aceptación y riesgo por ítem.

================================================================================


- Problema: tras la convergencia, cada hallazgo A debía demostrarse con repro real antes de
  implementar (evitar corregir fantasmas).
- Evidencia: inspección directa archivo:línea de cada H (detectors/bos.py:90-91,
  detectors/choch.py:14-24, coverage.py:44-47/71, run.py:64/412/433-435, stats_validator.py:83/101,
  dataset_builder.py:14/234, run_backtest.py:103, train.py:311-314, dataset_builder.py:146-161,
  engine.py:160/229, strategy_mtf.py:101-103) + `ls data/raw/XAUUSD_M15.parquet` (EXISTE).
- Alternativas consideradas: (a) aceptar la forense sin re-validar; (b) re-validar cada ID con
  repro (elegido, obligatorio por ETAPA 1).
- Decisión tomada: escribir VALIDACION_DE_HALLAZGOS.md con una entrada por ID (repro + línea +
  salida medible). Two correcciones a la forense: H14 (XAUUSD M15 YA EXISTE, Falla 4 de datos
  resuelta por descarga de hoy) y H3 (v2 YA versionado por commits previos).
- Justificación: la validación independiente halló que dos fallas forenses ya no aplicaban a
  nivel de datos/repo — corregirlas habría sido trabajo inventado. La ETAPA 1 cumplió su fin.
- Impacto esperado: la ETAPA 4 (corrección) se enfoca solo en hallazgos A realmente vigentes
  (H4,H5,H12,H13,H15,H16,H17,H18,H20,H21,H22); H3/H14 degradados a "ya resueltos".
- Cómo verificarla: VALIDACION_DE_HALLAZGOS.md existe con los 12 IDs + 2 correcciones; sin
  código modificado (solo docs + comandos de inspección).

================================================================================


- Problema: el proyecto tenía ~60 archivos sin commitear (docs, código, datos, borrados
  previos) y ningún tag de referencia; la forense (Falla 1) ya había mostrado que el motor v2
  no era reproducible desde clon limpio.
- Evidencia: `git status` pre-congelamiento mostraba modificados/sin trackear en múltiples
  áreas; `git tag` vacío; auditoría forense Falla 1 (v2 no comiteado).
- Alternativas consideradas: (a) taggear directo sobre 104964c ignorando los sueltos; (b)
  commitear todo en un mega-commit; (c) commits atómicos por tipo + tag (elegido).
- Decisión tomada: congelar el estado COMPLETO en commits atómicos C1..C7 (docs, fuente,
  datos/ml, data/raw, fuente modificado, nuevos, borrados) y crear tag `baseline-2026-07-17`
  sobre `c885ac3`.
- Justificación: el baseline debe ser el estado real reproducible; commits atómicos cumplen la
  regla de gobierno ("un commit = un bug" es para ETAPA 4; para congelar, por tipo es razonable).
- Impacto esperado: desde clon limpio en el tag, `ict_backtest/v2/orchestrator.py` es visible
  (Falla 1 resuelta a nivel de versionado); cualquier cambio de ETAPAS 1+ se mide contra este
  punto fijo.
- Cómo verificarla: `git cat-file -e baseline-2026-07-17:ict_backtest/v2/orchestrator.py`
  devuelve OK (verificado). Resto sin commitear: solo results/ (ignorado).

================================================================================


- Problema: tras las auditorías + convergencia + roadmap, el proyecto pasa de "investigación"
  a "ejecución controlada". Riesgo de que Hermes programa en piloto totalmente autónomo y
  toma decisiones estratégicas (lógica ICT, teoría) sin revisión.
- Evidencia: evolución del proyecto (arquitectura definida, cuellos identificados, auditoría
  forense, convergencia, roadmap de 11 etapas). Trabajo difícil ya hecho ANTES de implementar.
- Alternativas consideradas: (a) piloto autónomo total (rechazado: pierde control estratégico);
  (b) piloto automático supervisado con puntos de control (elegido); (c) mano a mano en cada
  commit (rechazado: mata la velocidad del trabajo repetitivo/disciplinado).
- Decisión tomada: Hermes avanza autónomamente DENTRO de cada etapa, pero se detiene al cerrar
  cada fase para entregar informe (qué hizo/evidencia/cambió/impacto/recomienda). Puede corregir
  UN hallazgo por vez, commits atómicos, tests+backtest tras cada cambio. NO puede cambiar lógica
  ICT, Silver Bullet, eliminar filtros por más N, tocar varios componentes en un commit, ni
  cambiar parámetros sin evidencia. Puntos de control: fin de fase; métricas >5-10% de cambio;
  cambio de TEORÍA (no impl); contradicción entre auditorías.
- Justificación: conserva el control de decisiones estratégicas en Ruben mientras Hermes hace el
  trabajo técnico repetitivo y disciplinado. Combina velocidad con gobernanza.
- Impacto esperado: implementación trazable y revisable; sin regresiones no detectadas; sin
  deriva de la estrategia ICT/Silver Bullet.
- Cómo verificarla: cada fase cierra con el informe obligatorio; ningún commit toca Fase 0 del
  informe de convergencia; cualquier desvío >5-10% de métricas detiene a Hermes para revisión.

================================================================================


- Problema: el proyecto avanzaba "arreglando cosas sueltas" sin salida clara ni criterio de
  aceptación; riesgo de regresiones silenciosas y de optimizar el backtest en vez de representar
  la estrategia.
- Evidencia: auditorías AUDITORIA_COMITE_TECNICO + AUDIT_R6_V2_MTF_Y_EDGEDIAG + INFORME_DE_
  CONVERGENCIA_ARQUITECTONICA coinciden en deuda ALTA (motores duplicados, train/serve skew,
  cap inválido, sin reproducibilidad).
- Alternativas consideradas: (a) seguir parcheando bug a bug; (b) reescribir el motor de golpe;
  (c) proceso por etapas con gates (elegido).
- Decisión tomada: adoptar PLAN_IMPLEMENTACION_ETAPAS.md (11 etapas, regla de oro de un cambio
  estructural a la vez + revalidación contra baseline, y DECISION_LOG vivo).
- Justificación: separa "validar" de "corregir" de "refactor" de "calibrar"; impide tocar la
  estrategia (Fase 0 prohibida) y obliga a evidencia antes de cada avance.
- Impacto esperado: cambios trazables, sin regresiones no detectadas, y un sistema que
  REPRESENTA ICT/Silver Bullet en vez de optimizar N/PF.
- Cómo verificarla: este archivo existe y crece por entrada; cada bug corregido en ETAPA 4
  tiene su DEC-xxx referenciando evidencia y comparación contra baseline.

================================================================================

## DEC-009f — Aclaración de alcance del PlanFSM (cierra contradicción doc, 2026-07-20)

- Problema: ARQUITECTURA_TEMPORALIDADES.md (líneas 10-17 y matriz §3) decía "las
  temporalidades superiores CREAN/modifican el plan" y "D1/H4/H1 → Crea/modifica plan ✅",
  lo cual CONTRADICE la regla de hierro de ETAPA_4_FASE_C_PLAN.md §1-§2 ("un solo cerebro.
  C es capa de CONTEXTO, no de decisión") y la filosofía del roadmap maestro (C = percepción,
  no 2do cerebro). La contradicción llevó a proponer erróneamente convertir al PlanFSM en un
  "cerebro de dirección" que delegara la dirección de run_sequence — violando el contrato.
- Evidencia: cruce ARQUITECTURA_TEMPORALIDADES.md vs ETAPA_4_FASE_C_PLAN.md §1-§2 vs
  ROADMAP_TESIS_DRIVEN_2026-07-17.md §4 (SB/Turtle sacados de Fase C "por filosofía C = capa
  de autoridad, no 2do cerebro") vs SPEC §1/§9 + libro 18 §0 #2 (HTF = filtro top-down, motor
  único R7 decide).
- Decisión tomada: enmendar ARQUITECTURA_TEMPORALIDADES.md para releer "crea/modifica plan"
  como "aporta contexto/dirección como FILTRO top-down". El PlanFSM queda definido como
  máquina de MADUREZ/EJECUCIÓN (lo ya implementado: Opción B, A1 Nivel 2), NO como cerebro de
  dirección. La dirección la dicta el HTF como filtro y la decide el motor único R7.
- Justificación: elimina la ambigüedad que permitía reinterpretar el PlanFSM como 2do cerebro
  (riesgo de duplicar lógica de decisión, violando R7 y el contrato de no invasión de C).
  Respeta tu regla "un solo cerebro".
- Impacto esperado: ningún agente (ni Hermes) vuelve a proponer PlanFSM-como-cerebro-de-
  dirección. La Brecha A1 real se cierra cableando top_down_allows_trade al motor canónico
  como filtro (ver PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md), no creando FSM nueva.
- Cómo verificarla: ARQUITECTURA_TEMPORALIDADES.md §1 y §3 ya releen la columna y agregan nota
  de coherencia apuntando a ETAPA_4_FASE_C_PLAN.md §1; sin contradicción con "un solo cerebro".

## DEC-009g — Propuesta Brecha A1 real: cablear top_down_allows_trade al motor canónico (2026-07-20)

- Problema: el motor canónico (run_sequence) decide dirección solo desde H4 (sequence.py:380);
  NO hace el top-down D1→H4→H1 que exige la tesis (Brecha A1 "3 capas reales"). El cronograma
  marca "A1 Nivel 2 CERRADA" pero eso es solo la compuerta de EJECUCIÓN (plan_gate, madurez),
  no las 3 capas reales en el motor. Confusión de nombres en el cronograma.
- Evidencia: top_down_allows_trade YA EXISTE en ict_backtest/v2/context_mtf.py:136 (gate
  D1→H4→H1→PD, devuelve (ok,reason), soporta counter_trend), pero solo se usa en el motor v2
  LEGACY (no versionado). El canónico no lo llama.
- Alternativas consideradas: (a) convertir PlanFSM en cerebro de dirección (RECHAZADO: viola
  "un solo cerebro", contrato Fase C); (b) cablear top_down_allows_trade al canónico como
  filtro (ELEGIDO); (c) reescribir lógica de dirección (RECHAZADO: ya existe, no reinventar).
- Decisión tomada: dejar PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md (borrador, NO implementado).
  Diseño: run_sequence construye `stack` desde MultiTFContext (cerrado-only) y llama
  top_down_allows_trade tras calcular direction; anota ICTSignal.htf_aligned. Opción B
  (anotación+bonus, igual filosofía Fase C) recomendada para arrancar; Opción A (filtro duro)
  como knob APAGADO por default. Turtle Soup usa counter_trend=True.
- Justificación: cierra la Brecha A1 FUNCTIONAL sin 2do cerebro, reusando código ya validado
  (anti-look-ahead por build_context_stack). Respeta tu regla "un solo cerebro" y la SPEC.
- Impacto esperado: el motor deja de "pensar en H4→M15" y filtra por cascada D1→H4→H1 real.
- Cómo verificarla / PENDIENTE: requiere (1) OK de Ruben Opción A vs B; (2) firma de Fase 0
  (SPEC_TESIS_FORMAL sigue DRAFT) antes de tocar código (regla R1); (3) escribir MDS
  docs/specs/*.md que exige R2 (hoy NO existen). Sin esos, NO se implementa. Backtest de PF
  bloqueado hasta Fase G (R4). Verificación por fidelidad + diag_etapas con datos chicos.

## DEC-009h — Fase 0 firma de SPEC + creación de MDS (R1/R2 cumplidas, 2026-07-20)

- Problema: la SPEC_TESIS_FORMAL seguía DRAFT (no firmada) pese a que B1/C0-C4/A1 Nivel 2
  ya se implementaron sin ella (violación de R1). Y los MDS (docs/specs/*.md) que exige R2
  NO existían: la matriz §9 marcaba 8 componentes OBLIGATORIOS como ❌ sin diseño de módulo.
- Evidencia: ROADMAP_TESIS_DRIVEN §9 (8 obligatorios ❌), §11 R1 (SPEC precede código),
  R2 (sincronía SPEC↔MDS); SPEC_TESIS_FORMAL header "DRAFT"; búsqueda docs/specs/ vacía.
- Decisión tomada:
  (a) FIRMAR SPEC_TESIS_FORMAL (R1): pasa a CONTRATO FUENTE. Se registra excepción DEC-009g
      para B1/C0-C4/A1 Nivel 2 (hechos antes, ya validados, sin alterar conteo).
  (b) CREAR docs/specs/ con 8 MDS nuevos + INDICE_MDS.md (R2): B2 (exec M5/M1), B3
      (internal/external liq), Killzones L/NY PM, C2 (Silver Bullet), C3 (Turtle Soup),
      D1 (OTE), E1 (Trade Mgmt), RR por setup. Cubre todos los ❌ de la matriz §9.
  (c) Cronograma v2.7: fila "Fase 0 — Formalización (SPEC firmada) + MDS" CERRADA; fila
      "Brecha A1 real — 3 capas en motor" como PENDIENTE/propuesta.
- Justificación: cumple tu regla de gobernanza R1 (SPEC precede código) y R2 (trazabilidad
  SPEC↔MDS). Cierra la deuda de diseño que impedía implementar B2→E1 con base contractual.
- Impacto esperado: cualquier implementación de B2/C2/C3/D1/E1 ahora tiene SPEC firmada +
  MDS como contrato. Orden sugerido B2→B3→C2→C3→D1→E1 (ROADMAP §4).
- Cómo verificarla: SPEC header dice "FIRMADA"; docs/specs/ tiene 8 MDS + índice; cronograma
  v2.7 refleja ambos. Backtest de PF sigue bloqueado hasta Fase G (R4).

## DEC-009i — Principio de zona horaria: hora del SERVIDOR + conversión (2026-07-20)

- Principio dictado por Ruben: "se toma la hora del servidor (donde está instalado MT5/
  Hermes = broker time) y se hace LA CONVERSIÓN horaria" (a ET / UTC canónico) antes de
  evaluar cualquier lógica ICT horaria. NO se asume que el timestamp ya está en ET ni en
  UTC, y PROHIBIDO offset fijo hardcodeado.
- Evidencia de bug en código REAL (detectado al redactar MDS_KILLZONES):
  * `detectors/killzones.py:11-14` asume `time` del parquet "YA está en hora broker" y NO
    convierte; usa offset FIJO ("NY=-4, LDN=0, TOKYO=+9 en verano") → ignora DST/zonas reales.
  * `ict_backtest/rules.py:killzone_en` asume `ts` "ya viene en UTC" y evalúa crudo.
  * `docs/ict/01_KILLZONES.md §4` marcaba KZ-1 "resuelto" pero persiste el hueco KZ-2
    (3 relojes en la práctica: ET mentorship / broker chart / UTC approx falso).
- Decisión tomada:
  * Establecer como REGLA DURA en `docs/specs/MDS_KILLZONES_L_NYPM.md` §0: server_time →
    conversión vía ZoneInfo (DST) → UTC canónico → evaluar bandas. Zona del broker =
    CONFIG (`SMC_BROKER_TZ`), no hardcode. Reusar patrón de `app_observador/core/timezone.py`
    (UTC canónico + ZoneInfo). Anti-look-ahead: solo `time` de vela ya cerrada.
  * Firma propuesta `server_to_utc(ts, broker_tz)` + `killzone_en(ts, broker_tz=None)` que
    convierte SIEMPRE antes de evaluar.
  * MDS_KILLZONES reescrito para exigir la muerte del offset fijo (KZ-2) al implementar.
- Justificación: cumple el principio de Ruben y evita killzones falsas por DST/zona (el bug
  actual da ventanas desfasadas ~1h en verano y en brokers fuera de NY).
- Impacto esperado: killzone idéntica en backtest (ts vela convertido) y en vivo (reloj PC
  convertido), sin 3 relojes. Cierra KZ-2.
- Cómo verificarla: MDS_KILLZONES §0 tiene la regla dura + bug citado; tests de aceptación
 con broker NY / DST / broker otra zona. Implementación pendiente (es fase de diseño).

 ## DEC-009i — Ruben elige C: el PlanFSM SÍ será cerebro de DIRECCIÓN (modifica DEC-009f, 2026-07-20)

 - Contexto: en esta sesión se cerraron por código Brecha A1 real (cascada D1→H4→H1
 cableada en `run_sequence` como filtro Opción B), Fase B2 (exec M5/M1) y Brecha A
 (POI anclado como bonus vía `htf_poi_fn`). Los 3 con TDD + call site real + verify
 empírico (22 tests nuevos + 9 de regresión canónica, 31 passed). Ver CRONOGRAMA
 filas Brecha A1 real / Fase B2 / Brecha A, y ROADMAP_BIBLIOTECA §R3.5.
 - Decisión tomada (Ruben, opción C): PROMOVER el PlanFSM a cerebro de DIRECCIÓN de la
 estrategia. Esto MODIFICA la filosofía de DEC-009f ("PlanFSM NO es cerebro de
 dirección, un solo cerebro, run_sequence decide filtrado por HTF"). El PlanFSM dejará
 de ser solo máquina de MADUREZ/EJECUCIÓN (lo que hoy es, A1 Nivel 2 = compuerta
 Opción B) y pasará a dictar la DIRECCIÓN (emitir sesgo D1→H4→H1, consumir POI anclado
 Fase C, premium/discount, PO3/AMD como gates de timing) y run_sequence le DELEGARÁ la
 dirección (quitando su lectura de H4 trend y su hook `htf_poi_fn` muerto).
 - Evidencia que lo motiva: auditoría `docs/plan/AUDITORIA_PLANFSM_CEREBRO.md` probó que
 el PlanFSM HOY NO puede ser cerebro de dirección sin antes ampliar B1-B7 (no emite
 dirección; POI anclado desconectado de `emit_h1`; premium/discount ignorado por
 emisores; PO3 solo bonus; `top_down_allows_trade` fuera del PlanFSM en v2 legacy;
 duplicación de cerebro en H4; contrato "un solo cerebro" incumplido en la práctica).
 - Alternativas consideradas y descartadas: (a) dejar el PlanFSM como portero de madurez
 y no tocar dirección (RECHAZADA: Ruben quiere que el motor use la cascada de verdad,
 no solo filtre); (b) que run_sequence siga decidiendo (RECHAZADA: viola la intención
 C de un único cerebro de dirección).
 - Justificación: cierra la queja original de Ruben ("el motor piensa solo en H4→M15").
 La cascada ya frena (A1); en C la cascada TAMBIÉN manda la dirección, unificada en el
 PlanFSM.
 - Impacto esperado: reestructuración de los emisores del PlanFSM (B1-B7) y del contrato
 `run_sequence ↔ PlanFSM`. NO es "enchufar una cables": requiere dar contenido
 direccional al PlanFSM primero.
 - PRÓXIMO PASO (no en este commit): diseñar el PlanFSM ampliado (emite DIRECCIÓN, consume
 POI anclado Fase C, pd_side, PO3 como gate de timing) + demo sintética + OK de Ruben
 (regla de gobernanza: diseño+demo antes de producción). Luego cablear run_sequence
 para delegar dirección/POI al PlanFSM.
 - Cómo verificarla: tras el diseño, los tests de call site real deben mostrar que la
 dirección de la señal sale del PlanFSM, no de `extract_htf_layer` en run_sequence.
 - Regla de commit: este DEC-009i se commitea junto con el cierre de A1/B2/Brecha A
   (roadmap + cronograma al día en el mismo commit, según regla de Ruben).
 - ACLARACIÓN POSTERIOR (Ruben, 2026-07-20, tras discutir opciones): la
   "opción C" se EJECUTA como el CAMINO DE LA TESIS, no como PlanFSM dictador
   duro. O sea: PlanFSM queda como PORTERO de madurez (A1 Nivel 2), y la
   DIRECCIÓN la sigue dictando run_sequence PERO con el FILTRO HTF ENRIQUECIDO
   (D1 sesgo + H4 POI anclado + H1 liquidez + premium/discount + PO3/AMD como
   gates de timing). Esto es literal libro 18 §0 #2 y SPEC §1/§9 ("HTF = filtro
   top-down, motor único R7 decide") y evita el pozo de A'' (gate duro HTF = PF
   0.900). El PlanFSM NO se vuelve un 2do cerebro de dirección ciego; se enriquece
   el filtro que run_sequence ya usa. Ver cierre de B3 (DEC-009j) como primer
   paso de ese enriquecimiento (jerarquía de liquidez internal/external ya
   anotada en la señal como metadato, listo para E1).

 ## DEC-009j — B3 CERRADO: jerarquía de liquidez internal vs external (2026-07-20)

 - Problema: `_tp_liquidity` (engine.py) usaba clusters lejanos (libro 20 §8)
   y no distinguía liquidez INTERNAL (swing reciente de sesión) de EXTERNAL
   (PDH/PDL/EQ high-low). La tesis (§14) exige TP primario = internal, objetivo
   macro = external.
 - Decisión tomada: `_tp_liquidity(row, direction, df=None)` ahora devuelve
   `dict{internal, external}`. `internal` = bsl_price/ssl_price del row (idéntico
   a histórico). `external` = PDH (long) / PDL (short) del día previo en `df`
   (calculado; antes no existía). Call-site en `canonical.evaluate_signals` usa
   `internal` como TP primario (regresión cero: antes también usaba bsl/ssl) y
   anota `external_tp` en `ICTSignal` como metadato para E1 (Trade Management).
 - Justificación: cierra MDS_B3_LIQUIDEZ_INT_EXT (OBLIGATORIO, SPEC §14) sin
   alterar entry/SL/TP ni el conteo de señales (principio Brecha D: metadato de
   percepción, no filtro). Es el primer ladrillo del enriquecimiento del filtro
   HTF que pide la "opción C como camino de tesis" (DEC-009i aclaración).
 - Impacto esperado: el TP sigue siendo internal (BSL/SSL, igual que antes); el
   external queda disponible para E1 (ej. BE+corrida a PDH/PDL macro). Sin
   `df` o sin día previo → external=None → comportamiento histórico intacto.
 - Cómo verificarla: tests `tests/test_b3_tp_hierarchy.py` (5: unidad RED→GREEN
   + aceptación call-site real con 2 días: TP=1.1300 internal / external_tp=1.1100
   PDH). Batería completa 36 passed (B3+B2+A1+POI+fase1+r7). Sin datos reales.

## DEC-009k — C2/C3/D1/E1/RR/KZ CERRADOS: setups ICT cableados al orquestador (2026-07-20)

- Problema: el motor tenia Brechas C2/C3/D1/E1/RR/KZ de la tesis sin cerrar
  (Silver Bullet, Turtle Soup, OTE, Trade Mgmt, RR por setup, Killzones TZ).
- Decisión tomada: cerrarlos como MÓDULOS AISLADOS (cada agente leaf creó su
  archivo nuevo, regiones disjuntas, TDD RED→GREEN, SIN tocar canonical/engine
  en la implementación) y luego YO cablearlos en `canonical.evaluate_signals`
  como PASO POST (knob apagado = solo anotan, no filtran duro — principio
  Brecha D / lección A''). Esto evita el pozo de A'' (gate duro HTF = PF 0.900)
  y respeta "un solo cerebro" (run_sequence decide, los setups enriquecen la
  señal como metadato).
  - C2 `setups/silver_bullet.py`: `is_silver_bullet` + `flag_silver_bullet`
    (anota `sb_confirmed`/`sb_killzone`). Reusa `killzone_en` (KZ-2).
  - C3 `setups/turtle_soup.py`: `is_turtle_soup` + `flag_turtle_soup` (anota
    `turtle_confirmed`/`turtle_broke`). PDH/PDL día previo desde `frames[ltf]`.
  - D1 `setups/ote.py`: `ote_zone`/`is_ote_entry`/`flag_ote` (anota
    `ote_confirmed`/`ote_zone`). Fib 0.62-0.79 de la pierna.
  - E1 `trade_mgmt.py`: `to_breakeven`/`partial_exit`/`trailing_stop` (funciones
    PURAS, listas para consumir post-entry; NO cableadas aún al simulador).
  - RR `setups/rr_map.py`: `RR_BY_SETUP`/`rr_for`/`flag_rr` (anota `rr_target`).
    SB→2.0, Turtle→1.5, OTE→3.0, default→3.0.
  - KZ-2 `detectors/killzones.py` + `ict_backtest/rules.py`: `server_to_utc`
    vía ZoneInfo (DST automático), mata offsets fijos NY=-4/LDN=0/TOKYO=+9.
    Firma `killzone_en(ts, broker_tz=None)` estable.
- Justificación: cierra 6 OBLIGATORIOS de la tesis en orden de roadmap con
  gobernanza TDD + call-site real auditable (no test aislado: `test_orchestrator_
  setups_wired.py` corre `evaluate_signals` real y afirma que la señal trae
  `sb_confirmed=True`/'L' y `rr_target==2.0`). Regresión cero: los flags no
  alteran entry/SL/TP; `evaluate_signals` sigue produciendo señales idénticas.
- Impacto esperado: la señal ICT ahora sale ENRIQUECIDA con setup detectado +
  RR objetivo + liquidez external (B3) + POI (Brecha A) + cascada HTF (A1).
  Pendiente (Fase siguiente, NO este commit): (a) aplicar `rr_target` al cálculo
  de TP en canonical (hoy fuerza 1:3); (b) cablear E1 al simulador post-entry;
  (c) knob de filtro duro opcional (veto por setup) si el backtest lo justifica.
- Cómo verificarla: batería 96 passed (C2 11 + C3 6 + D1 10 + E1 19 + RR 6 +
  KZ 7 + B3 5 + B2 4 + A1 6 + POI 12 + fase1 2 + r7 7 + orquestador 1). Sin
  datos reales. Commit pendiente de OK de Ruben (regla de commit).

## DEC-009l — APLICACIÓN real de RR por setup (→TP) y E1 Trade Mgmt (→simulador) (2026-07-20)

- Problema (pendiente de DEC-009k): los setups ICT anotaban `rr_target` y
  `apply_trade_management` existía como funciones puras, pero NO se aplicaban
  al cálculo real del TP ni al simulador de trade. Riesgo anti-test-verde-aislado
  (Ruben): anotar no es cablear.
- Decisión: (a) RR→TP: `canonical.evaluate_signals` ahora resuelve el setup de
  la señal CRUDa dentro del loop vía `_rr_for_raw_signal(s, ltf_df, direction,
  ltf)` (call-site real del pipeline, usa los detectores `is_silver_bullet`/
  `is_turtle_soup`/`is_ote_entry` reales) y aplica `tp = entry +/- rr_target *
  risk` reemplazando el `3.0*risk` fijo. La guarda de mínimo 2R solo aplica al
  fallback de liquidez internal (cuando no hay BSL/SSL). (b) E1→simulador:
  `trade_mgmt.apply_trade_management(entry, sl, tp, direction, df, ...)` simula
  el recorrido post-entry (parcial en tp1 + BE + trailing + cierre en TP/SL/BE,
  PnL ponderado). Es el call-site real que `run_backtest` llamará por señal.
- Justificación: cierra la trampa "función aislada vs cableada". El TP ahora
  obedece el setup (SB 1:2, Turtle 1:1.5, OTE 1:3, default 1:3) de forma
  empírica, y E1 tiene su motor de gestión listo y testeado para el backtest.
  Regresión cero: sin setup confirmado, RR sigue 3.0 (idéntico histórico).
- Impacto: la señal ICT produce TP por setup y el trade management tiene
  simulador propio. Backtest de PF sigue BLOQUEADO hasta Fase G (no se corrió
  `run_backtest` con estas funciones sobre datos reales; solo unidad sintética).
- Cómo verificarla: batería 103 passed (96 + `test_rr_applied_to_tp.py` 4 +
  `test_e1_applied_trade_mgmt.py` 3). Sin datos reales. Commit pendiente de OK
  de Ruben.

## DEC-009m — Phase 0 freeze: inventory del motor de decisión LEGACY (2026-07-21)

- Problema: R7 unificó el path vivo en `ict_backtest.canonical`, pero la deuda
  H2/H3 (`legacy/backtest`, `ml/dataset_builder`) seguía sin freeze ni grafo
  exhaustivo de consumidores. Riesgo: nuevos imports del motor viejo mientras
  se planifica la purga.
- Evidencia: `docs/plan/PLAN_PURGA_MOTOR_LEGACY.md` (inventario path:line);
  imports verificados en `ml/dataset_builder.py:14`, `scripts/edge_diagnosis/run.py:54`,
  `scripts/run_fundednext_compliance.py:23`, `adapters/__init__.py:4-6`,
  `paper_trading/runner.py:26`, `signals/pipeline.py:89`; path canónico
  `app_observador/core/engine.py` → `latest_plan`.
- Alternativas: (a) borrar legacy de una (rechazado: rompe ML/harness/paper);
  (b) freeze + inventory por fases (elegido).
- Decisión tomada: congelar el motor de decisión legacy — **ningún código nuevo**
  importa `legacy.backtest` / `from backtest` / `_build_signals_from_context` como
  fuente de trades. `_data_legacy` queda clasificado DATA_ONLY (no decisión).
  Plan de purga en 5 fases; Phase 0 DONE, Phase 1 = dead scripts.
- Justificación: sin freeze el grafo de deuda crece; sin inventory no se puede
  rewire ML/adapters con seguridad.
- Impacto esperado: purga ordenada sin tocar observador/canonical; Phase 1 puede
  matar scripts rotos (`_measure_ml_filter`, `_run_ml_iso`, `_smc_measure_ml_gate`).
- Cómo verificarla: `docs/plan/PLAN_PURGA_MOTOR_LEGACY.md` §0–§8; grep freeze
  documentado en §0; cero cambios de comportamiento en path PROTECT.

================================================================================
