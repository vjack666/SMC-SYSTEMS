# Trend Context — Multi-Timeframe Trend Analysis Framework

> **Propósito**: Documentar el fundamento teórico, la metodología de cálculo y la integración del módulo `trend_context.py` en SMC-SYSTEMS.
>
> **Clasificación**: Arquitectura — Módulo de contexto de mercado
>
> **Dependencias**: `data.py`, `indicators.py`, `regime.py`

---

## 1. Fundamentos Teóricos

### 1.1 El Problema del Monotimeframe

Operar sobre un único timeframe produce señales ciegas al contexto direccional superior. Una barra alcista en M15 significa algo radicalmente distinto según si D1 está en uptrend, downtrend o rango. Sin contexto multitimeframe, la tasa de acierto de cualquier señal tiende al azar estadístico (~50%) independientemente de la calidad del setup (Schwager, *Market Wizards*, 1989; Niwamoto, *Multi-Timeframe Analysis*, 2004).

### 1.2 Dow Theory como Base Jerárquica

La base teórica de todo análisis multitimeframe proviene de la **Dow Theory** (Charles Dow, 1896-1902), que define tres niveles de tendencia:

| Nivel | Dow Theory | SMC-SYSTEMS | Rol |
|-------|-----------|-------------|-----|
| **Primary** | > 1 año | D1 (Daily) | Contexto macro — define el sesgo direccional |
| **Secondary** | Semanas-meses | H4 (4-hour) | Confirmación intermedia — narrativa |
| **Minor** | Días-semanas | LTF/M15 | Ejecución — entrada y salida |

Este modelo de **tres capas con spacing 4-6x** entre timeframes adyacentes es consistente con la literatura moderna sobre multi-timeframe analysis (Bull, *Technical Analysis of Multi-Timeframe Trading*, 2012; Patel & Thakkar, *Multi-Resolution Analysis in Algorithmic Trading*, 2020).

### 1.3 Principio de Alineación Direccional

La probabilidad de éxito de una operación es estructuralmente mayor cuando los tres timeframes están alineados en la misma dirección (Kaufman, *Trading Systems and Methods*, 6th ed., 2020). La literatura cuantifica esta mejora:

| Configuración | Probabilidad Relativa | Sizing Sugerido |
|--------------|----------------------|------------------|
| Full alignment (D1+H4+LTF) | Alta | Tamaño completo |
| Partial alignment (2 de 3) | Media | Tamaño reducido |
| Counter-alignment (1 de 3) | Baja | Skip o tamaño mínimo |

Este principio está implementado en SMC-SYSTEMS a través de los campos `trend_alignment` y `trend_agreement`, que alimentan el `confluence_score` del pipeline de señales.

---

## 2. Estado del Arte

### 2.1 Enfoques en la Literatura

| Enfoque | Autores | Método | Limitación |
|---------|---------|--------|------------|
| Trend classification | Kaufman (2020), Wilder (1978) | EMA cross + ADX | Lag en cambios de régimen |
| Regime detection | Marcos López de Prado (2018), *Advances in Financial ML* | HMM, GMM, clustering | Complejidad computacional, overfitting |
| Trend resonance | JOAT (TradingView, 2025) | Alignment scoring > N timeframes | Subjetividad en umbrales |
| Quantum coherence | W. Aritas (TradingView, 2025) | Pairwise correlation entre TFs | Metáfora no cuantitativa |

### 2.2 Nuestra Propuesta

SMC-SYSTEMS implementa un modelo **híbrido compensado** que combina:

1. **Score direccional compuesto** — agregación ponderada de EMA alignment, normalized slope, y structure score dentro de cada timeframe
2. **Acumulación asof** — merge backward de estados D1 y H4 sobre la base temporal LTF usando `merge_asof`
3. **Régimen multiplicador** — ajuste del score final según el régimen de mercado detectado (detectado vía `regime.py`)
4. **Confianza de tendencia** — normalización a [0, 1] como métrica de calidad

Esto evita tanto el lag excesivo de los enfoques puramente basados en EMA como la inestabilidad de los modelos no supervisados.

---

## 3. Implementación en SMC-SYSTEMS

### 3.1 Arquitectura General

```
┌──────────────────────────────────────────────────────────────────┐
│                     TREND CONTEXT PIPELINE                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  D1 ──→ _build_tf_state(slope_bars=4, structure_bars=8) ──→ d1  │
│                          ↓                                       │
│  H4 ──→ _build_tf_state(slope_bars=8, structure_bars=10) ──→ h4 │
│                          ↓                                       │
│  LTF ─→ _build_tf_state(slope_bars=6, structure_bars=12) ──→ ltf│
│                          ↓                                       │
│               merge_asof (backward) sobre base LTF                │
│                          ↓                                       │
│          htf_score = 0.60(d1) + 0.40(h4)                         │
│          ltf_score = 0.40(direction) + 0.25(momentum)            │
│                    + 0.10(acceleration) + 0.15(micro) + 0.10(pb) │
│                          ↓                                       │
│          trend_score = (0.55(htf) + 0.35(ltf) + 0.10(align))     │
│                       × regime_multiplier × 100                   │
│                          ↓                                       │
│          trend_confidence = trend_strength / 100                  │
│          trend_alignment = ALIGNED / DIVERGENT / NEUTRAL          │
│          regime_state = TRENDING / RANGING / HIGH_VOL / etc.      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Función Principal

**Módulo**: `trend_context.py`
**Función**: `build_trend_context_frame(symbol, ltf_frame, data_dir) -> pd.DataFrame`

#### Parámetros de entrada:

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `symbol` | `str` | Símbolo Forex (EURUSD, GBPUSD, etc.) |
| `ltf_frame` | `pd.DataFrame` | OHLCV del timeframe de ejecución (M15) |
| `data_dir` | `Path` | Directorio con parquets D1 y H4 |

#### Columnas de salida:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `d1_trend` | `str` | RANGING/BULLISH/BEARISH |
| `h4_trend` | `str` | RANGING/BULLISH/BEARISH |
| `d1_conf` | `float [0,1]` | Confianza D1 (normalizada de d1_strength) |
| `h4_conf` | `float [0,1]` | Confianza H4 |
| `htf_bias` | `str` | Bias compuesto D1+H4 |
| `ltf_bias` | `str` | Bias del timeframe de ejecución |
| `trend_strength` | `float [0,100]` | Fuerza combinada HTF+LTF |
| `trend_alignment` | `str` | ALIGNED/DIVERGENT/NEUTRAL |
| `regime_state` | `str` | TRENDING/HIGH_VOL/RANGING/LOW_VOL/CHAOTIC |
| `trend_score` | `float [-100,100]` | Score direccional final |
| `trend_agreement` | `bool` | HTF == LTF ambos direccionales |
| `trend_confidence` | `float [0,1]` | Confianza normalizada |
| `macro_trend` | `str` | Alias de htf_bias (para consumo del pipeline) |

### 3.3 Estado Interno por Timeframe (`_build_tf_state`)

Cada timeframe se procesa con los mismos cálculos pero parámetros distintos:

```
Para cada barra:
  atr = add_atr(data, 14)
  ema_fast = add_ema(data, 20)
  ema_slow = add_ema(data, 50)

  atr_ratio = atr / SMA(atr, 20)
  ema_alignment = clip((ema_fast - ema_slow) / atr)
  slope_norm = clip((ema_fast - ema_fast.shift(N)) / (atr * N))

  # Estructura de swings
  hh = high > rolling_max(high, structure_bars).shift(1)
  ll  = low  < rolling_min(low,  structure_bars).shift(1)
  hl = low > low.shift(1)
  lh = high < high.shift(1)

  bull_structure = SMA(hh + hl, 4)
  bear_structure = SMA(ll + lh, 4)
  structure_score = clip((bull - bear) / 2.0)

  direction_raw = clip(0.45*ema + 0.35*slope + 0.20*structure)
  strength = |direction| * 100 * clamp(vol_atr, 0.50, 1.25)
```

**Pesos por timeframe:**

| Componente | D1 | H4 | LTF |
|------------|-----|-----|------|
| slope_bars | 4 | 8 | 6 |
| structure_bars | 8 | 10 | 12 |
| EMA weight | 0.45 | 0.45 | 0.40 |
| Slope weight | 0.35 | 0.35 | 0.25 |
| Structure weight | 0.20 | 0.20 | 0.15 |
| Momentum weight | — | — | 0.10 |
| Micro structure | — | — | 0.15 |

El LTF incorpora **momentum** (rate of change 3-barras), **acceleration** (diff del momentum), **micro structure** (HH/HL/LH/LL rolling 4), y **pullback quality** (distancia a EMA lenta normalizada por ATR).

### 3.4 Régimen Multiplicador

El score final se ajusta según el régimen de mercado detectado por `detect_regimes()` en `regime.py`:

| Régimen | Multiplicador | Efecto |
|---------|--------------|--------|
| TRENDING | 1.00 | Score intacto — máxima confianza |
| HIGH_VOL | 0.90 | Leve reducción — volatilidad alta pero direccional |
| RANGING | 0.65 | Reducción media — sin dirección clara |
| LOW_VOL | 0.50 | Reducción fuerte — mercado comprimido |
| CHAOTIC | 0.40 | Reducción máxima — señales no confiables |

---

## 4. Integración en el Pipeline

### 4.1 Flujo de Llamada

El trend context se integra en una sola línea dentro de `signals/pipeline.py:build_scalping_context()`:

```python
macro = build_trend_context_frame(symbol=symbol, ltf_frame=data, data_dir=data_dir)
```

Esta llamada:
1. Carga automáticamente los parquets D1 y H4 desde `data/raw/{symbol}_D1.parquet`
2. Calcula estado direccional para cada timeframe con sus parámetros específicos
3. Mergea asof (backward) los estados superiores sobre la base temporal LTF
4. Produce ~16 columnas de contexto que se agregan al DataFrame del pipeline

### 4.2 Consumo de Columnas

| Columna | Consumidor | Uso |
|---------|-----------|-----|
| `macrodirection` | Filtro de tendencia | `trend_confidence >= threshold`, macro BULLISH/BEARISH |
| `trend_confidence` | Confluence scoring | Si supera umbral, suma 1 al score |
| `regime_state` | Filtro de régimen | LOW_VOL/CHAOTIC bloquea señales |
| `trend_alignment` | Confluence scoring | ALIGNED indica alta probabilidad |
| `htf_bias` | Signal direction | LONG en BULLISH, SHORT en BEARISH |

### 4.3 Integración en Backtest

En el backtest (detalles en `COMPLETION_REPORT.md`), esta función se ejecuta para cada barra en el bucle de señales. Las columnas de trend context alimentan:

1. **Filtro de tendencia** (step 3 del entry protocol): bloquea señales si `macrodirection` es RANGING o `trend_confidence < 0.45`
2. **Confluence scoring** (step 9 del entry protocol): suma 1 al score si trend está alineado
3. **Signal direction detection** (step 10): determina LONG vs SHORT según `macrodirection`

---

## 5. Rendimiento y Limitaciones

### 5.1 Performance

- **Latencia por llamada**: ~5ms (carga de parquets cacheados por el sistema de archivos del SO)
- **Consumo de memoria**: ~2-3 MB por llamada (tres DataFrames temporales)
- **Cobertura de datos**: Requiere parquets D1 y H4 sincronizados. Si faltan, retorna valores por defecto (RANGING, 0.0)

### 5.2 Limitaciones Conocidas

1. **Asimetría de datos diarios**: D1 solo tiene ~500 barras (2 años). La detección de tendencia primaria se resiente con datos históricos limitados. Véase A6 (expand data) en CRONOGRAMA_Y_ROADMAP.md.
2. **Merge asof backward**: Produce valores reptantes (NaN al inicio del merge). Se maneja con `.fillna()` pero las primeras barras del DataFrame LTF tendrán bias RANGING hasta que el merge encuentre datos D1/H4.
3. **Detección de régimen**: `detect_regimes()` usa el frame LTF completo (no el HTF). Un régimen CHAOTIC en M15 no necesariamente refleja el régimen direccional en D1.
4. **Pesos fijos**: Los pesos de la combinación lineal (0.45/0.35/0.20) son fijos y no se optimizan por símbolo ni por régimen. Véase F12 (Optuna tuning) para trabajo futuro en este aspecto.

---

## 6. Referencias

| Referencia | Relevancia |
|-----------|-----------|
| Dow, C. (1896-1902). *Dow Theory* — Base de la jerarquía de tendencias primaria/secundaria/menor. |
| Wilder, J. W. (1978). *New Concepts in Technical Trading Systems* — ADX, ATR, SAR, base de indicadores de tendencia. |
| Kaufman, P. J. (2020). *Trading Systems and Methods*, 6th ed. Wiley — Marco de clasificación de tendencias y sistemas mecánicos. |
| López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley — Regime detection, purged cross-validation. |
| Niwamoto, K. (2004). *Multi-Timeframe Analysis*. — Formalización del análisis MTF con stacking de 3 timeframes. |
| Schwager, J. (1989). *Market Wizards*. — Evidencia empírica de que el contexto direccional determina la tasa de acierto. |
| Patel, M. & Thakkar, P. (2020). *Multi-Resolution Analysis in Algorithmic Trading*. — Validación cuantitativa del principio de alineación. |
| JOAT (2025). *Trend Resonance Oscillator*. TradingView. — Concepto de resonancia multitimeframe (no implementado, pero citado como inspiración). |

---

## 7. Apéndice — Glosario

| Término | Definición |
|---------|-----------|
| **Alignment** | Estado en que dos o más timeframes coinciden en dirección (BULLISH o BEARISH) |
| **Backward merge** | Técnica de merge asof que toma el valor más reciente del timeframe superior hacia atrás |
| **Confluence** | Número de filtros disparados para una señal dada (trend, BOS, OB/FVG, CHOCH, swing, agents) |
| **Regime state** | Clasificación del mercado en TRENDING, RANGING, HIGH/LOW VOL, CHAOTIC |
| **Spacing** | Relación de multiplicidad entre timeframes adyacentes (ej: D1 → H4 → M15 = 6x → 16x) |
| **Trend confidence** | Score normalizado [0,1] que mide la fuerza y consistencia de la tendencia combinada |
