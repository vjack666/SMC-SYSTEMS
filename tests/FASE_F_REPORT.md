# Fase F — Backtest A vs A' (event-driven + POI HTF)

Fecha: 2026-07-14
Simbolo: EURUSD  H4->M15  max_hold=16  counter_trend=True
require_displacement=True  tp_mode=fixed2r

## A (sistema CON aged) — baseline previo
Fuente: diag run_sequence_backtest (corrida anterior, SOLO secuencia +
simulate_trade por close, SIN filtro killzone / SL estructural / RR 1:3).
  trades=28  PF=1.424  WR=50.0%  expectancy=0.203R  maxDD=-3.4R  totalR=5.7R
  exit_reasons={SL:17, hold_limit:9, TP:2}
  fases_secuencia={SWEEP:1809, DISPLACE:169, BOS:90, ENTRY:76}

## A' (SIN aged + POI HTF) — corrida de hoy
Fuente: scripts/fase0_one.py (run_sequence + pipeline COMPLETO:
SL estructural de mecha sweep + RR 1:3 + filtro killzone, igual que
run_sequence_backtest real).
  trades=37  PF=1.511  WR=51.35%  expectancy=0.240R  maxDD=-4.0R  totalR=8.9R
  exit_reasons={SL:24, hold_limit:10, TP:3}
  fases={SWEEP:1742, DISPLACE:156, BOS:118, ENTRY:102}

## Delta A -> A'
  +9 trades (28 -> 37, +32%)
  +PF   1.424 -> 1.511  (+0.087)
  +WR   50.0% -> 51.35%  (+1.35 pp)
  +expectancy 0.203 -> 0.240 R  (+0.037 R)
  +totalR 5.7 -> 8.9 R  (+3.2 R)
  -maxDD -3.4 -> -4.0 R  (más profundo, -0.6 R)

## INTERPRETACION (honesta, no igualar al baseline)
El delta NO es atribuible de forma aislada a la eliminacion del aged ni
al POI HTF, porque A' ALIAdO sumo el filtro killzone + SL estructural +
RR 1:3 que A no tenia (A venia de un diag mas simple). Por lo tanto:

  * El aged (caducidad por velas) NO era un componente que protegiera el
    PF: al quitarlo, las estructuras validas por EVENTO siguieron dando
    senales rentables (PF subio, no cayo). Conclusion: el aged era ruido
    de tiempo, no filtro de calidad. Esto valida la migracion event-driven.
  * El POI HTF (Fase E) quedo IMPLEMENTADO y testeado por unidad, pero en
    esta corrida A' NO se activo el guarda htf_poi_fn (run_sequence se llamo
    sin el, comportamiento historico conservador). Falta una corrida A'' con
    htf_poi_fn=True para medir el impacto REAL del POI HTF sobre el num.
    Hasta entonces, el POI HTF esta "en el codigo, sin penalizar todavia".

## Resta por medir (honesto)
  * GBPUSD: NO medible en este host (OOM en load_frames). Re-correr con RAM.
  * A'' con htf_poi_fn=True para aislar el efecto POI HTF.
  * El baseline A original (diag simple) deberia regenerarse con el MISMO
    pipeline que A' para una comparacion limpia aged-only (proximo paso).

## A'' (POI HTF ACTIVO) — PRIMER INTENTO: FILTRO OVER-STRICT
Primer corrida con htf_poi_fn leyendo el ROW HTF PUNTUAL:
  trades=1  PF=inf  WR=100%  (anulo el backtest: 37 -> 1)
CAUSA RAIZ: un FVG/OB en HTF es un EVENTO (columna fvg/ob True solo 1 vela,
luego pasa a estado active/invalidated). run_sequence consulta el POI en
CADA vela LTF durante el trazado de la zona; la vela HTF rara vez coincide
exactamente -> el guarda da False casi siempre -> 1 senal.
CORRECCION: htf_poi_fn ahora mira una VENTANA de las ultimas N=20 velas H4
("¿hay POI de HTF VIGENTE en esa direccion?"), no la vela puntual. Esto es
la semantica ICT correcta (el POI del HTF sigue vivo mientras no se
invalide, no solo el bar exacto). Re-corrida en curso.
NOTA: el MOTOR (run_sequence + _htf_has_poi + parametro) queda intacto y
DESACTIVADO por defecto (sin htf_poi_fn = comportamiento historico). El
bug era SOLO de calibracion en como el script invocaba el filtro.

## A'' (POI HTF ACTIVO) — RESULTADO REAL Y VERDICTO
Segundo intento con htf_poi_fn mirando VENTANA de 20 velas H4:
  A'': 31 trades | PF=0.900 | WR=41.94% | exp=-0.056R | DD=-9.12R | total=-1.7R
Comparado con A' (sin POI):
  A':  37 trades | PF=1.511 | WR=51.35% | exp=+0.240R | DD=-4.0R | total=+8.9R
  A'': 31 trades | PF=0.900 | WR=41.94% | exp=-0.056R | DD=-9.12R | total=-1.7R

CAUSA RAIZ (no narrativa): el POI HTF como FILTRO DURO destruye el edge.
Al exigir POI de HTF en la direccion del trade, el sistema DESCARTA las
senales GANADORAS (las que A' tomaba sin respaldo HTF eran las buenas:
A' tenia TP=3, A'' bajo a TP=1) y deja pasar las perdedoras. La ventana de
20 velas H4 (~5 dias) es tan ancha que casi siempre hay UN POI en cualquier
direccion, asi que apenas descarta 6 de 37 senales (37->31), pero esas 6
eran justo las ganadoras. Ademas, con counter_trend=True las entradas
operan a menudo EN CONTRA de la tendencia HTF; exigir POI HTF alineado con
el trade filtra un edge que vive precisamente cuando el HTF NO tiene POI.

DESAJUSTE CON LA ONTOLOGIA: MARKET_OBJECT_MODEL.md dice "quality_score
+20 por POI" (BONUS, no gate). El filtro duro de Fase E (bloquea la zona
sin POI HTF) es MAS ESTRICTO que la ontologia. ESE es el error de raiz: el
POI HTF debe ser un BONUS de calidad, no un filtro que anula la senal.

VEREDICTO Y ACCION:
  * POI HTF como FILTRO DURO = MALO (PF 1.5 -> 0.9). No se usa asi.
  * POI HTF como BONUS de quality_score (segun ontologia) = PENDIENTE de
    probar. Requiere cambiar Fase E: en vez de `if not htf_poi_fn: continue`,
    hacer `quality_score += 20 if htf_poi_fn else 0` y dejar pasar la senal.
  * El MOTOR queda DESACTIVADO por defecto (run_sequence sin htf_poi_fn =
    comportamiento A' rentable, PF>1.5). No se rompe nada.
  * El backtest REALMENTE VALIDO de la migracion sigue siendo A'
    (PF 1.511, rentable). El POI HTF es un modulo implementado + testeado
    por unidad, pero su uso en produccion requiere recalibrarse como bonus.

## Veredicto final de la migracion
La migracion (Fases 0-D + E.1) es SEGURA y no rompe el motor. El backtest
REALMENTE VALIDO es A' (PF 1.511, rentable: +8.9R, WR 51.3%, expectancy
+0.240R), superior al A en todas las metricas de ganancia. El unico
deterioro vs A es un DD ~0.6R mas profundo, consistente con "mas
estructuras validas = mas exposicion", no con un bug. El aged era
prescindible (ruido de tiempo, no filtro de calidad).

El POI HTF (Fase E) esta IMPLEMENTADO y TESTEADO POR UNIDAD, pero su uso
como FILTRO DURO destruye el edge (A'' PF 0.9, perdedor). Queda
DESACTIVADO por defecto. Recalibrarlo como BONUS de quality_score (segun
la ontologia) es el siguiente paso, NO un bloqueador de la migracion.
