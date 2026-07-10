# Edge Diagnosis Report

**Generated:** 2026-07-09T20:47:01-05:00
**Units completed:** 168  |  valid OOS cells: 105  |  insufficient N: 63  |  zero trades: 21  |  errors: 0

## Verdict (read this first)

This harness measures the **detector stack alone** (no ML, no agents, neutral risk governor).
A real edge needs **OOS PF > 1.1 with N>=100 per split** on more than one symbol, and
that it **survives** ablation (does not vanish when one filter is removed).

- **Best avg OOS PF by variant:** `no_session` → PF **1.126** (over 5 symbol cells)
- **Worst avg OOS PF by variant:** `prox_1` → PF **1.054** (over 5 symbol cells)

> **Candidate edge** under variant `no_session` (avg OOS PF 1.126 over 5 symbols). Still validate walk-forward before any live automation.

## Ranking — variants (avg OOS PF, cells with n_oos>=20 and sufficient N)

| Rank | Variant | Avg OOS PF | # cells |
|-----:|---------|----------:|--------:|
| 1 | `no_session` | 1.126 | 5 |
| 2 | `w0_choch` | 1.097 | 5 |
| 3 | `w0_trend` | 1.097 | 5 |
| 4 | `no_atr` | 1.096 | 5 |
| 5 | `baseline` | 1.095 | 5 |
| 6 | `no_choch` | 1.095 | 5 |
| 7 | `mc_1` | 1.095 | 5 |
| 8 | `mc_3` | 1.095 | 5 |
| 9 | `mc_4` | 1.095 | 5 |
| 10 | `no_swing` | 1.095 | 5 |
| 11 | `no_micro` | 1.095 | 5 |
| 12 | `w0_ob_fvg` | 1.095 | 5 |
| 13 | `w0_bos` | 1.095 | 5 |
| 14 | `w0_swing` | 1.095 | 5 |
| 15 | `w0_agents` | 1.095 | 5 |
| 16 | `w0_sweep` | 1.095 | 5 |
| 17 | `w0_ote` | 1.095 | 5 |
| 18 | `no_sweep_ote` | 1.084 | 5 |
| 19 | `prox_2` | 1.076 | 5 |
| 20 | `prox_3` | 1.073 | 5 |
| 21 | `prox_1` | 1.054 | 5 |

## Ranking — symbols (avg OOS PF across variants)

| Rank | Symbol | Avg OOS PF | # cells |
|-----:|--------|----------:|--------:|
| 1 | `XAUUSD` | 1.376 | 21 |
| 2 | `USDCAD` | 1.264 | 21 |
| 3 | `EURUSD` | 1.162 | 21 |
| 4 | `AUDUSD` | 0.849 | 21 |
| 5 | `NZDUSD` | 0.809 | 21 |

## Top 10 cells (variant × symbol) by OOS PF

| Variant | Symbol | OOS N | OOS WR | OOS PF | OOS Sharpe | OOS avg R |
|---------|--------|------:|-------:|-------:|-----------:|----------:|
| `no_session` | `XAUUSD` | 900 | 55.1% | 1.642 | 3.28 | 0.2306 |
| `no_atr` | `XAUUSD` | 900 | 55.3% | 1.417 | 2.25 | 0.1419 |
| `baseline` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `no_choch` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `mc_1` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `mc_3` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `mc_4` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `no_swing` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `no_micro` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |
| `w0_trend` | `XAUUSD` | 900 | 60.1% | 1.379 | 2.11 | 0.0789 |

## Bottom 10 cells (worst OOS PF)

| Variant | Symbol | OOS N | OOS WR | OOS PF |
|---------|--------|------:|-------:|-------:|
| `prox_3` | `NZDUSD` | 676 | 52.1% | 0.779 |
| `prox_1` | `NZDUSD` | 663 | 52.5% | 0.791 |
| `prox_2` | `NZDUSD` | 673 | 52.3% | 0.791 |
| `w0_ote` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `w0_sweep` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `w0_agents` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `w0_swing` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `w0_bos` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `w0_ob_fvg` | `NZDUSD` | 670 | 52.4% | 0.794 |
| `no_micro` | `NZDUSD` | 670 | 52.4% | 0.794 |

## Baseline detail (reference config)

| Symbol | N total | IS PF | OOS PF | OOS N | Insufficient |
|--------|--------:|------:|-------:|------:|:------------:|
| `AUDUSD` | 2126 | 0.812 | 0.839 | 638 | no |
| `EURUSD` | 1553 | 1.084 | 1.170 | 466 | no |
| `GBPUSD` | 0 | — | — | 0 | YES |
| `NZDUSD` | 2232 | 1.001 | 0.794 | 670 | no |
| `USDCAD` | 3000 | 0.957 | 1.290 | 900 | no |
| `USDCHF` | 2 | — | — | 1 | YES |
| `USDJPY` | 3 | — | — | 1 | YES |
| `XAUUSD` | 3000 | 1.186 | 1.379 | 900 | no |

## Artifacts

- Progress (live): `results\edge_diagnosis\progress.json`
- Full results JSON: `results/edge_diagnosis/full_results.json`
- Per-variant CSVs: `results/edge_diagnosis/*.csv`
- Summary CSV: `results/edge_diagnosis/summary.csv`

## How to re-run

Double-click `run_edge_diagnosis.bat` or:

```bat
python -u scripts/edge_diagnosis/run.py --all
```

The job **resumes** from `full_results.json` if interrupted.
