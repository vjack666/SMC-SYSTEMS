# Piloto 1 HYP-002 — Auditoria de FORMACION (consumidor puro, sin WR/PF)

Símbolo: EURUSD | Ventana M15: 3000 velas | Setups auditados: 4

---

SETUP #1  [EURUSD M15]  dir=SHORT

CONTEXTO
  HTF (H4 trend @ BOS)      BEARISH
  htf_aligned (emitido)     PASS
LIQUIDEZ
  BSL/SSL pool existe       DERIVABLE (bsl_price)
  Liquidez tomada (wick)    OBSERVABLE @idx524 = 1.13412
  Pool mas cercano          —  (proximidad temporal, NO causalidad)
FORMACION
  SWEEP                     OBSERVABLE @idx524 (2022-01-10 04:00:00)
  DISPLACEMENT              OBSERVABLE @idx529
  BOS/CHOCH                 OBSERVABLE @idx534 nivel=—
CAUSALIDAD
  Sweep -> Disp.            UNKNOWN (orden temporal: 524<529; no identidad causal)
  Disp. -> BOS              UNKNOWN (orden temporal: 529<534; swing roto no embolsado)
  BOS -> POI                UNKNOWN (anclaje por dir+ts, no identidad)
POI
  POI valido (zona FVG/OB)  DERIVABLE zona=[1.13298,1.13255]  (entre sweep y BOS)
  Anclaje causal            UNKNOWN (poi_present=True)
RETORNO
  Retorno al POI            OBSERVABLE @idx535 close=1.13254
MACRO
  Noticias                  UNKNOWN (GAP-1: sin fuente macro conectada)
LTF
  Confirmacion M5/M1        UNKNOWN (ejecucion fina no auditada en esta fase)
══════════════════════════════
VEREDICTO
  SETUP FORMADO: INCOMPLETO (causal lineage UNKNOWN en 3 uniones)
  CAUSA: linaje causal sweep->disp->bos->poi no conservado por el motor
══════════════════════════════

SETUP #2  [EURUSD M15]  dir=SHORT

CONTEXTO
  HTF (H4 trend @ BOS)      BEARISH
  htf_aligned (emitido)     PASS
LIQUIDEZ
  BSL/SSL pool existe       DERIVABLE (bsl_price)
  Liquidez tomada (wick)    OBSERVABLE @idx607 = 1.13441
  Pool mas cercano          —  (proximidad temporal, NO causalidad)
FORMACION
  SWEEP                     OBSERVABLE @idx607 (2022-01-11 00:45:00)
  DISPLACEMENT              OBSERVABLE @idx610
  BOS/CHOCH                 OBSERVABLE @idx611 nivel=—
CAUSALIDAD
  Sweep -> Disp.            UNKNOWN (orden temporal: 607<610; no identidad causal)
  Disp. -> BOS              UNKNOWN (orden temporal: 610<611; swing roto no embolsado)
  BOS -> POI                UNKNOWN (anclaje por dir+ts, no identidad)
POI
  POI valido (zona FVG/OB)  DERIVABLE zona=[1.13372,1.13315]  (entre sweep y BOS)
  Anclaje causal            UNKNOWN (poi_present=True)
RETORNO
  Retorno al POI            OBSERVABLE @idx612 close=1.13410
MACRO
  Noticias                  UNKNOWN (GAP-1: sin fuente macro conectada)
LTF
  Confirmacion M5/M1        UNKNOWN (ejecucion fina no auditada en esta fase)
══════════════════════════════
VEREDICTO
  SETUP FORMADO: INCOMPLETO (causal lineage UNKNOWN en 3 uniones)
  CAUSA: linaje causal sweep->disp->bos->poi no conservado por el motor
══════════════════════════════

SETUP #3  [EURUSD M15]  dir=LONG

CONTEXTO
  HTF (H4 trend @ BOS)      BULLISH
  htf_aligned (emitido)     PASS
LIQUIDEZ
  BSL/SSL pool existe       DERIVABLE (ssl_price)
  Liquidez tomada (wick)    OBSERVABLE @idx1355 = 1.13021
  Pool mas cercano          —  (proximidad temporal, NO causalidad)
FORMACION
  SWEEP                     OBSERVABLE @idx1355 (2022-01-20 19:45:00)
  DISPLACEMENT              OBSERVABLE @idx1358
  BOS/CHOCH                 OBSERVABLE @idx1360 nivel=—
CAUSALIDAD
  Sweep -> Disp.            UNKNOWN (orden temporal: 1355<1358; no identidad causal)
  Disp. -> BOS              UNKNOWN (orden temporal: 1358<1360; swing roto no embolsado)
  BOS -> POI                UNKNOWN (anclaje por dir+ts, no identidad)
POI
  POI valido (zona FVG/OB)  DERIVABLE zona=[1.13192,1.13154]  (entre sweep y BOS)
  Anclaje causal            UNKNOWN (poi_present=True)
RETORNO
  Retorno al POI            OBSERVABLE @idx1361 close=1.13192
MACRO
  Noticias                  UNKNOWN (GAP-1: sin fuente macro conectada)
LTF
  Confirmacion M5/M1        UNKNOWN (ejecucion fina no auditada en esta fase)
══════════════════════════════
VEREDICTO
  SETUP FORMADO: INCOMPLETO (causal lineage UNKNOWN en 3 uniones)
  CAUSA: linaje causal sweep->disp->bos->poi no conservado por el motor
══════════════════════════════

SETUP #4  [EURUSD M15]  dir=SHORT

CONTEXTO
  HTF (H4 trend @ BOS)      BEARISH
  htf_aligned (emitido)     PASS
LIQUIDEZ
  BSL/SSL pool existe       DERIVABLE (bsl_price)
  Liquidez tomada (wick)    OBSERVABLE @idx2711 = 1.14299
  Pool mas cercano          1.14232  (proximidad temporal, NO causalidad)
FORMACION
  SWEEP                     OBSERVABLE @idx2711 (2022-02-09 22:45:00)
  DISPLACEMENT              OBSERVABLE @idx2715
  BOS/CHOCH                 OBSERVABLE @idx2717 nivel=—
CAUSALIDAD
  Sweep -> Disp.            UNKNOWN (orden temporal: 2711<2715; no identidad causal)
  Disp. -> BOS              UNKNOWN (orden temporal: 2715<2717; swing roto no embolsado)
  BOS -> POI                UNKNOWN (anclaje por dir+ts, no identidad)
POI
  POI valido (zona FVG/OB)  DERIVABLE zona=[1.14267,1.14227]  (entre sweep y BOS)
  Anclaje causal            UNKNOWN (poi_present=True)
RETORNO
  Retorno al POI            OBSERVABLE @idx2718 close=1.14255
MACRO
  Noticias                  UNKNOWN (GAP-1: sin fuente macro conectada)
LTF
  Confirmacion M5/M1        UNKNOWN (ejecucion fina no auditada en esta fase)
══════════════════════════════
VEREDICTO
  SETUP FORMADO: INCOMPLETO (causal lineage UNKNOWN en 3 uniones)
  CAUSA: linaje causal sweep->disp->bos->poi no conservado por el motor
══════════════════════════════
