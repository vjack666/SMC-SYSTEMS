# ICT — Scalping (Silver Bullet): Entrada, SL y TP en M1/M5

| Campo | Valor |
|-------|-------|
| **ID** | `17_SCALPING_ENTRADA_SL_TP.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Autor** | SMC-SYSTEMS (Ruben + agente) |
| **Estado** | Propuesta de aplicación al motor (v30+ scalping) |
| **Fuente verdad** | Código repo + innercircletrader.net (Silver Bullet) |
| **Relaciona** | `07_SILVER_BULLET.md`, `16_TEMPORALIDAD_EJECUCION.md`, `15_INTRADIA_ENTRADA_SL_TP.md` |

---

## §0 Contrato operativo (CITABLE)

1. Scalping = HTF **M15/H1** para sesgo + **M5/M1** como TF de ejecución. Killzone **NY AM 10:00–11:00 ET** (Silver Bullet).
2. **Entrada**: retorno al FVG M5/M1 creado por el displacement tras el sweep en el exec TF. Rápido, en ventana de 1h.
3. **SL**: sobre/bajo el swing protegido (la mecha del sweep o el borde del FVG/OB). Buffer pequeño (0.2–0.3 ATR del exec TF).
4. **TP**: liquidez opuesta INMEDIATA (el primer BSL/SSL que el precio toca yendo a favor). RR 1:2 rápido, salida en minutos.
5. **No confundir con intradía**: el scalping NO usa H4→M15 para ejecutar; usa M15 para sesgo y M5/M1 para disparar.

---

## 1. Por qué el motor actual no hace scalping real

`build_signals_from_frames` itera el LTF (en backtest v29 fue M15) y entra en `row["close"]`. Para scalping, el exec TF debe ser **M5 o M1**, no M15. El repo YA soporta M1/M5 (`TF_FREQ` engine.py 251: `"M1"`, `"M5"`), y `checklist_scalping` (rules.py 174) ya modelo Silver Bullet: sweep en exec_tf → FVG en M1/M5 → SL en FVG/OB → salida en liquidez opuesta rápida.

Pero el backtest v29 corrió H4→M15 (intradía), no M15→M5 (scalping). Por eso el TP quedó lejos: el exec TF era grueso.

El fix no es nuevo código de detección: es **correr el motor con `ltf=M5` (o M1) y `htf=M15`**, y que `_tp_liquidity` use el nivel cercano (ver libro 15, §4). El motor ya itera cualquier LTF; solo había que elegir el fino.

---

## 2. Entrada scalping (Silver Bullet, fuente ICT)

Secuencia (innercircletrader.net Silver Bullet):
1. Killzone NY AM 10:00–11:00 ET.
2. Sesgo del día filtra dirección (solo setups a favor del sesgo).
3. Sweep de SSL/BSL en M5 (o M1).
4. FVG se forma en M5/M1 por el displacement.
5. **Entrada**: retorno al FVG M5/M1 (la zona de imbalance).
6. SL: sobre/bajo el swing protegido (mecha del sweep o borde del FVG).
7. TP: liquidez opuesta inmediata, RR 1:2, salida en minutos.

`checklist_scalping` (rules.py 174) ya valida esto ítem por ítem. El motor debe usar `exec_tf=M5` y leer el FVG de M5/M1.

---

## 3. SL scalping

Reusa `calc_structural_sl` (v29) pero con el exec TF = M5/M1:
- SL = mecha del sweep M5 ± buffer (0.2–0.3 ATR de M5).
- El buffer es MÁS chico que en intradía porque el exec TF es fino y el ruido también.
- `STRUCT_SL_MAX_ATR` (6.0) sigue como filtro: si el sweep en M5 fue gigante, salta.

No necesita nuevo código: `calc_structural_sl` lee `sweep_low`/`sweep_high` del DataFrame del exec TF. Solo correrlo con `ltf=M5`.

---

## 4. TP scalping

`_tp_liquidity` con exec TF = M5/M1:
- TP = primer BSL/SSL opuesto en M5/M1 más cercano al entry.
- En scalping el TP es CORTO por diseño (liquidez inmediata, no la del HTF).
- RR 1:2 rápido (checklist_scalping ítem 7).

Esto mata el hold_limit: el TP está a pocas velas M5 del entry.

---

## 5. Diferencia clave intradía vs scalping (tabla)

| Dimensión | Intradía (libro 15) | Scalping (este libro) |
|-----------|---------------------|------------------------|
| HTF sesgo | H4 | M15 / H1 |
| Exec TF | M15 | M5 / M1 |
| Killzone | London/NY (amplio) | NY AM 10–11 ET (estrecho) |
| Entrada | retorno a FVG/OB M15 | retorno a FVG M5/M1 |
| SL | mecha sweep M15 ± 0.3 ATR | mecha sweep M5 ± 0.2 ATR |
| TP | liquidez opuesta M15 cercana | liquidez opuesta M5 inmediata |
| Hold | ≥ 40 velas M15 | pocas velas M5 (minutos) |
| RR | 1:2 a 1:3 | 1:2 rápido |

---

## 6. Auditoría

- `checklist_scalping` ya exige exec_tf explícito (rules.py 183) para evitar la desincronización que silenció Silver Bullet (ver `AUDIT_BUG_SILVER_TF.md`).
- El FVG debe leerse de la vela cerrada (`.shift(1)`), no la en formación.
- Killzone NY AM debe calcularse en la zona horaria correcta (pendiente TZ en libro 01).

---

## 7. Checklist de aplicación (v30+ scalping)

- [ ] Script `r4_scalping_v30.py`: `htf=M15`, `ltf=M5`, `--model scalping`, `--tp-mode liquidity`.
- [ ] `build_signals_from_frames`: entry en retorno a FVG M5 (no close del BOS M5).
- [ ] `_tp_liquidity`: nivel cercano en M5.
- [ ] `max_hold` corto (velas M5, no M15).
- [ ] Re-correr y medir: % hold_limit debe ser ~0, PF debe sostenerse.

---

> **Nota de veracidad**: el scalping aún no se backtesteó en v29 (corrió H4→M15). Los números de scalping se miden en v30+, no se afirman antes.
