# Ítem F — Resolución de conflicto ICT/Wyckoff (P4)

**Estado:** DIAGNÓSTICO + BORRADOR MEDIBLE (no aplicado). Código de producción intacto.
**Objetivo:** Decidir si la *penalización suave* actual (`conflict_penalty=0.15`) es mejor que un
*veto duro* (señal NEUTRAL cuando ICT y Wyckoff contradicen), midiendo Profit Factor (PF)
en walk-forward out-of-sample (OOS).

> ⚠️ REGLA ESTRICTA: este documento SOLO crea archivos nuevos. No se modifica `agents/`,
> `backtest/`, `detectors/`, `adapters/`, `signals/`. El diff de abajo es una *propuesta*;
> la implementación la hace el usuario tras validar los resultados del harness.

---

## 1. Cómo funciona HOY la penalización suave

Flujo ICT + Wyckoff → decisión (en `agents/decision_agent.py`):

1. **`decide()`** (`agents/decision_agent.py:129-135`) recibe los `AnalysisResult` de ICT, Wyckoff y
   Structure (más `ml_probability` opcional) y construye un `DecisionRecord`.
2. Cada agente aporta `bias` (BULLISH/NEUTRAL/BEARISH) y `confidence` con un peso fijo
   (`DecisionConfig`, `agents/decision_agent.py:11-18`): ICT 0.35, Wyckoff 0.30, Structure 0.20,
   ML 0.15. Se calcula `weighted_bias_sum / total_weight` → `combined_bias_val` y
   `combined_confidence` (`agents/decision_agent.py:205-206`).
3. **Lógica de conflicto** (`agents/decision_agent.py:208-214`):

```python
biases = [r.bias for r in [ict, wyckoff, structure] if r is not None and r.confidence > 0.0]
if len(set(b for b in biases if b != "NEUTRAL")) > 1:
    conflict_penalty = self.config.conflict_penalty
    combined_confidence = max(combined_confidence - conflict_penalty, 0.0)
    record.conflict_penalty_applied = conflict_penalty
    conflicts.append(f"conflict: {', '.join(biases)}")
    reasons.append(f"conflict penalty -{conflict_penalty:.2f}")
```

- Si hay **más de un** bias no-neutral distinto (p.ej. ICT=BULLISH y Wyckoff=BEARISH), entra al `if`.
- Resta `conflict_penalty` (0.15) a `combined_confidence`, con piso en 0.0.
- **NO anula la señal**: si el bias combinado sigue ≥ 0.15 → BULLISH, ≤ -0.15 → BEARISH
  (`agents/decision_agent.py:216-221`). Solo degrada la confianza.
- El valor aplicado se registra en `record.conflict_penalty_applied`
  (`agents/decision_agent.py:43`, `212`), visible en `orchestrator.py:104` y en el dataset ML
  (`models/quality_filter.json:67`).

**Consecuencia:** con conflicto, la señal suele bajar de `min_combined_confidence=0.55`
(`agents/decision_agent.py:17`, `231-232`) y queda invalidada, PERO si la confianza base era alta
(>0.70) la señal conflictiva AÚN se emite. El veto suave solo "castiga", no "bloquea".

---

## 2. Dónde insertar el flag de veto duro

El punto de inserción es **justo después** de detectar el conflicto
(`agents/decision_agent.py:209-214`). Se añade un campo `conflict_mode` a `DecisionConfig`
(`agents/decision_agent.py:18`) y una rama `if` que, en modo `"hard"`, fuerza NEUTRAL y
confianza 0.0 antes de calcular `final_bias` (`agents/decision_agent.py:216`).

`combined_bias_val` sigue igual; lo que cambia es que el conflicto en modo duro descarta la
señal completamente (comportamiento equivalente a un filtro de invalidación más estricto).

---

## 3. DIFF PROPUESTO (no aplicado)

```diff
--- a/agents/decision_agent.py
+++ b/agents/decision_agent.py
@@
 class DecisionConfig:
     ict_weight: float = 0.35
     wyckoff_weight: float = 0.30
     structure_weight: float = 0.20
     ml_weight: float = 0.15
     min_combined_confidence: float = 0.55
     conflict_penalty: float = 0.15
+    # "soft" = resta conflict_penalty a la confianza (actual)
+    # "hard" = fuerza NEUTRAL/confianza 0.0 si ICT y Wyckoff contradicen
+    conflict_mode: str = "soft"
@@
         biases = [r.bias for r in [ict, wyckoff, structure] if r is not None and r.confidence > 0.0]
         if len(set(b for b in biases if b != "NEUTRAL")) > 1:
             conflict_penalty = self.config.conflict_penalty
-            combined_confidence = max(combined_confidence - conflict_penalty, 0.0)
-            record.conflict_penalty_applied = conflict_penalty
-            conflicts.append(f"conflict: {', '.join(biases)}")
-            reasons.append(f"conflict penalty -{conflict_penalty:.2f}")
+            conflicts.append(f"conflict: {', '.join(biases)}")
+            if self.config.conflict_mode == "hard":
+                # Veto duro: señal NEUTRAL, confianza 0.0
+                record.conflict_penalty_applied = 1.0
+                reasons.append("conflict HARD veto -> NEUTRAL")
+            else:
+                # Penalización suave (comportamiento actual)
+                combined_confidence = max(combined_confidence - conflict_penalty, 0.0)
+                record.conflict_penalty_applied = conflict_penalty
+                reasons.append(f"conflict penalty -{conflict_penalty:.2f}")
@@
+        # Aplicar veto duro ANTES de mapear bias final
+        if self.config.conflict_mode == "hard" and any("HARD veto" in r for r in reasons):
+            final_bias = "NEUTRAL"
+            combined_confidence = 0.0
+        elif combined_bias_val >= 0.15:
             final_bias = "BULLISH"
         elif combined_bias_val <= -0.15:
             final_bias = "BEARISH"
         else:
             final_bias = "NEUTRAL"
```

> Notas: en modo `"hard"`, `conflict_penalty_applied` queda en `1.0` solo como marcador de
> diagnóstico (no es una resta real). La rama respeta `record.conflicts`/`reasons` para que el
> dataset ML y el orchestrator sigan funcionando sin cambios.

---

## 4. Cómo medir (harness de ablación)

Se crean dos escenarios invocables por `python -m harness --scenario ...` usando
`harness/scenarios/backtest_veto_ablation.yaml` + `harness/fixtures/backtest_veto_ablation_fixture.yaml`.

El fixture apunta a `data/raw` (H4) **sin MT5** y define `conflict_mode` en el bloque `config` del
backtest. **Importante:** `CombinedBacktestConfig` (`backtest/engine.py:30-48`) hoy NO recibe
`DecisionConfig`; el backtest usa el ensemble vía `AgentOrchestrator` con `DecisionAgent()` por
defecto. Para que la ablación sea MEDIBLE sin tocar producción, el fixture declara la intención y
la clave `conflict_mode` que el adapter leerá cuando se implemente el Ítem F. El escenario de
ablation corre **dos pases** (soft / hard) sobre los mismos símbolos H4 y compara PF.

Ver archivos:
- `harness/scenarios/backtest_veto_ablation.yaml`
- `harness/fixtures/backtest_veto_ablation_fixture.yaml`

---

## 5. Decisión: walk-forward OOS

Ambos modos (`soft` y `hard`) deben evaluarse en **walk-forward out-of-sample** sobre `data/raw`
H4 (EURUSD, GBPUSD, XAUUSD, NZDUSD, USDCAD, USDCHF, USDJPY). Métrica de elección: **PF OOS**.
Elegir el mayor. La decisión final la toma el usuario tras correr el harness — el subagente NO
aplica el cambio de producción.

**Riesgo a vigilar:** el veto duro reduce el número de señales (puede subir PF pero bajar
exposición/oportunidades). Complementar PF con `total_trades` y `max_drawdown_pct` para no
sobreajustar a un periodo.
