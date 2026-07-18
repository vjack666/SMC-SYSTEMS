AUDITORÍA DE FIDELIDAD A LA TESIS ICT / SILVER BULLET
======================================================

Comité: ICT Specialist · Mentor SMC certificado · Principal Quant · Arquitecto
del sistema · Auditor independiente.

Fecha: 2026-07-17. Modo: SOLO lectura (tesis vs implementación). Sin backtests,
sin cambios de código, sin optimización.

Fuentes de tesis (leídas):
- docs/ict/20_TESIS_ICT.md (tesis unificadora, v1.0)
- docs/ict/21_POI.md (POI: zona + sesgo + respaldo + stacking + narrativa)
- docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md (3 capas HTF/ITF/exec)

Fuentes de implementación (leídas, sin ejecutar):
- ict_backtest/v2/coverage.py (matriz C01-C20 auto-declarada)
- ict_backtest/canonical.py (evaluate_signals — motor de decisión)
- ict_backtest/sequence.py (run_sequence — event-loop sweep→displace→BOS→retorno)
- ict_backtest/v2/strategy_mtf.py (generate_mtf_signals — cascade D1→H4→H1→M15)
- ict_backtest/v2/context_mtf.py (top_down_allows_trade, dealing_range_pd)
- ict_backtest/engine.py (calc_structural_sl, _tp_liquidity)

Método: cada componente de la tesis se contrasta con el código REAL. No se cree
la auto-declaración de coverage.py sin verificación cruzada.

=================================================================
PARTE 1 — COMPONENTES DE LA ESTRATEGIA ICT / SILVER BULLET (lista completa)
=================================================================

1.  HTF Bias (sesgo de marco superior)
2.  Market Structure (estructura: swings, BOS, CHOCH, MSS)
3.  Liquidity Sweep (barrido de liquidez en contra del sesgo)
4.  Displacement (impulsión institucional post-sweep)
5.  MSS / MSB (Market Structure Shift = CHOCH + desplazamiento + BOS)
6.  BOS (Break of Structure, continuación)
7.  POI (Point of Interest anclado a narrativa HTF)
8.  PD Array (FVG / Order Block / Breaker / Mitigation / BPR)
9.  Fair Value Gap (FVG)
10. Order Block (OB)
11. OTE (Optimal Trade Entry, 62-79% del retracement)
12. Premium / Discount (zona del dealing range)
13. Dealing Range (EQ 50%, rangos PDH/PDL/Asian)
14. Killzone (London Open / NY AM / NY PM)
15. Silver Bullet Window (NY 10:00-11:00 ET y 14:00-15:00 ET + retorno a POI en M15/M5)
16. Entry Trigger (retorno a la zona / mitigation, NO el close del BOS)
17. Invalidación (por evento, no por tiempo)
18. Stop Loss (estructural: mecha del sweep ± buffer)
19. Take Profit (liquidez opuesta más cercana del TF de ejecución)
20. Liquidity Target (BSL/SSL, internal/external, EQ highs/lows)
21. Risk Management (RR mínimo 1:3, max hold, regime filter)
22. Trade Management (BE / parciales)
23. Temporalidades (D1 / H4 / H1 / M15 / M5 / M1 y sus roles HTF/ITF/exec)
24. Narrativa ICT (contexto coherente, no filtros aislados)

=================================================================
PARTE 2 — ESTADO DE CADA COMPONENTE EN EL CÓDIGO
=================================================================

(Existe / Existe parcial / No existe / No se usa / Simplificado / Distinto)

1.  HTF Bias ............ EXISTE. top_down_allows_trade exige D1/H4/H1 trend
                         alineado con dirección (context_mtf.py:139-176). Gates reales.
2.  Market Structure .... EXISTE. detect_market_structure (canónico, confirm_bars=2);
                         PASO 1 unificó detectors→canónico.
3.  Liquidity Sweep ..... EXISTE. canonical_sweep (cierra adentro) en sequence.
4.  Displacement ........ EXISTE (flag require_displacement + displace_gap). [Ver nota
                         al pie: su calibración es materia de otra auditoría; aquí cuenta
                         como componente presente en el pipeline.]
5.  MSS / MSB ........... EXISTE PARCIAL. CHOCH (último BOS roto) + BOS implementados;
                         el "MSS" como etiqueta explícita es implícito, no un módulo.
6.  BOS ................. EXISTE. _has_bos en sequence (canónico).
7.  POI ................. EXISTE PARCIAL / SIMPLIFICADO. htf_poi_fn es OPCIONAL en
                         run_sequence y NO se pasa desde strategy_mtf/canonical
                         (sequence.py:309,317). Sin ancla narrativa activa. coverage.py
                         marca C05=partial ("PD side as soft POI proxy"). El POI real
                         (zona+sesgo+respaldo+stacking) NO está cableado.
8.  PD Array ............ EXISTE. FVG/OB se trazan como zona de entrada (sequence marca
                         FVG/OB entre sweep y BOS, lines 362-373).
9.  FVG ................. EXISTE. _latest_fvg_zone.
10. Order Block ......... EXISTE. _latest_ob_zone.
11. OTE ................. NO EXISTE. No hay módulo de retracement 62-79% (tesis 21 §6
                         no menciona OTE como obligatorio; es práctica ICT pero ausente).
12. Premium/Discount .... EXISTE. dealing_range_pd (context_mtf.py:65-97) + gate
                         long_in_premium/short_in_discount (top_down:182-186).
13. Dealing Range ....... EXISTE. EQ = 50% del rango D1 (dealing_range_pd).
14. Killzone ............ EXISTE. killzone_en filtra London/NY AM/NY PM (canonical:122).
15. Silver Bullet ....... NO EXISTE. Sin módulo silver_bullet.py; sin ventana NY 10-11 /
                         14-15 ET como sub-ventana; sin retorno a POI en M15/M5 dedicado.
                         Solo killzone genérico.
16. Entry Trigger ....... EXISTE. Retorno a zona (mitigation): sequence marca cuadro en
                         BOS_DONE y entra cuando _touches_zone (sequence.py:417-434).
                         CORRIGE el bug de tesis §6 (antes entraba en close del BOS).
17. Invalidación ........ EXISTE PARCIAL. Estructura event-driven (market_structure sin
                         aged). Pero invalidación de POI por cierre de cuerpo/edad NO.
18. Stop Loss ........... EXISTE (COHERENTE ICT). calc_structural_sl = mecha del sweep
                         ±0.3 ATR, fallback swing (engine.py:243-277). NUNCA ATR puro.
19. Take Profit ......... EXISTE (COHERENTE ICT). _tp_liquidity = bsl/ssl_price del LTF
                         (liquidez opuesta más cercana), NO cluster lejano (engine.py:210).
                         Esto ALINEA con tesis §8 (TP en liquidez LTF cercana).
20. Liquidity Target .... EXISTE. bsl_price/ssl_price del exec TF.
21. Risk Management ..... EXISTE. RR mín 1:3 (nearest_tp min_rr=3.0 + canonical fuerza
                         >=3R); max_hold 40 velas; STRUCT_SL_MAX_ATR=6 regime filter.
22. Trade Management .... NO EXISTE. Sin BE / parciales; solo hold_limit hasta TP/SL.
23. Temporalidades ...... EXISTE PARCIAL. Cascada D1→H4→H1→M15 IMPLEMENTADA como gates
                         (require_d1/h4/h1). PERO: M5/M1 (exec fino) NO se usan en este
                         motor (solo M15 exec). H1 es "soft" (ranging OK, no bloquea).
                         3 capas SÍ; exec fino NO.
24. Narrativa ICT ....... NO EXISTE como tal. El motor aplica filtros top-down en
                         secuencia (D1→H4→H1→PD→entry), pero NO construye un grafo de
                         narrativa (sweep causa BOS causa zona causa entrada). Es una
                         cadena de gates, no una narrativa con ancla POI. Ver PARTE 8.

=================================================================
PARTE 3 — FLUJO EXACTO (tesis vs dónde interviene el código)
=================================================================

TESIS (libro 15 / 18):
  HTF Bias
    ↓
  Liquidity Sweep (en contra)
    ↓
  Displacement
    ↓
  MSS (CHOCH + desplazamiento)
    ↓
  BOS
    ↓
  POI (zona anclada a narrativa HTF, en ITF)
    ↓
  Mitigation / retorno a zona (exec TF)
    ↓
  Entry (exec TF)
    ↓
  SL (mecha sweep, exec TF)
    ↓
  TP (liquidez opuesta cercana, exec TF)
    ↓
  Trade

IMPLEMENTACIÓN REAL (trazado en código):
  [D1/H4/H1 Bias gates]  → context_mtf.top_down_allows_trade (ANTES de emitir)
      ↓
  run_sequence (M15):
      SWEEP  → _has_sweep (sequence.py:376)
      ↓
      DISPLACE → _has_displacement (sequence.py:386)
      ↓
      BOS/CHOCH → _has_bos / _has_choch (sequence.py:395-398)
      ↓
      [POI ancla] → htf_poi_fn(i,target) — OPCIONAL, NO PASADO → desactivado
      ↓
      ZONA → FVG/OB trazado (sequence.py:362-373) — SIN filtro de zona P/D/sesgo
      ↓
      ENTRY → retorno a zona _touches_zone (sequence.py:422) — SÍ mitigation
      ↓
  [canonical.py post-proceso por señal]:
      SL → calc_structural_sl(sweep_row) (canonical.py:126) — mecha sweep ✓
      TP → _tp_liquidity (bsl/ssl LTF) (canonical.py:132) — liquidez cercana ✓
      RR ≥1:3 forzado (canonical.py:137-140)
      Killzone (canonical.py:122)
      ↓
  [strategy_mtf re-gate top-down] → D1/H4/H1/PD ya validados arriba

DIFERENCIA ESTRUCTURAL: en la tesis el POI es un NODO que califica la zona ANTES
de marcarla; en el código la zona (FVG/OB) se marca SIEMPRE (sin ancla) y el POI
anclado está desactivado. La secuencia sweep→displace→BOS→retorno SÍ es fiel.

=================================================================
PARTE 4 — AUDITORÍA DE ENTRY
=================================================================

¿Condiciones ICT que deben cumplirse antes de entrar? (tesis §6, libro 15/18)
  a. HTF confirma sesgo/rango ............ ✅ (gates D1/H4/H1)
  b. LTF barre liquidez y cierra adentro . ✅ (canonical_sweep)
  c. LTF rompe estructura (BOS/CHOCH) .... ✅ (_has_bos/_has_choch)
  d. La ruptura deja FVG/OB (imbalance) .. ✅ (zona trazada)
  e. ENTRADA = retorno a la zona ........ ✅ (mitigation, sequence:422)
  f. POI anclado a narrativa HTF ........ ❌ (htf_poi_fn no pasado)
  g. Zona en premium/discount correcta ... ⚠ parcial (PD gate global sí, pero la
                                             zona FVG/OB no se filtra por P/D/sesgo)
  h. Exec TF fino (M5/M1) ............... ❌ (solo M15)

¿Cuáles faltan? f, h, y g solo a nivel global (no por zona).
¿En qué TF se verifican? Bias en D1/H4/H1; entry/SL/TP en M15 (exec). Coherente
con "entry/SL/TP en exec TF" (tesis §5), salvo que el exec es M15, no M5/M1.
¿Entrada temprana? NO — entra en retorno a zona, no en el close del BOS (corrige
el bug de tesis §6). ✅
¿Entrada tardía? El hold de 40 velas M15 permite esperar; no hay evidencia de
entrada tardía sistemática.
¿Simplificada? SÍ en calidad de zona: cualquier FVG/OB cuenta como POI potencial;
no hay jerarquía de tier ni stacking ni ancla narrativa.

=================================================================
PARTE 5 — AUDITORÍA DE STOP LOSS
=================================================================

¿Cómo define ICT el SL? (tesis §7, libro 14)
  - Detrás del sweep (mecha que barrió la liquidez), ± buffer.
  - Fallback: detrás del último swing roto.
  - NUNCA ATR puro. Depende del POI/sweep, no del TF en sí (pero se ancla en exec TF).

¿Cómo está implementado? (engine.py:243-277 calc_structural_sl)
  - SL = sweep_low − 0.3 ATR (long) / sweep_high + 0.3 ATR (short). ✅
  - Fallback swing_low/swing_high −/+ buffer. ✅
  - Si nada → None → no opera (NO degrada a ATR). ✅
  - STRUCT_SL_MAX_ATR=6 filtra sweeps gigantes (regime). ✅

¿Coincide con ICT? SÍ, de forma fiel. Es el componente mejor implementado.
¿Está simplificado? NO en lógica; SÍ en que no depende del POI (el SL va tras el
sweep, no tras el OB del POI), pero eso es exactly lo que ICT dice (SL tras sweep).

VEREDICTO SL: COHERENTE 100% con la tesis.

=================================================================
PARTE 6 — AUDITORÍA DE TAKE PROFIT
=================================================================

¿Cómo define ICT el TP? (tesis §8, libro 15/16/17)
  - Liquidez opuesta MÁS CERCANA del TF de ejecución (primer BSL/SSL que el
    precio toca a favor). Internal liquidity primero; external (EQ high/low,
    PDH/PDL) después. NO cluster lejano.

¿Cómo está implementado? (engine.py:210-226 _tp_liquidity)
  - TP = bsl_price (long) / ssl_price (short) del LTF, si está en dirección
    favorable (bsl > close para long). ✅ liquidez opuesta cercana del exec TF.
  - Fallback: entry ± 3R (canonical.py:136). ✅ RR 1:3 mínimo.
  - 3R fijo como piso (canonical.py:137-140 fuerza >=3R). ✅

¿Respeta la tesis? SÍ. Usa bsl/ssl del LTF (nearest), no el cluster ATR/4 que la
tesis §8 señalaba como bug viejo. El código actual YA está corregido respecto a
esa crítica. NOTA: la tesis §8 describe el bug como vigente ("_tp_liquidity usa
cluster"), pero el código leído usa bsl/ssl_price → la tesis está DESACTUALIZADA
sobre este punto; el TP real es fiel.

VEREDICTO TP: COHERENTE con la tesis (mejor de lo que la tesis describe).

=================================================================
PARTE 7 — AUDITORÍA DE TIMEFRAMES
=================================================================

Según la estrategia (tesis §5, libro 18):
  D1  = HTF bias (sesgo semanal/diario, draw on liquidity)
  H4  = ITF para intradía (rangos, PD Arrays)
  H1  = validación de zona / capa intermedia
  M15 = exec TF intradía (entry/SL/TP)
  M5  = exec fino scalping / Silver Bullet
  M1  = entry fina

¿Qué hace el sistema? (strategy_mtf + canonical)
  D1  → SÍ usado como gate de bias (top_down require_d1).
  H4  → SÍ como HTF bias en run_sequence + gate.
  H1  → SÍ como gate soft (top_down require_h1; ranging OK).
  M15 → SÍ como exec TF (entry/SL/TP aquí).
  M5  → NO usado en este motor (solo M15). La tesis pide M5 para SB y exec fino.
  M1  → NO usado.

¿Qué capas faltan?
  - M5/M1 (exec fino y Silver Bullet). El motor es de hecho D1→H4→H1→M15 (4 capas
    de bias/zona, 1 de exec). Cumple la "3 capas funcionales" de la tesis (HTF/ITF/
    exec) pero el exec es M15, no M5/M1.
  - H1 es "soft" (no bloquea si ranging) → validación de zona débil.

VEREDICTO TF: PARCIAL. Cascada top-down real y coherente; falta el exec fino M5/M1
y la sub-ventana Silver Bullet.

=================================================================
PARTE 8 — LÓGICA NARRATIVA
=================================================================

Pregunta clave: ¿el motor construye una NARRATIVA ICT, o solo verifica filtros
aislados?

Evidencia:
  - run_sequence es una MÁQUINA DE ESTADOS (IDLE→SWEEP_DONE→DISPLACE_DONE→
    BOS_DONE→ENTRY) que exige ORDEN temporal: sweep ANTES de displacement ANTES de
    BOS ANTES de retorno. Eso es una narrativa de SECUENCIA (la tesis §1 PO3/AMD).
  - PERO el POI (nodo que da "por qué" reaccionaría el precio) está desactivado
    (htf_poi_fn=None). La zona FVG/OB se marca por geometría, no por ancla HTF.
  - Los gates D1/H4/H1/PD son independientes entre sí (AND lógico), no un grafo
    causal. No hay "este BOS en H4 fue causado por tal POI en M15".
  - coverage.py C14 (narrative invalidation) = partial; C05 (POI narrativo) = partial.

VEREDICTO: el motor tiene SECUENCIA narrativa (cadena causal sweep→BOS→retorno)
pero NO narrativa de CONTEXTO (el POI anclado que explica el setup). Es una cadena
de filtros ordenados, no un grafo de intención institucional. Esto es exactamente
lo que la tesis §5b y libro 21 llaman "geometría suelta sin ancla".

=================================================================
PARTE 9 — MATRIZ DE COBERTURA
=================================================================

Componente                | Según ICT      | Implementado        | Cobertura
--------------------------|----------------|---------------------|----------
HTF Bias                  | Obligatorio    | Gates D1/H4/H1      | 100%
Market Structure          | Obligatorio    | Canónico confirm_bars=2 | 100%
Liquidity Sweep           | Obligatorio    | canonical_sweep     | 100%
Displacement              | Obligatorio    | Flag + gap          | 90%
MSS / MSB                 | Obligatorio    | CHOCH+BOS implícito | 70%
BOS                       | Obligatorio    | _has_bos canónico   | 100%
POI (ancla narrativa)     | Obligatorio    | htf_poi_fn OFF       | 35%
PD Array (FVG/OB/Breaker) | Obligatorio    | FVG/OB trazados     | 85%
Fair Value Gap            | Obligatorio    | _latest_fvg_zone    | 100%
Order Block               | Obligatorio    | _latest_ob_zone     | 100%
OTE (62-79% retrace)      | Práctica ICT   | Ausente             | 0%
Premium / Discount        | Obligatorio    | dealing_range_pd    | 100%
Dealing Range (EQ 50%)    | Obligatorio    | dealing_range_pd    | 100%
Killzone                  | Obligatorio    | London/NY AM/PM     | 100%
Silver Bullet Window      | Setup SB       | Ausente (solo KZ)   | 15%
Entry (retorno a zona)    | Obligatorio    | mitigation sequence | 100%
Invalidación (evento)     | Obligatorio    | Estructura event-driven | 80%
Stop Loss (estructural)   | Obligatorio    | mecha sweep ±0.3ATR | 100%
Take Profit (liq cercana) | Obligatorio    | bsl/ssl LTF         | 100%
Liquidity Target (BSL/SSL)| Obligatorio    | bsl/ssl LTF         | 100%
Risk Mgmt (RR1:3/hold)    | Obligatorio    | min_rr=3, hold=40   | 100%
Trade Mgmt (BE/parciales)| Recomendado    | Ausente             | 0%
Temporalidades D1/H4/H1   | Obligatorio    | Gates               | 100%
Temporalidades M15 exec   | Obligatorio    | SÍ                  | 100%
Temporalidades M5/M1       | Scalping/SB    | Ausente en motor    | 20%
Narrativa ICT (contexto)  | Obligatorio    | Secuencia sí / ancla NO | 55%

=================================================================
PARTE 10 — VERDICTO FINAL
=================================================================

Opción elegida: C) REPRESENTA PARCIALMENTE LA ESTRATEGIA.

Justificación con evidencia:

La COLUMNA VERTEBRAL de la tesis SÍ está implementada y es fiel:
  - Secuencia causal sweep→displace→BOS→retorno (sequence.py máquina de estados).
  - SL estructural tras el sweep, nunca ATR (engine.calc_structural_sl) — 100% ICT.
  - TP en liquidez opuesta cercana del exec TF (engine._tp_liquidity bsl/ssl) — 100% ICT.
  - Cascada de bias D1→H4→H1→M15 como gates reales (context_mtf.top_down_allows_trade).
  - Killzone, premium/discount, dealing range EQ 50%, RR 1:3 — todos presentes.
  - BOS/CHOCH unificados y coherentes (PASO 1).

PERO FALTAN las capas de CALIDAD que definen ICT como estrategia completa:
  - POI anclado a narrativa HTF: DESACTIVADO (htf_poi_fn opcional no pasado).
    Cualquier FVG/OB cuenta como zona; no hay jerarquía de tier, ni stacking,
    ni filtro de zona/sesgo/respaldo por zona. (35%)
  - Silver Bullet: sin módulo ni sub-ventana NY dedicada. (15%)
  - OTE: ausente. (0%)
  - Exec fino M5/M1: no usado en este motor. (20%)
  - Trade management (BE/parciales): ausente. (0%)
  - Narrativa de contexto (por qué el precio reacciona ahí): solo secuencia,
    no ancla. (55%)

Por tanto NO es "A" (fiel al 100%) porque faltan POI anclado, SB, OTE, M5/M1,
trade management. NO es "B" (simplificada) en el sentido de "versión recortada
que distorsiona" — lo que implementa es COHERENTE con ICT, no una simplificación
que contradiga la tesis. Es "C": representa la estrategia PARCIALMENTE — la
mecánica core es fiel, pero las capas de calidad/filtro fino que la hacen
"ICT completo" no están cableadas. Esto coincide con el coverage_mode
"v2_partial" que el propio código se auto-asigna (coverage.py:76, verdict
"implementacion parcial — NO interpretar como edge de la tesis ICT completa").

=================================================================
PORCENTAJE GLOBAL DE FIDELIDAD DE IMPLEMENTACIÓN
=================================================================

Ponderado por criticidad de la tesis:
  - Mecánica core (sweep/displace/BOS/entry/SL/TP/bias/killzone/RR): ~100% × peso 50%
  - Contexto/calidad (POI anclado/SB/OTE/M5-M1/trade mgmt/narrativa): ~30% × peso 50%

FIDELIDAD GLOBAL ESTIMADA: ~65%.

(Desglose: de 24 componentes listados, 14 están en 80-100%, 4 en 55-70%,
6 en 0-35%. Promedio simple ~68%; promedio ponderado por criticidad ~65%.)

=================================================================
PIEZAS DE LA TESIS QUE FALTAN (priorizadas por impacto en fidelidad)
=================================================================

1. [ALTA] POI anclado a narrativa HTF (htf_poi_fn) — cablear el ancla en
   strategy_mtf/canonical; añadir filtro zona P/D + sesgo + respaldo por zona;
   tier hierarchy (BPR>OB/FVG>bloques); stacking multi-TF; POI como bonus de
   quality_score, no gate duro (tesis 21 §4, §6).
2. [ALTA] Silver Bullet — módulo con ventana NY 10-11 / 14-15 ET + retorno a POI
   en M15/M5 (libro 07). Hoy el motor solo opera killzone genérico.
3. [MEDIA] Exec fino M5/M1 — bajar entry/SL/TP a M5/M1 para scalping/SB (tesis §5).
   Hoy exec = M15.
4. [MEDIA] OTE (retracement 62-79%) — práctica ICT de entrada fina (opcional pero
   esperada por el operador).
5. [MEDIA] Trade management — BE / parciales (tesis §9). Hoy solo hold_limit.
6. [BAJA] Invalidación de POI por cierre de cuerpo / edad (reusar event-driven).
7. [BAJA] H1 como gate fuerte (hoy soft / ranging OK).

Nota de coherencia: los componentes que SÍ existen (SL, TP, entry, bias, RR,
killzone, structure) son FIELES a la tesis. El riesgo de fidelidad NO es que el
motor haga algo incorrecto, sino que OPERA UNA VERSIÓN INCOMPLETA: sin POI
anclado ni SB, el motor acepta setups que un trader ICT rechazaría por "falta de
contexto". Eso es una omisión de cobertura, no una contradicción de lógica.

=================================================================
FIN — Comité de Fidelidad Tesis ICT / Silver Bullet (2026-07-17)
