> **✅ HISTORICAL** — Fase B1 completada 2026-07-18 (commit DEC-009g). PD Arrays + tiers/stacking implementados.

PLAN DE IMPLEMENTACIÓN — FASE B1 (Geometría fina de PD Arrays + tiers/stacking)
================================================================================

ID: ETAPA_4_FASE_B1_PLAN.md
Fase: B1 del ROADMAP_TESIS_DRIVEN_2026-07-17.md (Fase B — Geometría fina)
Contrato fuente: docs/ict/SPEC_TESIS_FORMAL.md §3 (PD Arrays FVG/OB), §4 (PD Arrays
  completos), §5 (Stacking multi-TF).
Estado: PLAN — requiere OK de Ruben para implementar (Ruben rule: no commit sin OK).
Vinculación R2: esta Fase toca código → la SPEC §3/§4/§5 ya cubre estos componentes.

---------------------------------------------------------------------
0. OBJETIVO
---------------------------------------------------------------------

Añadir al motor la GEOMETRÍA FINA de la tesis (SPEC §4/§5) que hoy falta:
  - Tipos de PD Array: FVG, OB, BREAKER, REJECTION_BLOCK, MITIGATION_BLOCK,
    PROPULSION (tesis 20 §5b, libro 21 §2).
  - Tiers jerárquicos: T1 (BPR) > T2 (OB/FVG fuerte) > T3 (rejection/mitigation)
    (libro 21 §2).
  - Stacking multi-TF: POI de TF menor dentro de zona de TF mayor eleva autoridad.

NO se toca la lógica de decisión de `run_sequence` (fuente única R7). Solo se
enriquecen los METADATOS de los PD Array detectados para que POI (§16) y stacking
(§5) los consuman. Esto es añadir información, no cambiar el motor de señal.

---------------------------------------------------------------------
1. ALCANCE (qué SÍ y qué NO)
---------------------------------------------------------------------

SÍ:
  - Columnas `pd_type` y `pd_tier` en detectors/fvg.py y detectors/ob.py.
  - Exponer `pd_type`/`pd_tier` en el MarketObject (data_feed → translation).
  - Cálculo de tier básico por tipo + stacking multi-TF en sequence (metadato).
  - Test unitario de que los tipos/tiers se detectan y propagan al call site.
  - Smoke test: sequence sigue emitiendo señales idénticas (n_changed=0 en decisión).

NO (queda para B2 / fases siguientes, con su propio OK):
  - Exec fino M5/M1 (§10) — requiere el reloj MTF, más invasivo.
  - POI como BONUS ya existe (quality_score+=20); aquí solo se enriquece el tipo.
  - Cambiar RR, SL, TP, killzone — fuera de alcance.

---------------------------------------------------------------------
2. ARCHIVOS A TOCAR
---------------------------------------------------------------------

  detectors/fvg.py        · añadir pd_type (FVG), pd_tier (T2 default; T1 si BPR)
  detectors/ob.py         · añadir pd_type (OB/BREAKER/REJECTION/MITIGATION/PROPULSION),
                           pd_tier (T2/T3 según tipo)
  ict_backtest/data_feed.py · propagar pd_type/pd_tier al MarketObject meta
  ict_backtest/translation.py · incluir pd_type/pd_tier en meta del objeto
  ict_backtest/sequence.py · leer pd_type/pd_tier para enriquecer zona (metadato)
  tests/test_fase_b1_pd_arrays.py · NUEVO test unitario

Fuente única respetada: run_sequence sigue siendo el único decisor. Los nuevos
campos son INFORMACIÓN, no cambian el flujo sweep→displace→BOS→return.

---------------------------------------------------------------------
3. API PROPUESTA (metadatos, sin romper lo existente)
---------------------------------------------------------------------

detectors/fvg.py — tras detect_fvg:
  data["pd_type"] = np.where(data["fvg_bullish"]|data["fvg_bearish"], "FVG", "NONE")
  data["pd_tier"] = "T2"   # FVG es tier 2 por defecto (libro 21 §2)
  # BPR (T1): FVG que coincide en zona con OB del mismo TF → marcar T1.
  # (el cruce FVG/OB se calcula en data_feed tras ambos detectores)

detectors/ob.py — tras detect_order_blocks:
  # tipo por morfología:
  #  - OB normal            → "OB"        (T2)
  #  - vela de rechazo fuerte (body_ratio>0.7 y mecha opuesta larga) → "REJECTION_BLOCK" (T3)
  #  - OB que mitiga un FVG previo → "MITIGATION_BLOCK" (T3)
  #  - OB de continuación post-BOS → "PROPULSION" (T2)
  #  - estructura rota que se respeta como soporte/resistencia → "BREAKER" (T1/T2)
  # tier: BREAKER>=T1, OB/PROPULSION=T2, REJECTION/MITIGATION=T3

data_feed.py — tras detect_fvg + detect_order_blocks:
  # cruzar: si FVG y OB caen en misma zona de precio → ambos pd_tier="T1" (BPR)
  # armar MarketObject con meta={"pd_type":..., "pd_tier":...}

---------------------------------------------------------------------
4. VERIFICACIÓN DE CALL SITE (Ruben rule: prueba empírica de cableo)
---------------------------------------------------------------------

NO basta con "el test de la función aislada pasa". Debe verificarse el CALL SITE real:

  (a) Unitario: tests/test_fase_b1_pd_arrays.py
      - detect_fvg produce pd_type=="FVG", pd_tier=="T2".
      - detect_order_blocks produce tipos correctos en un caso sintético.
      - BPR (FVG+OB misma zona) → ambos pd_tier=="T1".
  (b) Call site real: smoke test sobre un símbolo real (EURUSD M15, 8000 velas):
      - ejecutar evaluate_signals(...) antes y después del cambio.
      - assert: MISMA lista de señales (n_changed == 0) — los metadatos no alteran
        la decisión (fuente única R7 intacta).
      - assert: las señales ahora llevan meta pd_type/pd_tier accesible.
  (c) Regresión: los tests existentes test_bos_choch_regression / test_detectors
      siguen PASS (PRE/POST dN=0, dPF=0).

Solo si (a)+(b)+(c) pasan → el cableo es real, no ilusorio.

---------------------------------------------------------------------
5. RIESGOS Y MITIGACIÓN
---------------------------------------------------------------------

  R1 (romper fuente única): los nuevos campos son metadatos; run_sequence no los
      usa para decidir. Smoke test (b) lo garantiza (n_changed==0).
  R2 (BPR mal detectado): tolerancia de "misma zona" en % de ATR; si duda, dejar
      T2 (no inflar T1). Parámetro explícito, decisión de ing etiquetada R3.
  R3 (perf): añadir columnas vectorizadas (numpy/pandas), sin loop por barra en
      el hot path. Ya detect_fvg/ob son vectorizados; se mantiene.
  R4 (ambigüedad tipo): frontera REJECTION vs OB normal es decisión de ing (§4
      SPEC). Se documenta en el código y en el DECISION_LOG.

---------------------------------------------------------------------
6. COMMIT (hecho — DEC-009g)
---------------------------------------------------------------------

Commit DEC-009g: "Fase B1: PD Arrays completos + tiers/stacking (metadatos)".
Incluye: los 5 archivos de código + test nuevo + smoke test + este plan +
ROADMAP_TESIS_DRIVEN §4/§9 actualizados (B1 DONE) + DECISION_LOG DEC-009g.

VERIFICACIÓN REALIZADA (Ruben rule: prueba empírica de cableo):
  (a) tests/test_fase_b1_pd_arrays.py — 5 passed (FVG T2, OB/REJECTION T2/T3,
      BPR->T1, translation propaga meta, run_sequence end-to-end).
  (b) tests/_smoke_b1_stash.py — EURUSD M15 REAL: B1=2 señales == baseline=2
      señales. Los metadatos NO alteran la decisión de run_sequence (R7 intacta).
  (c) Regresión: tests/test_detectors.py + test_bos_choch_regression → 53 passed.
      NOTA: test_detectors_now_requires_2_bars YA FALLA en baseline (sin B1);
      no es regresión de esta fase (verificado con git stash).

DECISIONES DE INGENIERÍA (etiquetadas R3):
  - Tolerancia BPR = 0.3 ATR; si duda, el OB queda T2 (no se infla T1).
  - BPR (FVG dentro/cerca del OB) tiene prioridad sobre MITIGATION_BLOCK (T3).
  - MITIGATION_BLOCK = OB tapa FVG previo que NO es su zona exacta.
  - REJECTION_BLOCK requiere mecha opuesta >= 1.5x el cuerpo (definición libro 21 §2).
  - Tipos finos BREAKER/MITIGATION/PROPULSION se resuelven en data_feed (cruce),
    no en los detectores aislados.

FIN — Fase B1 COMPLETADA (pendiente commit DEC-009g).
