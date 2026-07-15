# MARKET_OBJECT_MODEL.md — Ontología del Mercado (Contrato Conceptual)

> **Para Hermes:** este NO es un documento técnico. No describe código ni
> Python. Define QUÉ EXISTE REALMENTE EN EL MERCADADO y cómo se relacionan
> los objetos. Es el CONTRATO que mantiene coherentes el código
> (`ict_backtest/market_object.py`) y la biblioteca ICT (`docs/ict/*.md`).
> Es anterior al PLAN DE EJECUCION TDD: sin este contrato, programar seria
> adivinar. Sin "haz commit y push" no se commitea.
>
> Complementa: DISENO_ARQUITECTURA_OBJETOS_MERCADO.md (modelo de datos) y
> REVISION_ARQUITECTURA_CONVIVENCIA.md (capa de traducción).

---

## 0. Principio rector

ICT no dice "hay un BOS". ICT dice "el mercado está buscando liquidez".
Sweep, BOS, MSS, FVG, OB son CONSECUENCIAS de una narrativa, no la
narrativa misma.

Por eso el modelo tiene DOS capas:

```
MarketNarrative   (¿qué está haciendo el mercado? -> buscar liquidez)
      |
      +-- MarketObject (los hitos concretos de esa búsqueda)
```

Un `MarketObject` NO se entiende solo. Solo tiene sentido como parte de una
`MarketNarrative` (la cadena causal: liquidez HTF -> POI -> sweep -> MSS ->
entry).

---

## 1. MarketNarrative (la capa superior)

Una narrativa es UNA historia de precio coherente. Vive mientras sus
objetos la sostienen; muere cuando un evento la contradice.

Atributos conceptuales (no código):
- `thesis`: qué busca el mercado (ej. "barrer BSL semanal y continuar").
- `session`: killzone donde transcurre (Asia / London / NY AM / NY PM).
- `higher_tf_context`: sesgo H4/D1 del que parte (la marea).
- `members`: lista de MarketObjects que la componen (enlazados por
  parent_object).
- `state`: ALIVE (coherente) | BROKEN (un evento la contradice).

Regla dura: un MarketObject solo es válido si pertenece a una narrativa
activa. Un FVG suelto sin narrativa es ruido, no señal.

---

## 2. MarketObject — definición por objeto

Cada objeto se documenta con las MISMAS 8 preguntas (la ontología):

1. ¿Qué representa?
2. ¿Cómo nace? (evento disparador)
3. ¿Qué eventos lo modifican? (transiciones de estado)
4. ¿Qué estados puede tener?
5. ¿Qué objetos puede CREAR? (hijos)
6. ¿Qué objetos puede CONSUMIR? (los usa para vivir/morir)
7. ¿Quién puede ser su PADRE?
8. ¿Quién puede ser su HIJO?

---

### 2.1 LIQUIDITY (BSL / SSL)
1. Representa: un POOL de órdenes detenidas (stop-loss de la contraparte /
   órdenes límite) sobre un máximo/mínimo previo. Es el "premio" que el
   mercado busca.
2. Nace: cuando el precio marca un swing high (BSL) o swing low (SSL) y hay
   volumen/órdenes detenidas ahí (detect_liquidity).
3. Modifican: el precio la TOCA (mitigada parcial) o la ATRAVIESA y cierra
   fuera (consumida/barrida).
4. Estados: CREATED -> ACTIVE -> MITIGATED (tosco) -> CONSUMED (barrida).
5. Crea: es el ORIGEN. No crea hijos directos; es el objetivo de un SWEEP.
6. Consume: nada. Es consumida por SWEEP.
7. Padre: MarketNarrative (la narrativa "buscar liquidez X").
8. Hijo: ninguno. Ella es la hoja de destino.

---

### 2.2 SWEEP
1. Representa: el barrido de una LIQUIDITY (rompe el nivel y CIERRA adentro
   en la misma vela — falla el breakout = liquidity grab). Es el ACTO de
   buscar el premio.
2. Nace: `low < prior_low AND close > prior_low` (sweep_down) o espejo
   (sweep_up) — canonical_sweep.
3. Modifican: al cerrar la vela ya es un hecho; luego puede ser INVALIDADO si
   el precio no continúa (falsa bandera) — pero el sweep en sí es evento.
4. Estados: CREATED (la vela del sweep) -> ACTIVE -> CONSUMED (usado por un
   BOS/MSS posterior) | INVALIDATED (el precio lo ignora y sigue).
5. Crea: provee el ANCLA del SL estructural (la mecha del sweep) y es el
   disparador de un BOS/MSS que nazca tras él.
6. Consume: la LIQUIDITY que barrió (la relaciona por parent_object).
7. Padre: LIQUIDITY (la que barrió) o MarketNarrative.
8. Hijo: BOS / MSS / CHOCH que nazcan en las velas siguientes.

---

### 2.3 BOS (Break of Structure) / MSS
1. Representa: el mercado ROMPIÓ la estructura previa en una dirección. Es
   cambio de carácter (Market Structure Shift). No es un indicador: es un
   EVENTO que confirma intención.
2. Nace: el precio cierra por encima del swing high previo (BOS alcista) o
   debajo del swing low (bajista) tras un SWEEP.
3. Modifican:
   - precio retorna y cierra del otro lado del swing roto -> INVALIDATED.
   - precio toca el nivel del swing roto (mitigación parcial) -> MITIGATED.
   - se opera con él -> CONSUMED.
4. Estados: CREATED -> ACTIVE -> MITIGATED | INVALIDATED | CONSUMED.
5. Crea: valida/continúa una narrativa; es el padre de un FVG/OB de
   REFINEMENT que nazca en la misma zona.
6. Consume: el SWEEP previo (la intención que lo justifica). Sin sweep previo
   es un BOS "en el aire" (menor calidad).
7. Padre: SWEEP (o CHOCH en reversión) | MarketNarrative.
8. Hijo: FVG / OB de refinement en la zona del BOS.

---

### 2.4 CHOCH (Change of Character)
1. Representa: el PRIMER cambio de carácter que anuncia giro (en reversión /
   Turtle Soup es el paso 2 de BOS->CHOCH->BOS).
2. Nace: estructura de baja hace un BOS alcista (o viceversa) contra el sesgo
   HTF.
3. Modifican: igual que BOS (retorno invalida; operación consume).
4. Estados: igual que BOS.
5. Crea: en contratendencia, habilita el BOS de giro (es padre de ese BOS).
6. Consume: el sesgo HTF opuesto (es la prueba de que la marea se quiebra).
7. Padre: MarketNarrative (reversión) | sesgo HTF.
8. Hijo: BOS de giro.

---

### 2.5 FVG (Fair Value Gap)
1. Representa: desequilibrio de oferta/demanda dejado por una vela de
   DESPLAZAMIENTO. Es la "huella" del dinero grande moviéndose.
2. Nace: vela de displacement (cuerpo grande) que deja un hueco entre la mecha
   de la vela anterior y la mecha de la siguiente.
3. Modifican:
   - precio VUELVE al hueco y lo cierra -> MITIGATED (ya lo usó).
   - precio lo ATRAVIESA sin respetarlo y sigue -> INVALIDATED (no fue POI).
4. Estados: CREATED -> ACTIVE -> MITIGATED | INVALIDATED.
5. Crea: NADA. Es zona, no evento. SU rol define su función:
   - role=POI (HTF): zona institucional donde el dinero puede reaccionar.
   - role=REFINEMENT (LTF): entrada fina tras el sweep/BOS.
6. Consume: el DESPLAZAMIENTO que lo creó (su padre lógico).
7. Padre: BOS / MSS (zona del break) | DESPLAZAMIENTO | MarketNarrative.
8. Hijo: ninguno. Es zona de espera.

---

### 2.6 ORDER BLOCK (OB)
1. Representa: la vela (o cuerpo) de DESPLAZAMIENTO previa al movimiento
   institucional — la "base" desde donde el dinero grande operó.
2. Nace: vela de displacement opuesta a la dirección del movimiento posterior.
3. Modifican: igual que FVG (retorno lo mitiga; atravieso lo invalida).
4. Estados: CREATED -> ACTIVE -> MITIGATED | INVALIDATED.
5. Crea: NADA (zona). Su rol define función (POI HTF vs refinement LTF).
6. Consume: el DESPLAZAMIENTO que lo formó.
7. Padre: BOS / MSS | DESPLAZAMIENTO.
8. Hijo: ninguno.

---

### 2.7 POI (Point of Interest) — NO es un tipo, es un ROL
1. Representa: el PD array (FVG u OB) de HTF que el mercado debe respetar.
2. Nace: cuando un FVG/OB de HTF recibe role=POI.
3. Modifican: el precio lo respeta (mitigación = entrada) o lo ignora
   (invalidado).
4. Estados: hereda de FVG/OB.
5. Crea: la ZONA donde un SWEEP/MSS de LTF debe ocurrir para validar la
   narrativa.
6. Consume: el sesgo HTF (el POI solo existe dentro de una narrativa H4/D1).
7. Padre: MarketNarrative (sesgo HTF).
8. Hijo: el SWEEP/MSS de LTF que lo visita.

Regla dura (tesis 18): `origin_tf="M15", role=POI` es INVÁLIDO. El POI
institucional SOLO existe en HTF. Un FVG M15 es siempre REFINEMENT.

---

## 3. Cadena causal canónica (ejemplo EURUSD)

```
MarketNarrative: "H4 BULLISH busca barrer SSL semanal y continuar"

  LIQUIDITY (SSL, H4)              <- el premio
      |
      v  (padre de)
  SWEEP (M15 barre la SSL H4)      <- el acto
      |
      v  (padre de)
  BOS alcista (M15, tras sweep)    <- la intención
      |
      v  (padre de)
  FVG (M15, refinement)            <- la entrada fina
      |
      v  (consumido por)
  ENTRY (SL anclado a mecha del SWEEP, TP a BSL opuesta del H4)
```

Cada flecha es un `parent_object`. Si falta un eslabón (ej. BOS sin sweep
previo), la narrativa es débil y el quality_score baja.

---

## 4. quality_score — EXPLICABLE, no caja negra

NO es un número mágico. Es la SUMA de factores auditables. El sistema debe
poder explicar cada punto.

Factores (pesos ejemplo, a calibrar con datos):
```
+30  Liquidez HTF barrida (el sweep tocó BSL/SSL de H4/D1)
+20  POI institucional presente (FVG/OB de HTF en la zona)
+15  Desplazamiento fuerte (la vela del BOS/FVG tuvo cuerpo grande)
+21  Dentro de killzone (London/NY AM/PM)
-15  Contra la narrativa HTF (setup contratendencia no intencional)
-10  Sin confirmación (BOS sin sweep previo)
-10  Dentro del rango (H4 en RANGING, sin marea)
```

Entonces el sistema explica:
```
quality = 86
  porque: +30 +20 +15 +21 = 86  (setup a-favor limpio en killzone)
```
o
```
quality = 41
  porque: +15 (disp) +20 (POI) +10 (KZ parcial) -15 (contra HTF) -10 (sin sweep)
```

El quality_score NUNCA debe ser una salida opaca de un modelo. Si no se
puede descomponer en factores, ese factor no entra. (ML puede sugerir pesos
después, pero el desglose siempre es visible — ver features/engine.py y ml/*
que usan las columnas; el score se construye SOBRE ellas, no las reemplaza.)

---

## 5. Contrato de coherencia (lo que este documento garantiza)

- Cualquier objeto nuevo (patrón, estrategia, modelo de IA) debe responder
  las 8 preguntas de la sección 2 y enlazarse por parent_object a una
  narrativa. Si no, no pertenece al modelo.
- El código (`market_object.py`) y la biblioteca (`docs/ict/*.md`) deben
  coincidir con este contrato. Si el código hace algo que esta ontología no
  permite (ej. FVG M15 como POI), el código está MAL, no el contrato.
- La capa de traducción (`translation.py`) traduce columnas <-> objetos SIN
  romper estas relaciones: `objects_to_legacy_df` reconstruye columnas, pero
  `parent_object`/`role`/`state` viven en el objeto, no en el df.

---

## 6. Estado de este documento

Es el CONTRATO. Antes de escribir el PLAN DE EJECUCION TDD, este documento
debe estar aprobado. La implementación deja de ser diseño y pasa a ser
ingeniería cuando este contrato existe.
