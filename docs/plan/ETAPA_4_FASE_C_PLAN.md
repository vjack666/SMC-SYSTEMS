ETAPA 4 — FASE C: SISTEMA DE PERCEPCIÓN DE AUTORIDAD DE ZONAS
================================================================

Estado: DISEÑO (no toca el motor). Fase B1 DONE (metadatos pd_type/pd_tier).
Roadmap maestro: ROADMAP_TESIS_DRIVEN_2026-07-17.md §4 Fase C (C1 POI anclado).
Regla de oro del roadmap: se acepta por FIDELIDAD A LA TESIS (§5), NO por PF.

ESTADO DE REVISIÓN: APROBADO CON AJUSTES (revisión Ruben 2026-07-18).
Se incorporan: (a) C evalúa calidad CONTEXTUAL de zona, NO trades; (b) BONUS
renombrado a PESO DE CONFIANZA (no "bonus = comprar"); (c) no gate duro = regla
de hierro; (d) CONTRATO DE NO INVASIÓN DE C; (e) C NUNCA crea zonas nuevas.

---------------------------------------------------------------------
0. PRINCIPIO RECTOR (frase de Ruben, regla del proyecto)
---------------------------------------------------------------------
"Primero enseñar al sistema dónde mirar. Después enseñarle cuándo disparar."

C = "dónde mirar" = CAPA DE PERCEPCIÓN DE AUTORIDAD DE ZONAS.

Diferencia arquitectónica que protege el proyecto (Ruben 2026-07-18):

  C NO EVALÚA SI UN TRADE ES BUENO.
  C EVALÚA LA CALIDAD CONTEXTUAL DE UNA ZONA.

No es matiz de palabras: si C "evalúa trades", poco a poco se vuelve un
segundo cerebro que decide por R7. Si C "evalúa la calidad contextual de una
zona", solo aporta información y el jefe sigue siendo R7.

Analogía humana:
  ❌ "Encontré FVG, compro."
  ✅ "Encontré FVG... pero ¿está en un lugar importante?"
Eso es C.

Restricciones (no negociables — ver Contrato §1):
  (R1) C NO aumenta señales. Por diseño su efecto sobre el conteo es CERO: solo
       anota. Cualquier reducción de ruido es decisión de quien CONSUME la
       autoridad (observador / umbral en R7 modo strict), NO borrado por C.
  (R2) C NO decide dirección, entry, SL ni TP. No toca la secuencia de R7.
  (R3) Métrica de aceptación = FIDELIDAD (checklist §5), NO PF (regla de oro).
  (R4) Por defecto C es PESO DE CONFIANZA (información), NO gate duro.
       REGLA DE HIERRO: nunca se activa como filtro duro en producción.
       Evidencia A'' (Fase F): POI HTF como filtro DURO destruyó el edge
       (A'': PF 0.900 vs A' PF 1.511).

---------------------------------------------------------------------
1. CONTRATO DE NO INVASIÓN DE C  (regla de hierro del proyecto)
---------------------------------------------------------------------
Este contrato protege todo el proyecto. C es una capa de PERCEPCIÓN. Nunca
puede:

  1. Crear señales.
  2. Eliminar directamente operaciones (solo anota; la reducción de ruido la
     decide quien consume la autoridad, no C borrando).
  3. Decidir dirección.
  4. Decidir entrada.
  5. Usar indicadores (solo matemática pura del precio + contexto de TF superiores).
  6. Modificar R7 (no toca la secuencia sweep->displace->BOS->retorno).
  7. Solo agrega información contextual.
  +8. NUNCA crea zonas nuevas. Solo puede MIRAR las zonas que YA existen
     (las que trazó el detector / MarketObject). No inventa zonas por
     "interpretación propia".

Ejemplo correcto:
  Detector: "Aquí hay FVG."
  C: "Este FVG está respaldado por H4 (sweep + BPR)."  ✅ (lee zona existente)

Ejemplo PROHIBIDO:
  C: "No hay FVG, pero yo creo que aquí hay una zona."  ❌ (C no crea zonas)

Si algún día C hace alguno de los puntos 1-8, se ha roto el contrato y hay
que revertir: es la trampa del "segundo cerebro" que R7 resolvió.

---------------------------------------------------------------------
2. DIAGRAMA DE ARQUITECTURA (donde encaja C)
---------------------------------------------------------------------
              DATOS PRECIO
                   |
                   v
            Detectores matemáticos (sweep, displacement, BOS, FVG, OB)
                   |   (trazan las zonas; C NO crea ninguna)
                   v
            Objetos de mercado (MarketObject + meta pd_type/pd_tier, B1)
                   |
                   v
        >>> C: PERCEPCIÓN DE AUTORIDAD DE ZONA <<<   (SOLO anota)
                   |   lee zonas existentes; devuelve nivel de confianza
                   v
          Motor único R7 decide (run_sequence)  <-- EL JEFE SIGUE SIENDO R7
                   |
                   v
              Ejecución (simulate_trade)

Un solo cerebro. C es una capa de CONTEXTO, no de decisión.

Flujo de autoridad (no binario):
  Zona encontrada
        |
        v
  Evaluador C  -->  Autoridad: Alta | Media | Baja
        |
        v
  Motor R7 decide IGUAL (la autoridad solo es información de la zona)

  Zona A: H4 alineado + sweep + BPR + FVG   -> Autoridad 90% (Alta)
  Zona B: FVG solo, sin contexto            -> Autoridad 30% (Baja)
  Ambas siguen siendo observables. C no mata ninguna.

---------------------------------------------------------------------
3. ROOT CAUSE: por qué el POI anclado está MUERTO hoy (verificado en código)
---------------------------------------------------------------------
El hook existe pero no tiene datos:

  - run_sequence (sequence.py:313) YA acepta htf_poi_fn; gate en linea 370:
        poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))
  - est_htf_fn en canonical.py:87 SOLO entrega del HTF:
        {"trend", "sweep_up", "sweep_down"}
    NO entrega fvg_bullish/ob_bullish (las columnas que lee _htf_has_poi).
  - detect_market_structure (HTF) NO computa FVG/OB (solo swings/bos/choch/trend).
  - Por eso _htf_has_poi (sequence.py:200) que lee est_htf.get("fvg_bullish")
    SIEMPRE ve False. Con htf_poi_fn=_htf_has_poi, el gate mataría TODAS las
    entradas (coincide con el resultado empírico A'': PF 0.900 = edge destruido).

Descubrimiento (Ruben): el enchufe está puesto, pero el cable no llega.
  HTF --manda tendencia--> C
  HTF --X falta info de zonas--> C no puede evaluar
Hay que llevar la información:
  HTF --tendencia + FVG + OB + zonas--> C evalúa

Conclusión: el POI anclado no falla por diseño, falla por PLUMBING (el HTF
nunca expone sus PD arrays al evaluador). C = construir ese plumbing + evaluator.

---------------------------------------------------------------------
4. DISEÑO DE C — Percepción de autoridad de zona (lee, no crea)
---------------------------------------------------------------------
Nuevo módulo: ict_backtest/zone_authority.py (aislado, testeable por unidad).

ENTRADA del evaluador (por vela i, dirección target):
  - narrativa HTF: trend, sweep_up/down (lo que ya da est_htf_fn).
  - MAPA de PD arrays del HTF activos en la ventana de la vela i:
        lista de {tf, pd_type, pd_tier, direction, zone_high, zone_low}
    (construido desde detectors/fvg.py + detectors/ob.py sobre frames HTF,
     usando los metadatos B1 pd_type/pd_tier).
  - zona LTF candidata YA TRAZADA por el motor (FVG/OB, B1 metadatos).
    C la RECIBE; no la inventa.

SALIDA (información de contexto, NO booleano duro por defecto):
  ZoneAuthority(
      has_htf_anchor: bool,        # ¿el HTF tiene PD array en dir target?
      tier: str,                   # T1 (BPR apilado) > T2 (FVG/OB) > T3
      stacking_level: int,         # cuántas capas TF respaldan (1..N)
      confidence_weight: float,    # 0..1  PESO DE CONFIANZA de la zona
      level: str,                  # Alta | Media | Baja (derivado del peso)
  )

PUNTO DE ENCHUFE (run_sequence, linea 366-381, donde se traza state.zone_*):
  - Reemplazar el gate binario por: auth = evaluate_zone_authority(i, target, est_htf)
  - MODO PRODUCCIÓN (default, respeta R4 + evidencia A'' + contrato §1):
        la autoridad alimenta un PESO DE CONFIANZA de la zona (quality_score /
        bonus de contexto). El motor corre IGUAL. Zonas sin ancla HTF =
        confidence_weight bajo, pero NO se matan. C no cambia el conteo.
  - MODO STRICT (solo observador / configurable, NUNCA default; violaría R4
    si se pusiera en producción): un umbral de autoridad mínimo puede filtrar
    más fuerte. El knob existe pero queda APAGADO en producción.

Esto cumple R1 (C no altera señales: solo anota) y R2 (no decide por el motor).
Y respeta tu corrección de lenguaje: C "evalúa la calidad contextual de una zona",
no "si el trade es bueno".

---------------------------------------------------------------------
5. MÉTRICA DE VALIDACIÓN (tu pregunta, no PF)
---------------------------------------------------------------------
"No medir ¿cuántas entradas encontró? sino: de las que encontró antes,
¿cuántas eran zonas donde un humano habría mirado?"

Procedimiento (checklist §5 del roadmap maestro):
  1. Subconjunto etiquetado a MANO: 20 setups por componente (comité).
  2. Medir ANTES (motor actual, htf_poi_fn=None) y DESPUÉS (C en modo pesop de
     confianza):
       - % de zonas trazadas por el motor que TIENEN respaldo HTF (ancla).
       - % de zonas trazadas SIN respaldo HTF (basura objetivo de C).
       - nº de señales: DEBE SER IGUAL (C no las toca, R1). Cualquier baja es
         bug de invasión, no feature.
  3. Criterio de aceptación de la fase (no PF):
       - "zonas sin respaldo HTF" bien caracterizadas (C las marca Baja, no las
         borra).
       - coincidencia de decisión (dir/entry/SL/TP) contra etiquetado ≥ umbral
         del comité (checklist §5).

PF se mide UNA vez, al final, en Fase G (regla de oro). C no reporta PF.

---------------------------------------------------------------------
6. ORDEN DE IMPLEMENTACIÓN (TDD, una cosa a la vez, sin tocar R7)
---------------------------------------------------------------------
  C0  plumbing: FVG/OB del HTF + mapa temporal  ........ test unitario del mapa
  C1  est_htf_fn enriquecido (canonical.py) ......... test: entrega PD arrays HTF
  C2  zone_authority.evaluate_zone_authority ....... test: tier/stacking/peso aislado
  C3  cablear en run_sequence (modo pesop de confianza)  test: NO altera señales base
                                                  (mismo chequeo que B1: EURUSD M15
                                                   real B1==baseline señales)
  C4  tests de fidelidad (§5) ....................... 20 setups etiquetados
  C5  (después) validación manual comité + métrica §5

Cada paso: commit atómico + roadmap §4 C1 y matriz §9 actualizados en el MISMO
commit (regla de gobernanza). Sin modificar la secuencia de decisión de R7.

---------------------------------------------------------------------
7. ANTI-OBJETIVOS (lo que C NO hace — ver Contrato §1)
---------------------------------------------------------------------
  - NO cambia dirección / entry / SL / TP.
  - NO crea señales ni zonas.
  - NO elimina operaciones directamente (solo anota; la reducción la decide
    quien consume la autoridad).
  - NO añade parámetros mágicos arbitrarios (Principio 1 arquitectónico).
  - NO es un segundo motor de decisión.
  - NO corre backtest de rendimiento (suspendido hasta Fase G por regla de oro).
  - NO usa POI como gate duro por defecto (evidencia A'').
  - NO usa indicadores (solo matemática pura del precio + contexto HTF).

---------------------------------------------------------------------
8. RESULTADO ESPERADO (Antes vs Después)
---------------------------------------------------------------------
Antes:
  FVG = FVG                      (toda zona pesa lo mismo)

Después:
  FVG cualquiera
  vs
  FVG con:
    - liquidez tomada (sweep)
    - estructura HTF (trend + BOS/CHOCH)
    - PD array superior (FVG/OB/BPR del HTF)
    - alineación (dirección coherente)

C no decide si operar. Solo distingue "zona visible" de "zona importante",
usando ÚNICAMENTE matemática del precio y contexto de marcos superiores.

---------------------------------------------------------------------
9. TRAZABILIDAD
---------------------------------------------------------------------
  - Roadmap maestro §4 Fase C (C1 POI anclado a narrativa HTF).
  - Tesis 20 §5b, libro 21 §2/§3/§4 (tiers, stacking, POI bonus no filtro duro).
  - Desbloqueado por B1 (metadatos pd_type/pd_tier ya presentes en el LTF).
  - Enchufe: run_sequence línea 370 (gate poi_ok) -> evaluator de autoridad.
  - Pendiente de Fase C (roadmap): C2 Silver Bullet (RR 1:2), C3 Turtle Soup
    (contratendencia) — estos SON setups nuevos y vienen DESPUÉS de validar C1.
  - B2 (exec M5/M1) se mantiene CONGELADO hasta validar C (decisión Ruben).

---------------------------------------------------------------------
10. ESTADO
---------------------------------------------------------------------
  DISEÑO FORMALIZADO (v2, con ajustes de revisión). Sin código. Sin commit.
  El árbol de trabajo sucio de ETAPA 4 (delegación BOS/CHOCH + _diag + borrado
  INFORME) queda INTACTO y sin pushear hasta decisión expresa.

  Próximo paso propuesto (requiere OK de Ruben): implementar C0->C4 por TDD,
  con commit atómico por paso y roadmap al día en cada commit.
