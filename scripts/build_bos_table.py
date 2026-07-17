"""scripts/build_bos_table.py

Genera ``ict_backtest/bos_table.json`` (R10 dinamico) desde datos historicos
del repo. SIN indicadores: solo high-low del market structure.

Pipeline (reusa logica pura de ict_backtest.bos_table_builder):
  1. Por cada (symbol, M15) disponible en data/raw:
     load_frames -> detect_market_structure (inyecta bos_dir/bos_level)
  2. extract_bos_events + measure_mitigation (anti-sesgo supervivencia)
  3. Acumula N_real por bucket de fuerza (1..5, formula del motor)
  4. Mediana por bucket -> bos_table.json

Uso:
  python scripts/build_bos_table.py [--symbols EURUSD GBPUSD ...] [--out ict_backtest/bos_table.json]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ict_backtest.bos_table_builder import build_bos_table  # noqa: E402
from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.market_structure import detect_market_structure  # noqa: E402

DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "NZDUSD", "AUDUSD"]
LTF = "M15"


def build_for_symbol(symbol: str, out_path: Path) -> dict:
    frames = load_frames(symbol, (LTF,))
    ltf = detect_market_structure(frames[LTF])
    return build_bos_table(ltf, tf=LTF)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build empirical bos_table.json (R10 dynamic)")
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS,
                    help="symbolos M15 a usar (default: todos los disponibles)")
    ap.add_argument("--out", default=str(ROOT / "ict_backtest" / "bos_table.json"),
                    help="ruta de salida del JSON")
    args = ap.parse_args()

    out_path = Path(args.out)
    merged: dict[int, list[int]] = {}

    for sym in args.symbols:
        try:
            frames = load_frames(sym, (LTF,))
        except Exception as e:  # símbolo sin datos -> skip
            print(f"[skip] {sym}: {e}")
            continue
        ltf = detect_market_structure(frames[LTF])
        table = build_bos_table(ltf, tf=LTF)
        if not table:
            print(f"[warn] {sym}: sin eventos BOS suficientes")
            continue
        for bucket, n_real in table.items():
            merged.setdefault(bucket, []).append(n_real)
        print(f"[ok] {sym}: buckets={{ {', '.join(f'{k}:{v}' for k,v in sorted(table.items()))} }}")

    if not merged:
        print("[error] ningun simbolo produjo eventos BOS")
        return 1

    # Mediana final por bucket (agrega todas las muestras de todos los simbolos)
    final = {b: int(round(sum(v) / len(v))) for b, v in sorted(merged.items())}
    out_path.write_text(json.dumps(final, indent=2), encoding="utf-8")
    print(f"[done] bos_table -> {out_path} : {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
