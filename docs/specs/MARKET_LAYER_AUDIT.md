# MARKET_LAYER_AUDIT — SDD

**Estado:** DRAFT  
**Propósito:** motor de backtest crítico por capas que NO persigue ganar plata, sino auditar la estructura real del mercado y la lógica del sistema SMC-SYSTEMS capa por capa.  
**Regla de oro:** sin indicadores. Sin ATR/Wilder como filtro. Solo velas, BOS, CHOCH, FVG, OB y su tipología.  
**Granularidad:** M5 vela a vela. Cada 12 velas M5 se reevalúa la capa HTF (H1).

---

## 1. Requirements (concretos)

### REQ-MLA-01: Ejecución vela-a-vela M5
El motor recorre el dataset M5 símbolo por símbolo, barra por barra, cerrada a cerrada. No detecta eventos dentro de la vela en curso.  
**Criterio de aceptación:** la salida del motor es una tabla donde cada fila es exactamente una vela M5 del dataset.

### REQ-MLA-02: Capa HTF (D1/H4/H1)
El motor identifica en cada vela M5:
- Sesgo D1: alcista/bajista/rango
- Sesgo H4: alcista/bajista/rango
- Sesgo H1: alcista/bajista/rango
- Estructura HTF: último H4H confirmado, último H4L confirmado, último H1H/H1L
- Zona D1/H4: premium/discount
- Live/Dead structure: si el HTF sigue válido o invalidado

**Criterio de aceptación:** para cada capa HTF el motor expone `valid=True/False` y `bias=BULLISH/BEARISH/RANGE`.

### REQ-MLA-03: Capa BOS
El motor detecta BOS de mercado en M5:
- BOS alcista: rompe H4H anterior
- BOS bajista: rompe H4L anterior
- BOS internal: rompe H1H/H1L pero NO rompe H4H/H4L
- Fuerza del BOS: cantidad de velas desde el último H4H/H4L hasta el break

### REQ-MLA-04: Capa CHOCH
El motor detecta CHOCH en M5:
- CHOCH alcista: mínimo más alto + máximo más alto desde el último H4L
- CHOCH bajista: máximo más bajo + mínimo más bajo desde el último H4H
- Confirmación: cierre fuera de la zona invalidada
- Tiempo de invalidación: cantidad de velas M5 hasta confirmar

### REQ-MLA-05: Capa FVG
El motor detecta FVG en M5:
- FVG alcista: gap de compra (low[i+2] > high[i])
- FVG bajista: gap de venta (high[i+2] < low[i])
- Mitigación: % del gap rellenado
- Fill status: unfilled / partial / full
- Unfill probability: estimación basada en estructura actual

### REQ-MLA-06: Capa OB + Tipología
El motor detecta OB en M5:
- Bullish OB: vela con cuerpo alcista + close > open, low respetado posterior
- Bearish OB: vela con cuerpo bajista + close < open, high respetado posterior
- Mitigation: % del OB rellenado
- Types: breaker OB, swing OB, CHOCH OB, FVG-triggered OB

### REQ-MLA-07: Capa Liquidez
El motor detecta:
- Sweep arriba: toque por encima de H4H/H1H + cierre dentro
- Sweep abajo: toque por debajo de H4L/H1L + cierre dentro
- Internal vs external: sweep dentro del rango HTF o fuera
- Stop-hunt fallido: sweep sin follow-through

### REQ-MLA-08: Capa Ejecución (entradas TP/SL)
El motor calcula en cada vela M5 si una entrada estaría viva o muerta:
- Entradas largas/cortas solo cuando sesgo HTF + BOS + FVG/OB + CHOCH validan en la MISMA dirección
- SL: estructural (swing low/high M5) o ATR puro del dataset
- TP: liquidez interna (BSL/SSL) o RR 1:2 mínimo
- Gestión: BE, parcial, trailing

### REQ-MLA-09: Criterios de Crítica
Por cada símbolo/backtest el motor produce:
- Coherencia HTF→LTF: % de entradas donde sesgo D1/H4/H1 están alineados
- BOS sin follow-through: % de BOS que no producen movimiento ≥ 2R
- CHOCH sin confirmación: % de CHOCH tardíos (>24 velas)
- FVG sin mitigación: % de FVG que quedan unfilled al final del dataset
- OB invalidados: % de OB que se perforan antes de un follow-through
- Liquidity grab sin follow: % de sweeps sin cambio direccional posterior
- Equity curve realista: curva de equidad SIN SL/TP imaginarios, solo cerrados por estructura

### REQ-MLA-10: Sin datos inventados
- Si un timeframe no está cargado en disco, el motor reporta `MISSING` para ese nivel
- Si hay NaN en altos/bajos HTF, el motor los salta con logging estricto
- El motor NUNCA inventa swing points para completar una secuencia

### REQ-MLA-11: Capa 8 — Rastro forense (trace)
El motor registra, en cada vela M5, el estado completo de todas las capas anteriores en formato append-only.  
Registra por evento: zonas validadas, zonas invalidadas, FVG pendientes/consumidos, liquidez usada/no usada, entrada ejecutada/no ejecutada.  
Criterio de aceptación: al final del backtest se puede reconstruir el árbol completo de decisiones y el Porqué de cada descarte.

### REQ-MLA-12: Memoria del proceso estocástico
El motor audita si el mercado tiene memoria dependiente del tiempo contra GBM por permutación.  
Criterio: mide coseno del ángulo en M5, H1, D1; compara contra null-permutación; reporta si existe dependencia geométrica significativa.

### REQ-MLA-13: Memoria de estado del motor
El motor expone el estado interno de BOS/CHOCH al final de cada vela: último H4H/H4L válido, última dirección BOS/CHOCH, contador de velas desde el último evento, invalidaciones y reseteos.  
Criterio: se puede verificar que un BOS/CHOCH del pasado sigue vivo o fue reemplazado/ invalidado, y por qué evento.

---

## 2. Diseño

### 2.1 Arquitectura por capas (independientes)
```
Layer 1: HTF Structure (D1/H4/H1) - sesgo, zonas, estructura
Layer 2: BOS             - rompimientos de estructura
Layer 3: CHOCH           - invalidación de estructura
Layer 4: FVG             - gaps de eficiencia
Layer 5: OB + Tipología  - bloques de órdenes
Layer 6: Liquidity        - sweeps, stops
Layer 7: Execution        - entradas, TP, SL, gestión
```

Cada capa recibe el DataFrame M5 y produce un reporte propio.  
Capa 7 consume los reportes 1-6 y decide entrada/salida.  
Las capas NO acoplan: si capa 2 reporta "no BOS", capa 7 lo usa como veto.

### 2.2 Flujo de datos
```
Input: EURUSD_M5.parquet (cerrado, ordenado por time)
 ↓
build_htf_structure(frames["M5"]) → report_htf
build_bos(report_htf, frames["M5"]) → report_bos
build_choch(report_bos, frames["M5"]) → report_choch
build_fvg(frames["M5"]) → report_fvg
build_ob(frames["M5"]) → report_ob
build_liquidity(report_htf, report_bos, frames["M5"]) → report_liquidity
build_execution(report_htf, report_bos, report_choch, report_fvg, report_ob, report_liquidity, frames["M5"]) → trades[]
log_critique(report_*, trades) → audit_report
```

### 2.3 Salidas
1. `audit_report.json`: métricas por capa + coherencia
2. `trades.csv`: entradas, SL, TP, close, razón de salida, duración velas
3. `equity_curve.csv`: timestamp, equity, drawdown%
4. `layer_report.json`: reporte detallado por capa (BOS por fecha, CHOCH por fuerza, FVG por fill%, OB por tipo)

### 2.4 Parámetros (todos versionados en `config/audit_v1.yaml`)
- `sl_atr_multiplier`: multiplicador ATR para SL estructural
- `tp_rr`: riesgo/beneficio mínimo
- `htf_lookback`: velas M5 equivalentes a D1 (144) / H4 (48) / H1 (12)
- `bos_strength_threshold`: % mínimo de movimiento para considerar BOS válido
- `choch_confirmation_bars`: velas M5 máximas para confirmar CHOCH
- `fvg_mitigation_threshold`: % mínimo mitigado para considerar FVG "activo"
- `ob_invalidation_pct`: % del OB que debe romperse para invalidarlo

---

## 3. Tareas de ingeniería

### 3.1 Capa HTF (D1/H4/H1)
Responsable: construir estructura HTF desde velas M5 agregadas.  
Entregables:
- `ict_backtest/layers/layer_htf.py`: calcula D1/H4/H1 por agregación estricta de M5
- Tests TDD: D1 tiene el mismo high/low/close que la vela D1 cargada de MT5 (si existe)
- Números honestos: si D1 no está cargado, calcular a partir de las 12 velas M5 por H1

### 3.2 Capa BOS
Responsable: detectar rompimiento de estructura HTF en M5.  
Entregables:
- `ict_backtest/market_structure.py`: detección canónica BOS/CHOCH con estado secuencial y onset-only
- Tests TDD: `tests/test_market_structure.py` (exclusión mutua, onset-only, invariantes sintéticas)
- Métrica: fuerza del BOS = velas desde último swing HTF hasta break

### 3.3 Capa CHOCH
Responsable: detectar cambio de carácter.  
Entregables:
- `ict_backtest/market_structure.py`: CHOCH contra swing opuesto estructural, no contra nivel ya roto
- Tests TDD: ratio BOS >= CHOCH en datos reales, invalidación por cruce de close
- Métrica: tiempo de confirmación = velas M5 desde el quiebre hasta cierre confirmado

### 3.4 Capa FVG
Responsable: detectar y mitificar FVG.  
Entregables:
- `ict_backtest/layers/layer_fvg.py`: FVG + fill status + % mitigated
- Tests TDD: 3 velas con gap + 10 velas de relleno parcial/total
- Métrica: unfilled rate vs follow-through rate

### 3.5 Capa OB + Tipología
Responsable: detectar OB y clasificar tipo.  
Entregables:
- `ict_backtest/layers/layer_ob.py`: OB + tipos (breaker, swing, CHOCH, FVG-triggered)
- Tests TDD: OB sobre dataset sintético con 3 bodies grandes + mitigación
- Métrica: % invalidados, % mitigados, % con follow-through

### 3.6 Capa Liquidez
Responsable: detectar sweeps y stop-hunts.  
Entregables:
- `ict_backtest/layers/layer_liquidity.py`: sweep up/down + follow-through check
- Tests TDD: sweep sobre H4H + cierre dentro
- Métrica: grab success rate = sweeps con cambio direccional posterior

### 3.7 Capa Ejecución
Responsable: simular entradas con SL/TP realistas.  
Entregables:
- `ict_backtest/layers/layer_execution.py`: entradas largas/cortas + SL estructural + TP por liquidez
- Tests TDD: 5 entradas sintéticas con TP exacto al toque de BSL
- Métrica: win rate por contexto HTF, expectancy por tipo de entrada

### 3.8 Integración y Reporte
Responsable: unir capas + generar audit_report.  
Entregables:
- `ict_backtest/layers/orchestrator.py`: recorre M5, ejecuta capas, produce `audit_report.json`
- `scripts/run_layer_audit.py`: CLI para ejecutar sobre un símbolo
- Tests TDD: dataset sintético 500 velas M5 → audit_report con 6 capas pobladas
- Config: `config/audit_v1.yaml` con parámetros congelados

### 3.9 Validación real
Responsable: ejecutar sobre datos reales y extraer conclusiones.  
Entregables:
- Ejecutar sobre EURUSD_M5.parquet (≥2 años)
- Ejecutar sobre GBPUSD_M5.parquet
- Ejecutar sobre XAUUSD_M5.parquet
- Generar `docs/audit_results/layer_critique_YYYY-MM-DD.md` con hallazgos

---

## 4. Rules of Engagement

1. **Ley Inquebrantable de Veracidad:** El backtest es el juez, no el motor. La tesis determina las reglas del backtest; el motor se adapta para cumplirlas, nunca al revés. Si el motor no puede entregar el resultado que solicita la tesis, se actualiza el motor para pasar la prueba. No se modifican las reglas de la tesis para complacer al motor ni para obtener números más bonitos. Cualquier divergencia entre resultado del motor y resultado esperado por la tesis se resuelve actualizando el motor, nunca relajando la tesis.
2. **Sin magia**: no hay indicadores suavizados, no hay ATR como filtro de entrada, no hay constantes arbitrarias sin justificación matemática.
3. **Sin optimización**: no se tunean parámetros sobre resultados. Los parámetros son los que DETERMINA la tesis, no los que maximizan PF.
4. **Sin look-ahead**: todas las capas usan velas cerradas. El cierre de M5 no se considera disponible hasta la vela siguiente.
5. **Transparencia**: cada decisión de entrada tiene un timestamp y un estado de capas. Se puede trazar la razón completa por trade.
6. **Honestidad estadística**: se reportan n por capa. Si un BOS tiene n=3, no se concluye nada.
7. **Motor como fuente de verdad:** Los datos de backtest, simulación y reporting deben obtenerse ejecutando el motor forense sobre el dataset. No se escriben rutinas paralelas ni cálculos ad-hoc fuera del motor para generar métricas. Si el motor no puede producirlas, se extiende el motor.

---

## 5. Before/After — Corrección BOS/CHOCH (2026-07-31)

### Estado anterior
- `run_layer_audit.py` importaba `backtest.layers.layer_bos` y `backtest.layers.layer_choch`.
- CHOCH se medía contra el nivel ya roto por el último BOS (`last_bos_level`), generando falsos positivos por pullbacks.
- No había estado secuencial; el mismo nivel podía generar CHOCH repetido en múltiples barras.
- Ratio EURUSD 50k M5: **BOS 903, CHOCH 1955** → CHOCH 2.16× mayor que BOS, contradictorio con ICT.

### Estado corregido
- Ruta canónica única: `ict_backtest/market_structure.py:detect_market_structure`.
- CHOCH rompe el swing opuesto estructural del movimiento, no el nivel ya roto.
- Estado secuencial `bias` + onset-only + invalidación por cruce de close.
- Ratio EURUSD 50k M5: **BOS 8569, CHOCH 366** → BOS >> CHOCH, coherente con ICT.
- Código muerto eliminado: `backtest/layers/layer_bos.py`, `backtest/layers/layer_choch.py`, tests legacy asociados.
- Documentación actualizada: `docs/specs/MARKET_LAYER_AUDIT.md` sección 3.2/3.3.
- Commit: `c510665` en rama `feature/r3.5-ict-gaps`.

### Impacto en capas superiores
- `sequence.py`: sin cambios, lee `bos_dir`/`choch_dir` desde `MarketObject.meta`.
- `run_layer_audit.py`: ahora consume directamente el detector canónico.
- Traza forense: evento `choch_detected` con `new_state=ACTIVE/INVALIDATED`, no solo `PENDING`.
- Plots BOS/CHOCH: ahora marcan puntos de posible giro estructural, no pullbacks rutinarios.

### Calibración pendiente: CHOCH LTF = 0
- Dato anómalo: EURUSD 50k M5 con clasificación HTF/ITF/LTF dio CHOCH LTF = 0.
- Diagnóstico: el clasificador usa niveles agregados H4/H1 convertidos a M5; al agregar, casi todos los niveles significativos pasan a HTF/ITF y no queda una base LTF pura.
- Acción siguiente: calibración de la clasificación sin borrar aún código ni tests; documentado como faltante para la fase 3 final.

---

## 6. Definition of Done

1. 7 capas implementadas con TDD, tests verdes, coverage ≥ 80% por módulo.
2. `run_layer_audit.py` ejecuta sobre EURUSD_M5.parquet sin errores.
3. `audit_report.json` generado con las 9 métricas por capa.
4. `layer_critique_YYYY-MM-DD.md` generado con conclusiones.
5. Sin dependencias de indicadores externos. Sin ATR, sin RSI, sin Stochastic.
6. Config congelada con parámetros alineados a la tesis.

---

## 7. Tareas paralelas posibles (no bloqueantes)

- Capas HTF/BOS/CHOCH paralelas entre sí (Fronts A, B, C)
- Capa FVG/OB paralelas (Fronts D, E)
- Capa Execution/Integration después que A-E estén validadas

---

Fin del SDD.
