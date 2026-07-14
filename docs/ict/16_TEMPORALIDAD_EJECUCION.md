# ICT — Temporalidad de ejecución: jerarquía HTF → LTF → exec

| Campo | Valor |
|-------|-------|
| **ID** | `16_TEMPORALIDAD_EJECUCION.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Autor** | SMC-SYSTEMS (Ruben + agente) |
| **Estado** | Marco de aplicación al motor (v30) |
| **Fuente verdad** | Código repo + innercircletrader.net (Turtle Soup / Silver Bullet) |
| **Relaciona** | `15_INTRADIA_ENTRADA_SL_TP.md`, `17_SCALPING_ENTRADA_SL_TP.md`, `14_STOP_LOSS_ESTRUCTURAL.md` |

---

## §0 Contrato operativo (CITABLE)

1. Toda operación ICT tiene 3 capas de temporalidad:
   - **HTF** (sesgo): dónde quiere ir el precio (H4 intradía, M15/H1 scalping).
   - **LTF** (contexto de zona): dónde marcar niveles (M15 intradía, M5 scalping).
   - **exec TF** (disparo): dónde entra el trade (M15 intradía, M5/M1 scalping).
2. El **sesgo** se lee del HTF. La **estructura** (BOS/CHOCH/sweep/FVG) se marca en el LTF. La **entrada, SL y TP** se resuelven en el exec TF.
3. Nunca resolver entry/SL/TP en el HTF. Nunca usar el HTF como exec TF (infla distancias: el bug de v28/v29).
4. El motor debe permitir `htf` y `ltf` independientes (ya lo hace: `build_signals_from_frames(htf=, ltf=)`).

---

## 1. El bug que este libro corrige

R4 v28 (ATR) y v29 (SL estructural) corrieron `htf=H4, ltf=M15`. El motor entra en `row["close"]` del LTF (M15) y el TP apunta a la liquidez del LTF. Eso es intradía correcto en teoría, PERO:

- El entry en close de BOS M15 = tarde (no retorno a zona).
- El TP en cluster de liquidez M15 = lejano → hold_limit (v29: 7/11 y 11/13).

El presente de Ruben era CIERTO: el H4 infla el sesgo, y resolver todo en M15 (grueso) infla el TP. La solución no es "usar H4 para el stop" (eso sería peor), es **bajar el exec TF al nivel fino donde ICT realmente ejecuta**: M5/M1 para scalping, y para intradía usar el retorno a la zona M15 en vez del close del BOS.

---

## 2. Jerarquía soportada por el repo (código real)

`ict_backtest/engine.py` `TF_FREQ` (líneas 250-252):
```
TF_FREQ = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
    "H1": pd.Timedelta(hours=1),
    ...
}
```
El motor ya itera cualquier LTF. `build_signals_from_frames(htf=, ltf=)` ya acepta HTF y LTF distintos. `checklist_scalping` (rules.py 174) ya pasa `exec_tf` explícito.

O sea: la infraestructura para bajar el exec TF YA EXISTE. El backtest v29 solo no la usó para scalping (corrió H4→M15).

---

## 3. Mapeo ICT (fuente: innercircletrader.net)

| Modelo | HTF (sesgo) | LTF (zonas) | exec TF (disparo) | Killzone |
|--------|-------------|-------------|-------------------|-----------|
| Turtle Soup intradía | H4 | M15 | M15 (retorno a zona) | London/NY |
| Silver Bullet scalp | M15/H1 | M5 | M5/M1 | NY AM 10–11 ET |
| PO3 | D1 | H4 | H4/M15 | London open |

El humano ICT marca en M15 (parent chart) y ejecuta en M5/M1. El robot v29 marcaba y ejecutaba en M15 (no tan fino).

---

## 4. Cómo el motor debe usar las 3 capas

`build_signals_from_frames` debe:
1. Leer `trend` del HTF para sesgo (ya lo hace, línea 85).
2. Detectar sweep/BOS/CHOCH/FVG en el LTF (ya lo hace vía `detect_market_structure` + `build_features`).
3. **Entry**: retorno a la zona del LTF (FVG/OB) — no close del BOS.
4. **SL**: mecha del sweep del LTF ± buffer (`calc_structural_sl`, ya hecho).
5. **TP**: liquidez opuesta del LTF MÁS CERCANA (`_tp_liquidity` a corregir en v30).

Para scalping: correr con `ltf=M5`, `htf=M15`. El motor no cambia, solo el argumento.

---

## 5. Auditoría de look-ahead por temporalidad

- El sesgo del HTF debe leerse de la vela YA CERRADA del HTF (`.shift(1)` en `_row_at_time`, ya aplicado en auditoría #1).
- El sweep/FVG del LTF debe leerse de la vela cerrada (`.shift(1)`).
- El exec TF (entry) debe ser una vela posterior al sweep confirmado, no la misma.
- Nunca leer el HTF "hacia adelante" para justificar una entrada en el LTF (eso es look-ahead por mal alineo de TF — ya auditado en `AUDIT_BUG_SILVER_TF.md`).

---

## 6. Checklist de aplicación (v30)

- [ ] `run_backtest.py` / scripts v30: permitir `ltf=M5` para scalping.
- [ ] `build_signals_from_frames`: separar "marcar zona LTF" de "disparar exec TF".
- [ ] Intradía (H4→M15): entry en retorno a zona M15, TP cercano M15.
- [ ] Scalping (M15→M5): entry en retorno a FVG M5, TP inmediato M5.
- [ ] Re-medir ambos: hold_limit debe caer, PF debe sostenerse > 1.

---

> **Nota de veracidad**: la jerarquía está en el código (TF_FREQ, build_signals_from_frames, checklist_scalping). Los números de scalping se miden en v30+, no se afirman antes.
