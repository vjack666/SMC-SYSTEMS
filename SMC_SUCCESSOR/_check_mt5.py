import MetaTrader5 as mt5
if not mt5.initialize():
    print(f"MT5 initialize failed: {mt5.last_error()}")
    raise SystemExit(1)

symbols = mt5.symbols_get()
if symbols:
    forex = [s.name for s in symbols if "Forex" in (s.path or "")]
    print(f"Total forex symbols from path: {len(forex)}")
    for s in sorted(forex)[:20]:
        print(f"  {s}")
    print("...")
    # Also check our target symbols directly
    targets = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]
    for t in targets:
        info = mt5.symbol_info(t)
        print(f"  {t}: {'FOUND' if info else 'NOT FOUND'}")
else:
    print(f"No symbols returned")
    print(f"Total symbols: {mt5.symbols_total()}")
    # Try without path filter
    all_s = mt5.symbols_get()
    if all_s:
        print(f"All symbols ({len(all_s)}):")
        for s in all_s[:10]:
            print(f"  {s.name} path={s.path}")

mt5.shutdown()
