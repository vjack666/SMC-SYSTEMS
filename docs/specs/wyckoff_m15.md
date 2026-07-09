# SDD — Fase Wyckoff M15 en la ficha

Detecta la fase del ciclo de Wyckoff (Accumulation/Markup/Distribution/Markdown)
en M15 usando el WyckoffAgent YA EXISTENTE del proyecto, y la muestra en la ficha.

---

## 1. REQUIREMENTS

**R1:** THE SYSTEM SHALL cargar EURUSD_M15 (data/raw) y enriquecerlo con las
columnas que WyckoffAgent necesita: atr, swing_label, macro_direction,
stoch_k, stoch_d (tick_volume YA viene en el parquet).

**R2:** THE SYSTEM SHALL correr WyckoffAgent.analyze(frame, -1) sobre M15 y
extraer phase, bias, confidence y eventos (spring/upthrust/sos/sow).

**R3:** THE SYSTEM SHALL mostrar en la ficha: fase actual (en espanol), sesgo,
confianza y eventos detectados.

**R4:** THE SYSTEM SHALL integrarse a rutina_eurusd.py (analyze_timeframe M15)
y renderizarse bajo la seccion de EJECUCION M15.

---

## 2. DESIGN

### Reuso (no duplicar)
- `agents/wyckoff_agent.py` → WyckoffAgent (logica de fase 100% del proyecto)
- `detectors/bos.py` → detect_bos() ya pone swing_label
- `indicators/` → compute_stochastic() da stoch_k/stoch_d
- `compute_zones`/`detect_trend` ya en rutina (macro_direction del trend)
- `docs/WYCKOFF_RULEBOOK.md` → reglas (solo referencia)

### Enriquecimiento M15 (funcion _enrich_wyckoff)
- atr: rolling TR 14
- swing_label: detect_bos(df)['swing_label']
- macro_direction: del trend (BULLISH/BEARISH/RANGING)
- stoch_k, stoch_d: compute_stochastic
- tick_volume: ya presente

### Mapa fase -> espanol
ACCUMULATION* -> "ACUMULACION", MARKUP -> "MARKUP (subida)",
DISTRIBUTION* -> "DISTRIBUCION", MARKDOWN -> "MARKDOWN (bajada)",
UNKNOWN -> "INDDEFINIDA"

### Archivos
- Nuevo: `scripts/fase_wyckoff_m15.py` (utilidad + test manual)
- Modifica: `scripts/rutina_eurusd.py` (integra en M15 + render)

---

## 3. TASKS
- [ ] T1: `_enrich_wyckoff(df)` calcula columnas faltantes.
- [ ] T2: correr WyckoffAgent, extraer phase/bias/conf/eventos.
- [ ] T3: integrar en analyze_timeframe(M15) y render.
- [ ] T4: verificar con datos reales.
- [ ] T5: documentar en RUTINA_EURUSD.md.

---

## 4. FUERA DE ALCANCE
- Nuevas reglas Wyckoff (ya estan en el rulebook y el agente).
- Abrir ordenes.
