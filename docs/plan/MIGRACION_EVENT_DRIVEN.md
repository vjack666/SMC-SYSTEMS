# Plan técnico: BOS/CHoCH/OB → arquitectura event-driven pura

Estado: PLAN TÉCNICO DE IMPLEMENTACIÓN. NO se modifica código. NO commit/push.
Fecha: 2026-07-14. Basado en lectura directa del repo (no en resumen).

================================================================
A) ARCHIVOS QUE SERÁN MODIFICADOS (y por qué, con línea)
================================================================

  MODIFICAR:
  1. detectors/bos.py
     - BosConfig.max_age=24 (línea 15) → eliminar.
     - _track_bos_validity (líneas 110-139): borrar rama `elif age>max_age:
       "aged"` (135-136). Queda solo INVALIDATED por cruce (129-134).
  2. detectors/choch.py
     - detect_choch llama _track_choch_validity(..., max_age=20, ...) (línea 27).
     - _track_choch_validity (33-62): borrar rama aged (líneas 57-58).
  3. detectors/ob.py
     - _track_ob_validity(data, max_age=20) (línea 39).
     - Borrar rama aged (líneas 74-75).
  4. ict_backtest/market_structure.py  (MOTOR CANÓNICO)
     - StructureConfig: quitar max_age_atr (65), max_age_bars (66).
     - _track_structure (185-243): eliminar bloque rest_bars/aged
       (líneas 228-241, incluye threshold y progressed). Queda solo
       INVALIDATED por cruce (234-235).
  5. ict_backtest/data_feed.py
     - build_features (líneas 46-66): reemplazar detect_bos/detect_choch/
       detect_order_blocks por market_structure.detect_market_structure.
       Mantener alias bos_direction/bos_status/ob_direction/ob_status
       mapeados desde market_structure para no romper UI/rules.
  6. ict_backtest/sequence.py
     - Al entry (donde hoy state.reset()), marcar la estructura usada como
       CONSUMED (en SequenceState o en el df). Hoy NO usa aged; solo añade
       el estado CONSUMED formal.
  7. ict_backtest/states.py  (NUEVO)
     - enum StructureState + helper str→enum.
  8. tests/test_ict_backtest.py, tests/test_check_separation.py
     - Actualizar asserts de "aged" (no deben existir). Añadir tests de
       estructura viva >max_age velas.
  9. ict_backtest/_cmp_bos.py, _smoke.py
     - Fixtures: quitar "aged" de bos_status.

  NO TOCAR (ya event-driven, verificado):
  - detectors/fvg.py (mitigación por toque de gap, líneas 67-71).
  - detectors/liquidity.py, detectors/liquidity_context.py (renovación por
    nueva zona, sin max_age).

================================================================
B) CONSUMIDORES REALES (boss/choch/ob_status, aged, active)
================================================================

  bos_status:
    - ict_backtest/rules.py:82-85  → if st=="active" (solo activo)
    - ict_backtest/rules.py:279    → fixture de test ({"bos_status":"active"})
    - app_observador/core/engine.py:97,120 → str(info.get("bos_status",""))
    - app_observador/ui/resumen_widget.py:335-338 → if st=="active"
    - app_observador/ui/noticias_widget.py:25-28 → if bos_status=="active"
  choch_status:
    - app_observador/core/engine.py:106,128 → str(get("choch_status","-"))
    - app_observador/ui/resumen_widget.py:148 → not in ("-","none","nan","")
  ob_status:
    - producers: detectors/ob.py genera ob_status (línea 39). No hay
      consumidor que lo lea para decidir (solo lo crea).
  aged:
    - SOLO lo PRODUCEN los detectores (bos.py:136, choch.py:58, ob.py:75,
      market_structure.py:241). CERO consumidores lo leen para lógica. El
      motor de secuencia usa bos_dir/choch_dir (int), NO bos_status.
  active:
    - Los consumidores arriba solo testean "active". Al quitar aged,
      "active" persistirá más velas (correcto en ICT). Sin cambio de lógica.

  CONCLUSIÓN: eliminar aged NO cambia ninguna decisión de trading ni de UI.
  Solo deja de "morir" estructuras que hoy mueren a las 24/20 velas.

================================================================
C) CONFIRMACIÓN DE NO-REGRESIÓN (análisis de impacto)
================================================================

  - Motor de secuencia (sequence.py): no lee *_status. Usa bos_dir/choch_dir.
    El aged no afectaba sus señales → 0 regresión de señales por quitarlo.
  - rules.py / UI: solo leen "active". La estructura seguirá "active" (no
    pasa a "aged"), así que siguen funcionando igual o mejor (más activas).
  - Backtest PF/WR: puede CAMBIAR (más estructuras vivas → más oportunidades
    de retorno). Por eso Fase 5 mide A vs A' con métricas. No es regresión de
    bug, es cambio de comportamiento correcto. Se reporta delta, no se asume.
  - Look-ahead: intacto (no toco _swing_points ni confirm_bars).
  - Veredicto: eliminar aged no introduce regresión de CORRECTITUD; puede
    cambiar números de backtest (esperado y medido en Fase 5).

================================================================
D) NUEVA MÁQUINA DE ESTADOS
================================================================

  Enum (ict_backtest/states.py):
    class StructureState(Enum):
        CREATED = "created"
        ACTIVE = "active"
        MITIGATED = "mitigated"
        INVALIDATED = "invalidated"
        CONSUMED = "consumed"

  Transiciones (todas por EVENTO de mercado, NINGUNA por nº de velas):
    CREATED  → ACTIVE      : el cierre rompe el nivel (confirm_bars cuerpos).
    ACTIVE   → INVALIDATED : el cierre CRUZA de nuevo el nivel roto
                             (evento de precio; líneas 129-134 / 234-235).
    ACTIVE   → MITIGATED   : el precio toca el cuadro anclado (FVG/OB lleno;
                             para BOS/CHOCH, mitigación = el nivel es superado
                             en sentido útil; en la práctica la secuencia lo
                             consume o lo invalida).
    ACTIVE   → CONSUMED    : la secuencia USA el objeto para entrar (sequence
                             lo marca al entry).
    (Sin transición por tiempo. "aged" se ELIMINA.)

  Mapeo desde strings actuales:
    "none"→CREATED, "active"→ACTIVE, "invalidated"→INVALIDATED,
    "aged"→(eliminado; no se emite), bullish_unfilled/bearish_unfilled→ACTIVE.

================================================================
E) ÚNICA FUENTE DE VERDAD (market_structure.py)
================================================================

  Hoy hay DOS definiciones divergentes:
    (a) detectors/bos.py + detectors/choch.py + detectors/ob.py
    (b) ict_backtest/market_structure.py (canónico, confirm_bars + aged)
  data_feed.build_features llama a (a) y mapea a bos_dir/choch_dir que el
  motor usa. Esa divergencia causó el bug del 0 señales (Piso 1).

  Migración:
    1. data_feed.build_features llama ÚNICAMENTE a
       market_structure.detect_market_structure (fuente única).
    2. Los nombres que la UI/rules esperan (bos_direction, bos_status,
       ob_direction, ob_status, choch_signal/choch_status) se EXPONEN como
       ALIAS desde market_structure:
         d["bos_direction"] = d["bos_dir"].map({1:"BULLISH",-1:"BEARISH",0:"-"})
         d["bos_status"]    = d["bos_status_enum"].map(...)  # active/invalidated
         d["ob_direction"]  = ... (de ob_bullish/ob_bearish de market_structure)
         d["choch_signal"]  = d["choch_dir"].map({1:CHOCH_BULLISH,-1:CHOCH_BEARISH,0:NONE})
         d["choch_status"]  = estado mapeado
    3. detectors/bos.py, choch.py quedan DEPRECATED (docstring + FutureWarning
       si se importan fuera de data_feed). detectors/ob.py se migra a llamar
       market_structure o se depreca igual. NO se borran aún (evita romper
       imports externos).

================================================================
F) COMPATIBILIDAD TEMPORAL (aliases)
================================================================

  - rules.py:82 y UI leen bos_status=="active" → el alias de (E.2) sigue
    emitiendo "active"/"invalidated"/"none". Sin tocar rules.py ni UI.
  - ict_backtest/rules.py:279 es un fixture de test → actualizar en tests.
  - _smoke.py/_cmp_bos.py: actualizar fixtures (sin "aged").

================================================================
G) ESTRATEGIA DE PRUEBAS
================================================================

  G.1 BASELINE (antes del cambio, fixture no código):
      - Correr run_backtest EURUSD H4→M15 y GBPUSD H4→M15 CON el código
        actual (con aged). Guardar en tests/baseline_aged.json:
          {symbol, n_trades, pf, wr, expectancy, max_dd, hold_limit_pct,
           avg_min_to_entry, avg_struct_active_bars}
      - Esto es un snapshot; no modifica comportamiento.

  G.2 POST-CAMBIO (A'):
      - Mismos símbolos/periodo. Guardar tests/baseline_eventdriven.json.
      - Comparar: delta PF, delta WR, delta n_trades, delta max_dd,
        delta % hold_limit, delta avg_min_to_entry, delta avg_struct_active_bars.

  G.3 TESTS UNITARIOS NUEVOS:
      - test_bos_no_aged: estructura sin progreso por 100 velas sigue ACTIVE
        (antes pasaba a aged).
      - test_choch_no_aged / test_ob_no_aged: análogos.
      - test_state_enum: mapeo str→StructureState correcto, sin "aged".
      - test_single_source: build_features no llama detectors.bos.py
        (patch/assert); bos_dir/choch_dir provienen de market_structure.
      - test_consumed: tras entry en sequence, estructura queda CONSUMED.
      - test_alias_compat: bos_status expuesto sigue siendo "active" cuando
        market_structure dice ACTIVE (UI/rules no cambian).

  G.4 REGRESIÓN: los 17 tests existentes + los nuevos deben pasar. Si PF baja
      en A', investigar si el aged ocultaba señales malas (no revertir a ciegas;
      documentar en docs/auditorias/).

================================================================
H) PLAN POR FASES (orden recomendado)
================================================================

  Fase 0 — Baseline (sin cambio de código):
    - Generar tests/baseline_aged.json (EURUSD + GBPUSD). Commit aparte si
      autoriza.

  Fase 1 — Única fuente de verdad:
    - data_feed.build_features → solo market_structure.detect_market_structure.
    - Aliases bos_status/ob_status/choch_signal desde market_structure.
    - detectors/bos.py/choch.py/ob.py → DEPRECATED (FutureWarning).
    - Test test_single_source + test_alias_compat.

  Fase 2 — Matar aged en market_structure (canónico):
    - Quitar max_age_bars/max_age_atr de StructureConfig.
    - _track_structure: eliminar bloque rest_bars/aged (228-241).
    - Mapear a enum StructureState.
    - Tests test_bos_no_aged / test_choch_no_aged / test_state_enum.

  Fase 3 — Matar aged en detectores legacy:
    - bos.py / choch.py / ob.py: sin rama aged.
    - Test test_ob_no_aged.

  Fase 4 — CONSUMED en secuencia:
    - sequence.py marca CONSUMED al entry.
    - Test test_consumed.

  Fase 5 — Backtest comparativo:
    - A' vs baseline_aged.json. Reporte de métricas (PF/WR/n/DD/hold_limit).
    - Doc en docs/auditorias/MIGRACION_EVENT_DRIVEN_RESULT.md.

  Fase 6 — Documentación:
    - Actualizar DISENO_VENTANA_ESPERA.md (caducidad = ventana_espera, no
      max_age), METRICS_CANON.md, AGENTS.md.

================================================================
I) RIESGOS
================================================================

  R1 Motor secuencia: BAJO (no consume aged).
  R2 rules/UI: BAJO (solo "active"; alias preserva).
  R3 Backtest PF/WR: MEDIO (esperado cambio; medido en Fase 5, no asumido).
  R4 Divergencia 2 detectores: ALTO si no se unifica → Fase 1 obligatoria.
  R5 Look-ahead: BAJO (no toco swing_points/confirm_bars).
  R6 Costo CPU: BAJO-MEDIO (más estructuras activas → más eval de retorno;
      acotado por ventana_espera de killzone en la secuencia).

================================================================
J) CRITERIOS DE ACEPTACIÓN
================================================================

  AC1: Ningún módulo emite estado "aged" para BOS/CHoCH/OB.
  AC2: Estructura vive hasta cruce de nivel (INVALIDATED) o mitigación;
       nunca por conteo de velas (test test_*_no_aged lo prueba con 100 velas).
  AC3: Enum StructureState con 5 estados usado por sequence + data_feed.
  AC4: Única fuente = market_structure; build_features no llama detectors
       legacy (test test_single_source).
  AC5: UI/rules siguen funcionando sin edición (alias; test test_alias_compat).
  AC6: Backtest A' genera baseline_eventdriven.json y delta documentado vs
       baseline_aged.json (PF/WR/n/DD/hold_limit).
  AC7: 17 tests previos + nuevos (Fase 2/3/4) pasan (pytest canónico).
  AC8: Sin commit/push hasta autorización explícita "haz commit y push".

================================================================
K) FUERA DE ALCANCE
================================================================

  - Piso 2 ventana_espera() (aprobado, pendiente de implementar).
  - OU / first-passage (bloqueado hasta diag μ≠0 en killzone).
  - R3.5 (libros 21/22/23), R7 (anti-islas grafo).
