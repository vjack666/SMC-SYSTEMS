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
