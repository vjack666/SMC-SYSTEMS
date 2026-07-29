# AUDITORÍA DE BACKTEST — SMC-SYSTEMS
## Parte II: Fidelidad, Poder Estadístico y Capacidad de Demostración Científica

**Fecha:** 2026-07-22  
**Fuentes:** `docs/METRICS_CANON.md`, `docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md`,  
`ict_backtest/{sequence,engine,run_backtest,optimize,invalidators,diagnostics}.py`

---

## 1. Fidelidad al sistema (¿reproduce el proceso mental ICT?)

### 1.1 Componentes utilizados hoy

| Componente tesis | Usado en backtest actual | Módulo |
|---|---|---|
| Sweep manipulación | Sí | `sequence.py` § `_has_sweep` |
| BOS/CHOCH | Sí | `market_structure.py` |
| Displacement | Sí | `sequence.py` § `_has_displacement` |
| FVG/OB | Sí | `sequence.py` § `_has_fvg`, `_has_ob` |
| SL estructural | Sí | `engine.py` `calc_structural_sl` (respaldado por med. empírica v29) |
| Fill next-open + costos | Sí | G2/G3 en Capa 2/3 |
| POI como bonus | Parcial | `poi_filter.py` existe, pero `enable_pd_index=False` por defecto |
| Dealing range / premium-discount | No | `dealing_range.py` existe pero no integrado en `evaluate_signals` |
| 3 capas HTF/ITF/exec | No | `exec_tf == ltf` |
| Entry retorno a zona | No | Cierra BOS |
| TP liquidez cercana | No | Cluster HTF promedio |
| RR 1:3 mínimo | No | `fixed2r` default |
| Killzones completas | No | Solo NY AM lógica |
| PlanFSM | No | No orquesta `run_sequence_backtest` |
| Invalidación estructural post-entry | No | no ejecutada en pipeline |
| SMT Divergence | No | No existe |

**Veredicto:** el backtest actual reproduce **un subconjunto disciplinado** de la tesis: eventos estructurales + SL estructural + simulación vela-a-vela con costos. Ignora o invierte entry, TP, RR, refinamiento multi-TF, POI anclada, dealing range y gestión post-entry.

### 1.2 ¿Puede explicar por qué una operación gana o pierde?

**Parcial.** Produce:
- `entry`, `SL`, `TP`, `exit_reason`, `pnl_r`, `mfe_r`, `mae_r`, `hold_bars` → Sí.
- `RawDiagnosticData` por trade con `htf_context`, `market_stack` → Existe, pero **no se exporta a reporte ejecutable en Capa 2/3 estándar**; está diseñado para Fase D/Paso 3.
- Cobertura `v2_partial` / `v2_full` → Documenta módulos activos, pero **no diagnostica hipótesis individuales**. No distingue: “perdió porque el entry fue close del BOS” vs “perdió porque el TP quedó muy lejos”.

**Brecha:** no hay motor de diagnosis integrado a las métricas publicadas. `diagnostics/hypothesis_engine.py` existe pero no se invoca en los runs que publican números.

---

## 2. Poder estadístico y científico

### 2.1 Tamaño muestral

| Corrida | Símbolo | Trades | N trade-level | Tiempo |
|---|---|---|---:|---|
| R6.4 prod | EURUSD | 18 | 18 | ~3 meses |
| R6.4 prod | GBPUSD | 30 | 30 | ~3 meses |
| R6.4 prod | USDCHF | 25 | 25 | ~3 meses |
| v2 mtf | EURUSD | 0–? | 0–4 | 6 meses |
| E2 ES aislado | EURUSD | 8 | 8 | 2 años |
| E3 Turtle aislado | EURUSD | 466 | 466 | 2 años |

**Veredicto:** N=18–30 no alcanza para conclusiones poblacionales (DSR, PBO).  
E3 sí da masa crítica, pero evalúa un modelo desligado del pipeline principal (no 3-capas completo).  
**Bloqueo científico real:** falta de datos ≥3-4 años y multi-símbolo con M15 real.

### 2.2 Sesgos detectados/posibles

1. **Survivorship / selección de símbolo:** no se corren los 8 majors sistemáticamente en todas las versiones; XAUUSD excluido por falta de M15.
2. **Data leakage cross-timeframe (R4 v2.5):** confeccionada por `row_at_time` leía H4 aún en formación → 97.4% velas M5 afectadas. Corrida limpia es solo v2.7+.
3. **Sesgo de horizonte:** runs cortos (~3 meses) coinciden con régimen trending EURUSD/GBPUSD; no cubren eventos de riesgo, noticias rojas, cambios de régimen.
4. **Sesgo de confirmación:** métricas publicadas mezclan runs con cost ON/OFF; diferencia entre teoría/producción no siempre explícita en documentos previos.
5. **Selección de parámetros:** Optuna se aplicó, pero sobre parámetros de motor simplificado (no sobre entry/TP refinados que faltan). Riesgo: overfit a una hipótesis MUY reducida.

### 2.3 Métricas suficientes para demostrar la tesis

**No, actualmente no.** El backtest publica solo:
- PF, Winrate, Total R, Max DD, Expectancy.

Faltan para una auditoría científica:
- **DSR / DSR<0** → ausente en runs públicos.
- **PBO** → ausente en runs públicos.
- **PurgedKFold** → código existe (`optimize.py`), pero **no aplicado a Capa 2 estándar**.
- **Cohort analysis** → no segmenta por setup (PO3/Turtle/Silver) en reportes públicos.
- **Hypothesis drill-down** → no aísla: “¿la señal ganó por BOS real o por TP cluster afortunado?”.

---

## 3. Capacidad de experimentación

### 3.1 ¿Qué puede contestar el backtest hoy?

- ¿Motor sequence + SL estructural gana en EURUSD sin costos? → Sí/No.
- ¿Costos hunden el edge actual? → Sí, muy claro.
- ¿Displacement on mejora vs off? → Sí, medido en R4 v2.7.
- ¿POI como bonus cambia el PF? → Parcial:我们知道 PF 1.511 con bonus, 0.900 con gate, pero no reproducido en runs actuales porque `enable_pd_index=False`.
- ¿Entry en retorno a zona mejora el close del BOS? → **No puede contestarlo todavía**, porque no está implementado.

### 3.2 ¿Qué NO puede contestar?

- ¿La tesis ICT completa tiene edge? → No, porque no ejecuta dealing range, POI anclada, 3-capas, entry retorno, TP nearest, RR 1:3.
- ¿SMT Divergence aporta valor? → No, no existe.
- ¿El edge persiste tras 3-4 años y múltiples eventos de riesgo? → No, datos insuficientes.

---

## 4. Cobertura de módulos (Coverage)

Fuente: `docs/METRICS_CANON.md` línea 64: `coverage v2_partial = 86.1%`

**Desglose de brecha real (C0x):**

| Código brecha | Módulo tesis | Cobertura actual | Acción |
|---|---|---|---|
| C01 | Dealing range / premium-discount | 0% en pipeline | Wire `dealing_range_motor.py` en `evaluate_signals` |
| C02 | POI anclado a narrativa HTF | Parcial: índice existe pero `enable_pd_index=False` | Encender por defecto + exponer `poi_present` |
| C03 | Entry retorno a zona | 0% | Cambiar lógica de entry |
| C04 | TP nearest liquidity | 0% | Cambiar `_tp_liquidity` |
| C05 | RR 1:3 mínimo | 0% | Cambiar default |
| C06 | Stacking multi-TF eleva tier | Parcial: módulo existe | Integrar en secuencia |
| C07 | Killzones completas | Parcial | Londres y NY PM + TZ |
| C08 | Invalidación estructural post-entry | 0% | Integrar `invalidators.py` |
| C09 | PlanFSM orquestando | 0% | Orquestar `run_sequence_backtest` |
| C10 | SMT Divergence | 0% | Nuevo módulo |

---

## 5. Reproducibilidad y causalidad

### 5.1 Look-ahead / leakage
- BOS/CHOCH: sin look-ahead confirmado (`shift(lookback)+ffill`).
- Cross-timeframe: documentada y corregida en la mayoría de paths, pero requiere re-validación formal.
- ML: dataset builder usa chronological split (no shuffle) → no hay leakage temporal.

### 5.2 ¿El loop reproduce el comportamiento real del motor?
- Sí en **eventos secuenciales** (sweep→displace→BOS→entry).
- No en **gestión post-entry** (invalidaciones, trailing, gestión multi-TF).
- No en **refinamiento fino** (exec TF separado, confirmación M1).

---

## 6. Veredicto global del backtest

> **El backtest actual NO es capaz de demostrar científicamente la tesis ICT completa.**  
> Es capaz de medir un subconjunto disciplinado y honesto de la tesis, y ese
> subconjunto ya mostró PF negativo en producción con costos. Ese hallazgo es
> real para la implementación ACTUAL, no para toda la tesis ICT.

| Capacidad | Calificación | Razón |
|---|---|---|
| Fidelidad al sistema | ⚠️ Media-Baja | Falta entry/TP/RR/exec TF |
| Poder estadístico | ❌ Bajo | N=18–38, sin DSR/PBO en runs estándar |
| Poder científico | ⚠️ Medio | Cobertura parcial, datos cortos, no hay diagnosis hipótesis |
| Poder de diagnóstico | ⚠️ Medio | Datos por trade existen, pero no hay reporte drill-down |
| Poder de experimentación | ⚠️ Medio | Motor parametrizable, pero no puede testear entry/TP porque no están parametrizables |
| Cobertura de módulos | ⚠️ 65–70% | 3 componentes estructurales ausentes |

---

## 7. Mapa de riesgos

| Riesgo | Nivel | Efecto |
|---|---|---|
| Concluir “ICT no tiene edge” desde R6.4 | Alto | Falso negativo por cobertura parcial |
| Overfit sobre 6 meses / 7 majors | Alto | Resultados no generalizan |
| Parámetros Optuna sobrerrepresentan motor simplificado | Medio | Selección bias |
| Ausencia de DSR/PBO + N baja | Alto | Conclusiones no estadísticamente sólidas |
| ~~Falta de datos XAUUSD M15 + ≥3-4 años~~ | ~~Alto~~ | ✅ Resuelto 2026-07-24 — A12 pendiente de re-run, no de data |
| Métricas públicas mezclan teoría/producción | Medio | Comparaciones inconsistentes |

---

## 8. Hoja de ruta para que el backtest demuestre la tesis

**Fase corta (1-2 semanas):**
1. Cambiar `entry` al primer toque de la zona FVG/OB post-BOS.
2. Cambiar `_tp_liquidity` al swing opuesto LTF más cercano.
3. Encender `enable_pd_index=True` en Capa 2 por defecto para exponer `poi_present`.

**Fase media (2-4 semanas):**
4. Añadir `invalidators.py` como paso post-entry.
5. Añadir `rr>=1.3` como filtro (no recomendación).
6. Separar `exec_tf` de `ltf` en `evaluate_signals`.

**Fase larga (post-datos):**
7. ~~Bajar XAUUSD M15 + ≥3-4 años (R5)~~ ✅ cerrado 2026-07-24 — ver `docs/DATA_STATUS.md`.
8. **A12:** walk-forward OOS `no_session`×XAUUSD con data multi-año.
9. Integrar Deal Range + Stacking como filtros de calidad, no gates.
10. Habilitar DSR/PBO + PurgedKFold automático en Capa 3 por defecto.

---

*Este informe es base para la Parte III/IV de la auditoría y debe leerse junto a `AUDITORIA_FIDELIDAD_TESIS_SMC_SYSTEMS.md`.*
