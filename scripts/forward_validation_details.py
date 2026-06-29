"""
Complement to Forward Validation:
Genera detalles adicionales: event timeline, detailed metrics, gráficas.
"""
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import numpy as np

DATA_DIR = Path("results/forward_validation")
RESULTS_DIR = Path("results")
OUT = DATA_DIR

sns.set_theme(style="darkgrid", palette="muted", font_scale=0.9)
plt.rcParams.update({"figure.dpi": 120, "figure.figsize": (12, 6)})

# Load data
df_all = pd.read_csv(RESULTS_DIR / "experiment_E.csv", parse_dates=["exit_time", "entry_time", "create_time"])
df_forward = pd.read_csv(OUT / "forward_signals.csv", parse_dates=["exit_time", "entry_time", "create_time"])

# EVENT TIMELINE
events = []
for _, row in df_forward.iterrows():
    setup_id = str(row.get("setup_id", f"trade_{len(events)}"))
    create_time = pd.to_datetime(row.get("create_time", row.get("entry_time")))
    entry_time = pd.to_datetime(row.get("entry_time"))
    exit_time = pd.to_datetime(row.get("exit_time"))
    
    events.extend([
        {
            "event_id": f"{setup_id}_1",
            "timestamp": create_time,
            "symbol": row.get("symbol", "UNKNOWN"),
            "state_from": "IDLE",
            "state_to": "FVG_CREATED",
            "reason": f"FVG direction={row.get('side', '?')}",
        },
        {
            "event_id": f"{setup_id}_2",
            "timestamp": entry_time,
            "symbol": row.get("symbol", "UNKNOWN"),
            "state_from": "FVG_CREATED",
            "state_to": "TRADE_OPEN",
            "reason": f"Entry price={row.get('entry_price', 0):.5f}, ML score={row.get('ml_confidence', 0):.3f}",
        },
        {
            "event_id": f"{setup_id}_3",
            "timestamp": exit_time,
            "symbol": row.get("symbol", "UNKNOWN"),
            "state_from": "TRADE_OPEN",
            "state_to": "TP_HIT" if row.get("pnl_r", 0) > 0 else "SL_HIT",
            "reason": f"PnL={row.get('pnl_r', 0):.3f}R, Exit={row.get('exit_price', 0):.5f}",
        },
    ])

df_events = pd.DataFrame(events)
df_events = df_events.sort_values("timestamp").reset_index(drop=True)
df_events.to_csv(OUT / "forward_event_timeline.csv", index=False)
print(f"Event timeline: {len(df_events)} events saved")

# FORWARD METRICS DETAILED
total_trades = len(df_forward)
wins = (df_forward["pnl_r"] > 0).sum()
losses = (df_forward["pnl_r"] < 0).sum()
avg_win = df_forward[df_forward["pnl_r"] > 0]["pnl_r"].mean() if wins > 0 else 0
avg_loss = abs(df_forward[df_forward["pnl_r"] < 0]["pnl_r"].mean()) if losses > 0 else 0
pnl_total = df_forward["pnl_r"].sum()
expectancy = pnl_total / total_trades if total_trades > 0 else 0
pf = (wins * avg_win) / (losses * avg_loss) if losses > 0 and avg_loss > 0 else 1.0
cumsum = df_forward["pnl_r"].cumsum()
peak = cumsum.cummax()
dd = peak - cumsum
max_dd = dd.max()
sharpe_daily = df_forward.groupby(df_forward["exit_time"].dt.floor("D"))["pnl_r"].sum()
sharpe = sharpe_daily.mean() / sharpe_daily.std() * np.sqrt(252) if len(sharpe_daily) > 1 else 0

metrics_forward = pd.DataFrame([{
    "total_trades": total_trades,
    "winrate": wins / total_trades if total_trades > 0 else 0,
    "profit_factor": pf,
    "expectancy": expectancy,
    "avg_win": avg_win,
    "avg_loss": avg_loss,
    "max_drawdown": max_dd,
    "sharpe": sharpe,
    "calmar": sharpe_daily.mean() / (max_dd + 1e-6) if max_dd > 0 else 0,
    "equity_final": cumsum.iloc[-1] if len(cumsum) > 0 else 0,
}])
metrics_forward.to_csv(OUT / "forward_metrics.csv", index=False)
print(f"Forward metrics saved")

# COMPARISON CHARTS
fig, axs = plt.subplots(2, 2, figsize=(14, 10))

# Equity curve
cumsum.plot(ax=axs[0, 0], label="Forward OOS", color="green", linewidth=2)
axs[0, 0].fill_between(range(len(cumsum)), cumsum, cumsum.cummax(), color="red", alpha=0.2)
axs[0, 0].set_title("Equity Curve (Forward OOS)")
axs[0, 0].set_ylabel("Cumulative PnL (R)")
axs[0, 0].legend()
axs[0, 0].grid()

# Drawdown
dd.plot(ax=axs[0, 1], color="red", linewidth=1.5)
axs[0, 1].set_title("Drawdown Timeline")
axs[0, 1].set_ylabel("Drawdown (R)")
axs[0, 1].grid()

# Win/Loss Distribution
sizes = [wins, losses]
colors = ["green", "red"]
axs[1, 0].pie(sizes, labels=["Wins", "Losses"], colors=colors, autopct="%1.1f%%", startangle=90)
axs[1, 0].set_title(f"Win/Loss Distribution (n={total_trades})")

# PnL by Symbol
df_forward.boxplot(column="pnl_r", by="symbol", ax=axs[1, 1])
axs[1, 1].set_title("PnL Distribution by Symbol")
axs[1, 1].set_ylabel("PnL (R)")
plt.setp(axs[1, 1].xaxis.get_majorticklabels(), rotation=0)

fig.tight_layout()
fig.savefig(OUT / "forward_validation_charts.png", dpi=120, bbox_inches="tight")
plt.close()
print("Forward validation charts saved")

# PER-TRADE DETAIL
available_cols = [c for c in [
    "symbol", "side", "entry_time", "exit_time", "pnl_r", "pnl_usd", 
    "ml_confidence", "session_bucket", "bars_since_fvg_creation", 
    "mitigation_depth_pct", "sl_atr_mult", "holding_bars"
] if c in df_forward.columns]
trades_detail = df_forward[available_cols].copy()
trades_detail.to_csv(OUT / "forward_trades_detail.csv", index=False)
print(f"Trades detail exported")

print("\n=== FORWARD VALIDATION DETAILS COMPLETE ===")
print(f"Files generated in {OUT}:")
print(f"  - forward_event_timeline.csv")
print(f"  - forward_metrics.csv")
print(f"  - forward_trades_detail.csv")
print(f"  - forward_validation_charts.png")
