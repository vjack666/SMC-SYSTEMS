# 11 — Sweep + OTE: manual vs automático vs SMC-SYSTEMS

| Campo | Valor |
|-------|-------|
| **ID** | `11_SWEEP_OTE_MANUAL_VS_AUTO.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable |
| **Tipo** | Investigación de campo + diseño |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato de diseño del sistema

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Hoy el operador puede trabajar **manual** con checklist del observador | Sí |
| 2 | Toda señal debe ser **automation-ready** (campos: dir, SL, TP, reason) aunque no se envíe orden | Sí |
| 3 | No hay ejecutor de órdenes cableado al flujo diario (modo observador) | Sí (política actual) |
| 4 | Shadow log “hubiera entrado” antes de bot real | Sí (R7) |
| 5 | Bot real solo tras A12 + autorización humana | Sí |

---

## 1. Teoría — tres modos

| Modo | Quién decide | Fortaleza | Debilidad |
|------|--------------|-----------|-----------|
| Manual | Trader | Contexto, intuición | Emoción, fatiga |
| Auto (EA) | Código | Disciplina, 24/5 | Rigidez, bugs |
| Híbrido SMC-SYSTEMS | Máquina propone, humano manda | Trazable | Hay que cerrar gaps |

---

## 2. Práctica manual (síntesis Bennett / rutinas públicas)

1. HTF primero (sesgo).  
2. OTE 62–79% del swing externo.  
3. Sweep + **esperar** confirmación.  
4. Bajar a M15 para entrada.  
5. SL detrás del sweep; TP liquidez opuesta.

---

## 3. Práctica automática (patrón EA ICT típico MQL5)

1. Bias H1.  
2. Sweep (swing / PDH-PDL / Asia).  
3. MSS por cierre.  
4. Displacement.  
5. FVG entry.  
6. TP liquidez o RR.  
7. Gestión de riesgo automática.

---

## 4. Código SMC-SYSTEMS (híbrido)

| Capa | Qué hace |
|------|----------|
| Detectores + pipeline | Cerebro de señal (similar al EA) |
| `ict_backtest` | Prueba la lógica |
| Observador | Checklist + mapas + semáforo |
| Paper/live runners | Existen, **no** en flujo diario observador |
| MQL5 bridge | Heredado, no cableado al día a día |

### Gaps hacia 100% auto

| Gap | Acción roadmap |
|-----|----------------|
| Sin ejecutor en flujo diario | R8 solo post-A12 |
| TP a menudo 2×ATR, no siempre liquidez | Alinear a libro 05 |
| OTE casi no-op | R3 libro 10 |
| PO3 no es estado complete | R1 |

---

## 5. Auditoría

Este libro no corrige bugs de mercado; fija **política**.  
Cualquier “auto” sin METRICS y A12 viola el cronograma.

---

## 6. Resultados

No hay PF de “modo manual”. El híbrido hereda [METRICS_CANON §2–3](../METRICS_CANON.md).

---

## 7. Checklist de aplicación

- [ ] Shadow log diario  
- [ ] Señal con SL/TP/reason serializable  
- [ ] No cablear bot hasta gates  
- [ ] TP por liquidez opuesta como opción  

---

## En resumen

Manual y auto hacen la **misma secuencia** (sesgo → sweep → confirmación → zona).  
SMC-SYSTEMS ya es un **cerebro de señal**; el 10/10 operativo es shadow fiel + gates, no un bot prematuro.
