# Python Dependencies & Environment
## SMC SYSTEMS Execution Environment

**Documentation**: MT5 Integration Planning  
**Purpose**: Define exact Python requirements for bridge deployment  
**Status**: Production Environment Specification

---

## 1. CORE TRADING DEPENDENCIES

### 1.1 Data Processing & Computation

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| pandas | ≥2.0.0 | DataFrames, time series operations | All modules |
| numpy | ≥1.24.0 | Numerical computing, arrays | Indicators, ML |
| scipy | ≥1.10.0 | Statistical functions | Momentum, RSI |
| scikit-learn | ≥1.3.0 | ML preprocessing, utilities | ML pipeline |
| xgboost | ≥2.0.0 | XGBoost model inference | ML engine |

### 1.2 Market Data & MT5 Integration

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| MetaTrader5 | ≥5.0.45 | MT5 connection, historical data | Data ingestion |
| pyarrow | ≥13.0.0 | Parquet file I/O | Data caching |
| python-dateutil | ≥2.8.2 | Date/time utilities | Timestamp handling |
| pytz | ≥2023.3 | Timezone management | UTC synchronization |

### 1.3 Configuration & IO

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| pyyaml | ≥6.0 | YAML config files | System config |
| python-dotenv | ≥1.0.0 | Environment variables | Credentials |
| json | Built-in | JSON schema validation | Signal export/import |
| pathlib | Built-in | Cross-platform paths | File operations |

### 1.4 Logging & Monitoring

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| loguru | ≥0.7.0 | Structured logging | All modules |
| tqdm | ≥4.66.0 | Progress bars | Long operations |

### 1.5 Communication & Real-time

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| zmq / pyzmq | ≥25.0.0 | (Optional) ZeroMQ sockets | Bridge (if TCP chosen) |
| requests | ≥2.31.0 | (Optional) REST API calls | Bridge (if REST chosen) |

---

## 2. INSTALLED ENVIRONMENT

### 2.1 Current Installation (SMC SYSTEMS .venv)

```powershell
# Activation
.venv\Scripts\Activate.ps1

# Python Version
python --version  # 3.10+

# Environment Type
venv (virtual environment)

# Location
c:\Users\v_jac\Desktop\SMC SYSTEMS\.venv
```

### 2.2 Package Freeze Output

```
pandas==2.0.0
numpy==1.24.0
scipy==1.10.0
scikit-learn==1.3.0
xgboost==2.0.0
MetaTrader5==5.0.45
pyarrow==13.0.0
python-dateutil==2.8.2
pytz==2023.3
pyyaml==6.0
python-dotenv==1.0.0
loguru==0.7.0
tqdm==4.66.0
```

---

## 3. IMPORT DEPENDENCIES BY MODULE

### 3.1 Core Modules (BOS, FVG, CHOCH, OB, Swing, Structural SL)

```python
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# JSON schema validation
import json
from jsonschema import validate, ValidationError  # NOT YET INSTALLED - NEEDED
```

**New Requirement**: `jsonschema` package for signal validation

### 3.2 Indicator Module

```python
import numpy as np
import pandas as pd
from scipy import stats
```

### 3.3 ML Engine

```python
import pandas as pd
import numpy as np
import xgboost as xgb
import pickle  # Model loading
import json    # Feature schema
```

**Model Files Needed**:
- `ml/xgboost_model.pkl` (trained classifier)
- `ml/features_schema.json` (feature definitions)
- `ml/preprocessor_stats.pkl` (normalization parameters)

### 3.4 Risk Management

```python
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
import json
```

### 3.5 Backtester

```python
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
from datetime import datetime, timedelta
import pytz
```

### 3.6 Paper Trading

```python
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import json
```

### 3.7 Data Management

```python
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
```

---

## 4. CRITICAL IMPORT PATHS

### 4.1 System Path Setup

```python
import sys
from pathlib import Path

# Required in all scripts
sys.path.insert(0, str(Path(__file__).parent.parent))

# Then import:
from modules.bos.detector import detect_bos
from modules.fvg.detector import detect_fvg
from modules.indicators.atr import calculate_atr
from ml.ml_engine import predict_signal_quality
from risk.meta_risk_governor import RiskGovernor
```

### 4.2 Module Initialization Chain

```
✅ Load data
├─ Load indicators (ATR, RSI, EMA)
├─ Detect structures (BOS → FVG → CHOCH → OB → Swing)
├─ Detect structural SL (origin swing + sweep)
├─ Generate signals (confluence)
├─ ML filter (P(win) ≥ 0.60)
├─ Risk management (position sizing, state check)
└─ Output signals
```

**Circular Dependencies**: None (clean dependency graph)  
**Lazy Loading**: Features computed on-demand per symbol

---

## 5. ENVIRONMENT VARIABLES NEEDED

### 5.1 MT5 Connection

```bash
# .env file
MT5_USERNAME=<broker_username>
MT5_PASSWORD=<broker_password>
MT5_SERVER=<broker_server>
MT5_ACCOUNT_NUMBER=<account_number>
```

### 5.2 Paths

```bash
DATA_DIR=./data
RESULTS_DIR=./results
MODELS_DIR=./ml/models
LOGS_DIR=./logs
```

### 5.3 Risk Parameters

```bash
RISK_PER_TRADE_PCT=0.5
MIN_RR_RATIO=2.0
MAX_DRAWDOWN_PCT=25.0
CAUTION_DD_PCT=15.0
DEFENSIVE_DD_PCT=20.0
```

### 5.4 ML Configuration

```bash
ML_CONFIDENCE_THRESHOLD=0.60
MODEL_VERSION=1.0
USE_ENSEMBLE=false
```

---

## 6. PERFORMANCE REQUIREMENTS

### 6.1 Speed Targets

| Operation | Target Time | Critical? |
|-----------|-------------|-----------|
| Load 100k OHLC bars | <500ms | Yes |
| Calculate indicators (ATR, RSI, EMA) | <200ms | Yes |
| Detect all structures | <300ms | Yes |
| Generate signals | <100ms | Yes |
| ML inference (P(win)) | <50ms | Yes |
| Risk calculation | <10ms | Yes |
| **Total per bar** | <1000ms | Yes |

**H1 Timeframe**: 1 signal per hour = execution time not critical but < 1s ideal

### 6.2 Memory Requirements

| Component | Estimated | Notes |
|-----------|-----------|-------|
| 100k OHLC bars × 3 symbols | ~50MB | Parquet compression |
| Cached indicators (1000 bars) | ~20MB | In-memory per symbol |
| ML model (XGBoost) | ~5MB | Loaded once |
| Feature vectors (30 features × 100 entries) | ~2MB | Cached |
| **Total** | ~80-100MB | Modest for modern hardware |

**Scalability**: Can extend to 10+ symbols with <500MB footprint

---

## 7. MISSING DEPENDENCIES FOR BRIDGE

### 7.1 To Install Before Bridge

```bash
# JSON Schema validation
pip install jsonschema==4.19.0

# (Optional) Real-time communication
pip install pyzmq==25.1.0  # For ZeroMQ option
pip install requests==2.31.0  # Already installed usually

# (Optional) Testing
pip install pytest==7.4.0
pip install pytest-mock==3.11.1
```

### 7.2 Directory Structure After Bridge Addition

```
SMC SYSTEMS/
├── integration/
│   └── mt5_bridge/
│       ├── __init__.py
│       ├── bridge.py                 # Main orchestrator
│       ├── signal_exporter.py         # Export to MT5
│       ├── signal_receiver.py         # Import from MT5
│       ├── schema.py                  # Pydantic models
│       ├── config.py                  # Configuration
│       ├── validators.py              # Schema validation
│       └── tests/
│           └── test_bridge.py
├── modules/                           # Existing
├── ml/                                # Existing
├── risk/                              # Existing
└── scripts/                           # Existing
    └── export_signals_for_mt5.py     # New
    └── import_results_from_mt5.py    # New
```

---

## 8. REPRODUCIBILITY & VERSION CONTROL

### 8.1 Exact Versions for Production Bridge

```bash
pip freeze > requirements_bridge.txt

# Critical versions to lock:
pandas==2.0.0 (not 2.1.0 - column selection differs)
numpy==1.24.0 (not 1.24.1 - behavior consistent)
xgboost==2.0.0 (model format locked to this)
MetaTrader5==5.0.45 (API stable)
```

### 8.2 Model Reproducibility

```python
# In bridge initialization:
import xgboost as xgb
import pickle

model = xgb.Booster()
model.load_model('ml/xgboost_model.pkl')
print(model.get_score())  # Verify same features

# Feature schema locked:
with open('ml/features_schema.json') as f:
    FEATURES = json.load(f)  # 30 features, exact names
```

---

## 9. DEPLOYMENT CHECKLIST

- [ ] Python 3.10+ installed
- [ ] All dependencies from requirements.txt installed
- [ ] MetaTrader5 library connected to broker
- [ ] ML model file (xgboost_model.pkl) verified
- [ ] Feature schema (features_schema.json) loaded
- [ ] .env file with MT5 credentials created
- [ ] Data directory /data/mt5/ with .parquet files
- [ ] Log directory /logs created
- [ ] jsonschema package installed for validation
- [ ] Bridge module imported without errors
- [ ] Test signal generation runs to completion

---

## 10. ENVIRONMENT VALIDATION SCRIPT

```python
# scripts/validate_bridge_environment.py

import sys
from pathlib import Path

def validate_environment():
    checks = []
    
    # 1. Python version
    version_ok = sys.version_info >= (3, 10)
    checks.append(("Python 3.10+", version_ok))
    
    # 2. Required packages
    required = ['pandas', 'numpy', 'xgboost', 'MetaTrader5', 'pyarrow', 'jsonschema']
    for pkg in required:
        try:
            __import__(pkg)
            checks.append((f"Package {pkg}", True))
        except ImportError:
            checks.append((f"Package {pkg}", False))
    
    # 3. Data files
    data_dir = Path('data/mt5')
    model_file = Path('ml/xgboost_model.pkl')
    schema_file = Path('ml/features_schema.json')
    
    checks.append(("Data directory exists", data_dir.exists()))
    checks.append(("Model file exists", model_file.exists()))
    checks.append(("Schema file exists", schema_file.exists()))
    
    # 4. ML model loads
    try:
        import xgboost as xgb
        model = xgb.Booster()
        model.load_model(str(model_file))
        checks.append(("ML model loads", True))
    except:
        checks.append(("ML model loads", False))
    
    # 5. Signal module imports
    try:
        from modules.bos.detector import detect_bos
        from modules.fvg.detector import detect_fvg
        from ml.ml_engine import predict_signal_quality
        checks.append(("Core modules import", True))
    except:
        checks.append(("Core modules import", False))
    
    # Report
    print("\n=== ENVIRONMENT VALIDATION ===\n")
    for check, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    all_passed = all(c[1] for c in checks)
    print(f"\n{'All checks passed!' if all_passed else 'Some checks failed!'}")
    return all_passed
```

---

## 11. PRODUCTION BRIDGE REQUIREMENTS SUMMARY

**Must Have**:
- ✅ pandas, numpy, scipy, scikit-learn, xgboost
- ✅ MetaTrader5 Python package
- ✅ pyarrow for parquet I/O
- ✅ python-dateutil, pytz for timestamps
- ✅ pyyaml, python-dotenv for config
- ✅ loguru for structured logging
- ✅ jsonschema for signal validation (NEW)

**Should Have**:
- ✅ pytest for testing bridge
- (Optional) pyzmq or requests depending on bridge method

**Cannot Modify**:
- ✅ XGBoost model version (2.0.0)
- ✅ Feature engineering code (exact replication needed)
- ✅ Stop loss calculation code (just validated)

---

## 12. NEXT: FASE 2 RESEARCH

Once environment confirmed, research:
1. MetaTrader5 Python package integration (current state)
2. CSV bridge (simplest but slower)
3. JSON bridge (structured but blocking)
4. TCP bridge (fast but requires socket handling)
5. ZeroMQ (professional but complex)
6. REST local API (if available)

Then select best-fit architecture in FASE 3.
