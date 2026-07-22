> **⚠️ STALE** — Diseño v2 (2026-07-14). Nunca implementado. Sin referencias activas en el repo.

# Diseño: ventana_espera() — ventana de retorno inteligente (Piso 2, Turtle Soup)

Estado: DISEÑO v2 (ajuste conceptual de Ruben: velocidad EMPÍRICA del log,
no factor fijo). Para REVISIÓN. No implementado. No commiteado.
Fecha: 2026-07-14.

Objetivo: reemplazar el número fijo de velas (bos_gap = 40) por una ventana
de ESPERA que dependa de (1) la escala INTRÍNSECA del setup (leg del
impulso) y (2) el reloj real de la killzone. Cero indicadores externos
(NO ATR) y SIN factores fijos de conversión: la velocidad la da el LOG.

================================================================
1) ENTRADAS (lo que recibe la función)
================================================================

  - bos_ts          : timestamp (UTC) de la vela del BOS (ya cerrada).
  - bos_price       : precio del BOS (close de la vela BOS).
  - disp_price      : precio de inicio del displacement (cierre de la vela
                      del displacement, índice displace_idx). -> punto (a).
  - zone_high/zone_low : cuadro de entrada (FVG/OB ya trazado en BOS_DONE
                      por la memoria de zona del Piso 1).
  - dist_zona       : distancia actual del precio al cuadro (se mide por vela
                      en el loop; al entrar a BOS_DONE se congela con el valor
                      inicial).
  - kz_name         : killzone de la vela del BOS (London/NY AM/NY PM/fuera).
  - kz_cierre_ts    : timestamp (UTC) de cierre de esa killzone (tabla fija).
  - k_entry         : param (default 2.0). INCÓGNITA a calibrar por OOS.
  - piso_min        : param (default 20 min). Borde temporal.
  - leg_p5/leg_p95  : percentiles P5/P95 del leg histórico en ESA killzone
                      (del log, §6). Se recalculan por corrida.
  - log_df          : tabla persistente de trades resueltos (§6). Fuente de la
                      velocidad empírica. NO es un factor fijo: es el histórico.

  NOTA: ya NO hay MINUTOS_POR_LEG fijo. La velocidad se estima del log (§3).

================================================================
2) SALIDAS
================================================================

  - ventana_minutos : cuántos MINUTOS esperar el retorno desde el BOS.
  - deadline_ts     : bos_ts + ventana_minutos (cuándo expira la paciencia).
  - calibrando      : bool. True si aún no hay suficiente histórico en esa
                      killzone (usó el seed, no el empírico).
  (La función NO decide la entrada; solo da la ventana. sequence.py: si el
   precio toca la zona antes de deadline_ts -> entry; si pasa deadline ->
   reset, setup muerto.)

================================================================
3) FÓRMULA DEL CÁLCULO (paso a paso)
================================================================

  Paso 1 — leg_BOS (escala intrínseca, del (a)):
      leg_BOS = |bos_price - disp_price|
      (tamaño del impulso que rompió estructura; NO el sweep, para no mezclar
       la púa de la mecha con el cuerpo del salto.)

  Paso 2 — recorte del leg por percentiles (del (b)):
      leg_eff = clip(leg_BOS, leg_p5, leg_p95)
      (un BOS atípico gigante o un chirriado de 2 pips no distorsiona la
       escala de ESE trade. P5-P95 del histórico, no pips fijos.)

  Paso 3 — distancia a la zona:
      dist_zona = min(|close - zone_high|, |close - zone_low|)

  Paso 4 — ratio adimensional (ICT-puro: mitigación relativa al leg):
      ratio = dist_zona / leg_eff            # puede ser <1 o >1

  Paso 5 — velocidad EMPÍRICA del log (AJUSTE CONCEPTUAL):
      velocidad = velocidad_emp(kz_name, log_df, bos_ts)
        = mediana( min_reales_i / ratio_i )  sobre trades RESUELTOS ANTES de
          bos_ts, en la MISMA killzone, que SÍ retornaron.
      Si hay < MIN_TRADES_HIST en esa killzone -> velocidad = SEED_MIN_POR_LEG
      y calibrando = True (seed, no empírico).
      -> NINGÚN factor fijo por código: la velocidad la dicta el mercado
         registrado. Cambia sola entre sesiones y días.

  Paso 6 — ventana intrínseca (usa la velocidad empírica, no constante):
      ventana_intrinseca = k_entry * ratio * velocidad

  Paso 7 — límites de tiempo (§5):
      min_restante_kz = (kz_cierre_ts - bos_ts) en minutos
      ventana_minutos = clip(ventana_intrinseca, piso_min, max(piso_min, min_restante_kz))
      si min_restante_kz < piso_min -> ventana_minutos = min_restante_kz
      (nunca operamos fuera de killzone)

  Paso 8 — deadline:
      deadline_ts = bos_ts + ventana_minutos

================================================================
4) MANEJO DE PERCENTILES P5–P95 (del (b))
================================================================

  - NO son números fijos en pips. Calculados DEL LOG por killzone en cada
    corrida (o cacheados entre corridas).
  - leg_p5 = percentil 5 de leg_BOS de esa killzone; leg_p95 = percentil 95.
  - Si no hay histórico (primera corrida) -> leg_eff = leg_BOS (sin recorte)
    y se marca para recalibrar. Evita división por cero (leg_BOS<=0 -> leg_eff
    = leg_p5 si >0, sino un epsilon).
  - La escala se adapta sola al régimen de cada killzone.

================================================================
5) LÍMITES DE TIEMPO Y BORDE TEMPORAL (de Claude)
================================================================

  - TOPE DURO = reloj de la killzone (kz_cierre_ts). Fuera de killzone cambia
    el régimen de liquidez; setup que no mitigó a tiempo es OTRA cosa.
  - PISO MÍNIMO = piso_min (20 min). Evita matar setups válidos por borde
    temporal (BOS cerca del cierre).
  - CASO BORDE: si min_restante_kz < piso_min (BOS en los últimos minutos de
    la sesión) -> NO forzamos el piso; ventana = min_restante_kz. No operamos
    fuera de killzone. Setup tarde muere; son pocos y es correcto.
  - Si el BOS cae FUERA de toda killzone -> el filtro existente no debería
    dejarlo llegar; si llega, tope MAX_ESPERA_MIN (240 min) para no colgar.

================================================================
6) SISTEMA DE LOGS (del (c), AMPLIADO por pedido de Ruben)
================================================================

  Archivo: data/metrics/sequence_retorno_log.parquet (append incremental,
  persistente entre corridas).

  SE ESCRIBE LA FILA AL RESOLVER EL TRADE (retorno o muerte por deadline),
  no al detectar el BOS: así tiempo_real y error se conocen al cerrar.

  Columnas (exactas, según tu pedido):
    - bos_ts                 : timestamp del BOS
    - symbol                 : par
    - kz_name                : killzone ("London Open"/"New York AM"/"New York PM"/"fuera")
    - leg_original           : leg_BOS (tu "Leg original")
    - leg_recortado          : leg_eff (tu "Leg recortado", tras P5-P95)
    - ratio                  : dist_zona / leg_eff (tu "Ratio distancia/leg")
    - tiempo_esperado        : ventana_minutos calculada en el BOS (Paso 7)
    - retorno                : "Sí" / "No" (tu "Retornó")
    - tiempo_real            : minutos hasta el retorno (tu "Tiempo real hasta el retorno");
                               NaN si retorno = "No"
    - error                  : tiempo_real - tiempo_esperado (tu "Error entre ambos");
                               NaN si no retornó
    - deadline_ts            : cuándo expiraba la paciencia
    - entro                  : bool (si hubo entry)
    - calibrando             : bool (velocidad usó seed, no empírico)
    - k_entry                : param usado

  Para qué sirve:
    - velocidad_emp (§3 Paso 5) = mediana(min_reales/ratio) de filas con
      retorno="Sí" y bos_ts < actual, misma killzone. Causal (sin look-ahead).
    - leg_p5/leg_p95 se recalculan de aquí por killzone.
    - Al barrer k_entry en {1,2,3,4} (OOS), ya tenés la serie empírica; no
      optimizás en vacío.
  El log se escribe SIEMPRE, aunque hoy no lo usemos para calibrar.

================================================================
7) INTERACCIÓN CON LA KILLZONE
================================================================

  - El filtro de killzone YA existe y decide si el SETUP arranca (solo
    London/NY AM/NY PM pasan).
  - ventana_espera() USA el cierre de esa killzone como tope de la espera.
  - Si el retorno no ocurre antes del cierre -> setup muerto, no entra.
  - Killzone filtra el INICIO; su reloj limita la ESPERA. Coherente con ICT.

================================================================
8) DÓNDE SE CONECTA EN EL CÓDIGO
================================================================

  ict_backtest/sequence.py, fase BOS_DONE:
    - Hoy: espera `i - state.bos_idx > cfg.bos_gap` (40 velas) por vela.
    - Nuevo: al entrar a BOS_DONE, calcular ventana_min = ventana_espera(...)
      con velocidad empírica del log; deadline_ts = bos_ts + ventana_min.
      En la fase de espera:
        si row.time > deadline_ts -> state.reset()  (muerto)
        si _touches_zone(row, zona) -> entry
      El conteo de velas se reemplaza por comparación de TIEMPO.
  ict_backtest/run_backtest.py, max_hold de trades abiertos:
    - Hoy: max_hold = 16 velas fijas.
    - Nuevo: max_hold en MINUTOS con param k_hold SEPARADO (§9).

================================================================
9) PARÁMETROS (las INCÓGNITAS que pediste)
================================================================

  - k_entry        : default 2.0. Se calibra con barrido OOS {1,2,3,4} usando
                     el log. Elije el que maximice PF con n>=30 y mayor % de
                     cierres por TP.
  - k_hold         : default = k_entry al inicio, luego DIVERGE (Claude: el
                     trade-off riesgo/tiempo no es simétrico entre esperar
                     entrada y sostener posición). Param separado desde el día 1.
  - SEED_MIN_POR_LEG : default 30 min (SOLO seed cuando no hay histórico en la
                     killzone). NO es factor fijo de producción: se reemplaza
                     por velocidad empírica en cuanto hay MIN_TRADES_HIST.
  - MIN_TRADES_HIST : umbral (ej. 10) para usar velocidad empírica en vez del
                     seed. Por killzone.
  - piso_min       : 20 min (borde temporal).
  - leg_p5/leg_p95 : calculados del log por killzone (no fijos).
  - MAX_ESPERA_MIN : 240 min (fallback fuera de killzone).

  Ningún número de conversión es "mágico": k y el umbral se llenan con OOS;
  la velocidad y los percentiles se llenan con el log. El "40 velas" muere.

================================================================
10) PSEUDOCÓDIGO
================================================================

  def velocidad_emp(kz_name, log_df, bos_ts, min_trades=10, seed=30.0):
      hist = log_df[(log_df.kz_name == kz_name) &
                    (log_df.bos_ts < bos_ts) &
                    (log_df.retorno == "Sí")]
      if len(hist) < min_trades:
          return seed, True          # calibrando: usamos seed
      vel = (hist["tiempo_real"] / hist["ratio"]).median()   # min por unidad ratio
      return vel, False

  def ventana_espera(bos_ts, bos_price, disp_price, zone_high, zone_low,
                     dist_zona, kz_name, kz_cierre_ts, k_entry, piso_min,
                     leg_p5, leg_p95, log_df):
      leg_BOS = abs(bos_price - disp_price)
      leg_eff = clip(leg_BOS, leg_p5, leg_p95) if leg_BOS > 0 else (leg_p5 or 1e-6)
      ratio = dist_zona / leg_eff
      velocidad, calibrando = velocidad_emp(kz_name, log_df, bos_ts)
      ventana_intrinseca = k_entry * ratio * velocidad
      if kz_name in KZ_CIERRE:
          min_restante = (kz_cierre_ts - bos_ts).total_seconds()/60
          tope = min_restante
      else:
          tope = MAX_ESPERA_MIN
      ventana_min = clip(ventana_intrinseca, piso_min, max(piso_min, tope))
      ventana_min = min(ventana_min, tope)
      return ventana_min, calibrando

  (La dist_zona se reevalúa por vela en el loop; la ventana se congela al
   entrar a BOS_DONE con dist_zona inicial. La velocidad se estima UNA vez
   por trade, causal, desde el log. ICT-style: la paciencia se fija una vez.)

================================================================
11) COMPARACIÓN DE RENDIMIENTO (cómo medir vs versión actual)
================================================================

  Correr run_backtest EURUSD H4->M15 (y GBPUSD) DOS veces:
    A) Versión actual: bos_gap = 40 velas fijas.
    B) ventana_espera(): leg-BOS + velocidad empírica del log + killzone-reloj
       + piso + log ampliado.
  Métricas (mismo periodo, mismos datos):
    - n señales
    - PF, WR, expectancy (R/trade)
    - % cierres por TP vs % por hold_limit (B debe bajar hold_limit)
    - distribución de minutos hasta entry (B debe agruparse en killzone)
    - bias del error (media de tiempo_real - tiempo_esperado): si es
      sistemáticamente positivo, k_entry < 1 sube; si negativo, k_entry > 1.
      Esto calibra k sin OOS ciego.
  Criterio de éxito de B: PF_B >= PF_A Y n_B >= 30 Y %hold_limit_B < %hold_limit_A.

================================================================
12) LO QUE NO HACEMOS (gate OU / Fase 3 futura)
================================================================

  - OU (Ornstein-Uhlenbeck) QUEDA BLOQUEADA hasta que un diag confirme
    reversión real (μ != 0) DENTRO de la killzone. Si μ≈0 (random walk),
    first-passage con μ=0 diverge igual y OU no salva. El log (§6) es el gate:
    si la velocidad empírica es estable y el error no diverge, first-passage
    simple alcanza; si no, se reconsidera OU.
  - No tocamos max_hold con la misma k que la entrada (k_hold separado).

================================================================
13) RIESGOS / EDGE CASES
================================================================

  - leg_BOS = 0 -> anti división por cero con leg_p5/epsilon.
  - Poca historia en una killzone -> seed + calibrando=True (transparente).
  - killzone desconocida -> tope MAX_ESPERA_MIN.
  - BOS en borde de cierre -> ventana = min_restante (no forzamos piso).
  - Look-ahead: velocidad_emp usa SOLO trades con bos_ts < actual (ventana
    expansiva causal). Sin futuro. El log es persistente entre corridas, pero
    al estimar para el trade T solo se usa histórico anterior a T.
  - Log crece -> append parquet por fecha, no rewrite.
  - TZ: bos_ts/kz_cierre en UTC; killzone_en ya usa UTC (rules.py).

================================================================
14) ORDEN DE IMPLEMENTACIÓN (cuando apruebes)
================================================================

  1) Log persistente: esquema + append al resolver trade (§6).
  2) velocidad_emp() con ventana expansiva causal (§10).
  3) ventana_espera() en sequence.py (reemplaza min_por_leg fijo).
  4) Reemplazar bos_gap por velas con deadline_ts en BOS_DONE.
  5) max_hold -> minutos con k_hold en run_backtest.
  6) Tests unitarios: leg recortado, velocidad seed vs empírica, piso, tope
     killzone, borde temporal, sin look-ahead.
  7) Backtest A vs B y tabla de comparación + reporte de bias de error.
  8) (Sin commit hasta tu "haz commit y push".)
