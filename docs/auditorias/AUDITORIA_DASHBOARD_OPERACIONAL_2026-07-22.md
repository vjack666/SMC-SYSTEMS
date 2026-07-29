# AUDITORÍA DASHBOARD OPERACIONAL — 2026-07-22

**Alcance:** `app_observador/` (PySide6) = el Dashboard operacional definido por la tesis.
**Corrección de arquitectura (Ruben):** el Dashboard es panel operacional (estado de mercado en vivo).
NO depende del backtest (laboratorio de investigación). Separación estricta mantenida.
**Método:** lectura de código + tesis (`docs/ict/20_TESIS_ICT.md`) + motor (`app_observador/core/engine.py`).
**Regla de diseño (Ruben):** si el motor no provee un campo, el widget muestra "EN CONSTRUCCIÓN". No forzar resultado.

---

## 1. Estado actual

App PySide6 de una ventana, 6 pestañas: Principal, Lab Setup, Noticias, Escáner, Chat, Mapa ICT.
Motor `engine.run_cycle` orquesta scripts MT5 en vivo (`rutina_eurusd`, `semaforo_fundednext`,
`mapa_precio`, `fase_wyckoff_m15`) + plan canónico R7 live (`_canonical_plan`). Cachea `last_cycle.json`.
NO importa `run_backtest` → cumple la separación backtest≠dashboard.
Black-box logging + retención 90 días presentes. Donde falta dato: "SIN DATOS MT5" / "sin datos M1/M5".

---

## 2. Dashboard vs Tesis (tabla de estado)

Elemento tesis | Estado | Dónde
---|---|---
Bias HTF (D1/H4/M15) | ✅ Implementado | SesgoWidget + veredicto.votes
Market Structure (trend) | ✅ | estructura[tf].trend
BOS | ✅ | bos_dir/bos_status
CHOCH | ✅ | choch_status
Sweep / Liquidez | ✅ | sweep_up/down + resumen + TP liquidez
OTE | ✅ | ote_long/ote_short + canonical plan
Kill Zones | ✅ | killzone_activa_ahora + reloj operador
Turtle Soup | ✅ | modelo_ict (score) + checklist intradia
Silver Bullet | ✅ | modelo_ict + checklist scalping (NY AM)
FVG | 🟡 Parcial | texto fvg_state; mapa pinta; NO widget dedicado
Order Blocks | 🟡 Parcial | ob_dir texto; mapa pinta; NO widget dedicado
PO3 (A/M/D) | ✅ | evaluate_po3 ("PO3 COMPLETO/INCOMPLETO")
Estado de mercado | ✅ | semáforo + sesgo + wyckoff
Riesgo | ✅ | EstadoWidget (riesgo día %, DLL 4%, vigilante)
Checklist operacional | ✅ | checklists intradia/scalping
SMT Divergence | ❌ No implementado | Opción B, código nuevo, no existe
Premium/Discount (dealing range 50% EQ) | ❌ No implementado | Tesis §5b/§11: "no existe en código" (libro 21)
Régimen de mercado | ❌ No implementado | no hay indicador en el observador. El motor backtest YA NO usa ATR (migró a rango puro `avg_candle_range`, Fase 1 2026-07-20: `STRUCT_SL_MAX_ATR`→`STRUCT_SL_MAX_RANGE`, `STRUCT_SL_BUFFER_ATR`→`STRUCT_SL_BUFFER_RANGE`). Reusar `avg_candle_range` para derivar régimen (rango comprimido=acumulación/rango; expandido=tendencia/manipulación), SIN ATR.
Strength Score (fuerza numérica) | ❌ No implementado | hay votes L/S + rr, pero no "fuerza %"
Confianza de señal (numérica) | 🟡 Parcial | semáforo color+motivos; no hay % del setup
Calidad de señal (quality_score) | 🟡 Parcial | PO3 complete + modelo score; no quality_score numérico

Preguntas del operador:
- ¿Qué hace el mercado ahora? → ✅
- ¿Sesgo institucional? → ✅
- ¿Fase del modelo ICT? → ✅ (Wyckoff M15 + PO3 + modelo más coherente)
- ¿Qué activos mayor calidad? → ❌ (solo EURUSD, 1 símbolo)
- ¿Sesiones activas? → ✅
- ¿Oportunidades ahora? → ✅ (setup armado + canonical plan + ficha escáner)
- ¿Riesgos antes de operar? → 🟡 Parcial (riesgo cuenta + motivos semáforo + noticias; falta régimen y riesgo del setup concreto)

---

## 3. Componentes faltantes

1. SMT Divergence (Opción B) — no existe en motor ni dashboard.
2. Premium/Discount (dealing range 50% EQ, libro 21) — no existe en código.
3. Régimen de mercado (rango/tendencia/volatilidad) — no hay indicador en el observador.
4. Strength Score / Confianza numérica del setup — el motor no lo calcula.
5. Ranking multi-activo ("¿qué activos mayor calidad?") — observador es 1-símbolo.
6. Widget de solo-FVG / solo-OB (hoy solo texto o pintado en mapa).
7. Evaluación de riesgo del setup concreto (no solo riesgo de cuenta).

---

## 4. Componentes innecesarios

- `monitoring/` (auditoría anterior): monitoreo de equity en vivo (Sharpe/Sortino/Calmar %),
  NO lo usa `app_observador`. Sistema paralelo fuera del alcance operacional.
  Marcar como "fuera de alcance operacional", NO borrar.
- `config.dashboard_report_dir` (de monitoring): muerto, nadie escribe ahí.

---

## 5. Componentes muertos / dudosos

- `engine.py:202-207` (`_canonical_plan` alinea votes): fuerza artificialmente
  `votes[LONG]=2` si el plan canónico es LONG. Hack que desvía el sesgo real del veredicto
  y CREA falso consenso (el operador cree que hay más acuerdo L/S del que hay).
  🚩 BANDERA AMARILLA: corregir ANTES de seguir — o quitar el override, o marcar el
  sesgo del plan canónico explícitamente separado del veredicto de contexto.
- `ResumenWidget` depende de `graphify-out/graph.json` y `docs/WYCKOFF_RULEBOOK.md` para
  citas; si faltan, citas vacías (graceful, no roto) — adornos frágiles, no dato de mercado.
- `chat_widget`: helper LLM, no dato de mercado; útil pero no es dashboard de mercado.

---

## 6. Información crítica que debería verse primero

Las 7 preguntas del operador deberían responderse en UNA CABECERA SIEMPRE VISIBLE
(sin cambiar de pestaña): Sesgo · Régimen · Sesión activa · Riesgo día % · Semáforo · Setup actual.
Hoy el operador debe mirar SesgoWidget (Principal), luego Mapa ICT (estructura visual),
luego Escáner (ficha) — tres pestañas para "¿oportunidad ahora?". Una cabecera always-on lo mata.

---

## 7. Propuesta de rediseño

Principio #1 (Ruben): NUNCA forzar resultado. Campo ausente → "EN CONSTRUCCIÓN"
(ya lo hacen parcialmente con "sin datos M1/M5"). Regla para SMT/premium/discount/régimen.

Referencias (sin copiar TradingView):
- Bloomberg Terminal: densidad + color semántico + cabecera always-on tipo "ticker strip".
- Bookmap: capa de liquidez visual (heatmap BSL/SSL reusa `detect_liquidity`).
- LuxAlgo: "quality/confidence" con barra numérica (reusa votes+rr+po3, sin cálculo nuevo).
- Sierra Chart: mosaico multi-TF (Mapa ICT hoy 1 TF a la vez → mosaico D1|H4|M15).
- Quantower: paneles acoplables (dockable) — baja prioridad, cosmético.

Concreto:
- Cabecera always-visible: Sesgo · Régimen · Sesión · Riesgo · Semáforo · Setup (reorganiza `result` existente).
- Nuevo widget "Calidad del setup" (score desglosado, NO predictor): muestra los sumandos
  reales que el motor YA calcula (HTF alineado, BOS confirmado, liquidez tomada, OTE, PO3,
  Killzone) y resta noticias cercanas → resultado /100. Dice "cumple más condiciones", no "ganará".
- Nuevo panel "MARKET STATE" (la historia del precado, ICT): Fase (Acumulación/Distribución/
  Markup/Markdown) · Bias · Liquidez (SSL/BSL taken) · Manipulación (sí/no) · Expansión
  (pendiente/hecha) · Entrada (esperar/listo). Responde "¿en qué historia está el precio?".
- Mapa ICT → mosaico 3-TF (reusa PNG existentes).
- SMT / Premium-Discount / Régimen → badges "EN CONSTRUCCIÓN" hasta que el motor los calcule.

---

## 8. Arquitectura recomendada

Motor ya está bien (orquesta scripts reales, no duplica). NO tocar backtest.
- Motor debe CALCULAR campos faltantes y exponerlos en `result`:
  SMT (Opción B), premium/discount (libro 21), régimen derivado de `avg_candle_range`
  (rango puro, sin ATR; el backtest ya migró de `STRUCT_SL_MAX_ATR` a `STRUCT_SL_MAX_RANGE`).
- Widgets consumen esas keys; "EN CONSTRUCCIÓN" si faltan.
- Reutilizar, no crear: `detect_liquidity` (backtest) para capa de liquidez del mapa;
  `evaluate_po3` ya se reusa; `signals/po3` ya importado. Cablear existentes al observador.

---

## 9. Roadmap por fases

- Fase A (Alta): cabecera always-visible de estado de mercado (reorganiza `result`, 0 cálculo nueva).
- Fase B (Alta): widget Calidad/Confianza (barra) reusa votes+rr+po3.complete.
- Fase C (Media): SMT Divergence (Opción B) → motor calcula + dato en resumen/mapa.
- Fase D (Media): Premium/Discount (dealing range 50% EQ, libro 21) → motor + badge.
- Fase E (Media): Régimen de mercado → derivado de `avg_candle_range` (rango puro, sin ATR;
  el backtest ya migró de `STRUCT_SL_MAX_ATR` a `STRUCT_SL_MAX_RANGE`) + indicador en cabecera.
- Fase F (Baja): ranking multi-activo → correr motor en N símbolos.
- Fase G (Baja): layout dockable (Quantower-style).

---

## 10. Prioridad

- Cabecera always-visible: ALTA
- Widget Calidad/Confianza: ALTA
- SMT Divergence: MEDIA
- Premium/Discount: MEDIA
- Régimen de mercado: MEDIA
- Ranking multi-activo: BAJA
- Layout dockable: BAJA

---

*Auditoría de código, sin cambios. NO commit/push (regla de Ruben). Corrige la recomendación
vieja de la auditoría `AUDITORIA_DASHBOARD_2026-07-22.md` (conectar run_backtest→dashboard):
queda RETRACTADA por la directiva de separación backtest≠dashboard operacional.*
