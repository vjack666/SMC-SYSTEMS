"""market_replay/api — CLI de inspección de lectura del motor.

Uso:
    python -m market_replay.api --symbol EURUSD --ltf M15 --limit 200

Arranca el motor con OHLC crudo (desde disco vía engine.data_feed) y observa
exactamente qué lee, vela a vela, sin ejecutar órdenes ni importar ict_backtest.

Es la respuesta a la condición del Director:
  "¿Si mañana borramos ict_backtest/, puedo arrancar el motor, alimentarlo
   con OHLC y observar exactamente qué está leyendo?"
"""

from __future__ import annotations

import argparse
import json
import sys

from engine.data_feed import load_frames
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay


def run_cli(symbol: str, ltf: str, limit: int, max_hold: int = 0) -> int:
    tfs = ("D1", "H4", "H1", "M15", "M5", "M1")
    frames = load_frames(symbol, tfs)
    if ltf not in frames:
        print(f"[market_replay] {symbol} {ltf} no disponible en disco", file=sys.stderr)
        return 2

    df = frames[ltf]
    if limit and len(df) > limit:
        # Recorta por el FINAL (lo más reciente) para inspección rápida.
        df = df.iloc[-limit:].reset_index(drop=True)
        # Recorta HTF al mismo rango aproximado.
        last = df["time"].iloc[-1]
        for tf in frames:
            if tf != ltf:
                f = frames[tf]
                frames[tf] = f[f["time"] <= last].reset_index(drop=True)

    feed = MarketFeed()
    for tf, f in frames.items():
        feed.ingest(tf, f)

    rp = MarketReplay(feed, ltf=ltf)
    res = rp.run()

    print(f"[market_replay] {symbol} {ltf}: {res.steps} pasos, "
          f"{len(res.journal)} eventos de lectura")
    print("--- journal causal (qué sabía el motor en cada instante) ---")
    for e in res.journal:
        d = e.to_dict()
        print(json.dumps(d, default=str))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="market_replay", description="Inspector de lectura del motor")
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--ltf", default="M15")
    p.add_argument("--limit", type=int, default=200)
    args = p.parse_args(argv)
    return run_cli(args.symbol, args.ltf, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
