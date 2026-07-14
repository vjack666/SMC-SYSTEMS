# TESIS ICT COMPLETA — Smart Money Concepts aplicados a SMC-SYSTEMS

| Campo | Valor |
|-------|-------|
| **ID** | `20_TESIS_ICT.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Autor** | SMC-SYSTEMS (Ruben + agente) |
| **Estado** | Síntesis unificadora de la biblioteca ICT + evidencia de backtest medida |
| **Fuente verdad** | Código repo + libros 01–17 + innercircletrader.net (respaldo) |
| **Relaciona** | Todos los libros 01–17; `METRICS_CANON.md`; `13_BACKTEST_PROFESIONAL/` |

---

## §0 Tesis en una frase (CITABLE)

> El mercado intradía es un ciclo repetible de **acumulación → manipulación → distribución** (PO3/AMD) donde el precio caza liquidez (stops) para financiar su expansión real; la ventaja del trader consiste en **identificar la manipulación (sweep), esperar la confirmación de estructura (BOS/CHOCH/MSS), y ejecutar la entrada, el SL y el TP en la temporalidad de ejecución correcta**, anclados a la estructura y no a medidas estadísticas (ATR).

El error que mató la rentabilidad en R4 v28 fue resolver el ciclo completo (entry + SL + TP) en el TF grueso (M15/H4) con medidas estadísticas (ATR). La corrección (v29→v30) es bajar la ejecución a la temporalidad fina donde ICT opera y anclar todo a la estructura.

---

## 1. Marco de mercado: el ciclo PO3/AMD (libro 08)

Todo setup ICT es una instancia del Power of Three (`08_POWER_OF_THREE.md`):

| Fase | Nombre | Qué hace el precio | En el código |
|------|--------|--------------------|--------------|
| **A** — Pasado | Accumulation | Marca sesgo HTF (D1/H4) y rangos (PDH/PDL/Asian) | `htf_trend` en `build_signals_from_frames` (engine.py 85) |
| **M** — Presente | Manipulation | Sweep de liquidez **en contra** del sesgo (caza stops) | `detect_liquidity` + `canonical_sweep` (liquidity_context.py) |
| **D** — Futuro | Distribution | CHoCH/BOS **a favor** + zona FVG/OB para entrar | `detectors/bos.py`, `detectors/fvg.py` |

`po3.complete = A and M and D and aligned` (rules.py). Sin las 3 fases, no es setup. Esto es la columna vertebral: **la manipulación (sweep) NO es la entrada, es la trampa; la entrada viene después, en la fase D.**

---

## 2. Estructura: cómo se confirma el giro (libro 02)

- **BOS** = ruptura de swing a favor de la tendencia (continuación). `detectors/bos.py` líneas 89-90: `close > swing.shift(1)` (sin look-ahead).
- **CHoCH** = primera ruptura del swing contrario (aviso de giro, no confirmación sola).
- **MSS/MSB** = CHoCH + desplazamiento + BOS de confirmación (reversión aceptada).

En Turtle Soup (contratendencia, libro 06), el BOS va **contra** la marea del HTF: el sweep manipula, el BOS contrario confirma el giro. En PO3 (a favor, libro 08), el BOS va a favor del sesgo. Misma mecánica, distinta dirección respecto al HTF.

---

## 3. Liquidez: el motor de todo (libro 05)

El precio existe para buscar **liquidez** (stops agrupados): BSL sobre highs, SSL bajo lows (`05_LIQUIDEZ.md`). 

- **Sweep válido** = rompe el nivel y **cierra de vuelta adentro** en la misma vela (`05` línea 20). `canonical_sweep` ya lo implementa.
- Las zonas BSL/SSL son **clusters** de swings en banda `atr/margin` (`detectors/liquidity.py`). Aquí vive el bug del TP (ver §7).
- La entrada va **después** del sweep, nunca en la mecha de caza (`05` línea 21).

---

## 4. Los dos setups del ciclo (libros 06, 07, 08)

| Setup | Fase usada | Dirección vs HTF | Temporalidad | Killzone |
|-------|-----------|------------------|--------------|-----------|
| **Turtle Soup** (06) | M + giro | Contratendencia | H4→M15 | London/NY |
| **PO3 / AMD** (08) | A+M+D completo | A favor del sesgo | D1→H4→M15 | London/NY |
| **Silver Bullet** (07) | M + FVG en ventana | A favor del sesgo intra | M15→M5/M1 | NY AM 10–11 ET |

Los tres son el mismo ciclo PO3 visto desde distinto ángulo temporal y direccional. No son estrategias distintas: son el mismo motor de liquidez con distinto horizonte.

---

## 5. Temporalidad de ejecución: la clave olvidada (libros 15, 16, 17)

Toda operación ICT tiene 3 capas (`16_TEMPORALIDAD_EJECUCION.md`):

1. **HTF** (sesgo): H4 intradía, M15/H1 scalping. Dónde quiere ir el precio.
2. **LTF** (zonas): M15 intradía, M5 scalping. Dónde marcar estructura y niveles.
3. **exec TF** (disparo): M15 intradía, M5/M1 scalping. Dónde entra el trade.

El motor ya soporta esto (`TF_FREQ` engine.py 251; `build_signals_from_frames(htf=, ltf=)`). El error de v28/v29 fue usar el LTF grueso (M15) como exec TF y resolver entry/SL/TP ahí. Eso infla distancias y corre el TP lejos.

**Tesis central de temporalidad:** el humano ICT marca en M15 (parent chart) y ejecuta en M5/M1. El robot debe imitar eso: marcar zonas en LTF, disparar en exec TF fino.

---

## 6. Entrada: el retorno a la zona, no el close del BOS (libro 15)

ICT no entra en el close de la vela del BOS. Entra en el **retorno a la zona** que dejó el displacement (FVG u OB del LTF). Secuencia (`15_INTRADIA_ENTRADA_SL_TP.md` §2):

1. HTF confirma sesgo/rango.
2. LTF barre liquidez (sweep) y falla (cierra adentro).
3. LTF rompe estructura (BOS/CHOCH) en dirección del setup.
4. La ruptura deja un **FVG/OB** (zona de imbalance).
5. **Entrada**: retrace del precio a esa zona.
6. SL: mecha del sweep ± buffer.
7. TP: primera liquidez opuesta del LTF más cercana.

El motor hoy hace (2)+(3) pero entra en `row["close"]` de (3) (engine.py 107). El paso (5) falta. Esa es la mitad del bug.

---

## 7. Stop Loss: estructural, nunca ATR (libros 14, 15, 17)

`calc_structural_sl` (engine.py, v29) ancla el SL a la **mecha del sweep** ± buffer (0.3 ATR):
- SL = `sweep_low` − buffer (long) / `sweep_high` + buffer (short).
- Fallback a `swing_low`/`swing_high` si no hay sweep.
- Si no hay nada → None → no opera (NO degrada a ATR).
- `STRUCT_SL_MAX_ATR = 6.0`: filtro de régimen (si el sweep fue gigante, salta el trade).

El ATR NO se borra: queda como buffer y filtro de sanidad (`14_STOP_LOSS_ESTRUCTURAL.md`). La evidencia medida (v29): PF pasó de 0.771→1.128 (EURUSD) y 0.993→2.101 (GBPUSD) al quitar el ATR del stop. **El SL estructural es la única corrección ya implementada y probada.**

---

## 8. Take Profit: liquidez cercana, no cluster lejano (libros 15, 16, 17)

`_tp_liquidity` (engine.py 283) usa `bsl_price`/`ssl_price` del LTF. Pero `detect_liquidity` arma **clusters** (promedio de swings en banda ATR/4). Si el rango es amplio, el cluster queda lejos → TP lejano → el trade se duerme.

Evidencia medida (v29): 7/11 (EURUSD) y 11/13 (GBPUSD) salieron por `hold_limit`. El SL ya no sacaba por ruido (bien), pero el TP no se alcanzaba en 16 velas M15.

**Corrección (v30):** TP = el **swing de liquidez opuesto MÁS CERCANO** al entry (primer BSL/SSL que el precio toca yendo a favor), no el cluster. En scalping (M5/M1) el TP es inmediato por diseño.

El libro 06 viejo decía "TP liquidez opuesta HTF" — eso es justo lo que falló. La tesis lo corrige: **TP en liquidez del LTF más cercana, no del HTF.**

---

## 9. Gestión: hold, RR y regimes (libros 13, 15, 17)

- **Max hold**: v29 usó 16 velas M15 → corto para un TP en liquidez. v30 debe usar ≥40 velas M15 (intradía) o pocas velas M5 (scalping). El hold corto dormía trades rentables.
- **RR**: 1:2 mínimo (ICT). El TP en liquidez cercana lo sostiene sin inflar el hold.
- **Regime filter**: `STRUCT_SL_MAX_ATR` salta sweeps gigantes. Para mayor robustez, operar Turtle Soup solo en rango (ICT: el setup vive en rango, no tendencia).

---

## 10. Auditoría y veracidad (libro 13, auditorías #1–#7)

- **Look-ahead**: `sweep_low`/`sweep_high` usan `.shift(1)` (data_feed.py). Sesgo HTF de vela cerrada (auditoría #1). FVG/OB de vela cerrada. Sin leer el futuro.
- **Killzone**: NY AM debe calcularse en TZ correcta (pendiente en libro 01).
- **Backtest profesional** (`13_BACKTEST_PROFESIONAL/`): reloj MTF, fill realista, costos, OOS, gaps G1–G12. Ningún PF se cree sin pasar esto.
- El SL estructural ya pasó la medición honesta (v29). La entrada fina y el TP cercano se miden en v30.

---

## 11. Mapa código ↔ tesis

| Tesis | Código real | Estado |
|-------|-------------|--------|
| Sweep manipulación | `canonical_sweep` (liquidity_context.py) | ✅ |
| Estructura (BOS/CHOCH) | `detectors/bos.py`, `detectors/choch.py` | ✅ |
| SL estructural | `calc_structural_sl` (engine.py, v29) | ✅ medido |
| Entrada en retorno a zona | `build_signals_from_frames` entra en `close` | ❌ pendiente v30 |
| TP liquidez cercana | `_tp_liquidity` usa cluster | ❌ pendiente v30 |
| Exec TF fino (M5/M1) | `TF_FREQ` soporta M1/M5 | ✅ infra; ❌ no usado en scalping |
| Killzone NY AM | `checklist_scalping` (rules.py 174) | ✅ lógica; ⚠ TZ pendiente |

---

## 12. Conclusión

La tesis ICT de SMC-SYSTEMS es coherente y trazable: el ciclo PO3/AMD explica por qué el precio caza liquidez y luego expande; los detectores ya materializan sweep/estructura/liquidez; el SL estructural ya está probado rentable. El eslabón débil era la **temporalidad de ejecución**: resolver entry/SL/TP en TF grueso con ATR mataba el edge. La corrección (v30) es bajar la ejecución al exec TF fino, anclar entry al retorno a zona y TP a la liquidez cercana. Eso cierra el ciclo PO3 de forma operativa.

> **Veracidad**: los números de v29 son medidos (log `R4V29_STRUCTSL.log`). Los de v30/scalping se miden en el re-run, no se afirman antes. La tesis unifica teoría (libros 01–08) y aplicación (14–17); no inventa conceptos fuera del canon ICT del repo.

---

*Síntesis v1.0 — 2026-07-13. Complementa, no reemplaza, los libros 01–17. La evidencia viva está en `results/r4/` y `docs/ict/logs/`.*
