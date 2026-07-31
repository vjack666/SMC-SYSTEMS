"""Interactive plot: last 1 week M5 candles + BOS/CHOCH from forensic trace."""
from pathlib import Path
import pandas as pd
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

SYMBOL = 'EURUSD'
IN_PATH = Path('data/raw/EURUSD_M5.parquet')
HTML_PATH = Path('backtest/plots/EURUSD_last7d_bos.html')
TRACE_PATH = Path('backtest/evidence/forensic_trace_EURUSD.jsonl')


def load_last_week():
    df = pd.read_parquet(IN_PATH)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
    df = df.dropna(subset=['open', 'high', 'low', 'close']).sort_values('time').reset_index(drop=True)
    end = df['time'].iloc[-1]
    start = end - pd.Timedelta(days=7)
    return df[df['time'] >= start].reset_index(drop=True), end, start


def build_figure(df: pd.DataFrame, end_ts, start_ts):
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True, vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='EURUSD M5',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
        whiskerwidth=0.8,
        line_width=1,
    ), row=1, col=1)

    if not TRACE_PATH.exists():
        return fig

    events = {'bos': [], 'choch': []}
    with TRACE_PATH.open('r', encoding='utf-8') as f:
        for line in f:
            ev = json.loads(line)
            layer = ev.get('layer')
            if layer in events and ev.get('event') == f'{layer}_detected':
                events[layer].append(ev)

    def add_levels(ev_list, prefix, color_map, dash_map, marker_map):
        seen = {}
        for ev in ev_list:
            price = ev.get('price')
            if price is None:
                continue
            ts = pd.Timestamp(ev['timestamp'])
            if ts < start_ts or ts > end_ts:
                continue
            direction = ev['direction']
            key = (direction, round(float(price), 5))
            if key in seen:
                continue
            seen[key] = True
            # Horizontal line from chart start to event point
            fig.add_trace(go.Scatter(
                x=[start_ts, ts],
                y=[float(price), float(price)],
                mode='lines+markers',
                name=f'{prefix} {direction}',
                line=dict(color=color_map[direction], width=1.5, dash=dash_map[direction]),
                marker=dict(symbol=marker_map[direction], size=10, color=color_map[direction], line=dict(width=1, color='black')),
                legendgroup=f'{prefix}-{direction}',
                showlegend=False,
                hoverinfo='text',
                hovertext=f'{prefix} {direction}<br>{price:.5f}<br>{ts.isoformat()}',
            ), row=1, col=1)

    # One legend item per direction per type
    bos_colors = {'BULLISH': '#26a69a', 'BEARISH': '#ef5350'}
    bos_dash = {'BULLISH': 'dash', 'BEARISH': 'dash'}
    bos_marker = {'BULLISH': 'triangle-up', 'BEARISH': 'triangle-down'}
    choch_colors = {'BULLISH': '#ffca28', 'BEARISH': '#ab47bc'}
    choch_dash = {'BULLISH': 'dot', 'BEARISH': 'dot'}
    choch_marker = {'BULLISH': 'diamond', 'BEARISH': 'square'}

    add_levels(events['bos'], 'BOS', bos_colors, bos_dash, bos_marker)
    add_levels(events['choch'], 'CHOCH', choch_colors, choch_dash, choch_marker)

    # Manual legend entries
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines+markers', name='BOS Alcista',
                             line=dict(color=bos_colors['BULLISH'], dash='dash'), marker=dict(symbol='triangle-up', size=10, color=bos_colors['BULLISH'])), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines+markers', name='BOS Bajista',
                             line=dict(color=bos_colors['BEARISH'], dash='dash'), marker=dict(symbol='triangle-down', size=10, color=bos_colors['BEARISH'])), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines+markers', name='CHOCH Alcista',
                             line=dict(color=choch_colors['BULLISH'], dash='dot'), marker=dict(symbol='diamond', size=10, color=choch_colors['BULLISH'])), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines+markers', name='CHOCH Bajista',
                             line=dict(color=choch_colors['BEARISH'], dash='dot'), marker=dict(symbol='square', size=10, color=choch_colors['BEARISH'])), row=1, col=1)

    fig.update_layout(
        title=dict(text=f'{SYMBOL} — últimas 7 días M5 con BOS/CHOCH — {end_ts:%Y-%m-%d %H:%M} UTC', x=0.5),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5, font=dict(size=10)),
        dragmode='pan',
        hovermode='x unified',
        height=700,
        margin=dict(l=60, r=60, t=80, b=40),
    )
    fig.update_xaxes(title_text='Tiempo', row=1, col=1)
    fig.update_yaxes(title_text='Precio', row=1, col=1)
    return fig


def main():
    df, end, start = load_last_week()
    print('rows', len(df), 'start', start.isoformat(), 'end', end.isoformat())
    fig = build_figure(df, end, start)
    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(HTML_PATH), auto_open=True)
    print('SAVED', HTML_PATH)


if __name__ == '__main__':
    main()
