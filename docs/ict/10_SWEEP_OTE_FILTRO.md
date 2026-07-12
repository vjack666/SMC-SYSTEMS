# 10 — Sweep de Liquidez + OTE como Filtros de Señal (Ítem D)

> Libro de INTEGRACIÓN. No es un concepto nuevo de ICT: retoma el **sweep de
> liquidez** (05_LIQUIDEZ) y el **OTE / Premium-Discount** (03_FVG, 04_ORDER_BLOCKS)
> y documenta cómo SMC-SYSTEMS los cablea al `confluence_score` de
> `signals/pipeline.py`. Incluye evidencia medida en EURUSD M15 (50.000 velas)
> y el HUECO REAL que aún no se cerró.

---

## 1. La tesis ICT (por qué importa)

En ICT, el precio no se mueve al azar: antes de una reversión real suele ir a
**cazar liquidez** — los stops agrupados por encima de un swing high (Buyside
Liquidity, BSL) o por debajo de un swing low (Sellside Liquidity, SSL). Ese
"barrido" se llama **liquidity sweep**: el precio rompe el nivel, lame los stops,
y cierra adentro (no es un BOS legítimo, es manipulación). El OTE (Optimal Trade
Entry) es el retroceso 62-79% del rango del swing donde la institución carga su
posición en discount (compras) o premium (ventas).

**Regla operativa ICT:** una entrada de reversión SIN un sweep previo es
desconfiable; una entrada en OTE (discount/premium según dirección) es de mayor
calidad. Por eso el sistema los usa como filtros de confluencia, no como triggers.

---

## 2. Cómo lo calcula el sistema (código real, verificado)

### 2.1 Detector de sweep — `detectors/liquidity.py`
Existe y es la fuente de verdad. Detecta un failed breakout contra el último
swing high/low confirmado:
- **Bearish sweep**: `bar_high > swing_level` AND `bar_close < swing_level`
  (rompe máximo previo, cierra adentro).
- **Bullish sweep**: `bar_low < swing_level` AND `bar_close > swing_level`.
- `sweep_strength` se normaliza por ATR (cap 3.0, clip a 1.0).

### 2.2 Cableado en el pipeline — `signals/pipeline.py` (Ítem D, YA FUSIONADO)
El `build_scalping_context` (líneas ~230-249) ya:
1. Calcula `liquidity_sweep_detected` (rompe + cierra adentro del swing).
2. Lo propaga con ventana rolling de `sweep_lookback=8` barras en
   `recent_liquidity_sweep` (coherente con `INDUCEMENT_LOOKBACK` del adapter).
3. Construye `filter_ote` con `premium_discount_zone` (de `compute_zones`).
4. Pesa ambos en `confluence_weights` (`sweep=2.0`, `ote=1.0` del rulebook).

El `confluence_score` (líneas ~283-297) ya suma
`filter_sweep * sweep_weight + filter_ote * ote_weight`.

> Nota de trazabilidad: el borrador `docs/proposals/item_D.md` describe este
> diff como "no aplicado". Está DESACTUALIZADO: el Ítem D ya está fusionado en
> `signals/pipeline.py` (flags en `ScalpingConfig` líneas 51-68, sweep/ote en
> `confluence_weights`). El borrador sirve solo como historia del diseño.

---

## 3. Evidencia medida (EURUSD M15, 50.000 velas, 2026-07-12)

Corrí `build_scalping_context('EURUSD','M15')` y medí la prevalencia real:

| Métrica | Valor | Interpretación |
|---|---|---|
| `liquidity_sweep_detected` | **14.44%** | 1 de cada 7 velas es un sweep crudo |
| `recent_liquidity_sweep` (ventana 8b) | **66.11%** | el sweep "reciente" está casi siempre activo |
| `filter_sweep` (activo) | **66.11%** | el filtro sweep pasa el 66% del tiempo |
| `filter_ote` (activo) | **1.00%** | casi NADIE pasa el filtro OTE |
| `OTE_LONG` / `OTE_SHORT` count | **0** | las bandas OTE jamás se activan |
| `premium_discount_zone` | DISCOUNT 24.337 / PREMIUM 25.663 | solo estas dos etiquetas aparecen |
| `confluence_score` medio | 2.6 | baseline actual |

**Conclusión empírica:** el sweep funciona y aporta (está activo el 66% del
tiempo, así que filtra el 34% de ruido de reversión sin sweep). El OTE, en
cambio, es un **casi no-op**: 1% de barras lo pasan.

---

## 4. HUECO REAL sin cerrar (documentado, no aplicado)

### 4.1 El OTE "puro" es inalcanzable en M15
`compute_zones` (detectors/zones.py) marca `OTE_LONG`/`OTE_SHORT` solo si el
close cae en el retroceso 62-79% del rango de swing. Probé con `swing_lookback`
5 / 10 / 20 en EURUSD M15:

```
swing_lookback=5 : OTE_LONG/SHORT = 0
swing_lookback=10: OTE_LONG/SHORT = 0
swing_lookback=20: OTE_LONG/SHORT = 0
```

El rango de swing en M15 es tan ancho que el retrace 62-79% **nunca** se cumple.
Por eso `filter_ote` (que usa `OTE_LONG`/`OTE_SHORT` en su diff original) cae a
usar solo DISCOUNT/PREMIUM — y como además exige `macro_direction` alineado,
termina pasando solo el 1% de las barras. El filtro OTE está **matando señales**
en vez de filtrar calidad.

### 4.2 Dos fuentes de verdad de sweep
El pipeline calcula el sweep con su propia heurística (líneas 232-236, sobre
`swing_high`/`swing_low` de `detect_bos`), mientras el adapter
`feature_enrichment_adapter.py` tiene su copia privada
`_detect_liquidity_sweeps`. No es un bug de señal, pero hay duplicación: si se
ajusta uno, el otro queda desincronizado.

---

## 5. Propuesta de fix (PENDIENTE de decisión del trader + walk-forward OOS)

1. **OTE efectivo = DISCOUNT/PREMIUM, no bandas 62-79%.** En M15 el filtro
   `filter_ote` debería usar `zone.isin(["DISCOUNT"])` para BULLISH y
   `["PREMIUM"]` para BEARISH (las bandas que SÍ se activan), o añadir un
   `ZoneConfig(swing_lookback=<corto>)` dedicado para M15. Esto convertiría el
   OTE de no-op (1%) en un filtro real de calidad.
2. **Unificar sweep en `detectors/liquidity.py`.** Hacer que el adapter importe
   el detector (ya existe) y borrar la copia privada, para una sola fuente.
3. **No fusionar sin walk-forward OOS.** Cualquier cambio de pesos/sweep/ote se
   decide DENTRO de la ventana de train de cada fold y se evalúa SOLO en OOS
   (PurgedKFold). Criterio: `with_sweep_and_ote` no debe degradar WR/PF OOS vs
   `without_sweep_ote`. Mejorar solo in-sample = descartar.

---

## 6. Conexión con la auditoría y los otros libros

- **05_LIQUIDEZ**: el sweep de este libro ES el hunt de liquidez documentado
  allí. El hueco que señaló 05 (liquidez decorativa desacoplada) quedó cerrado
  parcialmente: el pipeline YA filtra por sweep, pero el OTE sigue sin aportar.
- **Auditoría #1 (look-ahead)**: el sweep del pipeline usa `swing_high`/`swing_low`
  de `detect_bos` (ya sin look-ahead desde el commit 1074877). Sin fuga.
- **Capa 2/3 (`ict_backtest/sequence.py`)**: NO usa `filter_sweep`/`filter_ote`
  del pipeline; tiene su propia ventana `bos_gap`. Los números PF 1.548 / OOS
  3.389 no se mueven por este libro.
- **quality_filter.pkl**: re-entrenado hoy (AUC 0.498 = azar) con datos ya sin
  look-ahead. El filtro ML está OFF por defecto, así que no interfiere.

---

## 7. Estado

- ✅ Ítem D implementado: `detectors/liquidity.py` + `filter_sweep`/`filter_ote`
  cableados en `confluence_score` con pesos del rulebook.
- ✅ Sweep aporta (66% activo, filtra 34% de ruido).
- ⚠️ OTE es no-op en M15 (1% pasa; bandas 62-79% inalcanzables). Fix propuesto
  en §5.1, PENDIENTE de tu decisión + walk-forward OOS.
- ⚠️ Duplicación de sweep pipeline/adapter (§4.2), PENDIENTE de deduplicar.
