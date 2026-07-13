# 12 — Estrategias ICT Completas (inventario real del código)

> Libro índice de TODAS las estrategias ICT que SMC-SYSTEMS materializa en código.
> No es teoría sola: cada estrategia está anclada a la función/archivo real que la
> ejecuta, con los huecos verificados (no especulados). Inventario al 2026-07-12.

---

## 0. Mapa de estrategias

El sistema tiene **5 piezas** que constituyen la "estrategia ICT". Tres son modelos
con nombre (`rules.py`), una es el motor genérico subyacente (`sequence.py`), y una
es el agregador en vivo (`pipeline.py`). El grafo confirma que viven en **4 islas
separadas** (comunidades 0 / 25 / 27 / 197, 0 aristas entre ellas — ver §6).

| # | Estrategia | Archivo real | Modo |
|---|---|---|---|
| 1 | Intradia PO3 (Power of Three) | `ict_backtest/rules.py:checklist_intradia` | a-favor |
| 2 | Turtle Soup (contratendencia) | `rules.py:checklist_intradia(counter_trend=True)` | contra HTF |
| 3 | Silver Bullet (scalping) | `ict_backtest/rules.py:checklist_scalping` | a-favor |
| 4 | Motor Event-Sequence | `ict_backtest/sequence.py:run_sequence` | genérico (backtest) |
| 5 | Pipeline de confluencia en vivo | `signals/pipeline.py:build_scalping_context` | agregador (alertas) |

---

## 1. Intradia PO3 (Power of Three / AMD)

**Teoría ICT:** el día tiene 3 fases — acumulación → manipulación (barrido de
liquidez en killzone) → distribución. Se opera a-favor de la marea del HTF
(D1/H4), buscando el barrido de SSL/BSL y luego el BOS/CHOCH en el exec TF.

**Reglas exactas (`checklist_intradia`):**
1. Sesgo del día desde H4/D1 (L/S).
2. Contexto D1/H4 con tendencia definida (no rango).
3. Killzone intradia activa (London Open / NY AM / NY PM, UTC).
4. Sweep de liquidez SSL/BSL en HTF/exec.
5. BOS/CHOCH en exec TF (a-favor: dirección = marea HTF).
6. Dirección alineada (votos L/S o BOS M15).

**Código:** `ict_backtest/rules.py:90-169`. Evaluado por `evaluate(model="intradia")`.
El motor `engine.build_signals_from_frames(model="intradia")` recorre el LTF barra a
barra y genera `ICTSignal` si `verdict["ready"]`.

**TP / RR — YA IMPLEMENTADO (corrección de libro):** el checklist marca
`PENDIENTE: TP en liquidez opuesta` y `PENDIENTE: RR >= 1:2` (líneas 166-168), pero
ESOS DOS ESTÁN IMPLEMENTADOS EN EL MOTOR, no faltan. `engine.py` cierra cada señal
con `tp_mode`: `"fixed2r"` (TP = entry ± 2×risk, RR 1:2) o `"liquidity"` (TP en el
pool BSL/SSL opuesto vía `_tp_liquidity`, línea 261). `run_backtest.py --tp-mode`
expone ambos. El "PENDIENTE" del checklist es redundante (repite la regla de
ejecución que el motor ya cumple), NO un hueco real.

---

## 2. Turtle Soup (contratendencia)

**Teoría ICT:** el precio barre un swing (SSL/BSL) y revierte contra la marea del
HTF. Es la trampa a los traders que operan el breakout.

**Reglas (`checklist_intradia` con `counter_trend=True`):**
- HTF debe tener tendencia clara A OPONERSE.
- El disparo es un BOS/CHOCH en dirección OPUESTA al sesgo HTF (líneas 141-153).
- La dirección del setup = opuesta al HTF (función `_dir_setup`, líneas 62-65).

**Código:** mismo `checklist_intradia` que PO3 pero con `counter_trend=True`
(`rules.py:115-119, 141-153`). En el motor: `build_signals_from_frames(counter_trend=True)`.
`run_backtest.py` lo usa en la variante V3 ("CT liquidity+disp").

**TP / RR:** igual que PO3 — implementado en el motor (`fixed2r` / `liquidity`).

---

## 3. Silver Bullet (scalping)

**Teoría ICT:** ventana NY AM (10-11 ET). Se filtra por sesgo del día (solo a-favor),
se espera sweep de SSL/BSL en M15, y luego un FVG en M1/M5 para entrar; SL sobre el
FVG/OB; salida rápida en liquidez opuesta.

**Reglas (`checklist_scalping`):**
1. Ventana Silver Bullet (NY AM).
2. Sesgo del día filtra setups a favor.
3. Sweep SSL/BSL en M15.
4. FVG en M1/M5 tras el sweep.
5. Dirección coincide.
6. SL en FVG/OB (líneas 172-230).

**Código:** `ict_backtest/rules.py:172-230`. Evaluado por `evaluate(model="scalping")`.
El motor lo recorre igual que intradia pero con el modelo scalping.

**TP / RR — YA IMPLEMENTADO:** el checklist marca `PENDIENTE: RR >= 1:2, salida en
liquidez opuesta` (línea 228-229), pero el motor `engine.py` ya cierra con
`fixed2r`/`liquidity` (igual que arriba). No es hueco real.

---

## 4. Motor Event-Sequence (Capa 2 del backtest)

**Qué es:** el motor genérico que materializa la secuencia ICT pura, usado para
medir PF/WR. No tiene nombre de "estrategia" pero es la base de intradia/scalping.

**Secuencia (`sequence.py:run_sequence`, PHASE en línea 31):**
```
IDLE → SWEEP_DONE → DISPLACE_DONE → BOS_DONE → ENTRY
```
- `displace_gap=6` velas para el displacement tras el sweep.
- `bos_gap=10` velas para el BOS tras el displacement.
- Si se excede el gap sin avanzar, la secuencia se reinicia (no acumula ruido).
- A-favor o contratendencia (`_has_bos` línea 92, dirección según sesgo HTF).
- ENTRY = FVG/OB en la dirección (`_latest_fvg_zone` / `_latest_ob_zone`).

**Código:** `ict_backtest/sequence.py`. Validado en EURUSD M15 (PF 1.548 tras fixes
de auditoría; OOS 3.389±2.303). Es el número que reportamos.

**Hueco real:** `sequence.py` NO usa `filter_sweep`/`filter_ote` del pipeline (ver
libro 10 §6). O sea el backtest y las señales en vivo salen de motores distintos.

---

## 5. Pipeline de confluencia en vivo

**Qué es:** el agregador que te alerta en vivo. Junta TODOS los filtros en un
`confluence_score` y genera señal si pasa el umbral (`min_confluence_score`).

**Filtros y pesos (rulebook, unificados 2026-07-12):**
`trend=3, choch=3, ob=2, fvg=2, displacement=2, bos=1, swing=1, agents=2, sweep=2, ote=1`.

**Código:** `signals/pipeline.py:build_scalping_context` → `build_scalping_signals`.
Llega a vos vía `adapters/signal_adapter.py` → `rutina_eurusd.py` (popup+sonido).

**TP / RR:** `build_scalping_signals` usa TP = entry ± 2×ATR fijo (línea ~362), NO
apunta a liquidez opuesta como el motor `engine.py`. Este SÍ es un hueco real de
calidad (el EA pro ICT apunta a PDH/PDL/EQH/EQL). Ver libro 11 §5.

---

## 6. Fragmentación confirmada por el grafo

El grafo (`graphify-out/graph.json`, refrescado 2026-07-12: 3084 nodos / 6108
aristas) confirma que las 5 piezas viven en islas separadas:

| Módulo | Comunidad |
|---|---|
| `signals/pipeline.py` | 27 |
| `agents/ict_agent.py` | 0 |
| `ict_backtest/sequence.py` | 25 |
| `ict_backtest/rules.py` | 197 |

**Aristas ENTRE los 4 módulos: 0.** Cada uno implementa la "misma estrategia ICT"
con lógica y pesos que divergen:
- Pipeline (vivo): pesos en `ScalpingConfig` (rulebook, alineado).
- Agente ICT: pesos propios en `ict_agent.py:179` (BOS=1, CHOCH=2, SWEEP=2, FVG=2, OB=2, DISP=2, MTF=3) — similar pero NO idéntico.
- Backtest `sequence.py`: params propios (`displace_gap`, `bos_gap`).
- `rules.py`: checklist intradia/scalping aparte.

Consecuencia: cambiar el rulebook mueve solo el pipeline. Los otros 3 no se enteren.
Esto es deuda de arquitectura (ver libro 11 y propuesta de unificación futura).

---

## 7. Resumen de huecos REALES (no los del checklist)

1. **TP en vivo apunta a 2×ATR fijo**, no a liquidez opuesta (el motor de backtest
   SÍ lo hace vía `tp_mode="liquidity"`). Calidad de RR en vivo menor que en backtest.
2. **`sequence.py` no usa `filter_sweep`/`filter_ote`** del pipeline → backtest y vivo
   divergen en la cadena de liquidez.
3. **Agente ICT tiene pesos propios**, no los de `ScalpingConfig`.
4. **Fragmentación en 4 islas** (grafo §6) → no hay single source of truth.

Los "PENDIENTE: TP/RR" de los checklists de `rules.py` NO son huecos: el motor
`engine.py` ya cierra con RR 1:2 y TP en liquidez opuesta. Se documentan aquí para
no subestimar lo que ya existe.

---

## 8. Fuentes

- `ict_backtest/rules.py` — checklists intradia/scalping (código real).
- `ict_backtest/sequence.py` — motor event-sequence (código real).
- `ict_backtest/engine.py` — cierre de señales con TP/RR (`fixed2r` / `liquidity`).
- `signals/pipeline.py` — pipeline de confluencia en vivo.
- `agents/ict_agent.py` — agente ICT (pesos propios).
- `graphify-out/graph.json` — grafo de dependencias (comunidades 0/25/27/197).
- Libros 06_TURTLE_SOUP, 07_SILVER_BULLET, 08_POWER_OF_THREE, 10_SWEEP_OTE_FILTRO,
  11_SWEEP_OTE_MANUAL_VS_AUTO de docs/ict/.
