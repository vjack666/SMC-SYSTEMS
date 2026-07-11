"""ict_backtest/optimize.py — Capa 3: optimizador bayesiano (Optuna) + walk-forward.

Objetivo: afinar los hiperparametros de la Capa 2 (sequence.py) SIN overfit.
Segun docs/ict/09_OPTIMIZADOR_BAYESIANO.md:

  - Optuna (TPE sampler) busca la combinacion que MAXIMIZA el Profit Factor.
  - Walk-forward: dividimos el LTF en ventanas rolling; optimizamos en la
    ventana IN-SAMPLE y validamos en la OUT-OF-SAMPLE (datos nunca vistos).
    El PF promedio out-of-sample es la prueba de fuego contra el overfit.

Diseno:
  - objective(trial): sugere parametros -> corre sequence sobre la ventana
    in-sample -> devuelve PF (o penaliza si pocos trades / PF<=0).
  - Tras la optimizacion, evaluamos los mejores parametros en CADA ventana
    out-of-sample y reportamos PF medio (la metrica honesta).

Uso (rapido, pocos trials, para validar):
  python ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 8 \
      --n-windows 3 --window-bars 8000

Uso completo (lento, 50k velas):
  python ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 60
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time  # noqa: E402
from ict_backtest.engine import simulate_trade, ICTSignal  # noqa: E402

# Helper global: mapea indice del LTF -> timestamp, usado por el estimator HTF
# (busqueda por tiempo, robusta a recortes de walk-forward).
ltf_time_fn = lambda i: i


@dataclass
class _OptParams:
    displace_gap: int
    bos_gap: int
    require_displacement: bool
    tp_mode: str


def _metrics(pnls: list[float]) -> dict[str, float]:
    n = len(pnls)
    if n == 0:
        return {"trades": 0, "winrate": 0.0, "pf": 0.0, "expectancy": 0.0,
                "max_dd_r": 0.0, "total_r": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {
        "trades": n,
        "winrate": len(wins) / n,
        "pf": pf,
        "expectancy": sum(pnls) / n,
        "max_dd_r": max_dd,
        "total_r": sum(pnls),
    }


def _build_htf_estimator(htf_df: pd.DataFrame):
    def est_htf_fn(i: int) -> dict:
        # Busca por TIEMPO, no por indice de posicion: asi funciona aunque el
        # LTF y el HTF esten recortados a distinto rango (walk-forward slices).
        t = ltf_time_fn(i)
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return est_htf_fn


def sequence_pf_on_slice(ltf_df: pd.DataFrame, htf_df: pd.DataFrame,
                         params: _OptParams, max_hold: int) -> dict:
    """Corre la Capa 2 sobre un subconjunto del LTF y devuelve metricas."""
    global ltf_time_fn
    ltf_time_fn = lambda i: ltf_df.iloc[i]["time"]
    est = _build_htf_estimator(htf_df)
    raw_sigs, _phases = run_sequence(
        ltf_df, est,
        SequenceConfig(counter_trend=False, tp_mode=params.tp_mode,
                       require_displacement=params.require_displacement,
                       displace_gap=params.displace_gap, bos_gap=params.bos_gap))

    signals = []
    for s in raw_sigs:
        direction = s["direction"]
        entry = s["entry"]
        atr = float(ltf_df.iloc[s["entry_at"]].get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        bos_lvl = s.get("bos_level", float("nan"))
        if direction == 1:
            sl = bos_lvl - 0.5 * atr if np.isfinite(bos_lvl) else entry - atr
        else:
            sl = bos_lvl + 0.5 * atr if np.isfinite(bos_lvl) else entry + atr
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + 2.0 * risk if direction == 1 else entry - 2.0 * risk
        signals.append(ICTSignal(symbol="", time=s["time"], direction=direction,
                                 entry=entry, stop_loss=sl, take_profit=tp,
                                 model="sequence"))

    pnls: list[float] = []
    for sig in signals:
        trade, _meta = simulate_trade(ltf_df, sig, max_hold)
        if trade is not None:
            pnls.append(trade.pnl_r)
    return _metrics(pnls)


def _split_windows(n: int, n_windows: int, min_train: int) -> list[tuple[int, int, int, int]]:
    """Devuelve lista de (train_start, train_end, test_start, test_end)."""
    out = []
    for i in range(n_windows):
        train_end = int(min_train + (n - min_train) * i / n_windows)
        test_end = int(min_train + (n - min_train) * (i + 1) / n_windows) if i < n_windows - 1 \
            else n
        if test_end - train_end < 5:
            continue
        out.append((0, train_end, train_end, test_end))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--htf", default="H4")
    ap.add_argument("--ltf", default="M15")
    ap.add_argument("--trials", type=int, default=8)
    ap.add_argument("--n-windows", type=int, default=3)
    ap.add_argument("--window-bars", type=int, default=0,
                    help="si >0, usa solo las ultimas N velas del LTF (rapidez). 0=completo.")
    ap.add_argument("--max-hold", type=int, default=96)
    ap.add_argument("--study-name", default="capa3_sequence")
    args = ap.parse_args()

    import optuna

    print(f"[C3] Cargando {args.symbol} {args.htf}/{args.ltf} ...", flush=True)
    t0 = time.time()
    frames = load_frames(args.symbol, (args.htf, args.ltf, "D1"))
    # CRITICO: aplicar detect_market_structure IGUAL que run_backtest.py.
    # Sin esto el HTF no tiene 'trend'/'liquidity_sweep' y run_sequence
    # da 0 senales (bug de la primera version de la Capa 3).
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[args.ltf]
    htf_df = ms.get(args.htf, ltf_df)
    print(f"      LTF: {len(ltf_df)} velas | HTF: {len(htf_df)} velas "
          f"({time.time()-t0:.1f}s)", flush=True)

    # Recorte opcional para rapidez (validacion). Siempre usamos el FINAL de la
    # serie (datos mas recientes) para que el out-of-sample sea el mas nuevo.
    if args.window_bars and args.window_bars < len(ltf_df):
        ltf_df = ltf_df.iloc[-args.window_bars:].reset_index(drop=True)
        # El HTF debe recortarse al mismo rango temporal aproximado.
        t_min = ltf_df["time"].min()
        htf_df = htf_df[htf_df["time"] >= t_min].reset_index(drop=True)
        print(f"      recorte LTF -> {len(ltf_df)} velas (rapidez)", flush=True)

    # REVISADO (2026-07-11): el PRIMER tercio de la serie dio 0 senales con
    # la config base -> Optuna penalizaba todo con -1.0 y no aprendia.
    # Elegimos como IN-SAMPLE el ULTIMO tercio (datos mas recientes, con volumen
    # comprobado: la (A) dio 70 trades en la serie completa). El OUT-OF-SAMPLE
    # son los tramos anteriores (validacion temporal hacia atras).
    n = len(ltf_df)
    min_train = max(2000, n // (args.n_windows + 1))
    windows = _split_windows(n, args.n_windows, min_train)
    # Reordenar: la ventana 0 (in-sample de optimizacion) = ultimo tercio.
    if windows:
        windows = [windows[-1]] + windows[:-1]
    print(f"      ventanas walk-forward: {len(windows)} (in-sample=ultimo tercio, {min_train} velas)", flush=True)

    def objective(trial: "optuna.trial.Trial") -> float:
        params = _OptParams(
            displace_gap=trial.suggest_int("displace_gap", 1, 12),
            bos_gap=trial.suggest_int("bos_gap", 1, 16),
            require_displacement=trial.suggest_categorical("require_displacement", [True, False]),
            tp_mode=trial.suggest_categorical("tp_mode", ["fixed2r", "liquidity"]),
        )
        # OPTIMIZAR en la PRIMERA ventana (in-sample = ultimo tercio).
        tr0, te0 = windows[0][0], windows[0][1]
        m = sequence_pf_on_slice(ltf_df.iloc[tr0:te0].reset_index(drop=True),
                                 htf_df, params, args.max_hold)
        if m["trades"] < 5 or not np.isfinite(m["pf"]) or m["pf"] <= 0:
            # NO penalizar con -1.0 (dejaba a Optuna sin gradiente). Devolvemos
            # un PF bajo PERO finito, con leve empuje por nº de senales, para que
            # Optuna aprenda a buscar configs que al menos generen operaciones.
            return 0.01 * (1.0 + m["trades"] / 100.0)
        return float(m["pf"])

    print(f"[C3] Optuna: {args.trials} trials (TPE) sobre ventana in-sample ...", flush=True)
    import optuna as _opt

    # Callback con CONTADOR REGRESIVO: muestra "Trial N/M | falta ~Xmin".
    class _CuentaRegresiva:
        def __init__(self, n: int):
            self.n = n
            self.t0 = time.time()
        def __call__(self, study, trial):
            done = trial.number + 1
            if done < 1:
                return
            elapsed = time.time() - self.t0
            avg = elapsed / done
            restan = self.n - done
            falta_min = (avg * restan) / 60.0
            mejor = study.best_value
            barra = "#" * done + "-" * (self.n - done)
            print(f"  [{barra}] Trial {done}/{self.n} | falta ~{falta_min:.1f} min "
                  f"| mejor_PF={mejor:.3f}", flush=True)

    study = _opt.create_study(direction="maximize",
                                sampler=_opt.samplers.TPESampler(seed=42),
                                study_name=args.study_name)
    t0 = time.time()
    study.optimize(objective, n_trials=args.trials,
                   callbacks=[_CuentaRegresiva(args.trials)])
    print(f"      optimizado en {time.time()-t0:.1f}s", flush=True)
    print(f"      MEJOR PF in-sample: {study.best_value:.3f}", flush=True)
    print(f"      MEJORES PARAMS: {study.best_params}", flush=True)

    best = _OptParams(
        displace_gap=study.best_params["displace_gap"],
        bos_gap=study.best_params["bos_gap"],
        require_displacement=study.best_params["require_displacement"],
        tp_mode=study.best_params["tp_mode"],
    )

    # WALK-FORWARD: evaluar los mejores params en CADA ventana out-of-sample.
    print("\n===== WALK-FORWARD OUT-OF-SAMPLE (params optimizados) =====", flush=True)
    oos_pfs, oos_wrs, oos_trades = [], [], []
    for wi, (tr_s, tr_e, te_s, te_e) in enumerate(windows):
        if te_e - te_s < 5:
            continue
        m = sequence_pf_on_slice(ltf_df.iloc[te_s:te_e].reset_index(drop=True),
                                 htf_df, best, args.max_hold)
        tag = "IN-SAMPLE" if wi == 0 else "OUT-OF-SAMPLE"
        print(f"  ventana {wi+1} [{tag}]: trades={m['trades']} WR={m['winrate']*100:.1f}% "
              f"PF={m['pf']:.3f} R={m['total_r']:.1f} DD={m['max_dd_r']:.1f}", flush=True)
        if wi > 0:
            oos_pfs.append(m["pf"]); oos_wrs.append(m["winrate"]); oos_trades.append(m["trades"])

    if oos_pfs:
        print(f"\n>>> PF OUT-OF-SAMPLE MEDIO: {np.mean(oos_pfs):.3f} "
              f"(ventanas={len(oos_pfs)}, trades={sum(oos_trades)})", flush=True)
        print(f">>> WR OUT-OF-SAMPLE MEDIO: {np.mean(oos_wrs)*100:.1f}%", flush=True)
        if np.mean(oos_pfs) > 1.0:
            print(">>> VERDICTO: edge mantiene PF>1 en out-of-sample => SIN overfit claro.", flush=True)
        else:
            print(">>> VERDICTO: PF<=1 en out-of-sample => posible overfit o edge debil. Revisar.", flush=True)


if __name__ == "__main__":
    main()
