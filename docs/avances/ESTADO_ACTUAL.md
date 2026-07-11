# Estado Actual — Edge Diagnosis SMC-SYSTEMS

**Fecha:** 2026-07-10
**Estado:** EDGE DIAGNOSIS COMPLETA — 8/8 símbolos, 168/168 celdas, 0 errores, 0 insufficient.

## Qué estamos haciendo
Medir el **edge puro del stack de detectores SMC** (ICT/Wyckoff) sin ML ni agentes,
con el gobernador de riesgo neutralizado. Matriz de **21 variantes × 8 símbolos = 168 celdas**.
El reporte vive en `docs/EDGE_DIAGNOSIS_REPORT.md` y los datos crudos en
`results/edge_diagnosis/full_results.json`.

## Resultado final (edge diagnosis cerrada)
- 8 símbolos completos: EURUSD, AUDUSD, NZDUSD, USDCAD, XAUUSD, GBPUSD, USDCHF, USDJPY.
- Los 3 símbolos cortos (GBPUSD, USDCHF, USDJPY) pasaron el filtro de N:
  Baseline detail → Insufficient: **no** en los 3 (confirmado en el reporte).
- 0 celdas con insufficient N, 0 zero-trades, 0 errores.

## Hallazgo clave del edge (8 símbolos)
- Mejor variante promedio: `no_session` → **OOS PF 1.159** (8 celdas).
- Peor variante promedio: `prox_1` → OOS PF 1.084 (el filtro de proximidad OB/FVG destruye el edge).
- El resto de variantes se agrupan en PF ~1.10-1.12: el edge es ROBUSTO a la ablación
  (no desaparece al quitar un filtro), salvo `prox_*` y `no_atr` que lo erosionan.
- Mejor símbolo: **XAUUSD OOS PF 1.376 (21 celdas)**; luego USDCAD 1.264, USDJPY 1.209, EURUSD 1.162, GBPUSD 1.156, USDCHF 1.130.
- **AUDUSD (0.849) y NZDUSD (0.809) PIERDEN** — el stack se invierte en esos dos.
- Celda TOP: `no_session` × XAUUSD → **OOS PF 1.642, N=900, Sharpe 3.28, WR 55.1%**.
- Celda PEOR: `prox_3` × NZDUSD → OOS PF 0.779.

### Tabla de 8 símbolos (avg OOS PF por símbolo, 21 variantes c/u)
| Rank | Symbol | Avg OOS PF | # cells | Veredicto |
|-----:|--------|----------:|--------:|-----------|
| 1 | XAUUSD | 1.376 | 21 | EDGE fuerte |
| 2 | USDCAD | 1.264 | 21 | EDGE |
| 3 | USDJPY | 1.209 | 21 | EDGE marginal |
| 4 | EURUSD | 1.162 | 21 | EDGE marginal |
| 5 | GBPUSD | 1.156 | 21 | EDGE marginal |
| 6 | USDCHF | 1.130 | 21 | EDGE marginal |
| 7 | AUDUSD | 0.849 | 21 | PIERDE |
| 8 | NZDUSD | 0.809 | 21 | PIERDE |

### Baseline detail (config referencia) — los 3 nuevos confirmados válidos
| Symbol | N total | IS PF | OOS PF | OOS N | Insufficient |
|--------|--------:|------:|-------:|------:|:------------:|
| EURUSD | 1553 | 1.084 | 1.170 | 466 | no |
| AUDUSD | 2126 | 0.812 | 0.839 | 638 | no |
| NZDUSD | 2232 | 1.001 | 0.794 | 670 | no |
| USDCAD | 3000 | 0.957 | 1.290 | 900 | no |
| XAUUSD | 3000 | 1.186 | 1.379 | 900 | no |
| GBPUSD | 3000 | 1.052 | 1.150 | 900 | no |
| USDCHF | 3000 | 1.007 | 1.134 | 900 | no |
| USDJPY | 3000 | 1.188 | 1.216 | 900 | no |

## ¿Se sostiene el hallazgo previo con los 3 nuevos?
SÍ. Con 5 símbolos el ranking era XAUUSD > USDCAD > EURUSD (perdedores AUDUSD/NZDUSD).
Con 8 símbolos se mantiene: XAUUSD y USDCAD siguen siendo los tops, AUDUSD/NZDUSD
siguen perdiendo. Los 3 nuevos (GBPUSD/USDCHF/USDJPY) se ubican en el medio (1.13-1.21),
todos con edge marginal positivo. El hallazgo de `no_session` × XAUUSD como celda ganadora
se CONFIRMA y se refuerza (PF 1.642, Sharpe 3.28).

## Próximo paso (NO ejecutado en esta tarea — queda para la siguiente)
Validar **walk-forward real OOS** de la celda ganadora `no_session` × XAUUSD
(antes de considerar automatizar cualquier cosa):
- PurgedKFold, DSR>0, N>=200 por fold, PF>=1.10 out-of-sample.
- El edge de diagnóstico (PF 1.16-1.64) es sobre un split 70/30 temporal simple;
  el walk-forward es el filtro duro antes de live.

## Notas técnicas (no olvidar)
- El harness lee de `_ctx/*.pkl`, NO de los parquets crudos. Cambiar parquets no basta.
- `run_edge_diagnosis.bat` usa `C:\Python314\python.exe` (tiene MT5 real); funciona.
- Correr `run.py` con pipe (`| sed | grep`) lo mata con exit 127 — usar el `.bat`
  o redirigir a archivo (`> log 2>&1`). El `--status` (`check_edge_progress.bat`) es el medidor.
- Regla dura: NO tocar `signals/pipeline.py`.
- REGLA #0 de esta tarea: nada de app_observador/ ni UI — cumplido, solo se corrió el harness y se documentó.
