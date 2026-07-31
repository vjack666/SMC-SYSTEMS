"""Forensic runner: EURUSD M5 using canonical market_structure detector + MTF alignment.

Runs:
1. detect_market_structure on D1/H4/H1/M5 independently
2. align_structure_mtf(..., ltf="M5") for HTF/ITF/LTF classification
3. Emits forensic trace + audit report
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path('.')))

from ict_backtest.market_structure import StructureConfig, detect_market_structure
from ict_backtest.structure_mtf_align import AlignConfig, align_structure_mtf

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


# Load frames
frames: Dict[str, pd.DataFrame] = {}
for tf in ['D1', 'H4', 'H1', 'M5']:
    loaded = _load_frame(tf)
    if loaded is not None:
        if tf == 'M5':
            loaded = loaded.tail(50000).reset_index(drop=True)
        frames[tf] = loaded

if 'M5' not in frames or frames['M5'].empty:
    raise SystemExit('Missing M5 frame at data/raw/EURUSD_M5.parquet')

# Detect structure per TF independently
ms_by_tf = {tf: detect_market_structure(df, StructureConfig()) for tf, df in frames.items()}

# Align LTF onsets to HTF/ITF via temporal matching
align_cfg = AlignConfig(ltf='M5')
align_report = align_structure_mtf(ms_by_tf, align_cfg)
summary = align_report["summary"]
ltf_onsets = align_report["onsets"]

# Write trace
with TRACE_PATH.open('w', encoding='utf-8') as f:
    for onset in ltf_onsets:
        ev = {
            'bar_index_m5': 0,
            'timestamp': onset.time.isoformat(),
            'layer': onset.event,
            'event': f"{onset.event}_detected",
            'entity_id': f"{onset.event}_{onset.time.isoformat()}_{onset.direction}",
            'entity_type': onset.event,
            'tf_level': None,
            'direction': 'BULLISH' if onset.direction == 1 else 'BEARISH',
            'price': onset.level,
            'new_state': 'ACTIVE',
            'age_bars': 0,
            'reason': 'canonical_detect_market_structure',
        }
        # best-effort tf_level from summary counts
        by_tf = summary.get(onset.event, {}).get("by_tf", {})
        ev['tf_level'] = max(by_tf, key=by_tf.get) if by_tf else 'LTF'
        f.write(json.dumps(ev, ensure_ascii=False) + '\n')

audit = {
    'symbol': SYMBOL,
    'start': ms_by_tf['M5']['time'].iloc[0].isoformat(),
    'end': ms_by_tf['M5']['time'].iloc[-1].isoformat(),
    'total_bars_m5': int(len(ms_by_tf['M5'])),
    'layers_used': sorted(ms_by_tf.keys()),
    'summary': summary,
    'trace_path': str(TRACE_PATH),
}

with (OUT_DIR / f'audit_report_{SYMBOL}.json').open('w', encoding='utf-8') as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)

print('REPORT', json.dumps(audit, ensure_ascii=False, indent=2))
