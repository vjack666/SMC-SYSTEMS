"""PRUEBA DE FUEGO del edge — A12 del roadmap (walk-forward OOS de la celda ganadora).

Pipeline completo, con barra de progreso en vivo + ETA + log con timestamp:
  FASE 0  Verifica MT5 abierto/logueado (si --download-years se pide).
  FASE 1  (opcional) Baja histórico multi-año (A6) via MT5.
  FASE 2  Arma dataset v4 de la celda ganadora `no_session` x XAUUSD.
  FASE 3  Walk-forward con PurgedKFold + Deflated Sharpe Ratio (A12).
  FASE 4  Reporte + guardado en results/walkforward/.

La celda ganadora del edge diagnosis fue `no_session` x XAUUSD
(OOS PF 1.642, N=900, Sharpe 3.28). Este script valida que ese edge
AGUANTA validacion seria (split temporal, no el 70/30 simple del diagnostico).

Uso:
  python scripts/run_walkforward_validation.py            # solo prueba de fuego (usa data/raw actual)
  python scripts/run_walkforward_validation.py --download-years 4   # tambien baja 4 anos de historia (A6)
  python scripts/run_walkforward_validation.py --symbol XAUUSD --variant no_session

Reusa ml/walk_forward.py, ml/dataset_builder.py, ml/stats_validator.py.
No modifica codigo de produccion.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

from tqdm import tqdm

RESULTS_DIR = _ROOT / "results" / "walkforward"
STATUS_PATH = RESULTS_DIR / "progress.json"
LOG_PATH = RESULTS_DIR / "walkforward.log"

# Celda ganadora del edge diagnosis (docs/EDGE_DIAGNOSIS_REPORT.md)
DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_VARIANT = "no_session"
MIN_N_PER_WINDOW = 100
PF_GATE = 1.10  # OOS PF minimo aceptable por ventana


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _log(msg: str) -> None:
    line = f"{_iso_now()}  {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write_status(phase: str, done: int, total: int, **extra: object) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    elapsed = extra.pop("elapsed_seconds", None)
    eta = extra.pop("eta_seconds_remaining", None)
    payload = {
        "phase": phase,
        "done_units": done,
        "total_units": total,
        "percent": round(100.0 * done / total, 1) if total else 0.0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "eta_seconds_remaining": eta,
        "elapsed_seconds": elapsed,
        **extra,
    }
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(STATUS_PATH)


def _progress_bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + "?" * width + "]"
    frac = min(1.0, max(0.0, done / total))
    filled = int(width * frac)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {frac * 100:5.1f}%"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def _check_mt5() -> bool:
    """Devuelve True si MT5 esta abierto y logueado. False si no."""
    try:
        from data.mt5.connector import ConnectionConfig, MT5Connector
        from _data_legacy import MT5_TERMINAL_PATH
        with MT5Connector(config=ConnectionConfig(path=MT5_TERMINAL_PATH)) as mt5:
            return mt5.account_info() is not None or mt5.terminal_info() is not None
    except Exception as e:  # noqa: BLE001 - queremos saber si MT5 no esta
        _log(f"  [MT5] no disponible: {e}")
        return False


def _download_history(years: float, symbols: tuple[str, ...]) -> None:
    _log(f"FASE 1: bajando {years} anos de historia para {symbols}...")
    from scripts.download_multiyear import main as download_main
    import argparse as _ap

    # download_multiyear.main() parsea argv; lo invocamos armando sys.argv.
    sys.argv = [
        "download_multiyear.py",
        "--symbols", *symbols,
        "--timeframes", "M15", "H4", "D1",
        "--years", str(years),
        "--output", str(_ROOT / "data" / "raw"),
    ]
    download_main()


def _heartbeat(stop: threading.Event, phase: str, note: str, total: int, done: int) -> None:
    """Imprime barra + latido al log cada 15s para que el usuario vea actividad."""
    count = 0
    while not stop.is_set():
        if stop.wait(15):
            break
        count += 1
        _print_live(done, total, phase, f"{note} ({count * 15}s)")
        _log(f"  ... sigue trabajando ({count * 15}s) — {note}")


def _print_live(done: int, total: int, phase: str, extra: str = "") -> None:
    """Barra de progreso en vivo (una sola linea, se reescribe con \\r)."""
    bar = _progress_bar(done, total)
    line = f"\r  {bar}  {done}/{total}  [{phase}]  {extra}"
    print(line, end="", flush=True)


def _build_v4_dataset(symbol: str, variant: str) -> Path:
    _log(f"FASE 2: armando dataset v4 para {variant} x {symbol}...")
    _log("  (el builder de features SMC es pesado; puede tardar varios minutos)")
    _write_status("dataset", 1, 3, current_symbol=symbol, note="build_ml_dataset en curso")
    from ml.dataset_builder import DatasetBuildConfig, build_ml_dataset
    from signals import ScalpingConfig

    out_dir = RESULTS_DIR / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = DatasetBuildConfig(
        symbols=(symbol,),
        timeframes=("M15",),
        data_dir=_ROOT / "data" / "raw",
        output_dir=out_dir,
        max_bars=8000,
        min_confidence=0.0,
        scalping_config=ScalpingConfig(trend_confidence_threshold=0.0, min_atr_ratio=0.0),
        schema_version="v4",
        auto_download=False,
        combined_output=True,
    )
    _hb_stop = threading.Event()
    _hb = threading.Thread(target=_heartbeat, args=(_hb_stop, "dataset", "calculando features SMC", 3, 1), daemon=True)
    _hb.start()
    try:
        build_ml_dataset(config)
    finally:
        _hb_stop.set()
        _hb.join(timeout=1)
    dataset_path = out_dir / "v4_dataset.parquet"
    if not dataset_path.exists():
        # build_ml_dataset puede nombrar distinto; buscar el parquet generado
        candidates = sorted(out_dir.glob(f"*{symbol}*v4*.parquet")) or sorted(out_dir.glob("*.parquet"))
        if not candidates:
            raise FileNotFoundError(f"No se genero dataset v4 en {out_dir}")
        dataset_path = candidates[-1]
    _log(f"  dataset: {dataset_path}")
    return dataset_path


def _run_walkforward(dataset_path: Path, symbol: str, n_windows: int = 4):
    _log(f"FASE 3: walk-forward OOS (PurgedKFold) sobre {dataset_path.name}...")
    from ml.walk_forward import run_walk_forward, print_walk_forward_report
    from ml.trainer import FEATURES_ML_V3, TARGET_COLUMN

    result = run_walk_forward(
        dataset_path=dataset_path,
        feature_list=FEATURES_ML_V3,
        target_column=TARGET_COLUMN,
        n_windows=n_windows,
        calibrate=True,
        cv_strategy="purged_kfold",
        purge=5,
        embargo=5,
    )
    print_walk_forward_report(result)

    # Extraer metricas por ventana y calcular DSR (Deflated Sharpe Ratio).
    from ml.stats_validator import compute_deflated_sharpe_ratio

    sharpes = [w.get("sharpe", 0.0) for w in result.windows if w.get("n_test", 0) >= MIN_N_PER_WINDOW]
    dsr = compute_deflated_sharpe_ratio(np.array(sharpes)) if sharpes else 0.0

    pf_list = [w.get("profit_factor_impact", 0.0) for w in result.windows]
    mean_pf = float(np.mean(pf_list)) if pf_list else 0.0
    pass_pf = all(p >= PF_GATE for p in pf_list) and len(pf_list) > 0
    pass_dsr = dsr > 0

    summary = {
        "symbol": symbol,
        "n_windows": len(result.windows),
        "mean_oos_pf": mean_pf,
        "dsr": dsr,
        "pass_pf_gate": pass_pf,
        "pass_dsr": pass_dsr,
        "windows": result.windows,
        "aggregate_metrics": result.aggregate_metrics,
        "stability": result.stability,
    }
    return summary, dsr, pass_pf, pass_dsr


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward OOS validation (A12)")
    ap.add_argument("--symbol", default=DEFAULT_SYMBOL)
    ap.add_argument("--variant", default=DEFAULT_VARIANT)
    ap.add_argument("--download-years", type=float, default=0.0,
                    help="Si >0, baja N anos de historia (A6) antes del walk-forward")
    ap.add_argument("--windows", type=int, default=4, help="Cantidad de ventanas walk-forward")
    args = ap.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")  # log fresco
    _write_status("starting", 0, 3, note="arrancando")
    t0 = time.time()
    _log("=" * 70)
    _log(f"PRUEBA DE FUEGO (A12) — {args.variant} x {args.symbol}")
    _log("=" * 70)

    phases = 3 + (1 if args.download_years > 0 else 0)
    done = 0

    # FASE 0/1 — descarga opcional (requiere MT5)
    if args.download_years > 0:
        _print_live(done, phases, "mt5-check")
        _log("FASE 0: verificando MT5...")
        if not _check_mt5():
            _log("ERROR: MT5 no esta abierto o sin login. Abrilo, entra a tu cuenta y reintenta.")
            _write_status("mt5_faltante", done, phases, ok=False)
            sys.exit(2)
        _download_history(args.download_years, (args.symbol,))
        done += 1
        _write_status("download", done, phases)
        _print_live(done, phases, "download")

    # FASE 2 — dataset
    _write_status("dataset", done, phases)
    _print_live(done, phases, "dataset")
    dataset_path = _build_v4_dataset(args.symbol, args.variant)
    done += 1
    _write_status("dataset", done, phases)
    _print_live(done, phases, "dataset")

    # FASE 3 — walk-forward
    _write_status("walkforward", done, phases)
    _print_live(done, phases, "walkforward")
    summary, dsr, pass_pf, pass_dsr = _run_walkforward(dataset_path, args.symbol, args.windows)
    done += 1
    _write_status("walkforward", done, phases)
    _print_live(done, phases, "walkforward")

    # FASE 4 — reporte + veredicto
    elapsed = time.time() - t0
    verdict = "PASS" if (pass_pf and pass_dsr) else "FAIL"
    _log("=" * 70)
    _log(f"VEREDICTO: {verdict}")
    _log(f"  Media OOS PF: {summary['mean_oos_pf']:.3f}  (gate >= {PF_GATE})  -> {'OK' if pass_pf else 'NO'}")
    _log(f"  Deflated Sharpe Ratio: {dsr:.3f}  (gate > 0)  -> {'OK' if pass_dsr else 'NO'}")
    _log(f"  Ventanas: {summary['n_windows']}  |  Tiempo total: {_fmt_duration(elapsed)}")
    _log("=" * 70)

    out_json = RESULTS_DIR / "WALKFORWARD_REPORT.json"
    out_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _log(f"Reporte guardado: {out_json}")

    _write_status("done", phases, phases, ok=(verdict == "PASS"), verdict=verdict)
    print()  # salta linea despues de la barra viva
    _print_live(phases, phases, "done", f"VEREDICTO: {verdict}")
    print(f"\nVEREDICTO FINAL: {verdict}  (ver results/walkforward/WALKFORWARD_REPORT.json)")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - queremos dejar constancia y no colgar la ventana
        import traceback

        _log("=" * 70)
        _log(f"ERROR NO CONTROLADO: {e}")
        _log(traceback.format_exc())
        _write_status("error", -1, -1, ok=False, error=str(e))
        # No hacemos sys.exit aqui: la ventana del pipeline se queda abierta
        # mostrando el error para que el usuario lo lea antes de cerrar.
        print(f"\nERROR: {e}  (ver results/walkforward/walkforward.log)")
        input("Presiona ENTER para cerrar...")
