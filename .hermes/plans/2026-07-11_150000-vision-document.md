# Vision Document — SMC-SYSTEMS (ict_backtest + observador FundedNext)

> **Para Hermes:** este es un documento de VISIÓN (propósito y dirección a largo
> plazo), no un plan de implementación paso a paso. Sirve de brújula para
> decisiones arquitectónicas y priorización. Los planes de ejecución concretos
> viven en SDD/SDD_* y en `.hermes/plans/`.

**Fecha:** 2026-07-11
**Autor:** Hermes Agent (Ruben Mujica — Radiología / Trader prop firm)
**Estado:** Borrador v1.0 para revisión de Ruben

---

## 1. Propósito (el "por qué")

SMC-SYSTEMS debe convertir el análisis ICT/Wyckoff en **decisión de trading
confundable y verificable**, no en humo. Tres verdades lo guían:

1. **El edge se prueba, no se cree.** Todo número de performance
   (Profit Factor, Win Rate, Sharpe) debe ser reproducible desde datos crudos
   y soportar escrutinio externo (auditoría). Si un bug de look-ahead o una
   copia errónea de señal infla el PF, el sistema pierde su razón de ser.
2. **El trader manda, la máquina observa.** Hoy el sistema es un *observador*
   (loop 24/7, ficha técnica, semáforo, alertas). Nunca abre órdenes solo. La
   automatización total es una *opción futura*, no una obligación.
3. **Trazabilidad regla → código → número.** Cada métrica reportada debe poder
   rastrearse hasta la regla ICT documentada, el detector que la implementa y
   el test que la fija.

---

## 2. Contexto actual (post-auditoría 2026-07-11)

### 2.1 Lo que funciona (producción)
- **Observador FundedNext**: `scripts/loop_analisis.py` 24/7 (lun-vie), ficha +
  informe + semáforo + alertas. Arranque automático vía `start_hermes_session.ps1`.
- **Vigilante de riesgo**: cierra posiciones manuales al 2%/4% flotante (solo cierra).
- **App observador PySide6**: semáforo, mapa ICT, alineación Wyckoff D1/H4/M15.
- **Edge Diagnosis (SMC puro)**: 21 variantes × 8 símbolos = 168 celdas, 0 errores.
  Mejor celda `no_session` × XAUUSD OOS PF 1.642.
- **Backtest combinado (4 símbolos, ML)**: WR 63.7%, PF 1.61, Sharpe 3.33, DD 4.96%.

### 2.2 Lo que se acaba de corregir (refacción por auditoría externa)
Commiteado en `c8c92cd`. Hallazgos verificados empíricamente y corregidos:
- **#1 Look-ahead en `_swing_points`** → ventana no centrada + `shift(lookback)`.
  Test: `test_swing_no_lookahead`.
- **#2 CHOCH = copia de BOS** → CHOCH real rompe el swing del último BOS.
  Test: `test_choch_differs_from_bos`.
- **#3 Sin tests** → `tests/test_ict_backtest.py` (7 tests, <1s).
- **#4 Sin costos** → `simulate_trade` acepta `cost={spread,commission,slippage}`.
  Test: `test_engine_spread_reduces_pnl`.
- **#5 Walk-forward = 1 split** → rolling multi-fold, dirección temporal correcta.
  Test: `test_walkforward_multi_fold`, `test_walkforward_no_inverted`.
- **#7 Imports/duplicación** → `_row_at_time` en `ict_backtest/_util.py`.

### 2.3 Lo que está EN CURSO (corridas de verificación)
- Capa 2 corregida (params 12/8) → `docs/ict/logs/CAPA2_REFAC_CORRIDACORREGIDA.log`
- Capa 3 walk-forward multi-fold (n_windows=4, 12 trials) → `docs/ict/logs/CAPA3_REFAC_WF.log`
- **Pendiente medir:** PF real tras #1/#2. Hipótesis abierta (no asumida):
  el PF corregido será < 2.0-2.6 previos, pero debe seguir siendo >1 para
  confirmar edge. El veredicto se emite al terminar la Capa 3.

---

## 3. Principios rectores (no negociables)

| # | Principio | Aplicación concreta |
|---|-----------|---------------------|
| P1 | **Sin look-ahead, nunca** | Toda variable derivada se expone solo tras su vela de confirmación. Tests lo atrapan. |
| P2 | **Costos reales o silencio** | Ningún PF se reporta sin spread/comisión/slippage explícitos. |
| P3 | **Validación OOS múltiple** | Walk-forward ≥ 3 folds contiguos, dirección temporal correcta. Un solo split no cuenta. |
| P4 | **Tests deterministas** | Datos sintéticos pequeños para reglas; datos reales solo para corridas pesadas. |
| P5 | **Trader al mando** | Automatización de órdenes es opt-in y requiere aprobación de Ruben + cumplimiento FundedNext. |
| P6 | **Documentación viva** | Cada cambio de regla/arquitectura se documenta en `docs/ict/` (libro = carpeta). |
| P7 | **Reproducibilidad** | Corridas con params fijos + log + commit. Mismo input → mismo output. |

---

## 4. Alcance futuro (dirección)

### 4.1 Corto plazo (Ya en curso / próximo)
- **Cerrar veredicto Capa 3** con PF corregido multi-fold.
- **Extender Capa 3 a XAUUSD** (H4) — backtest en H4.
- **README.md / COMPLETION_REPORT.md** que AGENTS.md referencia (pendiente hace tiempo).
- **Curva de equidad barra-a-barra** (cada 15 min, R no realizado).

### 4.2 Medio plazo (cuando el edge corregido confirme PF>1 robusto)
- **Walk-forward PurgedKFold + DSR** (Deflated Sharpe) en `ict_backtest` siguiendo
  el estándar ya implementado en `ml/stats_validator.py` (F13).
- **Filtro de calidad opcional** en `ict_backtest` usando el XGBoost de `ml/`
  (hoy desacoplado; la Capa 3 es "SMC puro sin ML" por diseño).
- **Aumentar trials Optuna a 30-60** para refinar el óptimo.

### 4.3 Largo plazo (solo si Ruben lo autoriza)
- **Automatización de órdenes** vía puente MT5 ZeroMQ (hoy heredado, no cableado).
  Requiere: walk-forward OOS validado (A12), monitoring en loop, VPS, y cumplimiento
  Stellar Lite $5K (`tools/fundednext_compliance.py`).
- **Multi-símbolo en ict_backtest** (hoy solo EURUSD/XAUUSD puntuales).

---

## 5. No-objetivos (lo que este sistema NO es)

- **NO es un bot que opera solo** hoy. El modo actual es observador.
- **NO es un reemplazo del ICT Mentorship de pago.** `docs/ict/` son reglas
  operativas verificables de fuentes públicas.
- **NO promete PF sin costos.** Todo número lleva su factura de spread/comisión.
- **NO asume overfit como éxito.** PF alto en in-sample sin OOS multi-fold = ruido.

---

## 6. Riesgos y decisiones abiertas

| Riesgo | Impacto | Mitigación / Decisión |
|--------|---------|----------------------|
| PF corregido cae < 1.10 en OOS | Edge no viable tal como está | Revisar definición de CHOCH/BOS; probar en XAUUSD; reportar honestamente. |
| Overfit en optimización bayesiana | PF inflado | Walk-forward multi-fold + DSR; no usar solo in-sample. |
| Performance (~8 min / 50k velas) | Iteración lenta | Vectorizar loop de `sequence.py` (hallazgo #6, medio plazo). |
| Costos de MT5 reales distintos a los asumidos | PF teórico ≠ real | Calibrar spread/commission desde MT5 en vivo antes de cualquier automatización. |
| Automatización prematura | Riesgo de cuenta prop firm | Puerta dura: aprobación Ruben + cumplimiento + walk-forward OOS. |

---

## 7. Criterio de éxito de la visión

La visión se considera cumplida cuando:

1. Cualquier PF reportado por SMC-SYSTEMS es **reproducible, con costos y OOS
   multi-fold**, y sobrevive una auditoría externa como la de 2026-07-11.
2. El observador entrega a Ruben **contexto accionable** diario sin ruido.
3. La trazabilidad **regla ICT → detector → test → número** es completa y citada.

---

## 8. Relación con otros documentos

- `docs/CRONOGRAMA_Y_ROADMAP.md` — fuente de verdad de hitos (v2.2). Este VISION
  alinea la dirección técnica con esos hitos.
- `docs/ict/10_AUDITORIA_REFACCION/` — libro de la auditoría que motivó la refacción.
- `docs/ict/SDD_REFACCION_2026-07-11.md` — SDD de la refacción (ejecución concreta).
- `AGENTS.md` — reglas de operación autónoma del agente.
- `COMPLETION_REPORT.md` — wiring del pipeline y métricas de backtest.

> **Nota:** Este documento es vivo. Se actualiza tras cada hito relevante
> (corrida Capa 3 corregida, extensión XAUUSD, automatización). La versión
> v1.0 queda pendiente de aprobación de Ruben antes de marcarse como oficial.
