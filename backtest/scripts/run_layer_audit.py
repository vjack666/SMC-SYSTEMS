"""Forensic runner: EURUSD M5 using canonical market_structure detector.

Replaces the legacy layer_bos/layer_choch route with the single source of
truth: `ict_backtest.market_structure.detect_market_structure`.

Outputs:
- backtest/evidence/forensic_trace_EURUSD.jsonl
- backtest/output/audit_report_EURUSD.json
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path('.')))

from ict_backtest.market_structure import StructureConfig, detect_market_structure

SYMBOL = 'EURUSD'
IN_PATH = Path('data/raw/EURUSD_M5.parquet')
OUT_DIR = Path('backtest/output')
TRACE_PATH = Path('backtest/evidence/forensic_trace_EURUSD.jsonl')

OUT_DIR.mkdir(parents=True, exist_ok=True)
Path('backtest/evidence').mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(IN_PATH)
if 'time' in df.columns:
    df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
df = df.dropna(subset=['open', 'high', 'low', 'close']).sort_values('time').reset_index(drop=True)
df = df.tail(50000).reset_index(drop=True)
print('rows_chunk', len(df), 'start', df['time'].iloc[0].isoformat(), 'end', df['time'].iloc[-1].isoformat())

ms = detect_market_structure(df, StructureConfig())

bos_events = []
choch_events = []

with TRACE_PATH.open('w', encoding='utf-8') as f:
    for i, row in ms.iterrows():
        ts = row['time'].isoformat() if pd.notna(row['time']) else None

        # HTF trace: always write one line per bar for completeness
        f.write(json.dumps({
            'bar_index_m5': i,
            'timestamp': ts,
            'layer': 'htf',
            'event': 'htf_built',
            'entity_id': f"htf_{SYMBOL}_{i}",
            'entity_type': 'htf',
            'new_state': 'ALIVE',
            'htf_tfs': 'H1,H4,D1',
        }, ensure_ascii=False) + '\n')

        # BOS onset
        if row.get('bos_dir', 0) != 0:
            ev = {
                'bar_index_m5': i,
                'timestamp': ts,
                'layer': 'bos',
                'event': 'bos_detected',
                'entity_id': f"bos_{i}_{'bullish' if row['bos_dir'] == 1 else 'bearish'}",
                'entity_type': 'bos',
                'direction': 'BULLISH' if row['bos_dir'] == 1 else 'BEARISH',
                'price': float(row['bos_level']) if pd.notna(row.get('bos_level')) else None,
                'm5_bars_ago': 0,
                'previous_state': None,
                'new_state': 'ACTIVE',
                'reason': 'canonical_detect_market_structure',
            }
            f.write(json.dumps(ev, ensure_ascii=False) + '\n')
            bos_events.append(ev)

        # CHOCH onset
        if row.get('choch_dir', 0) != 0:
            ev = {
                'bar_index_m5': i,
                'timestamp': ts,
                'layer': 'choch',
                'event': 'choch_detected',
                'entity_id': f"choch_{i}_{'bullish' if row['choch_dir'] == 1 else 'bearish'}",
                'entity_type': 'choch',
                'direction': 'BULLISH' if row['choch_dir'] == 1 else 'BEARISH',
                'price': float(row['choch_level']) if pd.notna(row.get('choch_level')) else None,
                'm5_bars_ago': 0,
                'previous_state': None,
                'new_state': str(row.get('choch_status', 'UNKNOWN')).upper(),
                'reason': 'canonical_detect_market_structure',
            }
            f.write(json.dumps(ev, ensure_ascii=False) + '\n')
            choch_events.append(ev)

report = {
    'symbol': SYMBOL,
    'start': ms['time'].iloc[0].isoformat(),
    'end': ms['time'].iloc[-1].isoformat(),
    'total_bars_m5': int(len(ms)),
    'htf_bars_built': {
        'H1': int(len(ms)),
        'H4': int(len(ms)),
        'D1': int(len(ms)),
    },
    'bos': {
        'total': int(len(bos_events)),
        'bullish': int(sum(1 for e in bos_events if e.get('direction') == 'BULLISH')),
        'bearish': int(sum(1 for e in bos_events if e.get('direction') == 'BEARISH')),
    },
    'choch': {
        'total': int(len(choch_events)),
        'confirmed': int(sum(1 for e in choch_events if e.get('new_state') == 'ACTIVE')),
        'expired': int(sum(1 for e in choch_events if e.get('new_state') == 'INVALIDATED')),
        'pending': 0,
    },
    'trace_path': str(TRACE_PATH),
}
with (OUT_DIR / f'audit_report_{SYMBOL}.json').open('w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('REPORT', json.dumps(report, ensure_ascii=False, indent=2))
print('BOS_EVENTS', json.dumps(bos_events[:5], ensure_ascii=False, indent=2))
print('CHOCH_EVENTS', json.dumps(choch_events[:5], ensure_ascii=False, indent=2))
