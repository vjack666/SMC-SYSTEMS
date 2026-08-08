# INDICE_MDS.md — Índice Maestro de Componentes (R2)

> Fuente de verdad de QUÉ existe y qué falta en SMC-SYSTEMS.
> Nota de vigencia 2026-08-08: este índice fue auditado contra el MOTOR REAL
> (`engine/`) y el backtest (`ict_backtest/`). Varios componentes que el índice
> previo (2026-07-20) marcaba ❌ YA ESTÁN HECHOS en el motor; otros existen en
> `ict_backtest/` y deben RESCATARSE a `engine/` por la LEY FUNDAMENTAL
> (motor permanente = única fuente; backtest desechable = consumidor).

## Clasificación
- Todos OBLIGATORIO (algunos bonus).
- Fase: Base ✅ / B1 / B2 / B3 / C1 / C2 / C3 / D1 / E1.

## Estado REAL (auditado 2026-08-08)

| # | Componente | Fase | Estado | Dónde vive | SDD |
|---|-----------|------|--------|-----------|-----|
| 1 | Bias HTF (D1/H4/H1) | Base | ✅ | engine/bias/ | MDS_BIAS_HTF.md |
| 2 | Estructura BOS/CHOCH | Base | ✅ | engine/bos/ | MDS_BOS_CHOCH.md |
| 3 | Dealing Range / EQ / Prem-Disc | Base | ✅ | engine/dealing_range.py | MDS_DEALING_RANGE.md |
| 4 | Liquidez BSL/SSL | Base | ✅ | engine/liquidity_levels.py | MDS_LIQUIDEZ_BSL_SSL.md |
| 5 | POI anclado (PD arrays) | B1 | ✅ | engine/poi_anchor.py + zone_authority.py | MDS_B1_POI_ANCLADO.md |
| 6 | 3 capas HTF/ITF/exec (top-down) | B2 | ✅ | engine/plan.py (build_context_stack D1→M1) | MDS_B2_3CAPAS.md |
| 7 | **Exec fino M5/M1 (B2)** | B2 | ✅ HECHO | engine/execution.py + engine/micro.py | MDS_B2_EXEC_M5_M1.md |
| 8 | **OTE 62-79% (D1)** | D1 | ✅ HECHO | engine/dealing_range.py (OTE_MIN/MAX) | MDS_D1_OTE.md |
| 9 | **Killzone L/NY PM (B2)** | B2 | ✅ HECHO | engine/killzone.py (rescatado dd8f7ef) | MDS_KILLZONES_L_NYPM.md |
| 10 | **Silver Bullet (C2)** | C2 | ✅ HECHO | engine/silver_bullet.py (rescatado dd8f7ef) | MDS_C2_SILVER_BULLET.md |
| 11 | **Turtle Soup (C3)** | C3 | ✅ HECHO | engine/turtle_soup.py (rescatado dd8f7ef) | MDS_C3_TURTLE_SOUP.md |
| 12 | **Trade Management BE/parciales (E1)** | E1 | ✅ HECHO | engine/trade_mgmt.py (rescatado dd8f7ef) | MDS_E1_TRADE_MANAGEMENT.md |
| 13 | **RR por setup (C2)** | C2 | ✅ HECHO | engine/rr_by_setup.py (rescatado dd8f7ef) | MDS_RR_POR_SETUP.md |
| 14 | Liquidez internal/external (B3) | B3 | 🔲 no iniciado | — | MDS_B3_LIQUIDEZ_INT_EXT.md |

## Regla dura de implementación (Ruben 2026-08-08)
- **CERO indicadores técnicos** (EMA/RSI/ATR/MACD/Bollinger...).
- Solo **geometría de mercado pura**: OHLC, swings, estructura (BOS/CHOCH),
  liquidez (BSL/SSL/sweep), POI (PD arrays, FVG, OB).
- **ÚNICA excepción permitida**: VOLUMEN (tick volume) — es dato de mercado,
  NO indicador. Se usa para confirmar agotamiento/convicción en niveles,
  nunca como señal suavizada.
- Todo módulo de decisión vive en `engine/` (permanente). `ict_backtest/` es
  consumidor puro; al rescatar los ⚠️ arriba, NO se importa ict_backtest desde
  engine/.
