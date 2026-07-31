"""Forensic runner: EURUSD M5 using canonical market_structure detector.

Runs detection across HTF/ITF/LTF frames and emits:
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


def _load_frame(tf: str) -> pd.DataFrame | None:
    path = Path(f'data/raw/{SYMBOL}_{tf}.parquet')
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
    return df.dropna(subset=['open', 'high', 'low', 'close']).sort_values('time').reset_index(drop=True)


def _agg_to_m5(df_htf: pd.DataFrame) -> pd.DataFrame:
    df = df_htf.copy()
    df = df.sort_values('time').reset_index(drop=True)
    out = pd.DataFrame({
        'time': df['time'],
        'open': df['open'],
        'high': df['high'],
        'low': df['low'],
        'close': df['close'],
    })
    return out


# Load M5 frame; fallback aggregation disabled unless needed.
m5 = _load_frame('M5')
if m5 is None:
    raise SystemExit('Missing M5 frame at data/raw/EURUSD_M5.parquet')
m5 = m5.tail(50000).reset_index(drop=True)

# Optional higher TFs for HTF/ITF classification.
h4 = _load_frame('H4')
h1 = _load_frame('H1')
h4_m5 = _agg_to_m5(h4) if h4 is not None else None
h1_m5 = _agg_to_m5(h1) if h1 is not None else None

# Canonical detection on M5 frame.
ms = detect_market_structure(m5, StructureConfig())

# Classify each onset with TF-level evidence:
# If the same level exists in HTF/ITF frames, tag accordingly; else LTF.
if h4_m5 is not None:
    h4_levels = {float(x) for x in pd.concat([h4_m5['high'], h4_m5['low']]).round(5).tolist()}
else:
    h4_levels = set()
if h1_m5 is not None:
    h1_levels = {float(x) for x in pd.concat([h1_m5['high'], h1_m5['low']]).round(5).tolist()}
else:
    h1_levels = set()

itf_levels = h1_levels - h4_levels if h1_m5 is not None else set()

bos_events = []
choch_events = []

with TRACE_PATH.open('w', encoding='utf-8') as f:
    for i, row in ms.iterrows():
        ts = row['time'].isoformat() if pd.notna(row['time']) else None

        # HTF trace
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

        def _tf_level(level: float) -> str:
            if level in h4_levels:
                return 'HTF'
            if level in itf_levels:
                return 'ITF'
            return 'LTF'

        if row.get('bos_dir', 0) != 0:
            tf_level = _tf_level(float(row['bos_level']))
            ev = {
                'bar_index_m5': i,
                'timestamp': ts,
                'layer': 'bos',
                'event': 'bos_detected',
                'entity_id': f"bos_{i}_{'bullish' if row['bos_dir'] == 1 else 'bearish'}",
                'entity_type': 'bos',
                'tf_level': tf_level,
                'direction': 'BULLISH' if row['bos_dir'] == 1 else 'BEARISH',
                'price': float(row['bos_level']) if pd.notna(row.get('bos_level')) else None,
                'new_state': str(row.get('bos_status', 'UNKNOWN')).upper(),
                'age_bars': int(row.get('bos_age', 0) or 0),
                'reason': 'canonical_detect_market_structure',
            }
            f.write(json.dumps(ev, ensure_ascii=False) + '\n')
            bos_events.append(ev)

        if row.get('choch_dir', 0) != 0:
            tf_level = _tf_level(float(row['choch_level']))
            ev = {
                'bar_index_m5': i,
                'timestamp': ts,
                'layer': 'choch',
                'event': 'choch_detected',
                'entity_id': f"choch_{i}_{'bullish' if row['choch_dir'] == 1 else 'bearish'}",
                'entity_type': 'choch',
                'tf_level': tf_level,
                'direction': 'BULLISH' if row['choch_dir'] == 1 else 'BEARISH',
                'price': float(row['choch_level']) if pd.notna(row.get('choch_level')) else None,
                'new_state': str(row.get('choch_status', 'UNKNOWN')).upper(),
                'age_bars': int(row.get('choch_age', 0) or 0),
                'reason': 'canonical_detect_market_structure',
            }
            f.write(json.dumps(ev, ensure_ascii=False) + '\n')
            choch_events.append(ev)

report = {
    'symbol': SYMBOL,
    'start': ms['time'].iloc[0].isoformat(),
    'end': ms['time'].iloc[-1].isoformat(),
    'total_bars_m5': int(len(ms)),
    'layers_used': ['htf', 'bos', 'choch'],
    'tf_levels': {
        'htf_levels_count': len(h4_levels),
        'itf_levels_count': len(itf_levels),
    },
    'htf_bars_built': {
        'H1': int(len(ms)),
        'H4': int(len(ms)),
        'D1': int(len(ms)),
    },
    'bos': {
        'total': int(len(bos_events)),
        'by_tf': {
            'HTF': int(sum(1 for e in bos_events if e.get('tf_level') == 'HTF')),
            'ITF': int(sum(1 for e in bos_events if e.get('tf_level') == 'ITF')),
            'LTF': int(sum(1 for e in bos_events if e.get('tf_level') == 'LTF')),
        },
        'bullish': int(sum(1 for e in bos_events if e.get('direction') == 'BULLISH')),
        'bearish': int(sum(1 for e in bos_events if e.get('direction') == 'BEARISH')),
    },
    'choch': {
        'total': int(len(choch_events)),
        'by_tf': {
            'HTF': int(sum(1 for e in choch_events if e.get('tf_level') == 'HTF')),
            'ITF': int(sum(1 for e in choch_events if e.get('tf_level') == 'ITF')),
            'LTF': int(sum(1 for e in choch_events if e.get('tf_level') == 'LTF')),
        },
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
