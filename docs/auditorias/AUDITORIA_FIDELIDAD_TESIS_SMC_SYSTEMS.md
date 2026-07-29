# AUDITORÍA DE FIDELIDAD TESIS ↔ IMPLEMENTACIÓN
## SMC-SYSTEMS — Parte I: Estado real del sistema contra la tesis ICT

**Fecha:** 2026-07-22  
** Autor:** Auditoría interna (Hermes)  
**Fuentes:** `20_TESIS_ICT.md`, `SPEC_TESIS_FORMAL.md`, `docs/METRICS_CANON.md`,  
`ict_backtest/{sequence,market_structure,engine,canonical,run_backtest}.py`

---

## Resumen ejecutivo

El código implementa **el 62-70% de la tesis**. Existe un motor secuencial
event-driven limpio (sin look-ahead), SL estructural medido, POI como bonus
no-gate, y wiring parcial de setups nuevos. Pero **faltan 3 componentes
estructurales** de alta prioridad y **2 implementaciones están desfasadas**
de la tesis.

---

## Matriz tesis ↔ código

# leyenda:
# ✅ completo | ⚠️ parcial | ❌ ausente | ≠ diverge

| Componente tesis | Código real | Estado | Evidencia / gap |
|---|---|---|---|
| Sweep manipulación | `canonical_sweep` liquidity_context.py | ✅ | `sequence.py` § `_has_sweep` usa LTF+HTF |
| BOS/CHOCH/MSS | `detectors/bos.py`, `market_structure.py` | ✅ | `confirm_bars=2`, sin look-ahead |
| Displacement | `detectors/displacement.py` | ✅ | `sequence.py` § `_has_displacement` |
| PD Arrays FVG/OB | `detectors/fvg.py`, `detectors/ob.py` | ✅ | columnas `fvg_bullish/bearish`, `ob_bullish/bearish` |
| Breaker / MMXM | `ict_backtest/setups/breaker_block.py` | ⚠️ | detector unitario existe, wiring nuevo en `canonical.py`; tests fixtures rotos, no validado end-to-end |
| OTE (libro 23) | `ict_backtest/setups/ote.py` flag helper | ⚠️ | existe helper; wiring post-evaluate_signals en `canonical.py`; **sin calibración práctica** (sigue siendo no-op en producción real) |
| SMT Divergence | NO EXISTE | ❌ | no hay detector de pares correlacionados |
| 3 capas HTF/ITF/exec TF | `SequenceConfig` + runner `TF_CHAIN` | ⚠️ | infra existe, pero `exec_tf == ltf` y `build_signals_from_frames` no recibe `itf`/`exec_tf` separados |
| Entry en retorno a zona | `engine.py`:`build_signals_from_frames` | ❌ | **entra en `row["close"]` del BOS**, no en retorno a FVG/OB |
| SL estructural | `engine.py`:`calc_structural_sl` | ✅ | medido en v29: EURUSD PF 0.771→1.128 |
| TP liquidez cercana | `engine.py`:`_tp_liquidity` | ❌ | **usa cluster promedio HTF**, no swing opuesto LTF más cercano |
| RR mínimo 1:3 | `SequenceConfig.tp_mode="fixed2r"` | ❌ | default es 1:2; filtro 1:3 no aplicado |
| Killzone London + NY AM + NY PM | `rules.py`:`checklist_scalping` | ⚠️ | solo NY AM lógica; TZ pendiente; London/NY PM no cableadas |
| POI = PD Array en zona + sesgo + respaldo | `market_object.py` role=POI + `poi_filter.py` | ⚠️ | existe como bonus `poi_present`, pero filtros de zona/sesgo/respaldo no están parametrizados como contrato; Fase E mostró PF 0.900 cuando se usó como gate duro |
| POI anclado a narrativa HTF | `poi_anchor.py`, `htf_pd_index.py` | ⚠️ | existe índice HTF, pero `enable_pd_index=False` por defecto y v2 coverage `v2_partial` 86.1% con C06 POI MISSING |
| Dealing range / premium-discount (EQ 50%) | `dealing_range.py` + `dealing_range_motor.py` | ⚠️ | módulos existen pero **no integrados en pipeline canónico** `evaluate_signals` |
| Stacking multi-TF eleva tier | `tier_engine.py` | ⚠️ | infra existe pero no consumida por sequence canónico como regla de tier |
| Invalidación estructural | `sequence.py` + `invalidators.py` | ⚠️ | existe pero no ejecutada como paso post-entry en pipeline actual |
| PlanFSM | `plan_fsm.py` | ⚠️ | declarada; no integrada en `run_sequence_backtest` |
| ML quality filter | `ml/inference.py` + `paper_trading/runner.py` | ✅ | XGBoost gate en paper/live; opcional en backtest |
| Walk-forward OOS | `optimize.py`, `walk_forward.py` | ⚠️ | PurgedKFold existe; **data R5 OK (2026-07-24)** — A12 pendiente de re-run, no de descarga |
| Metrics científicas | `stats_validator.py` (DSR/PBO/CVaR) | ⚠️ | módulo existe pero **no se usa en runs estándar** de Capa 2/3; métricas publicadas solo PF/WR/ expectancy |

---

## Contradicciones código ↔ tesis

1. **Entrada close del BOS vs retorno a zona**  
   Tesis §6: *"ICT no entra en el close del BOS, entra en el retorno a la zona"*  
   Código: `engine.py` `build_signals_from_frames` setea entry al close de la vela de estructura.  
   Impacto: **alto** — es la mitad del bug que mató v28/v29.

2. **TP cluster HTF vs liquidez LTF cercana**  
   Tesis §8: *"TP = liquidez opuesta del LTF más cercana"*  
   Código: `_tp_liquidity` usa `bsl_price`/`ssl_price` del LTF pero como **cluster promedio**; si el rango es amplio, TP queda lejano y el trade sale por `hold_limit`.  
   Impacto: **alto** — 7/11 EURUSD y 11/13 GBPUSD salieron por hold limit en v29.

3. **POI como bonus vs filtro duro**  
   Tesis §5b + auditoría empírica: POI bonus mantiene PF; POI duro hunde a PF 0.900.  
   Código: `poi_filter.py` ya fija `as_gate=False` por defecto (bueno), pero `enable_pd_index=False` en runner hace que el bonus ni siquiera se calcule.  
   Impacto: **medio** — el código no ejecuta el bonus porque el flag está apagado por defecto.

4. **Ejecución en exec TF separado**  
   Tesis §5: *"SL y entry SIEMPRE en exec TF; HTF/ITF solo sesgo y zonas"*  
   Código: `exec_tf == ltf`, no hay `itf` separado.  
   Impacto: **medio-alto** — falta la capa de confirmación fina.

5. **RR 1:3 minimum vs fixed2r**  
   Tesis §9: **RR mínimo 1:3**  
   Código: `tp_mode="fixed2r"` usa 1:2.  
   Impacto: **medio** — el motor no exige el RR mínimo del modelo 2022.

---

## Módulos completos / parciales / inexistentes

**Completos (implementados y medidos empíricamente):**
- BOS/CHOCH con confirmación por cuerpo, sin look-ahead.
- SL estructural anclado a mecha del sweep.
- Pipeline simulación vela-a-vela con costos y fill next-open (R6.3).
- ML pipeline + quality filter opcional.
- POI como bonus, no gate duro (Fase E learning).

**Parciales (existe código pero no ejecuta la regla completa de la tesis):**
- Entry en retorno a zona → hoy close del BOS.
- TP en liquidez cercana → hoy cluster promedio HTF.
- Exec TF fino → hoy `ltf == exec_tf`.
- RR 1:3 → hoy fixed2r.
- Killzones → solo NY AM lógica, sin TZ ni London/NY PM.
- Dealing range/premium-discount → módulos sueltos sin wiring.
- PlanFSM → declarada pero no orquesta el runner actual.
- SMT Divergence → no existe.

**Inexistentes (sin código):**
- Detector SMT Divergence correlacionado.

---

## Conclusión Parte I

El sistema **no está alineado completamente** con la tesis. La columna vertebral
(eventos + estructura + SL estructural) está bien implantada y medida.  
Los desvíos están en **entry, TP, RR y temporalidad fina**: exactamente los
puntos que la tesis identifica como causa principal de resultados negativos
en v28/v29.

**Prioridad de cierre:**
1. Entry en retorno a zona (bug #1)
2. TP nearest opposite liquidity (bug #2)
3. RR 1:3 mínimo + exec TF separado
4. SMT Divergence + Brecha A ancla narrativa completa
5. Deal range + stacking como filtro, no gate
