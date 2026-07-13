# Auditoría R4 v2 — por qué PO3 y Silver Bullet dieron 0-1 señales

**Fecha:** 2026-07-13
**Contexto:** R4 v2 corrió con displacement ON. Turtle EURUSD PF 1.143 (11) /
GBPUSD PF 0.533 (19); PO3 1 trade EURUSD / 0 GBPUSD; Silver Bullet 0 trades.
Se investigó la CAUSA antes de documentar "sin edge".

## Hallazgo: NO es falta de edge, son errores de la cadena + un bug de mapeo

### Silver Bullet (0 señales) — falta de datos M5/M1
- `ict_backtest/rules.checklist_scalping` exige FVG en **M1/M5** (regla del libro:
  Silver Bullet opera M1/M5, sweep en M15). R4 v2 corrió `--ltf M15` → sin M5/M1
  en `frames` → `ready=False` siempre → 0 señales.
- Smoke `--ltf M5` mostró que **`data/raw/EURUSD_M5.parquet` tiene solo 1000
  velas (1 semana: 2026-06-23→2026-06-29)**. El `data_feed.load_tf` lee el parquet
  entero (NO hay tope de 1000 en el código); el dato en disco es pequeño.
- **Conclusión:** 0 señales = falta de datos M5/M1 históricos, NO modelo sin edge.
  Bajada de M5/M1 en curso (`update_mt5_data.py --tfs M5,M1`) para re-medir.

### PO3 (1 señal EURUSD / 0 GBPUSD) — bug de mapeo CHOCH + modo SUAVE
- `_build_estructura` (engine.py:248-256) NO popula `session_open` → PO3 corrió en
  modo **SUAVE (R1)**, no el duro `broke_open` del libro 08. (Corrige nota previa:
  la causa NO es broke_open; el filtro duro ni siquiera se aplicó.)
- **BUG de mapeo:** `build_features` crea `choch_signal` (detect_choch), pero el
  engine lo pasa como `choch_status` (engine.py:251 `row.get("choch_status","")`)
  y `evaluate_po3._phase_d` lee `choch_status`. Como `build_features` NO crea
  `choch_status`, ese campo siempre es `""` → la fase D del PO3 en backtest SOLO
  se activa por `bos_dir` a favor, IGNORANDO el CHOCH real. Esto explica las pocas
  señales PO3 (el CHOCH no cuenta). Es el mismo tipo de desincronización que
  advirtió la auditoría externa (H1/H2): detector vs motor usan nombres distintos.
- Confirmado por conteo vectorizado (alineado por tiempo): PO3 da ~0 setups tanto
  con choch vacío como con choch_signal correcto en M15/2años — la secuencia
  A+M+D+alineación es muy estricta para M15 EURUSD. El engine R4 v2 reportó 1
  (ruido de alineación fila-a-fila); el orden de magnitud es "muy pocas señales".

## Evidencia empírica
- Silver Bullet M5 smoke: `trades=0`, log "M5: 1000 velas" (1 semana en disco).
- `EURUSD_M5.parquet` real = 1000 filas (verificado con pandas).
- `_build_estructura` no incluye `session_open` ni `choch_status` poblado.
- `build_features` crea `choch_signal` (no `choch_status`).
- Conteo PO3 alineado por tiempo: 0 setups (motor actual y con choch correcto).

## Veredicto
Las 0-1 señales de PO3/Silver Bullet NO son evidencia de "modelo sin edge". Son:
(a) Silver Bullet = falta de datos M5/M1; (b) PO3 = bug de mapeo `choch_status`
    (CHOCH no llega al PO3) + secuencia A+M+D demasiado estricta para M15.

**NO se documenta R4 v2 como "PO3/Silver sin edge" hasta:** (1) bajar M5/M1 y
re-medir Silver Bullet; (2) corregir el mapeo `choch_signal`→`choch_status` en el
engine (cambio de código, fuera de alcance RFC-001, requiere visto bueno de Ruben)
y re-medir PO3.

## Corrección propuesta (pendiente visto bueno, NO aplicada)
En `engine._build_estructura`, línea ~251, mapear `choch_signal`:
  "choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
y en `build_features` asegurar que el campo llegue. Luego re-medir PO3.
