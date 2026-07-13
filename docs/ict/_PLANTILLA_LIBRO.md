# ICT — [NOMBRE DEL CONCEPTO]

| Campo | Valor |
|-------|-------|
| **ID** | `NN_NOMBRE.md` |
| **Versión** | 1.0 |
| **Fecha** | YYYY-MM-DD |
| **Estándar** | ADR-021 / RFC-001 |
| **Estado** | Draft \| Stable \| Needs-code |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) (no duplicar cifras) |

> **Fuente de verdad:** código del repo + auditorías. Fuentes externas solo como respaldo.

---

## 0. Contrato operativo (sí / no)

| # | Condición medible | Obligatorio |
|---|-------------------|:-----------:|
| 1 | … | Sí |
| 2 | … | Sí |

**Setup completo** = todas las filas “Sí” en verdadero.  
**Setup incompleto** = falta al menos una → el sistema **no** debe sugerir entrada.

---

## 1. Teoría

Definición en 1–2 párrafos. Términos en negrita. Sin jerga sin definir.

---

## 2. Práctica del trader

Pasos numerados: contexto HTF → trigger → confirmación LTF → SL/TP → sesiones.

---

## 3. Algoritmo (detección automática)

Pseudocódigo o condiciones booleanas. Riesgos: look-ahead, Chart Shift, profundidad de histórico, zona horaria.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Detector | `detectors/…` | … |
| Pipeline | `signals/pipeline.py` | … |
| Backtest | `ict_backtest/…` | … |
| UI | `app_observador/…` | … |

---

## 5. Auditoría y huecos

- Hallazgos cerrados (#1, #2, …) con enlace a `10_AUDITORIA_REFACCION/`.
- **Huecos abiertos** (lista accionable para el roadmap de aplicación).

---

## 6. Resultados

Enlazar `METRICS_CANON`. No copiar tablas de PF aquí.

---

## 7. Checklist de aplicación al sistema

- [ ] Tests sintéticos
- [ ] Alineación UI ↔ backtest
- [ ] Métricas aisladas del modelo
- [ ] Documentado en índice

---

## En resumen

3–5 oraciones. Qué es + dónde vive + qué falta.
