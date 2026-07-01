from __future__ import annotations

from pathlib import Path

import pandas as pd

from strategy.scalping_setup import ScalpingConfig, build_scalping_context

DATA_DIR = Path("data/mt5")
TMP_DIR = Path("data/tmp_debug")
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Pre-truncate to 10000 bars for speed
N = 10000
for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    for tf, n in [("M15", N), ("H4", 3000), ("D1", 1500)]:
        src = DATA_DIR / f"{symbol}_{tf}.parquet"
        df = pd.read_parquet(src)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df.tail(n).reset_index(drop=True).to_parquet(TMP_DIR / f"{symbol}_{tf}.parquet", compression="zstd")

# Debug: Check each symbol at which filter stage signals die
print(f"Data truncated to {N} bars.\n", flush=True)

for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
    print(f"\n{'='*60}", flush=True)
    print(f"SYMBOL: {symbol}", flush=True)
    print(f"{'='*60}", flush=True)

    ctx = build_scalping_context(
        symbol=symbol,
        data_dir=TMP_DIR,
        config=ScalpingConfig(
            use_wyckoff=True,
            use_stochastic_exhaustion=True,
            use_pac=True,
            use_structural_sl=True,
        ),
    )

    total = len(ctx)
    macro_counts = ctx["macro_direction"].value_counts()
    print(f"\nTotal bars: {total}", flush=True)
    print(f"Macro direction: {macro_counts.to_dict()}", flush=True)

    for f in ["filter_trend", "filter_session", "filter_atr", "filter_bos",
              "filter_ob_fvg", "filter_choch", "filter_swing",
              "filter_exhaustion", "filter_wyckoff"]:
        if f in ctx.columns:
            pct = ctx[f].mean() * 100
            print(f"  {f:<25} {ctx[f].sum():>6d} / {total} ({pct:>5.1f}%)", flush=True)

    print(f"\nConfluence score distribution:", flush=True)
    if "confluence_score" in ctx.columns:
        print(ctx["confluence_score"].value_counts().sort_index().to_dict(), flush=True)

    for direction, label in [(1, "BULLISH (LONG)"), (-1, "BEARISH (SHORT)")]:
        dir_name = "BULLISH" if direction == 1 else "BEARISH"
        dir_bars = ctx[ctx["macro_direction"] == dir_name]
        if len(dir_bars) == 0:
            print(f"\n  {label}: 0 bars with macro_direction={dir_name}", flush=True)
            continue

        pac_ready = dir_bars["pac_entry_ready"].sum() if "pac_entry_ready" in dir_bars.columns else 0
        pac_ready_pct = pac_ready / len(dir_bars) * 100 if len(dir_bars) > 0 else 0
        signal = (ctx["signal_direction"] == direction).sum()

        print(f"\n  {label}: {len(dir_bars)} bars", flush=True)
        print(f"    PAC entry ready:  {pac_ready:>4d} / {len(dir_bars)} ({pac_ready_pct:.1f}%)", flush=True)
        print(f"    signal_direction: {signal:>4d} bars", flush=True)

        if direction == -1:
            if "wyckoff_phase" in ctx.columns:
                phases = dir_bars["wyckoff_phase"].value_counts().to_dict()
                print(f"    Wyckoff phases: {phases}", flush=True)
            if "pac_entry_ready" in ctx.columns:
                non_pac = dir_bars[~dir_bars["pac_entry_ready"]]
                if len(non_pac) > 0:
                    if "pac_exhaustion_confirmed" in non_pac.columns:
                        no_exh = (~non_pac["pac_exhaustion_confirmed"]).sum()
                        print(f"    NOT PAC ready: {len(non_pac)} (exhaustion not confirmed: {no_exh})", flush=True)
                    if "pac_invalidation" in non_pac.columns:
                        inv = non_pac["pac_invalidation"].value_counts().to_dict()
                        if any(v > 0 for v in inv.values()):
                            print(f"    Invalidation causes: {inv}", flush=True)

    print(f"\n  Signal confidence by direction:", flush=True)
    if "signal_confidence" in ctx.columns:
        for dn in ["BULLISH", "BEARISH"]:
            vals = ctx[ctx["macro_direction"] == dn]["signal_confidence"]
            if len(vals) > 0:
                print(f"    {dn}: mean={vals.mean():.4f} min={vals.min():.4f} max={vals.max():.4f}", flush=True)
