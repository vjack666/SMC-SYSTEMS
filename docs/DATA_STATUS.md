# Data Status — SMC-SYSTEMS (2026-07-24)

> **Fuente viva de inventario de datos.** Si un doc dice "falta XAUUSD M15", está **obsoleto**.
> Verificar aquí (o en disco) antes de bloquear trabajo en R5/A12.

## Veredicto R5 / A6 (2026-07-24)

| Hito | Criterio | Estado | Evidencia en disco |
|------|----------|--------|--------------------|
| **R5** | ≥3–4 años M15 XAUUSD + EURUSD | ✅ **CERRADO (datos)** | XAUUSD_M15 ~4.54y (2022-01→2026-07); EURUSD_M15 ~4.56y |
| **A6** | Expandir históricos multi-año (principales) | 🟢 **Suficiente para A12** en EURUSD/XAUUSD (y GBPUSD con caveats) | Ver tabla abajo |
| **A12** | Walk-forward OOS celda top | 🔴 **Pendiente re-run** — **NO** bloqueado por parquet ausente | 1er pase falló con setup/datos viejos |

**Regla anti-bucle:** el bloqueo "hay que bajar XAUUSD M15" **ya no aplica**.  
Siguiente acción de datos/edge = **re-correr A12** (y arreglar runners que aún excluyen oro por hang), no re-descargar el M15 principal.

### Rangos verificados 2026-07-24 (lectura real de parquet)

| Archivo | Filas | Inicio | Fin | Años |
|---------|------:|--------|-----|-----:|
| `XAUUSD_M15.parquet` | 109 270 | 2022-01-02 | 2026-07-17 | **4.54** |
| `XAUUSD_H4.parquet` | 10 130 | 2020-01-02 | 2026-07-21 | 6.55 |
| `XAUUSD_H1.parquet` | 52 685 | 2018-01-22 | 2026-07-17 | 8.48 |
| `XAUUSD_M5.parquet` | 317 656 | 2022-01-02 | 2026-07-17 | 4.54 |
| `XAUUSD_M1.parquet` | 1 544 510 | 2022-01-02 | 2026-06-26 | 4.48 |
| `EURUSD_M15.parquet` | 113 397 | 2022-01-02 | 2026-07-24 | **4.56** |

## Resumen

**2 símbolos tienen los 6 TF completos** (D1/H4/H1/M15/M5/M1):  
EURUSD, XAUUSD. **GBPUSD falta M1** (M5/M15 reales 2012→2026).

**5 símbolos solo tienen 4 TF** (D1/H4/H1/M15):  
USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF.

Los 5 símbolos incompletos **faltan M5 y M1** (no bloquea A12 sobre XAUUSD/EURUSD).

---

## Por qué faltan M5 y M1

MT5 FundedNext (cuenta demo) **no almacena datos M1 ni M5**. Solo mantiene:
- D1: ~1,700 velas (2020-2026)
- H4: ~10,200 velas (2020-2026)
- H1: ~40,700 velas (2020-2026)

Los archivos M1/M5 de EURUSD, GBPUSD y XAUUSD vinieron de **HistData.com** (datos offline descargados en sesiones previas), no de MT5.

---

## Qué se actualizó hoy

| TF | Símbolos actualizados | De → A |
|----|----------------------|--------|
| H1 | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF | ~3,000 → ~40,700 velas |
| D1 | Los 8 símbolos | +10 velas cada uno (hasta jul 2026) |
| H4 | Los 8 símbolos | +60-70 velas cada uno (hasta jul 2026) |

---

## Cobertura final del motor (6 TFs)

| Símbolo | D1 | H4 | H1 | M15 | M5 | M1 | Estado |
|---------|----|----|----|----|----|----|--------|
| EURUSD | 1,703 | 10,200 | 40,739 | 113,118 | 325,433 | 1,619,941 | **COMPLETO** |
| GBPUSD | 1,703 | 10,200 | 40,738 | 50,000 | 1,154,150 | — | **FALTA M1** (M5 real 2012→2026) |
| XAUUSD | 1,691 | 10,130 | 52,685 | 109,270 | 317,656 | 1,544,510 | **COMPLETO** |
| USDJPY | 1,704 | 10,201 | 40,740 | 50,000 | — | — | **FALTA M5+M1** |
| AUDUSD | 1,704 | 10,201 | 40,740 | 50,000 | — | — | **FALTA M5+M1** |
| USDCAD | 1,703 | 10,200 | 40,739 | 50,000 | — | — | **FALTA M5+M1** |
| NZDUSD | 1,703 | 10,202 | 40,746 | 50,000 | — | — | **FALTA M5+M1** |
| USDCHF | 1,703 | 10,200 | 40,739 | 50,000 | — | — | **FALTA M5+M1** |

---

## Impacto en el motor

- **Backtest con EURUSD, XAUUSD**: funciona completo (6 TF). **GBPUSD**: 5 TF (sin M1) — usar `--htf D1 --ltf H15` o M5; `canonical.evaluate_signals` con `exec_tf=M1` falla (sin M1 en disco).
- **Backtest con los otros 5 símbolos**: `canonical.evaluate_signals()` intenta cargar M5/M1 y falla (KeyError). Solo funciona con `--htf D1 --ltf H4` o `--htf D1 --ltf H15` (sin M5/M1).
- **Tests `test_multitf_context.py`**: fallan para símbolos sin M5/M1.

---

## Opciones para conseguir M5/M1 de los 5 símbolos

1. **HistData.com** — descargar M1 gratis (2020-2026) y resamplear a M5. Funcionó para EURUSD/XAUUSD en sesiones previas (`scripts/rebuild_tf_from_m1.py`).
2. **MT5 real (no demo)** — las cuentas reales o funded suelen tener más histórico en M1/M5 que las demo.
3. **Otro broker/data vendor** — Dukascopy, TrueFX, etc.

**Decisión del operador:** trabajar con EURUSD/GBPUSD/XAUUSD como símbolos principales (completos) y usar los otros 5 solo para D1/H4/H1/M15.

---

## Docs / runners históricos (no reabrir R5)

Estos textos **fueron verdad en su fecha** y **no deben usarse como estado actual**:

| Doc / código | Claim viejo | Estado real 2026-07-24 |
|--------------|-------------|-------------------------|
| `AGENTS.md` (pre-fix) | XAUUSD_M15 no existe | Corregido en AGENTS.md |
| `docs/METRICS_CANON.md` §0 v2 mtf | XAUUSD excluido por falta M15 | Data existe; exclusión de esa corrida fue de **entonces** |
| `docs/avances/BACKTEST_V2_MTF_REPORTE_2026-07-17.md` | XAUUSD excluido / R5 bloqueado | Snapshot histórico 2026-07-17 |
| `docs/auditorias/AUDIT_R6_FORMAL_2026-07-23.md` Falla 4 / G9 | XAUUSD M15 no en disco | Enmienda: datos OK; ver sección enmienda del audit |
| `scripts/run_bt_v2_mtf.py` | Excluye XAUUSD | Por **hang del motor canónico con oro**, no por data ausente |

---

*Última verificación de parquet: 2026-07-25. Re-verificar en disco si se regeneran `data/raw/*`.*

---

## Limpieza 2026-07-25 + límite de histórico intraday (Dukascopy probe)

**Eliminados (stubs falsos):**
- `GBPUSD_M1.parquet` — era placeholder de 50.000 velas (2026-05-26→2026-07-13, 0.1y). GBPUSD **no tiene M1** en disco (Dukascopy solo tiene M1 de FX desde 2012; este stub no era real).
- `EURUSD_M30.parquet` — era 1.000 velas (1 mes, 2026-05→2026-06). Basura.

**Límite real de histórico intraday (probe `scripts/_probe_dukascopy.py`, chunks de 1 mes en 2003/2006/2012):**
- FX majors (EURUSD, GBPUSD, …): Dukascopy tiene intraday **solo desde 2012**. No hay fuente (MT5 ni Dukascopy) con 20 años de M1/M5/M15 para FX.
- XAUUSD (oro): Dukascopy tiene M1/M5/M15 **desde 2006** (confirmado en probe: 2006-01 = 25.906 bars M1, 6.306 M5, 2.141 M15).
- Conclusión: los **20 años históricos solo son reales en D1/H4/H1** (los 8 pares, 2006→2026). El intraday no llega a 20 años en FX.

**Nota al docstring de `scripts/download_dukascopy.py`:** afirma "FX majors ~20 años" — es **FALSO para intraday** (solo aplica a D1/H4/H1). El tope de FX intradía es 2012. XAUUSD sí admite 20 años intraday.

**Estado post-limpieza (TF completos):**
- 6 TF completos: EURUSD, XAUUSD.
- 5 TF (sin M1): GBPUSD.
- 4 TF (sin M5/M1): USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF.
