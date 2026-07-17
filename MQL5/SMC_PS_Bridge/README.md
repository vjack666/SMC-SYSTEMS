# SMC_PS_Bridge — Observador → Position Sizer

Loads Entry / SL / TP from the desktop observador into **EarnForex Position Sizer** chart lines.

**Does not open trades.** Position Sizer remains a risk calculator; you decide if/when to press Trade.

## One-time setup (MT5 FundedNext)

1. Copy `SMC_PS_Bridge.mq5` into:
   ```
   %APPDATA%\MetaQuotes\Terminal\<TERMINAL_ID>\MQL5\Experts\SMC_PS_Bridge\
   ```
   (or open the file from this repo folder in MetaEditor).
2. Open **MetaEditor** → compile `SMC_PS_Bridge.mq5` (F7). You need the `.ex5`.
3. On the **same chart** as the symbol you trade (e.g. EURUSD):
   - Attach **Position Sizer** (Experts → Position Sizer).
   - Attach **SMC_PS_Bridge**.
4. Allow algo trading / live trading only if you plan to use PS Trade yourself later; the bridge never calls `OrderSend`.

## App usage

1. Run the observador until Lab Setup shows Entry / SL / TP numbers.
2. Click **Enviar a Position Sizer** (or **Colocar orden (solo sizer)**).
3. Confirm the dialog — this writes:
   ```
   %APPDATA%\MetaQuotes\Terminal\Common\Files\SMC\ps_levels.csv
   ```
4. Within ~0.5 s the bridge EA moves `PS_EntryLine`, `PS_StopLossLine`, `PS_TakeProfitLine`.
5. Check lot size / risk % in Position Sizer. Adjust risk there. **Do not** treat this as auto-entry.

## File format (`ps_levels.csv`)

```
schema,smc_ps_levels_v1
seq,1710000000
ts_utc,2026-07-16T12:00:00Z
symbol,EURUSD
side,SHORT
entry,1.14645
sl,1.14747
tp,1.14603
rr,0.42
risk_pct,1.0
valid_rr,0
source,smc_observador
auto_trade,0
```

If `auto_trade` is ever non-zero, the EA **refuses** the handoff.

## Safety

| Action | Who |
|--------|-----|
| Calculate Entry/SL/TP | Observador |
| Size position (risk %) | Position Sizer |
| Open order | **You** (PS Trade button) or never |

Observador mode stays: **no bot orders from Python**.
