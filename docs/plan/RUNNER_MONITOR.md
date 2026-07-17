# Hermes Runner Monitor — heavy job policy

**Status:** Implemented (`scripts/runner_monitor.py`)  
**Date:** 2026-07-16  
**Goal:** Run heavy jobs without chat polling; show a clean secondary panel; protect a 16 GB laptop.

---

## Rule (agents) — NON-NEGOTIABLE

**Threshold: any job that may exceed 60 seconds.**

```text
Job > 60s (pytest | backtest | ML | optuna | bos_table | dataset | WF | export | …)
        ↓
python scripts/runner_monitor.py --window --title "NAME" -- <command>
        ↓
NEW Windows console opens (operator watches this)
        ↓
Agent: ONE blocking wait until process exit (OS event)
        ↓
Chat: SILENCE until done (no "still waiting" spam)
        ↓
Read exit code + results/runner_monitor_last.json + analyze once
```

**Required on Windows for jobs > 60s**

- Always pass **`--window`** so a **visible secondary console** opens.
- Parent process still **waits** (not fire-and-forget).
- Operator sees elapsed / CPU / RAM / real progress in that window.

**Forbidden**

- Hidden background / detached process with no visible window
- Chat polling every N seconds (“still waiting…”, “alive (73s)…”, “still running…”)
- Invented progress percentages
- CPU at 100% of logical cores by default
- Windows priority High / Realtime

**Allowed**

- UI refresh **inside the monitor window** (spinner / resources)
- Real progress only if the job writes `HERMES_PROGRESS_FILE` JSON

---

## Tiers

| Est. duration | Behaviour |
|---------------|-----------|
| **&lt; 60 s** | Main terminal OK (no monitor required) |
| **≥ 60 s** | **`runner_monitor.py --window`** + one blocking wait + chat silence |

---

## Resource policy (defaults)

| Knob | Default |
|------|---------|
| Workers | ~75% of `os.cpu_count()` via `HERMES_WORKERS` |
| Priority (Windows) | Above Normal |
| RAM soft cap | warn if system memory load ≥ 80% |
| Target RAM | keep headroom (~10–12 GB used on 16 GB machines) |

Env injected for consumers: `HERMES_WORKERS`, `JOBLIB_NUM_THREADS`, `OMP_NUM_THREADS`, etc.

**Host reference (operator laptop):** i9-class multi-core, **16 GB RAM**.  
Do not run the machine at 100% CPU or &gt;80% system RAM for long periods.

---

## Multi-symbol backtests (parallel batches)

**Yes — several pairs can run at the same time** to save wall-clock (finish near `max(t_i)` instead of `sum(t_i)`).

| Rule | Guidance (16 GB) |
|------|------------------|
| Max concurrent symbols | **2 default**; 3 if RAM &lt; 80%; avoid 4+ on full multi-TF |
| One monitor window per symbol | `--window --title "bt-EURUSD"` … |
| Workers budget | Split global ~75% CPUs **across** concurrent jobs (not 75% each) |
| Isolate outputs | `results/.../{symbol}/` so runs do not overwrite each other |
| On OOM | Drop to 1 concurrent and re-run that symbol |

```bat
rem Example: two pairs in parallel (two visible consoles)
start "bt-EURUSD" python scripts\runner_monitor.py --window --title "bt-EURUSD" -- python ict_backtest\run_backtest.py --symbol EURUSD
start "bt-XAUUSD" python scripts\runner_monitor.py --window --title "bt-XAUUSD" -- python ict_backtest\run_backtest.py --symbol XAUUSD
rem Agent waits for BOTH to exit (no chat spam). Then aggregates metrics.
```

Authority for backtest architecture + ops: `docs/plan/BACKTEST_V2_SPEC.md` §15.

---

## Progress file (optional, real only)

Path: `HERMES_PROGRESS_FILE` (default `results/runner_progress_<title>.json`).

```json
{
  "current": "Walk-forward fold 7",
  "done": 3458,
  "total": 8012,
  "unit": "trades"
}
```

If `total` is missing, the monitor shows counts **without** inventing a %.

---

## Commands

```bat
rem DEFAULT for long jobs on Windows: NEW visible console (parent still waits)
python scripts\runner_monitor.py --window --title "build_bos_table" -- python scripts\build_bos_table.py
python scripts\runner_monitor.py --window --title "pytest r10c" -- pytest tests\test_r10c_state_machine.py -q
python scripts\runner_monitor.py --window --title "backtest XAU" -- python ict_backtest\run_backtest.py --symbol XAUUSD

rem Same terminal only if job is short or CI
python scripts\runner_monitor.py --title "smoke" -- python -c "print('ok')"

rem Quiet (CI / no panel redraw) — not for interactive operator sessions
python scripts\runner_monitor.py --quiet-ui --title "unit" -- pytest -q

rem Shortcut
scripts\run_with_monitor.bat --window --title "mi job" -- <comando>
```

Summary JSON: `results/runner_monitor_last.json`  
One-liner for parsers: stdout line `HERMES_MONITOR_RESULT {...}`

---

## How agents should wait

One invocation with a long enough timeout. **Do not** loop “check status every 60s” in chat. The monitor process itself blocks until the child exits; that *is* the wait-by-event.

---

*Aligns with VISION (edge must be measurable) and R6 (honest long backtests without thrashing the host).*
