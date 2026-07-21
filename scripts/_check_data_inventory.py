"""Quick inventory of data/raw parquet files — rows, date range, coverage."""
import glob, os
import pandas as pd

SYMBOLS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","USDCHF","XAUUSD"]
TFS     = ["D1","H4","H1","M15","M5","M1"]

files = sorted(glob.glob("data/raw/*.parquet"))
print(f"Total parquet files on disk: {len(files)}\n")
print(f"{'File':<30} {'Rows':>8}   {'Start':>12}   {'End':>12}   {'MB':>6}")
print("-" * 78)

inventory = {}
for f in files:
    name = os.path.basename(f)
    df = pd.read_parquet(f)
    rows = len(df)
    start = str(df.index[0])[:10] if rows > 0 else "N/A"
    end = str(df.index[-1])[:10] if rows > 0 else "N/A"
    size_mb = os.path.getsize(f) / (1024 * 1024)
    print(f"{name:<30} {rows:>8,}   {start:>12}   {end:>12}   {size_mb:>6.2f}")

    # parse symbol and tf
    base = name.replace(".parquet", "")
    parts = base.rsplit("_", 1)
    if len(parts) == 2:
        sym, tf = parts
        inventory[(sym, tf)] = {"rows": rows, "start": start, "end": end}

print("\n\n=== COVERAGE MATRIX ===\n")
header = f"{'Symbol':<10}" + "".join(f"{tf:>8}" for tf in TFS)
print(header)
print("-" * (10 + 8 * len(TFS)))
for sym in SYMBOLS:
    row = f"{sym:<10}"
    for tf in TFS:
        info = inventory.get((sym, tf))
        if info:
            row += f"{info['rows']:>8,}"
        else:
            row += f"{'---':>8}"
    print(row)

# What the engine needs
print("\n\n=== ENGINE REQUIREMENTS ===")
print("canonical.evaluate_signals() loads 6 TFs: D1, H4, H1, M15, M5, M1")
print("v2 strategy_mtf needs: D1, H4, H1, M15")
print("test_multitf_context expects: D1, H4, H1, M15, M5, M1")
print()

for sym in SYMBOLS:
    missing = []
    for tf in ["D1","H4","H1","M15","M5","M1"]:
        if (sym, tf) not in inventory:
            missing.append(tf)
    if missing:
        print(f"  {sym}: MISSING {', '.join(missing)}")
    else:
        print(f"  {sym}: ALL 6 TFs present")
