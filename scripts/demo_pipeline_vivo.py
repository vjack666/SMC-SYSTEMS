"""Demo de pipeline vivo (data real EURUSD, NO backtest de PF).

Usa evaluate_signals (el cerebro unico R7) sobre EURUSD M15 real recortado,
y por cada senal real aplica el cableado recien hecho:
  - RR por setup -> TP real (canonical ya lo resuelve via _rr_for_raw_signal)
  - E1 apply_trade_management sobre la serie post-entry real (M15)
Solo muestra; no itera metricas agregadas (eso es backtest de PF, bloqueado).
"""
import warnings
import time
import pandas as pd
warnings.filterwarnings("ignore")

from ict_backtest.data_feed import load_frames
from ict_backtest.canonical import evaluate_signals
from ict_backtest.trade_mgmt import apply_trade_management

# Data real EURUSD M15 (recortada para velocidad del contexto HTF por barra).
frames = load_frames("EURUSD", ("M15",))
m15 = frames["M15"].iloc[-2000:].reset_index(drop=True)
frames["M15"] = m15

t0 = time.time()
sig = evaluate_signals("EURUSD", "H4", "M15", frames=frames, enable_pd_index=False)
elapsed = round(time.time() - t0, 2)
print(f"evaluate_signals: {len(sig) if sig else 0} senales en {elapsed}s (M15 real {len(m15)} velas)")

if not sig:
    print("OK: pipeline corre sobre data real sin error; esta ventana no emitio senales.")
else:
    shown = 0
    for s in sig[:12]:
        rr = getattr(s, "rr_target", None)
        direction = s.direction
        entry = s.entry
        sl = s.stop_loss
        tp = s.take_profit
        post = m15.iloc[s.entry_at:] if s.entry_at is not None else m15
        res = apply_trade_management(entry, sl, tp, direction, post,
                                     partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0)
        sett = ("SB" if getattr(s, "sb_confirmed", False)
                else "Turtle" if getattr(s, "turtle_confirmed", False)
                else "OTE" if getattr(s, "ote_confirmed", False)
                else "none")
        shown += 1
        print(f"  dir={direction:+d} rr={rr} setup={sett:6s} entry={entry:.4f} sl={sl:.4f} "
              f"tp={tp:.4f} -> E1={res['exit_reason']:7s} pnlR={res['pnl_r']:+.2f}")
    print(f"senales mostradas: {shown} (de {len(sig)})")
    print("OK: cableado RR->TP y E1->simulador funcionan sobre data real EURUSD (no backtest PF).")
