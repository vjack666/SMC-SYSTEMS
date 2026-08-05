# R4 Cierre — ICT puro + meta fondeo (6 meses)

**Fecha:** 2026-07-17  
**Protocolo:** R4-clean (sequence tesis 18) + funding-gate  
**Script:** `scripts/r4_clean_funding_gate.py`  
**Artefacto JSON:** `results/r4/r4_clean_funding_LATEST.json`

---

## Meta del proyecto (actualizada)

No basta un PF “bonito” en multi-año. La meta operativa es:

> **En ~6 meses de histórico, la estrategia debe ser capaz de pasar una prueba de fondeo**
> (estilo FundedNext Stellar: ~8% fase 1 / ~10% 1-step, sin romper ~4% diario ni ~8% max DD),
> con riesgo controlado (~1% por trade).

Si con 6 meses **no** se acerca a ese shape (o pierde), **la estrategia no sirve para fondeo**
bajo automatización actual.

---

## Contexto externo (investigación web, 2026-07-17)

Antes de descartar ICT/Turtle/Silver Bullet se consultaron fuentes públicas:

| Fuente | Hallazgo relevante |
|--------|-------------------|
| r/Forex (backtest mecánico 10y, 7 setups ICT, 2026) | **Silver Bullet** ~34% de ventanas 6m “FTMO-like”; **Turtle Soup** ~**27%** pese a WR 68%. Alta WR **no** salva challenges: **clustering de pérdidas** rompe daily DD. |
| FundedNext (Stellar 2-step) | Targets típicos **8% luego 5%**; daily/max loss firm-specific (~3–5% / ~6–10%). |
| Videos/marketing ICT “pasa challenges” | Abundan claims; **no** son evidencia reproducible con filtro mecánico + reglas de prop. |
| Prop risk notes (2026) | ICT con RR alto y 1–2% riesgo puede **quemar el daily** en 3 pérdidas seguidas. |

**Implicación:** no descartamos ICT “porque internet dice que es scam”. Lo medimos con **gate de fondeo de 6m**. Internet **sí** confirma que, en mecánico, los pass-rates de challenges con ICT puro son **bajos** y el WR engaña.

---

## Método (R4-clean honesto)

- Motor: `ict_backtest.canonical.evaluate_signals` → sequence  
- Filtros tesis 18: SL estructural (mecha sweep), RR ≥ 1:3 (o liquidez), killzone London/NY AM/NY PM  
- Fill: `next_open`  
- Costos: ON (tabla `costs.py`) y control OFF (teoría)  
- Ventana: **últimos 180 días** de M15 disponibles  
- Pares: **EURUSD, GBPUSD** · HTF→LTF **H4→M15**  
- Modos: **Turtle CT** (`counter_trend=True`) y **AT** (a-favor)  
- Funding sim: 1% riesgo/trade, DLL 4%, MLL 8% trailing, targets 8% / 10%

---

## Resultados (costos ON, 180 días)

| Celda | Señales | Trades | PF | WR | E[R] | Equity % | MaxDD % | ¿Viable fondeo 6m? |
|-------|---------|--------|-----|-----|------|----------|---------|---------------------|
| EURUSD **Turtle CT** | 5 | 5 | **0.70** | 40% | −0.19 | −0.97 | 3.2 | **NO** |
| EURUSD Sequence AT | 5 | 5 | **1.18** | 60% | +0.07 | **+0.37** | 1.7 | **NO** (no llega a +8%) |
| GBPUSD **Turtle CT** | 7 | 7 | **0.34** | 29% | −0.48 | −3.33 | 3.8 | **NO** |
| GBPUSD Sequence AT | 10 | 9 | **0.06** | 11% | −0.72 | −6.50 | 6.6 | **NO** |

### Control sin costos (Turtle CT)

| Celda | Trades | PF | Nota |
|-------|--------|-----|------|
| EURUSD CT theory | 5 | 1.05 | Casi flat; **costos** lo tiran a 0.70 |
| GBPUSD CT theory | 7 | 0.43 | Ya pierde sin costos |

**Ninguna celda:** `pass_stellar_2step_p1_shape` ni `pass_stellar_1step_shape`.  
**Ninguna** acumula ~8% en la ventana con 1% riesgo.

---

## Veredicto R4 (oficial)

### `REJECT_NO_EDGE` — sin edge para live / fondeo automatizado

1. **Turtle Soup v2.8 (CT, tesis 18, costos ON):** PF &lt; 1.10 en EURUSD y GBPUSD; expectancy negativa; **no** shape de fondeo en 6m.  
2. **Sequence a-favor:** EURUSD PF 1.18 pero **N=5** y **+0.37%** en 6m → **insuficiente** para challenge 8% (meta de fondeo fallida). GBPUSD AT destruye cuenta en el sim.  
3. Gate clásico R4 (PF OOS ≥ 1.10 por modelo con trades serios): **no pasado**.  
4. Gate meta proyecto (fondeo en 6m): **no pasado**.

### Recomendación operativa

| Uso | Decisión |
|-----|----------|
| Bot / auto LIMIT “porque ICT dice” | **NO** |
| Observador + decisión humana | **SÍ** (mapa, sesgo, vigilante) |
| Demo LIMIT para probar cable MT5 | **SÍ**, con riesgo chico, sin pretender edge |
| Paper / A12 sobre estos modelos ICT puros | **No prioritario** hasta cambiar reglas o discreción humana |

---

## Qué cierra y qué no

| Ítem | Estado |
|------|--------|
| R4 medición aislada + look-ahead | ✅ |
| R4-clean Turtle v2.8 + funding 6m | ✅ **CERRADO hoy** |
| R4-tesis libro 18 | ✅ (docs; sequence alineado) |
| Edge para bot | ❌ no demostrado |
| R3.5 libros 22/23 | Abierto (no bloquea cierre R4) |
| R5 datos multi-año | Abierto (útil para A12; **no** rescata estos 6m) |
| A12 walk-forward | Bloqueado: no hay celda ganadora R4 |

---

## Próximo paso científico (si se insiste en edge)

No “más Optuna sobre el mismo filtro”. Opciones honestas:

1. **Modelo discrecional asistido** (app observa; humano filtra) — alineado a “trader manda”.  
2. **Cambiar unidad de edge** (session model / NY open style con menor correlación de pérdidas — lo que mejoró pass-rate en el estudio público).  
3. **Aceptar** que el stack mecánico actual no es funding-ready y priorizar producto observador + riesgo.

---

*Cierre R4 firmado por corrida reproducible `scripts/r4_clean_funding_gate.py`.*
