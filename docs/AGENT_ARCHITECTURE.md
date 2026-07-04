# Agent Architecture

> The intelligence layer for SMC-SYSTEMS. Agents analyse market context and return structured evidence. They do **not** execute trades.

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

---

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
| **Columns read** | `swing_label`, `high`, `low`, `open`, `close`, `atr`, `tick_volume`, `macro_direction`, `stoch_k`, `stoch_d` |
| **Analysis** | Phase classification (ACCUMULATION, DISTRIBUTION, MARKUP, MARKDOWN), pattern detection (Spring, Upthrust, SOS, SOW, LPS, LPSY), effort vs result divergence, volume regime, **stochastic exhaustion detection** |
| **Source of truth** | `docs/WYCKOFF_RULEBOOK.md` |
| **Output** | `AnalysisResult` with bias, confidence, detected events (ACCUMULATION_EARLY, ACCUMULATION_LATE, DISTRIBUTION_EARLY, DISTRIBUTION_LATE, SPRING, UPTHRUST, SOS, SOW, LPS, LPSY, EFFORT_DIVERGENCE, **STOCH_EXHAUSTION**, **STOCH_DIVERGENCE**), evidence dict |
| **Forbidden** | Trade execution, position sizing, market structure analysis (delegates to ICT agent) |

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
| **Output** | Context DataFrame with 25 new `agent_*` columns appended |
| **ML integration** | Optional `ml_probabilities` array fed to Decision Agent |
| **Integration point** | Called from `pipeline.build_scalping_context()` when `orchestrator` parameter is provided |

---

## Data Flow (Full Pipeline)

```
MT5 Terminal
    │ mt5.copy_rates_from_pos()  (via MT5Connector — _data_legacy.py)
    ▼
data/raw/{symbol}_{tf}.parquet
    │ load_frame()
    ▼
build_scalping_context()
    │ detect_bos()         → swing_high, swing_low, swing_label, bos_direction, liquidity_sweep_*
    │ detect_choch()       → choch_signal
    │ detect_fvg()         → fvg_bullish, fvg_bearish, fvg_size, fvg_mid, fvg_fill_status
    │ detect_order_blocks()→ ob_bullish, ob_bearish, ob_top, ob_bottom, ob_distance
    │ detect_displacement()→ displacement_bullish, displacement_bearish, displacement_magnitude
    │ compute_zones()      → premium_discount_zone, premium_distance
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
Backtest / Live Execution
    │ GovernorPool (per-symbol risk)
    │ FeatureEngine (30+ features)
    │ ML quality filter (optional)
    │ Trade simulation or order execution
    ▼
results/{trades,metrics,equity}.{csv,json}
```

All detectors are wired and exported. Previous wiring gaps (displacement, zones) were fixed in Phase 1.4. `docs/AGENT_ARCHITECTURE.md` now reflects current code state (stochastic exhaustion implemented, 25 agent columns, 40-bar Wyckoff lookback).

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
| ICT | `bos.py`, `choch.py`, `fvg.py`, `ob.py`, `displacement.py`, `zones.py` | None |
| Wyckoff | `bos.py` (swing_label), indicators | None |
| Structure | `bos.py` (swing_label), trend_context | None |
| Decision | All agents | None |

### Harness Adapters

All modules are validated through the harness:

| Adapter | Module | Scenarios | Status |
|---------|--------|-----------|--------|
| `echo` | Echo test | 1 | ✅ |
| `signal_pipeline` | Signal generation | 1 | ✅ |
| `risk_governor` | Risk state machine | 4 (normal/caution/defensive/lockdown) | ✅ |
| `backtest` | Backtest engine | 0 | ⚠️ Pending |
| `feature_enrichment` | Feature pipeline | 1 | ✅ |
| `mt5_bridge` | ZeroMQ bridge | 1 | ✅ |
| `mt5_ea` | MQL5 EA simulation | 1 | ✅ |
| `langgraph_validation` | LangGraph orchestration | 1 | ✅ |
| `monitoring` | Production monitoring | 1 | ✅ |
| `governance` | Model governance | 1 | ✅ |
| `paper_trading` | Paper trading runner | 1 | ✅ |

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

## Completed Milestones

| Phase | Description | Status |
|-------|-------------|--------|
| **F1-F4** | Pipeline wiring, agents, contracts | ✅ |
| **F5** | ZeroMQ Bridge Module | ✅ |
| **F6** | MQL5 EA compiled | ✅ |
| **F7** | LangGraph backtest validation | ✅ |
| **F8** | Deployment Guide | ⬜ Pending |
| **F9-F13** | Quant audit (robustness, Wyckoff, ML, tuning, validation) | ✅ |
| **F14** | Feature enrichment (liquidity sweeps, displacement, zones, regime) | ✅ |
| **F15** | Production monitoring (drift, alerts, equity telemetry) | ✅ |
| **F16** | Governance & automation (model registry, retraining, reports) | ✅ |

### Known Gaps

- **Parameter tuning**: All hyperparameters are hardcoded — no Optuna/Hyperopt sweeps yet
- **Robust validation methods**: PurgedKFold, CVaR, DSR, PBO not yet implemented
- **Deployment guide**: No VPS/deployment documentation exists (postponed — last priority)
