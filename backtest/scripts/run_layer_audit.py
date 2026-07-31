"""Minimal runner for layer_audit: EURUSD M5 HTF + BOS + forensic trace."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.')))

import json
import pandas as pd

from backtest.layers.layer_htf import update_m5_state
from backtest.layers.layer_bos import update_bos
from backtest.layers.layer_choch import update_choch

SYMBOL = 'EURUSD'
IN_PATH = Path('data/raw/EURUSD_M5.parquet')
OUT_DIR = Path('backtest/output')
TRACE_PATH = Path('backtest/evidence/forensic_trace_EURUSD.jsonl')

OUT_DIR.mkdir(parents=True, exist_ok=True)
Path('backtest/evidence').mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(IN_PATH)
if 'time' in df.columns:
    df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
df = df.dropna(subset=['open','high','low','close']).sort_values('time').reset_index(drop=True)
df = df.tail(50000).reset_index(drop=True)
print('rows_chunk', len(df), 'start', df['time'].iloc[0].isoformat(), 'end', df['time'].iloc[-1].isoformat())

state = {
    'symbol': SYMBOL,
    'm5_bars': [],
    'bar_index_m5': -1,
    'timestamp': None,
    'htf_chain': {},
    'entities': {},
    'trace': [],
    'params': {},
    'memory': {'events': []},
}
bos_events = []
choch_count = 0
choch_confirmed = 0
choch_expired = 0
with TRACE_PATH.open('w', encoding='utf-8') as f:
    for i, row in df.iterrows():
        bar = {
            'timestamp': row['time'].to_pydatetime(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 0.0) or 0.0),
        }
        state = update_m5_state(state, bar)
        state = update_bos(state)
        state = update_choch(state)
        if i % 10000 == 0:
            print('bar', i, 'htf', list(state['htf_chain'].keys()), 'bos', len(state.get('entities', {})))
        f.write(json.dumps({
            'bar_index_m5': state['bar_index_m5'],
            'timestamp': bar['timestamp'].isoformat(),
            'layer': 'htf',
            'event': 'htf_built',
            'entity_id': f"htf_{SYMBOL}_{state['bar_index_m5']}",
            'entity_type': 'htf',
            'new_state': 'ALIVE' if state['htf_chain'] else 'PENDING',
            'htf_tfs': ','.join(state['htf_chain'].keys()),
        }, ensure_ascii=False) + '\n')
        for bos in state.get('last_bos_events', []):
            trace_event = {
                'bar_index_m5': state['bar_index_m5'],
                'timestamp': bar['timestamp'].isoformat(),
                'layer': 'bos',
                'event': 'bos_detected',
                'entity_id': bos['bos_id'],
                'entity_type': 'bos',
                'direction': bos['direction'],
                'price': bos['level'],
                'm5_bars_ago': 0,
                'previous_state': None,
                'new_state': 'ACTIVE',
                'reason': f"strength={bos['strength_pct']:.4f}% tf={bos['tf']}",
            }
            f.write(json.dumps(trace_event, ensure_ascii=False) + '\n')
            bos_events.append(trace_event)

        for choch in state.get('last_choch_events', []):
            trace_event = {
                'bar_index_m5': state['bar_index_m5'],
                'timestamp': bar['timestamp'].isoformat(),
                'layer': 'choch',
                'event': 'choch_detected',
                'entity_id': choch['choch_id'],
                'entity_type': 'choch',
                'direction': choch['direction'],
                'price': choch['price'],
                'm5_bars_ago': 0,
                'previous_state': None,
                'new_state': choch['status'],
                'reason': f"invalidated={choch['invalidated_level']} tf={choch['timeframe']}",
            }
            f.write(json.dumps(trace_event, ensure_ascii=False) + '\n')
            choch_count += 1

report = {
    'symbol': SYMBOL,
    'start': df['time'].iloc[0].isoformat(),
    'end': df['time'].iloc[-1].isoformat(),
    'total_bars_m5': int(len(df)),
    'htf_bars_built': {tf: int(state['htf_chain'].get(tf, {}).get('bar_index_m5', -1)) for tf in ['H1','H4','D1']},
    'bos': {
        'total': int(len(bos_events)),
        'bullish': int(sum(1 for e in bos_events if e.get('direction') == 'BULLISH')),
        'bearish': int(sum(1 for e in bos_events if e.get('direction') == 'BEARISH')),
    },
    'choch': {
        'total': int(sum(1 for ent in state.get('entities', {}).values() if ent.get('entity_type') == 'choch')),
        'confirmed': int(sum(1 for ent in state.get('entities', {}).values() if ent.get('entity_type') == 'choch' and ent.get('status') == 'CONFIRMED')),
        'expired': int(sum(1 for ent in state.get('entities', {}).values() if ent.get('entity_type') == 'choch' and ent.get('status') == 'EXPIRED')),
        'pending': int(sum(1 for ent in state.get('entities', {}).values() if ent.get('entity_type') == 'choch' and ent.get('status') == 'PENDING')),
    },
    'trace_path': str(TRACE_PATH),
}
with (OUT_DIR / f'audit_report_{SYMBOL}.json').open('w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print('REPORT', json.dumps(report, ensure_ascii=False, indent=2))
print('BOS_EVENTS', json.dumps(bos_events, ensure_ascii=False, indent=2))
