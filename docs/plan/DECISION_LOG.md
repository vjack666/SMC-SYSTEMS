# DECISION_LOG — Memoria técnica de SMC-SYSTEMS

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
