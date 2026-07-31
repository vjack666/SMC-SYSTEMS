"""Plot últimas 24h de M5 con velas japonesas, márgenes ~5cm lado izquierdo y derecho."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

SYMBOL = 'EURUSD'
IN_PATH = Path('data/raw/EURUSD_M5.parquet')
IMG_PATH = Path('backtest/plots/EURUSD_last24h.png')

def load_last_24h():
    df = pd.read_parquet(IN_PATH)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
    df = df.dropna(subset=['open','high','low','close']).sort_values('time').reset_index(drop=True)
    end = df['time'].iloc[-1]
    start = end - pd.Timedelta(hours=24)
    return df[df['time'] >= start].reset_index(drop=True), end

def plot_candles(df: pd.DataFrame, end_ts):
    fig, ax = plt.subplots(figsize=(12, 5))
    # Submargen izquierdo/derecho ~5 cm en figura de ~12x5 (aprox 2 pulgadas cada lado)
    fig.subplots_adjust(left=0.18, right=0.82)

    for i, row in df.iterrows():
        x = i
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        color = '#26a69a' if c >= o else '#ef5350'
        ax.add_patch(Rectangle((x - 0.35, min(o, c)), 0.7, abs(c - o), color=color, zorder=2))
        ax.plot([x, x], [l, h], color=color, linewidth=1, zorder=1)

    ax.set_xlim(-1, len(df))
    ax.set_xlabel('Velas M5 últimas 24h')
    ax.set_ylabel('Precio')
    ax.set_title(f'{SYMBOL} — últimas 24h M5 — {end_ts:%Y-%m-%d %H:%M} UTC')
    ax.grid(True, alpha=0.25)

    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda i, _: f"+{int(i)}"))
    plt.tight_layout()
    IMG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG_PATH, dpi=150)
    print('SAVED', IMG_PATH)
    plt.show()
    plt.close(fig)

if __name__ == '__main__':
    df, end = load_last_24h()
    print('rows', len(df), 'end', end.isoformat())
    plot_candles(df, end)
