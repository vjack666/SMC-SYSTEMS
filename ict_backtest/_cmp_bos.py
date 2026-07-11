"""Compara detectores viejos (detectors/) vs nuevo (market_structure) en XAUUSD H4."""
from ict_backtest.data_feed import load_frames
from detectors import detect_bos as old_bos, detect_choch as old_choch
from ict_backtest.market_structure import detect_market_structure

fr = load_frames("XAUUSD", ("H4",))
df = fr["H4"]

# Viejo
ob = old_bos(df)
oc = old_choch(df)
old_bos_active = int((ob["bos_status"] == "active").sum())
old_choch_any = int((oc["choch_signal"] != "NONE").sum())
old_choch_bull = int((oc["choch_signal"] == "CHOCH_BULLISH").sum())
old_choch_bear = int((oc["choch_signal"] == "CHOCH_BEARISH").sum())

# Nuevo
nm = detect_market_structure(df)
new_bos_active = int((nm["bos_status"] == "active").sum())
new_choch_any = int((nm["choch_dir"] != 0).sum())
new_choch_bull = int((nm["choch_dir"] == 1).sum())
new_choch_bear = int((nm["choch_dir"] == -1).sum())

n = len(df)
print(f"Velas H4: {n}")
print(f"{'':28} VIEJO      NUEVO")
print(f"{'BOS activos':28} {old_bos_active:6}   {new_bos_active:6}")
print(f"{'CHOCH total':28} {old_choch_any:6}   {new_choch_any:6}")
print(f"{'  CHOCH bull':28} {old_choch_bull:6}   {new_choch_bull:6}")
print(f"{'  CHOCH bear':28} {old_choch_bear:6}   {new_choch_bear:6}")
print(f"{'CHOCH por 1000 velas':28} {1000*old_choch_any/n:6.1f}  {1000*new_choch_any/n:6.1f}")
