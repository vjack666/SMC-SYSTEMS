"""Diagnostico MT5: muestra si initialize/terminal_info/account_info funcionan.
No descarga nada. Usa la misma ruta que los .bat via env SMC_MT5_TERMINAL.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from data.mt5.connector import ConnectionConfig, MT5Connector

path = os.environ.get("SMC_MT5_TERMINAL")
print("SMC_MT5_TERMINAL =", path)
print("existe el exe:", os.path.exists(path) if path else "NO SETEADO")

import MetaTrader5 as mt5
print("MT5 pkg version:", mt5.__version__ if hasattr(mt5, '__version__') else '?')

cfg = ConnectionConfig(path=path, timeout=15000)
try:
    ok = mt5.initialize(**({"path": path} if path else {}))
    print("initialize() ->", ok)
    if not ok:
        print("last_error:", mt5.last_error())
    else:
        ti = mt5.terminal_info()
        print("terminal_info() is None:", ti is None)
        if ti is not None:
            print("  terminal name:", ti.name)
            print("  connected:", ti.connected)
        ai = mt5.account_info()
        print("account_info() is None:", ai is None)
        if ai is not None:
            print("  login:", ai.login, "server:", ai.server, "balance:", ai.balance)
        # probar symbol
        for s in ["GBPUSD","USDCHF","USDJPY"]:
            si = mt5.symbol_info(s)
            print(f"  symbol {s}: {'OK' if si else 'None (no visible/select)'}")
            if si is not None:
                print(f"    visible={si.visible} trade_mode={si.trade_mode}")
except Exception as e:
    import traceback
    print("EXCEPCION:", repr(e))
    traceback.print_exc()
finally:
    try:
        mt5.shutdown()
    except Exception:
        pass
