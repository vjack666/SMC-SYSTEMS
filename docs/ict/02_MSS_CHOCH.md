# ICT — Market Structure Shift (MSS), Change of Character (CHoCH), Break of Structure (BOS)

> Tesis de este libro: **BOS y CHOCH no son solo "nombres de patrones" — son la
> forma en que traders y algoritmos leen la intención del mercado.** Cómo los
> usan los traders discretos (entrada/gestión), cómo los calculan las apps
> automáticas (indicadores/EAs en MQL5), y por qué el **desplazamiento del
> gráfico (Chart Shift)** y la **profundidad de histórico** cambian el resultado.
> Todo anclado a la auditoría de `ict_backtest/` (look-ahead #1 y CHOCH real #2).

Fuentes verificadas: MQL5 Articles (MetaQuotes) `articles/22249` y `articles/15017`,
FluxCharts "Break of Structure Explained", Alchemy Markets "Change of Character
Guide", y la ayuda oficial de MetaTrader 5 (Chart Settings / Chart Shift).

---

## 1. Las tres rupturas de estructura (jerarquía)

| Patrón | Señal | Confirmación | Implicación |
|--------|-------|--------------|-------------|
| **BOS** | Continuación de tendencia | Ruptura de swing **en la dirección** de la tendencia vigente | La tendencia probablemente continúa |
| **CHoCH** | Aviso temprano de reversión | Ruptura del swing **contrario** a la tendencia (1ª vez) | La tendencia se debilita — no es confirmación |
| **MSS / MSB** | Reversión confirmada | Fallo de swing + ruptura decisiva + **desplazamiento (displacement)** | Nueva tendencia formándose |

**Nota de nomenclatura (FluxCharts):** BOS confirma *continuación*; el
*término* "Market Structure Break" (MSB) en la literatura suele significar
reversión fuerte (equivalente a CHoCH+ / MSS). ICT usa MSS; SMC genérico usa MSB.
En SMC-SYSTEMS: `MSS = BOS tras CHoCH con desplazamiento`.

---

## 2. BOS (Break of Structure) — continuación

- Precio rompe un swing reciente **en la dirección de la tendencia vigente**.
- **Regla dura de validación (MQL5 art. 15017):** el break debe ser con el
  **cuerpo (close)** de la vela, no con mecha/wick. Un break solo por mecha se
  trata como **INVÁLIDO**. Esta es la regla que separa un BOS real de un
  "quasi-break" engañoso.
- Bullish BOS: rompe el swing high anterior hacia un nuevo Higher High (HH).
- Bearish BOS: rompe el swing low anterior hacia un nuevo Lower Low (LL).
- **Uso real de los traders (FluxCharts):** el BOS NO es entrada ni salida.
  Es *confirmación de que la estructura actual sigue viva*. Quien está long
  mantiene; quien está short mantiene. Se combina con CHoCH: entras en CHoCH
  (reversión temprana) y confirmas con BOS en la nueva dirección.
- En SMC-SYSTEMS: `detectors/bos.py` lo detecta (`bos_dir` + `bos_status`).
  La pestaña Principal lo usa para etiquetar "a favor / contra tendencia".

## 3. CHoCH (Change of Character) — primer aviso de reversión

- Precio rompe el swing **contrario** a la tendencia por primera vez:
  - En uptrend: nuevo **Lower Low** (rompe el último HL).
  - En downtrend: nuevo **Higher High** (rompe el último LH).
- **Es aviso temprano, NO confirmación.** La tendencia no terminó hasta que
  falla y se forma un LH tras el LL (o HL tras el HH).
- **Fake-out CHoCH (señal falsa):** ruptura débil — mecha, sin cierre limpio,
  vela pequeña, bajo volumen, rebote brusco. **Común en noticias de alto
  impacto** (Alchemy). Se trata como falsa.
- Confirmación extra (Alchemy): volumen que acompaña el break añade convicción,
  pero *structure is king, volume is secondary*. Un CHoCH de baja convicción se
  mantiene "no probado" hasta que un BOS en la misma dirección lo confirma.

## 4. La regla de contexto (a favor / contra tendencia)

- CHoCH/MSS en TF menor se lee **siempre contra el contexto del TF mayor**
  (H4/D1). Setup alineado con TF mayor = continuación (a favor). Setup opuesto =
  reversión (contra).
- CHoCH es más fiable en **London / New York** (participación institucional
  real). Fuera de sesión (Asia para pares EUR/USD) da falsas por distorsión de
  liquidez (Alchemy, MQL5 art. 15017).
- **Multi-Timeframe (Alchemy, práctica estándar):**
  - HTF (D1/H4) define el sesgo direccional y los PD arrays (OB, FVG, zonas).
  - LTF (M15/M5) da la confirmación y la entrada precisa.
  - Solo se dispara cuando **ambos** TF alinean dirección.

---

## 5. Desplazamiento del gráfico y profundidad de histórico (lo que pediste)

Esto es crítico y casi nunca se documenta en los libros de "teoría ICT", pero
los traders lo usan y los algoritmos lo sufren.

### 5.1 Chart Shift (desplazamiento del gráfico) — MT5
Según la ayuda oficial de MetaTrader 5 (Chart Settings):
- **Chart Shift** desplaza el gráfico desde el borde derecho hasta la "marca de
  desplazamiento" (triángulo gris arriba). Se arrastra entre **10% y 50%** del
  ancho de la ventana.
- **Chart Autoscroll** (auto-desplazamiento): al formarse una vela nueva, el
  gráfico se corre a la izquierda para mostrar siempre la última vela.
- **Implicación para estructura:** con Chart Shift activo, la última vela queda
  "adentro" de la ventana y se ve mejor el contexto de los swings recientes.
  Los traders lo usan para que el BOS/CHOCH más reciente no quede pegado al
  borde derecho (donde es ilegible). **No cambia el cálculo**, pero cambia qué
  parte del histórico está visible al evaluar un break.

### 5.2 Profundidad de histórico (cuántas barras "ve" el gráfico)
- MT5 carga histórico por símbolo/timeframe. La cantidad visible depende de
  "Max bars in chart" y de cuánto histórico tenga el terminal/servidor.
- **Para detectar swings necesitas histórico hacia atrás.** El indicador MQL5
  "Market Structure Sentinel" (art. 22249) usa `rightLeftBars` (barras a cada
  lado del pivote) y el EA BOS (art. 15017) usa `length = 20` barras de scan.
  O sea: para declarar un swing high/low válido necesitas al menos ~20-40 barras
  de contexto a cada lado.
- **Consecuencia directa para SMC-SYSTEMS (edge diagnosis / walk-forward A6/A12):**
  si el dataset solo tiene el tramo reciente (p.ej. EURUSD M15 con el volumen
  concentrado en el último tercio), los primeros swings NO se pueden validar →
  se pierden señales en el arranque del backtest. Por eso la auditoría recomienda
  >3-4 años de histórico (A6) antes de declarar robustez OOS.
- **En Strategy Tester / backtest:** MT5 descarga histórico bajo demanda. En H1
  o M15 "solo 100 barras horarias/15-min se requieren" (ayuda test_preparation)
  — insuficiente para estructura real. Hay que forzar descarga de años completos.

### 5.3 Look-ahead: el peligro automático (conecta con auditoría #1)
- Detectar un swing con una **ventana centrada** (mirar a ambos lados del pico)
  expone el swing *antes de que se confirme* → **look-ahead bias**.
- En MQL5, los indicadores recalculan en cada tick; si usan `iBarShift`/índices
  futuros o no respetan `IsNewBar`, dibujan líneas "que predicen el futuro".
- **Auditoría de SMC-SYSTEMS (2026-07-11, #1):** `_swing_points` usaba ventana
  centrada + `ffill` desde el pico → el swing idx 10 aparecía en la fila 10
  (debió ser 15). Corregido: ventana **NO centrada** + `shift(lookback).ffill()`
  → el swing solo se expone desde la vela de confirmación. Test:
  `test_swing_no_lookahead`.
- **Regla de oro para apps automáticas:** un swing solo existe después de
  `rightLeftBars` velas de confirmación. Nunca mires a la derecha del índice
  actual en producción/backtest.

---

## 6. Cómo lo calculan las aplicaciones automáticas (MQL5 / EAs)

Esto es lo que Ruben pidió: "cómo lo usan las aplicaciones automáticas".

### 6.1 Plantilla oficial MetaQuotes — "Market Structure Sentinel" (art. 22249)
Indicador MQL5 que detecta y visualiza BOS/CHOCH en tiempo real. Patrón clave:
- `struct st_SwingPoint { datetime time; double price; bool isBroken; }`
- `isSwingHigh(index)`: compara el high del índice contra `rightLeftBars` barras
  a cada lado (izquierda = histórico, derecha = confirmación).
- `getTrendDirection()`: evalúa el **par de swings más reciente** (adaptativo),
  no ancla a un solo tipo — reduce lag estructural.
- Mini-dashboard con flecha ↑/↓/↕ (tendencia/consolidación).
- **Lección para nosotros:** la detección de swings es el cuello de botella.
  Hacerla robusta (sin look-ahead, con confirmación) es lo que separa un
  indicador útil de uno que "predice el futuro".

### 6.2 EA "Break of Structure" (art. 15017)
- `OnTick` con control `isNewBar` (calcula 1 vez por vela, no por tick).
- Detecta swing high/low escaneando `length=20` barras a cada lado.
- **Valida el break por CIERRE del cuerpo**, no por mecha (regla de la sección 2).
- Entra en el break del swing; SL en el swing previo o R:R fijo; TP en el
  siguiente swing o R:R.
- **Advertencia del foro MQL5:** el código original del artículo tenía un bug de
  look-ahead (`left_index = curr_bar + j` miraba barras *futuras*). Los usuarios
  lo marcaron como "future function / cheating". Esto es exactamente el riesgo
  #1 de la auditoría de SMC-SYSTEMS.

### 6.3 XGBoost + SMC (art. 22526, MetaQuotes)
Guía oficial de MetaQuotes que entrena un modelo XGBoost (ONNX) sobre eventos
SMC (OB, FVG, **BOS**) de XAUUSD y lo embebe en un EA para filtrar setups.
**Conexión directa con nuestro `ml/inference.py` (QualityFilter XGBoost):** el
edge de SMC + filtro ML es la misma arquitectura que propone MetaQuotes. Nuestro
`bos_dir` es una de las features del modelo de calidad.

---

## 7. Qué corrigió la auditoría de SMC-SYSTEMS (cierre de la tesis)

La auditoría externa (Claude, 2026-07-11) encontró 2 bugs y se midió el impacto:

| Hallazgo | Qué pasaba | Fix | Impacto medido |
|----------|-----------|-----|----------------|
| **#1 Look-ahead** | `_swing_points` usaba ventana centrada + ffill desde el pico | Ventana NO centrada + `shift(lookback).ffill()` | El swing se expone solo en la vela de confirmación |
| **#2 CHOCH = BOS** | `choch_dir` era copia literal de `bos_dir` (0 filas distintas en 10.136 velas H4) | CHOCH real = rompe el swing del **último BOS**, en dirección opuesta (memoria `_track_bos`) | 7.764 filas distintas; test `test_choch_differs_from_bos` |
| Resultado | PF de Capa 2 inflado ~30% por los bugs | — | PF 2.003 → **1.548** al corregir |

**Conclusión empírica (nuestra, no de oídas):** el edge existe (PF>1) pero es
más modesto y **frágil** (walk-forward OOS 3.389 ± 2.303, solo 21 trades OOS,
un fold en 1.000). No se declara robusto hasta subir N (A6: más histórico) y
correr con costos reales (fix #4, flag `--cost` en `optimize.py`).

---

## 8. Reglas operativas resumidas (para el detector y la app)

1. BOS = break de swing **a favor** de la tendencia, validado por **cierre de cuerpo**.
2. CHoCH = 1er break **contrario**; aviso temprano, no entrada ciega.
3. MSS = CHOCH + displacement fuerte + (opcional) liquidity sweep previo.
4. Filtrar Fake-out CHOCH: mecha/sin cierre/bajo volumen/noticias = falsa.
5. Siempre leer contra TF mayor (H4/D1). London/NY > Asia para fiabilidad.
6. Swing = solo tras `rightLeftBars` velas de confirmación — **nunca look-ahead**.
7. Para backtest robusto: histórico de años completos (A6), no solo el tramo reciente.
8. CHOCH real ≠ BOS: rompe el swing del último BOS en dirección opuesta.

## En SMC-SYSTEMS
- `detectors/bos.py` (BOS) + `detectors/choch.py` (CHoCH) ya detectados.
- `ict_backtest/market_structure.py` tiene los fixes #1 (sin look-ahead) y #2
  (CHOCH real). `ict_backtest/optimize.py` expone `--cost` (fix #4, pendiente de
  aplicar en corrida final).
- La pestaña Principal etiqueta "a favor / contra tendencia" comparando
  `bos_dir` M15 vs tendencia D1.
- `ml/inference.py` (QualityFilter XGBoost) usa `bos_dir` como feature — misma
  arquitectura que la guía XGBoost+SMC de MetaQuotes (art. 22526).

## Referencias (trazabilidad regla → código → fuente)
- MQL5 "Market Structure Sentinel" — `mql5.com/en/articles/22249`
- MQL5 "Trading the Break of Structure (BoS) Strategy" — `mql5.com/en/articles/15017`
- MQL5 "Integrating AI into SMC: OB, BOS, FVG" — `mql5.com/en/articles/22526`
- FluxCharts "Break of Structure Explained" — `fluxcharts.com/articles/break-of-structure-bos-explained`
- Alchemy Markets "Change of Character Guide" — `alchemymarkets.com/education/strategies/change-of-character-guide/`
- MetaTrader 5 Help — Chart Settings (Chart Shift) — `metatrader5.com/en/terminal/help/charts_advanced/charts_settings`
- Auditoría interna: `docs/ict/10_AUDITORIA_REFACCION/` (00_INDICE, 02_CHOCH_REAL, 03_TESTS_FALTANTES)
