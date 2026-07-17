"""Solo CONSULTA: profundidad M5 historica real que entrega MT5 (MetaQuotes-Demo).

El broker rechaza rangos > ~30 dias (-2 Invalid params). Estrategia: ventanas de
30 dias deslizandose hacia atras, acumulando tuplas (forma nativa de copy_rates)
hasta que un bloque no aporte velas anteriores a las ya obtenidas. No escribe parquet.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import MetaTrader5 as mt5

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "XAUUSD"]
STEP = 30  # dias (maximo que acepta el broker por llamada)
# Indices del structured array devuelto por copy_rates: 0=time,1=open,2=high,3=low,4=close


def main() -> int:
    if not mt5.initialize():
        print(f"[!] init fallo: {mt5.last_error()}")
        return 3
    acc = mt5.account_info()
    print(f"[*] Cuenta {acc.login} server={acc.server}\n")

    for sym in SYMBOLS:
        if mt5.symbol_info(sym) is None:
            print(f"  {sym}: NOT FOUND")
            continue
        today = datetime.now()
        end = today
        rates: list = []  # acumulado ascendente por time (tuplas)
        empty_streak = 0
        guard = 0
        while guard < 220:  # tope ~220*30d = 18 anios
            guard += 1
            start = end - timedelta(days=STEP)
            block = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, start, end)
            if block is None or len(block) == 0:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                end = start
                continue
            empty_streak = 0
            block = list(block)
            if rates:
                min_have = rates[0][0]  # time de la primera ya tenida
                block = [x for x in block if x[0] < min_have]
            if len(block) == 0:
                break
            rates = block + rates
            first_ts = rates[0][0]
            if datetime.fromtimestamp(first_ts) > start + timedelta(days=1):
                break  # el bloque no llega hasta 'start' => fondo alcanzado
            end = start
        n = len(rates)
        first = datetime.fromtimestamp(rates[0][0]) if n else None
        last = datetime.fromtimestamp(rates[-1][0]) if n else None
        years = (last - first).days / 365.25 if (n and first and last) else 0
        print(f"  {sym}: M5 velas={n}  desde={first.date() if first else None} "
              f"hasta={last.date() if last else None}  (~{years:.2f} anios)")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
