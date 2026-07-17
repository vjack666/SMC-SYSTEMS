# DECISION_LOG — Memoria técnica de SMC-SYSTEMS

Base de conocimiento viva del proyecto (ETAPA 11). Cada decisión importante se registra con
el formato definido en PLAN_IMPLEMENTACION_ETAPAS.md. Orden cronológico inverso (más reciente
arriba). Cuando dentro de meses te preguntes "¿por qué hicimos X?", está aquí con su evidencia.

Formato por entrada:
- Problema · Evidencia · Alternativas consideradas · Decisión tomada · Justificación ·
  Impacto esperado · Cómo verificarla

================================================================================

## DEC-002 — Modo de operación: piloto automático supervisado (2026-07-17)

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
