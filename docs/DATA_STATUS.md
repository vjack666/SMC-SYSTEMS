# Data Status — SMC-SYSTEMS (2026-07-21)

## Resumen

**3 símbolos tienen los 6 TF completos** (D1/H4/H1/M15/M5/M1):  
EURUSD, GBPUSD, XAUUSD.

**5 símbolos solo tienen 4 TF** (D1/H4/H1/M15):  
USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF.

Los 5 símbolos incompletos **faltan M5 y M1**.

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
| GBPUSD | 1,703 | 10,200 | 40,738 | 50,000 | 50,000 | 50,000 | **COMPLETO** |
| XAUUSD | 1,691 | 10,130 | 52,685 | 109,270 | 317,656 | 1,544,510 | **COMPLETO** |
| USDJPY | 1,704 | 10,201 | 40,740 | 50,000 | — | — | **FALTA M5+M1** |
| AUDUSD | 1,704 | 10,201 | 40,740 | 50,000 | — | — | **FALTA M5+M1** |
| USDCAD | 1,703 | 10,200 | 40,739 | 50,000 | — | — | **FALTA M5+M1** |
| NZDUSD | 1,703 | 10,202 | 40,746 | 50,000 | — | — | **FALTA M5+M1** |
| USDCHF | 1,703 | 10,200 | 40,739 | 50,000 | — | — | **FALTA M5+M1** |

---

## Impacto en el motor

- **Backtest con EURUSD, GBPUSD, XAUUSD**: funciona completo (los 6 TF cargan).
- **Backtest con los otros 5 símbolos**: `canonical.evaluate_signals()` intenta cargar M5/M1 y falla (KeyError). Solo funciona con `--htf D1 --ltf H4` o `--htf D1 --ltf H15` (sin M5/M1).
- **Tests `test_multitf_context.py`**: fallan para símbolos sin M5/M1.

---

## Opciones para conseguir M5/M1 de los 5 símbolos

1. **HistData.com** — descargar M1 gratis (2020-2026) y resamplear a M5. Funcionó para EURUSD/XAUUSD en sesiones previas (`scripts/rebuild_tf_from_m1.py`).
2. **MT5 real (no demo)** — las cuentas reales o funded suelen tener más histórico en M1/M5 que las demo.
3. **Otro broker/data vendor** — Dukascopy, TrueFX, etc.

**Decisión del operador:** trabajar con EURUSD/GBPUSD/XAUUSD como símbolos principales (completos) y usar los otros 5 solo para D1/H4/H1/M15.

---

*Nota generada automáticamente. Actualizar al conseguir más datos.*
