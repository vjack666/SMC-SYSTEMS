# Auditoría: bug de mapeo CHOCH en backtest PO3 (`choch_signal` vs `choch_status`)

**Fecha:** 2026-07-13
**Severidad:** Media (sesga la medición PO3 del backtest; no afecta el dashboard en vivo)
**Tipo:** Desincronización detector ↔ motor (mismo patrón que advirtió la auditoría
externa H1/H2: nombres de campo distintos entre quien genera y quien lee).

## Causa raíz
- `ict_backtest/data_feed.build_features` (líns 54-55) crea **`choch_signal`**
  vía `detect_choch` (valores `CHOCH_BULLISH`/`CHOCH_BEARISH`).
- `ict_backtest/engine._build_estructura` (líns 248-256) pasa a `evaluate_po3`
  el campo **`choch_status`** (`row.get("choch_status","")`).
- `build_features` NO crea `choch_status` → siempre es `""`.
- `signals/po3.evaluate_po3._phase_d` (líns 113-143) lee `estructura[tf]["choch_status"]`
  y solo acepta `CHOCB_BULLISH/BEARISH/ACTIVE`. Con `""`, **la fase D del PO3
  en backtest SOLO se activa por `bos_dir` a favor, ignorando el CHOCH real**.

## Impacto empírico (R4 v2, EURUSD M15 2 años)
- PO3 reportó **1 señal EURUSD / 0 GBPUSD** (engine real).
- Conteo vectorizado alineado por tiempo: 0 setups (motor actual y con choch correcto).
  La secuencia A+M+D+alineación es muy estricta para M15; el CHOCH roto agrava.
- El PO3 en VIVO (dashboard `resumen_widget`) usa `ict_backtest/rules.checklist_intradia`
  que SÍ lee `choch_signal` correctamente → **divergencia vivo vs backtest**.

## Parche (APLICADO 2026-07-13, autorizado por Ruben — sin commit, regla de hierro)
En `ict_backtest/engine.py` `_build_estructura` lína ~251, mapear el CHOCH:
```python
"choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
```
Ahora el PO3 en backtest SÍ recibe el CHOCH. Re-medición en curso (R4 v2.6).

## Estado
- Documentado. Parche listo, sin aplicar ni commitear.
- Re-medición PO3 "tal cual" en curso (R4 v2.5) para tener el número honesto del
  sistema actual; el número "corregido" requiere aplicar el parche arriba.
