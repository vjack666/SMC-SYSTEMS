# Agent Architecture

> The intelligence layer for SMC_SUCCESSOR. Agents analyse market context and return structured evidence. They do **not** execute trades.

---

## Architecture Overview

```
                     MT5 Data
                         |
                         v
                 FeatureEngine / Context
                         |
            +------------+------------+
            |            |            |
            v            v            v
      ICT Agent   Wyckoff Agent   Structure Agent
            |            |            |
            +------------+------------+
                         |
                         v
                  Decision Agent
                         |
                         v
                  Signal Confidence
                         |
                         v
                  Risk Governor
                         |
                         v
                Backtest Execution
```

## Agent Responsibilities

### ICT Agent (`agents/ict_agent.py`)

| Aspect | Detail |
|--------|--------|
| **Input** | Context DataFrame row + 20-bar lookback window |
| **Columns read** | `swing_label`, `macro_direction`, `bos_direction`, `choch_signal`, `liquidity_sweep_up/down`, `recent_sweep_up/down`, `fvg_bullish/bearish`, `fvg_fill_status`, `fvg_size`, `atr`, `ob_bullish/bearish`, `ob_distance`, `premium_discount_zone`, `displacement_bullish/bearish`, `d1_direction` |
| **Analysis** | Market structure trend, BOS, CHOCH, liquidity sweeps, FVG quality, OB proximity, premium/discount zone, displacement, MTF alignment |
| **Source of truth** | `docs/ICT_RULEBOOK.md` |
| **Output** | `AnalysisResult` with bias, confidence, detected events (BOS, CHOCH, LIQUIDITY_SWEEP, FVG, ORDER_BLOCK, DISPLACEMENT, MTF_ALIGNMENT), evidence dict |
| **Forbidden** | Trade execution, position sizing, stop/target setting |

### Wyckoff Agent (`agents/wyckoff_agent.py`)

| Aspect | Detail |
|--------|--------|
| **Input** | Context DataFrame row + 40-bar lookback window |
| **Columns read** | `high`, `low`, `close`, `open`, `atr`, `swing_label`, `macro_direction`, `tick_volume` |
| **Analysis** | Phase classification (ACCUMULATION/MARKUP/DISTRIBUTION/MARKDOWN), Spring, Upthrust, SOS, SOW, LPS, LPSY, effort vs result divergence, volume regime |
| **Source of truth** | `docs/WYCKOFF_RULEBOOK.md` |
| **Output** | `AnalysisResult` with bias, confidence, detected events (SPRING, UPTHRUST, SOS, SOW, LPS, LPSY, EFFORT_RESULT_DIVERGENCE), evidence dict (phase, volume_regime, etc.) |
| **Forbidden** | Trade execution, hardcoded entries, conflicting phase interpretation |

### Structure Agent (`agents/structure_agent.py`)

| Aspect | Detail |
|--------|--------|
| **Input** | Context DataFrame row + 30-bar lookback window |
| **Columns read** | `macro_direction`, `swing_label`, `market_regime`, `volatility_regime`, `trend_confidence`, `range_compression`, `directional_efficiency`, `d1_direction`, `h4_trend` |
| **Analysis** | Trend direction, swing label counts (HH/HL/LH/LL), MTF alignment (D1/H4/LTF voting), range compression, directional efficiency |
| **Output** | `AnalysisResult` with bias, confidence, detected events (CONSECUTIVE_HH, CONSECUTIVE_LL, MTF_BULLISH, MTF_BEARISH, RANGE_COMPRESSION, HIGH_DIRECTIONAL_EFFICIENCY) |
| **Forbidden** | Trade execution, ICT concept interpretation (delegates to ICT agent) |

### Decision Agent (`agents/decision_agent.py`)

| Aspect | Detail |
|--------|--------|
| **Input** | `AnalysisResult` from ICT, Wyckoff, Structure agents + optional `ml_probability` |
| **Analysis** | Weighted voting (ICT 0.35, Wyckoff 0.30, Structure 0.20, ML 0.15), conflict detection, final bias computation |
| **Output** | `AnalysisResult` with combined bias, confidence, reasons list, conflicts list, invalidation conditions |
| **Forbidden** | Re-interpreting raw market data, overriding agent analyses without evidence |

### Orchestrator (`agents/orchestrator.py`)

| Aspect | Detail |
|--------|--------|
| **Input** | Full context DataFrame (all columns from detectors + indicators + trend context) |
| **Processing** | Iterates each bar → runs ICT → Wyckoff → Structure → Decision agents |
| **Output** | Context DataFrame with 14 new `agent_*` columns appended |
| **ML integration** | Optional `ml_probabilities` array fed to Decision Agent |
| **Integration point** | Called from `pipeline.build_scalping_context()` when `orchestrator` parameter is provided |

---

## Data Flow (Full Pipeline)

```
MT5 Terminal
    │ mt5.copy_rates_from_pos()  (via MT5Connector)
    ▼
data/raw/{symbol}_{tf}.parquet
    │ load_frame()
    ▼
build_scalping_context()
    │ detect_bos()         → swing_high, swing_low, swing_label, bos_direction, liquidity_sweep_*
    │ detect_choch()       → choch_signal
    │ detect_fvg()         → fvg_bullish, fvg_bearish, fvg_size, fvg_mid, fvg_fill_status
    │ detect_order_blocks()→ ob_bullish, ob_bearish, ob_top, ob_bottom, ob_distance
    │ detect_displacement()→ displacement_bullish, displacement_bearish, displacement_magnitude  ❌ NOT WIRED
    │ compute_zones()      → premium_discount_zone, premium_distance  ❌ NOT WIRED
    │ add_atr/ema/rsi      → atr, ema_fast/ema_slow, rsi
    │ build_trend_context  → macro_direction, d1_direction, h4_trend, trend_confidence, etc.
    ▼
AgentOrchestrator (optional)
    │ ICTAgent.analyze()
    │ WyckoffAgent.analyze()
    │ StructureAgent.analyze()
    │ DecisionAgent.decide()
    ▼
Filter computation
    │ filter_trend, filter_bos, filter_ob_fvg, filter_choch, filter_swing, filter_agents
    ▼
Confluence scoring + signal_confidence
    ▼
ScalpingSignal list (entry, SL, TP, direction, confidence)
    ▼
run_combined_backtest()
    │ GovernorPool (per-symbol risk)
    │ FeatureEngine.extract_features()
    │ ML quality filter
    │ Trade simulation
    ▼
results/{trades,metrics,equity,dataset}.{csv,json}
```

---

## Protocol

### `AgentProtocol` (`agents/base.py`)

```python
@runtime_checkable
class AgentProtocol(Protocol):
    name: str
    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult: ...
```

### `AnalysisResult` (`agents/base.py`)

```python
@dataclass
class AnalysisResult:
    agent_name: str = ""
    bias: str = "NEUTRAL"           # BULLISH / BEARISH / NEUTRAL
    confidence: float = 0.0         # 0.0 – 0.95
    detected_events: list[dict]     # [{"type": "FVG", "direction": "bullish", ...}, ...]
    evidence: dict                  # {"market_structure": "BULLISH", "fvg": {...}, ...}
    invalidation_conditions: list[str]  # reasons this analysis may be invalid
```

### Extending for New Agents

1. Create a class implementing `AgentProtocol` (duck typing — no explicit inheritance required).
2. Implement `analyze(self, context, index) -> AnalysisResult`.
3. Register in `orchestrator.py` if it should run automatically.
4. Add columns to `AGENT_COLUMNS` list.
5. Wire into `DecisionAgent.decide()`.

---

## Dependencies

### Runtime Dependencies

| Agent | Depends On | Missing |
|-------|-----------|---------|
| ICT | `bos.py`, `choch.py`, `fvg.py`, `ob.py` | `displacement.py` (columns not in pipeline), `zones.py` (columns not in pipeline) |
| Wyckoff | `bos.py` (swing_label), indicators | None |
| Structure | `bos.py` (swing_label), trend_context | None |
| Decision | All agents | None |

### Detector Export Gap

`detectors/__init__.py` does **not** export `detect_displacement` or `compute_zones`. These functions exist at `detectors/displacement.py` and `detectors/zones.py` but are not importable from the package.

### Pipeline Wiring Gap

`pipeline.py:build_scalping_context()` does **not** call `detect_displacement()` or `compute_zones()`. The columns `displacement_bullish`, `displacement_bearish`, `displacement_magnitude`, `premium_discount_zone`, `premium_distance` are not present in the context DataFrame that agents receive.

This means:
- **ICT Agent's displacement detection always returns `None`** (column defaults to `False` via `.get()`)
- **ICT Agent's premium/discount zone always returns `"UNKNOWN"`** (column defaults via `.get()`)
- **These features are completely silent** — no error, but no signal either.

---

## Forbidden Responsibilities

Agents must never:

1. **Execute trades** — no order placement, no entry/exit logic
2. **Set position sizes** — no risk calculation, no lot sizing
3. **Hardcode SL/TP levels** — these come from `ScalpingConfig`/volatility
4. **Override other agents** — Decision Agent weights are configurable, not hardcoded
5. **Introduce concepts outside their rulebook** — ICT Agent must stick to `ICT_RULEBOOK.md`, Wyckoff Agent to `WYCKOFF_RULEBOOK.md`
6. **Generate synthetic data** — agents read what detectors produce, nothing else
7. **Modify the context DataFrame** — analysis is read-only

---

## Testing Requirements

- Every agent must run independently with synthetic data
- Orchestrator must combine agent outputs into a single DataFrame
- Decision Agent must handle conflicting agent signals (ICT bullish + Wyckoff bearish)
- Full pipeline test with orchestrator wired must not crash
- Missing detector columns must be handled gracefully (not crash, but log/diagnose)

---

## Audit Findings (2026-06-28)

### Problems Discovered

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | **HIGH** | `detect_displacement()` not called in pipeline — ICT Agent's displacement analysis always returns `None` | `pipeline.py:66-69` |
| 2 | **HIGH** | `compute_zones()` not called in pipeline — ICT Agent's zone analysis always returns `"UNKNOWN"` | `pipeline.py:66-69` |
| 3 | **HIGH** | `detectors/__init__.py` doesn't export displacement or zones — pipeline can't import them | `detectors/__init__.py` |
| 4 | **MEDIUM** | Backtest loop never passes orchestrator to `build_scalping_context` | `engine.py:333-338` |
| 5 | **MEDIUM** | `DecisionAgent.analyze()` is a no-op stub — actual logic is in `decide()` | `decision_agent.py:36-42` |
| 6 | **LOW** | Agents don't explicitly inherit `AgentProtocol` (duck-typing works, but no static enforcement) | All agent files |
| 7 | **LOW** | `structure_agent.py` reads `volatility_regime` which duplicates `market_regime` in the feature engine | `structure_agent.py:42` |
| 8 | **LOW** | No integration test running full pipeline with orchestrator | `tests/test_agents.py` |

### Recommended Next Phase

1. **Wire displacement and zones into pipeline** — add `detect_displacement()` and `compute_zones()` calls in `build_scalping_context()`, export from `detectors/__init__.py`
2. **Wire orchestrator into backtest** — pass `AgentOrchestrator` through `build_scalping_context()` in `run_combined_backtest()`
3. **Add deployment-test** — end-to-end test that runs `build_scalping_context` with orchestrator on real/synthetic data
4. **Fix `DetectorAgent.analyze()`** — make it either a real per-bar analyze method or raise `NotImplementedError`
5. **Add agent confidence to feature matrix** — expose `agent_*` columns to ML training
6. **Performance benchmark** — agent analysis on 500k bars (O(n × lookback))
