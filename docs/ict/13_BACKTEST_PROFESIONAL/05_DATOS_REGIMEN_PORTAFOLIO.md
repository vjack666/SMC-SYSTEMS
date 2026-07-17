# 05 — Datos, régimen y portafolio

| Campo | Valor |
|-------|-------|
| **ID** | `13/05_DATOS_REGIMEN_PORTAFOLIO` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estado** | Stable |

---

## 1. Teoría

### Datos

En FX el “survivorship” de acciones pesa menos, pero importan:

| Riesgo | Efecto |
|--------|--------|
| Huecos / barras faltantes | Señales fantasma o ATR roto |
| TZ / DST | Killzones mal alineadas con London/NY |
| Convención de timestamp | Open MT5 vs close de otro vendor |
| Histórico corto | Overfit a un régimen (ej. solo 2024–25) |
| M1 incompleto | “Minuto a minuto” de marketing, no de ciencia |

### Régimen

Un edge que solo vive en tendencia fuerte o solo en high-vol **no es el mismo sistema** en todo el sample.  
Reportar PF global sin cortar por régimen es ocultar fragilidad.

### Portafolio

Backtest **por símbolo en serie** ignora:

- señales simultáneas multi-par  
- techo de riesgo prop (DD diario, max positions)  
- correlación (EUR + GBP = casi un solo bet)

---

## 2. Práctica

1. Descargar ≥ 3–4 años M15 de los símbolos del challenge (ver R5 roadmap).  
2. Validar gaps y TZ una vez (UTC canónico; display operador aparte — R2).  
3. Cortar métricas por año / por sesión (London vs NY) en reportes serios.  
4. Si el challenge es multi-par, simular **cola de riesgo** no solo PF por par.

---

## 3. Código SMC-SYSTEMS

| Pieza | Ruta | Notas |
|-------|------|-------|
| Parquet raw | `data/raw/{SYMBOL}_{TF}.parquet` | M1 a menudo corto (~1k filas) |
| TZ | `app_observador/core/timezone.py` | R2: UTC canónico |
| Régimen | `regime.py`, `detect_regimes` en legacy | Parcial en ICT sequence |
| Governor | `risk/governor.py` | Live/paper; no siempre en ICT BT |
| Compliance prop | `tools/fundednext_compliance.py` | Post-proceso, no motor full |

---

## 4. Huecos

| ID | Hueco | Prioridad |
|----|-------|-----------|
| G9 | Histórico M15 XAU multi-año (R5) | Alta (datos) |
| G10 | Simulación portafolio multi-símbolo + DD diario en ICT BT | Media |
| G11 | Métricas por régimen / sesión en reporte Capa 2 | Media |
| G12 | Replay M1 solo si el modelo real es sub-M15 | Baja hasta definir modelo |

---

## En resumen

Datos malos o cortos, un solo régimen, y un símbolo “campeón” son la forma clásica de **enganarse con un PF bonito**. El profesional corta la muestra y el portafolio hasta que el edge se vea feo o se vea real.
