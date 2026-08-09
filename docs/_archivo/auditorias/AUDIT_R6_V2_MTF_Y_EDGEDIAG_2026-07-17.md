# Auditoría: 4 fallas que invalidan las conclusiones de backtest R6 v2 mtf + edge_diagnosis (hallazgo operador)

**Fecha:** 2026-07-17
**Severidad:** CRÍTICA (invalida reproducibilidad y el veredicto de "edge" de XAUUSD/A12)
**Fuente:** Ruben (operador) revisó el repo clonado real — NO la vista cacheada de GitHub.
**Verificado por mí en código real:** SÍ (ver "Evidencia" por punto).

---

## Contexto

Hoy (2026-07-17) corrí el motor `ict_backtest/v2` (modo mtf, D1→H4→H1→M15, costos ON,
OOS 0.3) sobre 7 majors y escribí `docs/avances/BACKTEST_V2_MTF_REPORTE_2026-07-17.md`
con veredicto "GATE NO PASA / sin edge". El operador auditó el repo y encontró 4 fallas
que hacen que TANTO ese veredicto COMO el "candidate edge" de A12 (XAUUSD) sean
prematureos. Este documento las registra.

---

## Falla 1 — El backtest v2 mtf NO es reproducible (commit eb691c5)

**Severidad:** CRÍTICA (reproducibilidad).
**Evidencia (medida, no especulación):**
- `git log --all -- ict_backtest/v2/` → **vacío**. El módulo nunca fue comiteado.
- `git ls-files ict_backtest/v2/` → **vacío**. No está trackeado.
- `git check-ignore ict_backtest/v2/orchestrator.py` → "no ignorado" (no es .gitignore,
  simplemente no se agregó).
- En disco SÍ existe: `ict_backtest/v2/orchestrator.py`, `run_v2.py`, `context_mtf.py`,
  `coverage.py`, `live_structure_table.py`, `nearest_tp.py`, `contracts.py`, `event_log.py`.
- El commit eb691c5 agregó `scripts/run_bt_v2_mtf.py`, que hace
  `from ict_backtest.v2.orchestrator import run_mtf_intraday`. El launcher está versionado;
  el motor que importa, NO.

**Consecuencia:** los números del reporte `BACKTEST_V2_MTF_REPORTE_2026-07-17.md` salieron
de código que solo existe en el disco local. Desde un clon limpio, `run_bt_v2_mtf.py`
falla con `ModuleNotFoundError: ict_backtest.v2`. Nadie (ni yo mismo) puede reproducir el
backtest. El reporte queda colgando de código no versionado.

**Parche (PENDIENTE autorización):** commitear `ict_backtest/v2/` completo en el mismo
commit que este reporte + roadmaps.

---

## Falla 2 — `edge_diagnosis/run.py` no ablaciona lo que dice (cap MAX_SIGNALS_PER_VARIANT)

**Severidad:** CRÍTICA (contamina el símbolo clave XAUUSD).
**Evidencia (código real):**
- `scripts/edge_diagnosis/run.py:410`:
  `"agents": 0.0,  # sin orquestador` — **hardcodeado para TODAS las variantes**.
  El harness nunca corre agentes. La variante `w0_agents` ("peso agents=0") es idéntica
  al baseline por diseño, no por resultado → es un no-op estructural, no una ablación.
- `scripts/edge_diagnosis/run.py:64`: `MAX_SIGNALS_PER_VARIANT = 3000`.
- `run.py:430-432` y `run.py:627-628`: corte por **confianza descendente**
  (`rows[np.argsort(-conf)[rows]][:3000]`). Si el baseline ya genera ≥3000 señales
  candidatas para un símbolo, relajar un filtro (ej `no_choch`, `w0_sweep`) solo agrega
  candidatos de **menor** confianza que quedan FUERA del corte → el top-3000 no cambia.
- Síntoma medible (Ruben): para **XAUUSD**, 13 de 21 variantes
  (`baseline`, `no_choch`, `mc_1/3/4`, `no_swing`, `no_micro`, `w0_ob_fvg`, `w0_bos`,
  `w0_swing`, `w0_agents`, `w0_sweep`, `w0_ote`) devuelven **exactamente**
  PF 1.379 / WR 60.1% / Sharpe 2.11 / avgR 0.0789 / N=900 OOS. Coincidencia idéntica
  en 5 métricas = el corte de 3000 las deja iguales. El criterio que el propio harness
  usa para declarar "survives ablation" NO está siendo probado en el símbolo que sostiene
  todo el resultado (XAUUSD).

**Consecuencia:** la ablación de `edge_diagnosis` es inválida para XAUUSD. El "candidate
edge" de A12 descansa sobre un test que no diferencia variantes.

**Parche (PENDIENTE decisión):** el cap debe cortar por **fecha/ventana**, no por
confianza descendente, o elevarse/sustituirse por un esquema que permita que relajar un
filtro cambie realmente el set de señales. Requiere discutir el diseño antes de parchar
(líneas 64, 430-432, 627-628).

**Instrumentación aplicada (2026-07-17, commit posterior):** se agregó `n_raw`
(candidatos antes del cap) y `capped: bool` a cada celda del reporte
(`write_edge_report` + `summary.csv` en `edge_diagnosis/run.py`). Esto permite medir
qué celdas de las 168 están afectadas por `MAX_SIGNALS_PER_VARIANT` SIN cambiar la
semántica del backtest. Pendiente: correr la grilla y observar `capped=True` por
símbolo para confirmar si el cap solo afecta a XAUUSD. El corte en sí (criterio) sigue
pendiente de decisión.

---

## Falla 3 — Sin corrección por comparaciones múltiples

**Severidad:** ALTA (falsa significancia).
**Evidencia:**
- Grilla: 21 variantes × 8 símbolos = **168 celdas** evaluadas; se elige la mejor
  post-hoc (`no_session` × XAUUSD, PF 1.642).
- Con 168 pruebas independientes, encontrar 1-2 celdas con PF>1.6 por puro ruido es
  **esperable** bajo la hipótesis nula (sin edge real). No hay ajuste de significancia.
- `ml/stats_validator.py:83` `compute_deflated_sharpe_ratio` y `:101` `compute_pbo`
  EXISTEN y se usan en `scripts/run_walkforward_validation.py:217-220`, PERO
  **no se aplican** a la grilla de `edge_diagnosis/run.py`.

**Consecuencia:** "candidate edge" se declara sin descontar el look del número de pruebas.
Es selección óptima post-hoc no corregida.

**Parche (PENDIENTE):** aplicar DSR/PBO de `ml/stats_validator.py` a la grilla 168 antes
de imprimir cualquier "candidate edge".

---

## Falla 4 — "Candidate edge" es promedio, no conteo por símbolo (y vive en XAUUSD)

**Severidad:** ALTA (concentración de riesgo no declarada).
**Evidencia (Ruben, ranking por símbolo):**
- `no_session` gana con PF promedio **1.159 sobre 8 símbolos**.
- Pero por símbolo: AUDUSD **0.849**, NZDUSD **0.809** (PIERDEN en promedio general);
  XAUUSD **1.376** muy por encima del resto.
- El "edge" está concentrado en XAUUSD — el MISMO símbolo **EXCLUIDO** del backtest MTF
  de hoy (2026-07-17) por falta de M15 local.

**Consecuencia:** a un dato faltante (XAUUSD M15) de no poder validar el único símbolo
que sostiene la tesis. El "edge" promedio encubre que 2 de 8 símbolos pierden y que el
resultado depende de 1 símbolo.

**Parche (PENDIENTE):** traer XAUUSD M15 (R5, cuenta FundedNext real, no demo) y reportar
PF por símbolo con N y signo, no solo promedio.

---

## Menor — `ict_backtest/costs.py` solo calibra 3 símbolos

**Severidad:** MEDIA (sesgo de costo en símbolos "sobrevivientes").
**Evidencia:** `costs.py` calibra spread/comisión real solo para XAUUSD/EURUSD/GBPUSD;
los otros 5 (AUDUSD, NZDUSD, USDCAD, USDCHF, USDJPY — los del test MTF de hoy) usan un
`DEFAULT` genérico.
**Consecuencia:** los números MTF de hoy para USDCAD (PF 0.510) y USDCHF (0.295) podrían
estar mal por costo mal cobrado, justo en los símbolos "sobrevivientes".

---

## Veredicto

Ninguno de los dos veredictos extremos ("stack ICT sin edge" del reporte MTF de hoy, ni
"candidate edge en XAUUSD" de A12) está actualmente sustentado por pruebas válidas:
- El MTF de hoy no es reproducible (Falla 1) y puede tener costo mal cobrado (Menor).
- El "edge" de XAUUSD descansa sobre una ablación rota (Falla 2), sin corrección
  múltiple (Falla 3) y concentrada en 1 símbolo excluido del MTF (Falla 4).

**Acción requerida antes de cualquier veredicto:** (1) versionar `ict_backtest/v2/`;
(2) arreglar cap de señales en `edge_diagnosis/run.py`; (3) aplicar DSR/PBO a la grilla
168; (4) traer XAUUSD M15; (5) calibrar costos de los 5 símbolos restantes. Hasta eso,
CUALQUIER conclusión (a favor o en contra) es prematura.

---

*Formato alineado con `docs/auditorias/AUDIT_LOOKAHEAD_HTF.md` y `AUDIT_R4_FINAL_2026-07-13.md`.*
