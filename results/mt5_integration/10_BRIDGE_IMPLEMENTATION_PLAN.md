# FASE 5: Bridge Implementation Plan
## Python ↔ MT5 Communication Module

**Status**: Implementation guide (ready to code)  
**Effort**: 2-3 days of development + testing  
**Output**: `integration/mt5_bridge/` Python package

---

## 1. BRIDGE MODULE STRUCTURE

```
integration/
└── mt5_bridge/
    ├── __init__.py                          # Package initialization
    ├── bridge.py                            # Main orchestrator (Method A+B)
    ├── signal_exporter.py                   # Export signals to MT5
    ├── signal_receiver.py                   # Import trade results from MT5
    ├── schema.py                            # Pydantic validation models
    ├── config.py                            # Configuration management
    ├── validators.py                        # Validation functions
    ├── logger.py                            # Logging setup
    ├── exceptions.py                        # Custom exceptions
    ├── constants.py                         # Magic numbers, enums
    ├── utils.py                             # Helper functions
    ├── tests/
    │   ├── __init__.py
    │   ├── test_schema.py                   # Schema validation tests
    │   ├── test_exporter.py                 # Exporter unit tests
    │   ├── test_receiver.py                 # Receiver unit tests
    │   ├── test_bridge.py                   # Integration tests
    │   └── fixtures/
    │       ├── sample_signals.json
    │       └── sample_results.json
    └── docs/
        └── API.md                           # Public API documentation
```

---

## 2. MODULE IMPLEMENTATIONS

### 2.1 constants.py

```python
# Configuration constants
VALID_SYMBOLS = {'EURUSD', 'GBPUSD', 'XAUUSD'}
VALID_DIRECTIONS = {1, -1}  # 1=LONG, -1=SHORT
VALID_EXIT_REASONS = {'TP_HIT', 'SL_HIT', 'MANUAL_CLOSE', 'TIMEOUT', 'ERROR'}
VALID_RISK_STATES = {'NORMAL', 'CAUTION', 'DEFENSIVE', 'LOCKDOWN'}

# ML thresholds
ML_CONFIDENCE_MINIMUM = 0.60
ML_CONFIDENCE_CAUTION = 0.65
ML_CONFIDENCE_DEFENSIVE = 0.75

# Risk parameters
DEFAULT_RISK_PCT = 0.005  # 0.5%
DEFAULT_RR_RATIO = 2.0
MIN_POSITION_LOTS = 0.01
MAX_POSITION_LOTS = 100.0

# Slippage tolerances
MAX_SLIPPAGE_PIPS = 2.0
MAX_SLIPPAGE_PCT = 0.002

# CSV settings
CSV_ENCODING = 'utf-8'
CSV_DELIMITER = ','
SIGNAL_FILE = 'signals.csv'
RESULT_FILE = 'trade_results.csv'

# Retry logic
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

# Timeouts
API_TIMEOUT_SECONDS = 30
FILE_READ_TIMEOUT_SECONDS = 10
```

### 2.2 exceptions.py

```python
class SMCBridgeException(Exception):
    """Base exception for bridge module."""
    pass

class ValidationError(SMCBridgeException):
    """Signal/result validation failed."""
    pass

class ExportError(SMCBridgeException):
    """Failed to export signal to MT5."""
    pass

class ImportError(SMCBridgeException):
    """Failed to import result from MT5."""
    pass

class ConfigurationError(SMCBridgeException):
    """Configuration is invalid."""
    pass

class CommunicationError(SMCBridgeException):
    """Communication with MT5 failed."""
    pass

class FileIOError(SMCBridgeException):
    """File I/O operation failed."""
    pass
```

### 2.3 schema.py (Pydantic Models)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict
from datetime import datetime

class StructuralComponents(BaseModel):
    """Structural signal components."""
    bos_detected: bool
    bos_strength: Optional[float] = None
    fvg_detected: bool
    fvg_size_atr: Optional[float] = None
    ob_detected: bool
    ob_strength: Optional[float] = None
    choch_detected: bool
    structural_sl_price: float
    sweep_intensity: float

class SignalSchema(BaseModel):
    """Complete signal schema for export to MT5."""
    signal_id: str
    timestamp_utc: datetime
    symbol: str
    direction: int  # 1 or -1
    entry_price: float
    sl_price: float
    tp_price: float
    position_size_lots: float
    risk_usd: float
    reward_usd: float
    rr_ratio: float
    ml_score: float
    ml_confidence: float
    confluence_alignment: float
    signal_strength: float
    session: str
    market_regime: str
    structural_components: StructuralComponents
    entry_bar_index: int
    risk_state: str
    account_balance_at_signal: float
    drawdown_pct_at_signal: float
    
    @validator('direction')
    def validate_direction(cls, v):
        if v not in [1, -1]:
            raise ValueError('direction must be 1 or -1')
        return v
    
    @validator('ml_score')
    def validate_ml_score(cls, v):
        if not (0.60 <= v <= 1.0):
            raise ValueError('ml_score must be between 0.60 and 1.0')
        return v
    
    # ... more validators

class TradeResultSchema(BaseModel):
    """Trade result from MT5."""
    signal_id: str
    order_id: int
    symbol: str
    direction: int
    entry_price: float
    entry_time_utc: datetime
    entry_volume_lots: float
    exit_price: float
    exit_time_utc: datetime
    exit_reason: str
    holding_bars: int
    mfe: float
    mae: float
    pnl_usd: float
    pnl_r: float
    slippage_pips: float
    commission_usd: float
    status: str  # CLOSED, FAILED, PARTIAL

class FeatureVectorSchema(BaseModel):
    """ML feature vector for logging."""
    signal_id: str
    timestamp_utc: datetime
    features: Dict[str, float]
    ml_version: str
```

### 2.4 config.py

```python
import os
from enum import Enum
from pathlib import Path

class CommunicationMethod(Enum):
    METHOD_A = "mt5_api"        # MetaTrader5 Python package
    METHOD_B = "csv_bridge"     # CSV file exchange

class BridgeConfig:
    """Bridge configuration manager."""
    
    def __init__(self):
        self.method_primary = CommunicationMethod.METHOD_A
        self.method_fallback = CommunicationMethod.METHOD_B
        self.auto_failover = True
        self.csv_directory = Path(os.getenv('CSV_PATH', './data/bridge'))
        self.signal_file = self.csv_directory / 'signals.csv'
        self.result_file = self.csv_directory / 'trade_results.csv'
        self.archive_directory = self.csv_directory / 'archive'
        self.log_directory = Path(os.getenv('LOG_PATH', './logs/bridge'))
        
        # MT5 API settings
        self.mt5_login = int(os.getenv('MT5_LOGIN', ''))
        self.mt5_password = os.getenv('MT5_PASSWORD', '')
        self.mt5_server = os.getenv('MT5_SERVER', '')
        self.mt5_timeout = int(os.getenv('MT5_TIMEOUT', '30'))
        
        # Create directories
        self.csv_directory.mkdir(parents=True, exist_ok=True)
        self.archive_directory.mkdir(parents=True, exist_ok=True)
        self.log_directory.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> tuple[bool, str]:
        """Validate configuration."""
        if self.method_primary not in [CommunicationMethod.METHOD_A, CommunicationMethod.METHOD_B]:
            return False, "Invalid primary method"
        
        if self.method_primary == CommunicationMethod.METHOD_A:
            if not all([self.mt5_login, self.mt5_password, self.mt5_server]):
                return False, "MT5 credentials missing"
        
        if not self.csv_directory.exists():
            return False, f"CSV directory doesn't exist: {self.csv_directory}"
        
        return True, "Configuration valid"
```

### 2.5 validators.py

```python
from typing import Dict, Tuple, Any
from constants import *

def validate_signal(signal: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate signal before export.
    Returns: (is_valid, error_message)
    """
    
    errors = []
    
    # Check required fields
    required_fields = [
        'signal_id', 'timestamp_utc', 'symbol', 'direction',
        'entry_price', 'sl_price', 'tp_price', 'position_size_lots',
        'risk_usd', 'ml_score'
    ]
    
    for field in required_fields:
        if field not in signal:
            errors.append(f"Missing: {field}")
    
    # Type checks
    if 'direction' in signal and signal['direction'] not in VALID_DIRECTIONS:
        errors.append(f"Invalid direction: {signal['direction']}")
    
    if 'symbol' in signal and signal['symbol'] not in VALID_SYMBOLS:
        errors.append(f"Invalid symbol: {signal['symbol']}")
    
    # Price logic validation
    if all(k in signal for k in ['entry_price', 'sl_price', 'tp_price', 'direction']):
        entry = float(signal['entry_price'])
        sl = float(signal['sl_price'])
        tp = float(signal['tp_price'])
        direction = signal['direction']
        
        if direction == 1:  # LONG
            if sl >= entry:
                errors.append(f"LONG SL >= entry: {sl} >= {entry}")
            if tp <= entry:
                errors.append(f"LONG TP <= entry: {tp} <= {entry}")
        elif direction == -1:  # SHORT
            if sl <= entry:
                errors.append(f"SHORT SL <= entry: {sl} <= {entry}")
            if tp >= entry:
                errors.append(f"SHORT TP >= entry: {tp} >= {entry}")
    
    # RR ratio check
    if all(k in signal for k in ['entry_price', 'sl_price', 'tp_price', 'direction']):
        entry = float(signal['entry_price'])
        sl = float(signal['sl_price'])
        tp = float(signal['tp_price'])
        direction = signal['direction']
        
        if direction == 1:
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        
        if risk > 0:
            rr = reward / risk
            if rr < DEFAULT_RR_RATIO - 0.1:  # Allow small tolerance
                errors.append(f"RR too low: {rr:.2f} < {DEFAULT_RR_RATIO}")
    
    # ML score check
    if 'ml_score' in signal:
        if not (ML_CONFIDENCE_MINIMUM <= signal['ml_score'] <= 1.0):
            errors.append(f"ML score out of range: {signal['ml_score']}")
    
    # Position size check
    if 'position_size_lots' in signal:
        if not (MIN_POSITION_LOTS <= signal['position_size_lots'] <= MAX_POSITION_LOTS):
            errors.append(f"Position size out of range: {signal['position_size_lots']}")
    
    return len(errors) == 0, "; ".join(errors) if errors else "Valid"


def validate_trade_result(result: Dict[str, Any], original_signal: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate trade result from MT5.
    """
    
    errors = []
    
    # Check required fields
    required = ['signal_id', 'exit_reason', 'pnl_r', 'entry_price', 'exit_price']
    for field in required:
        if field not in result:
            errors.append(f"Missing: {field}")
    
    # Exit reason validation
    if 'exit_reason' in result:
        if result['exit_reason'] not in VALID_EXIT_REASONS:
            errors.append(f"Invalid exit_reason: {result['exit_reason']}")
    
    # P&L logic validation
    if 'exit_reason' in result and 'pnl_r' in result:
        if result['exit_reason'] == 'TP_HIT' and result['pnl_r'] < 1.8:
            errors.append(f"TP_HIT but pnl_r={result['pnl_r']} (expected ~2.0)")
        
        if result['exit_reason'] == 'SL_HIT' and result['pnl_r'] > -0.8:
            errors.append(f"SL_HIT but pnl_r={result['pnl_r']} (expected ~-1.0)")
    
    return len(errors) == 0, "; ".join(errors) if errors else "Valid"
```

### 2.6 signal_exporter.py (Method A + B Hybrid)

```python
import json
import csv
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple
import logging

from .schema import SignalSchema
from .validators import validate_signal
from .config import BridgeConfig, CommunicationMethod
from .exceptions import ExportError, ValidationError, CommunicationError

class SignalExporter:
    """Export signals to MT5 using Method A (MT5 API) or Method B (CSV)."""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.method_current = self.config.method_primary
        self.method_failed_count = {
            CommunicationMethod.METHOD_A: 0,
            CommunicationMethod.METHOD_B: 0
        }
    
    def export_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Export single signal to MT5.
        Uses Method A first, falls back to Method B if fails and failover enabled.
        
        Returns: (success, message)
        """
        
        # Validate signal
        is_valid, msg = validate_signal(signal)
        if not is_valid:
            raise ValidationError(f"Invalid signal: {msg}")
        
        # Try primary method
        if self.method_current == CommunicationMethod.METHOD_A:
            try:
                return self._export_via_mt5_api(signal)
            except CommunicationError as e:
                self.logger.warning(f"Method A failed: {e}")
                self.method_failed_count[CommunicationMethod.METHOD_A] += 1
                
                if self.config.auto_failover:
                    self.logger.info("Switching to Method B (CSV fallback)")
                    self.method_current = CommunicationMethod.METHOD_B
                    try:
                        return self._export_via_csv(signal)
                    except Exception as e:
                        raise ExportError(f"Both methods failed: {e}")
                else:
                    raise
        
        elif self.method_current == CommunicationMethod.METHOD_B:
            try:
                return self._export_via_csv(signal)
            except Exception as e:
                self.method_failed_count[CommunicationMethod.METHOD_B] += 1
                raise ExportError(f"CSV export failed: {e}")
    
    def _export_via_mt5_api(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """Export via MT5 Python package (Method A)."""
        
        try:
            # Initialize MT5 if not already
            if not mt5.initialize():
                raise CommunicationError("Failed to initialize MT5")
            
            # Login
            if not mt5.login(self.config.mt5_login, self
.config.mt5_password, self.config.mt5_server):
                raise CommunicationError(f"MT5 login failed: {mt5.last_error()}")
            
            # Prepare order
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': signal['symbol'],
                'volume': signal['position_size_lots'],
                'type': mt5.ORDER_TYPE_BUY if signal['direction'] == 1 else mt5.ORDER_TYPE_SELL,
                'price': signal['entry_price'],
                'sl': signal['sl_price'],
                'tp': signal['tp_price'],
                'comment': signal['signal_id'],
                'magic': 20260601,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise CommunicationError(f"Order failed: retcode={result.retcode}")
            
            self.logger.info(f"Signal {signal['signal_id']} placed via MT5: order={result.order}")
            return True, f"Order {result.order} placed"
        
        except Exception as e:
            raise CommunicationError(str(e))
        finally:
            mt5.shutdown()
    
    def _export_via_csv(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """Export via CSV file (Method B)."""
        
        try:
            # Prepare signal data
            signal_dict = self._flatten_signal(signal)
            
            # Atomic write: write to temp, then rename
            temp_file = self.config.signal_file.with_suffix('.tmp')
            
            # Check if file exists to determine if we need headers
            file_exists = self.config.signal_file.exists()
            
            # Read existing data if present
            if file_exists:
                df = pd.read_csv(self.config.signal_file)
                df = pd.concat([df, pd.DataFrame([signal_dict])], ignore_index=True)
            else:
                df = pd.DataFrame([signal_dict])
            
            # Write to temp file
            df.to_csv(temp_file, index=False, encoding='utf-8')
            
            # Atomic rename
            temp_file.replace(self.config.signal_file)
            
            self.logger.info(f"Signal {signal['signal_id']} written to CSV")
            return True, f"Signal written to {self.config.signal_file}"
        
        except Exception as e:
            raise ExportError(f"CSV export failed: {e}")
    
    def _flatten_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested signal structure for CSV export."""
        
        flat = {
            'signal_id': signal['signal_id'],
            'timestamp_utc': signal['timestamp_utc'],
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'sl_price': signal['sl_price'],
            'tp_price': signal['tp_price'],
            'position_size_lots': signal['position_size_lots'],
            'risk_usd': signal['risk_usd'],
            'ml_score': signal['ml_score'],
            'bos_detected': signal['structural_components']['bos_detected'],
            'fvg_detected': signal['structural_components']['fvg_detected'],
            'ob_detected': signal['structural_components']['ob_detected'],
            'choch_detected': signal['structural_components']['choch_detected'],
            'entry_bar_index': signal['entry_bar_index'],
            'risk_state': signal['risk_state'],
        }
        
        return flat
```

### 2.7 signal_receiver.py

```python
import csv
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

from .schema import TradeResultSchema
from .validators import validate_trade_result
from .config import BridgeConfig
from .exceptions import ImportError

class SignalReceiver:
    """Import trade results from MT5 via CSV or API."""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.processed_signals = set()
    
    def receive_results(self) -> List[Dict[str, Any]]:
        """
        Receive completed trade results from MT5.
        Returns list of trade results.
        """
        
        try:
            # Read CSV results file
            if not self.config.result_file.exists():
                self.logger.debug("No results file found yet")
                return []
            
            df = pd.read_csv(self.config.result_file)
            results = []
            
            for _, row in df.iterrows():
                result_dict = row.to_dict()
                
                # Skip if already processed
                if result_dict['signal_id'] in self.processed_signals:
                    continue
                
                # Validate result
                is_valid, msg = validate_trade_result(result_dict, {})
                if not is_valid:
                    self.logger.warning(f"Invalid result for {result_dict['signal_id']}: {msg}")
                    continue
                
                results.append(result_dict)
                self.processed_signals.add(result_dict['signal_id'])
            
            self.logger.info(f"Received {len(results)} new results")
            return results
        
        except Exception as e:
            raise ImportError(f"Failed to import results: {e}")
    
    def archive_result(self, signal_id: str) -> None:
        """Archive processed result."""
        
        try:
            # Move result to archive
            timestamp = pd.Timestamp.now().strftime('%Y%m%d')
            archive_file = self.config.archive_directory / f"results_{timestamp}.csv"
            
            # Append to archive
            if self.config.result_file.exists():
                df = pd.read_csv(self.config.result_file)
                if archive_file.exists():
                    df_archive = pd.read_csv(archive_file)
                    df = pd.concat([df_archive, df], ignore_index=True)
                df.to_csv(archive_file, index=False)
            
            # Clear result file
            self.config.result_file.unlink(missing_ok=True)
        
        except Exception as e:
            self.logger.error(f"Archive failed: {e}")
```

### 2.8 bridge.py (Main Orchestrator)

```python
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple

from .config import BridgeConfig
from .signal_exporter import SignalExporter
from .signal_receiver import SignalReceiver
from .schema import SignalSchema, TradeResultSchema
from .validators import validate_signal
from .exceptions import SMCBridgeException
from .logger import setup_logger

class SMCBridge:
    """
    Main bridge orchestrator.
    Handles signal export and result import with method fallback.
    """
    
    def __init__(self, config: BridgeConfig = None):
        self.config = config or BridgeConfig()
        self.logger = setup_logger(__name__, self.config.log_directory)
        
        # Validate config
        is_valid, msg = self.config.validate()
        if not is_valid:
            raise SMCBridgeException(f"Config invalid: {msg}")
        
        self.exporter = SignalExporter(self.config)
        self.receiver = SignalReceiver(self.config)
        self.logger.info("Bridge initialized")
    
    def export_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Export single signal to MT5.
        
        Args:
            signal: Signal dictionary with all required fields
        
        Returns:
            (success: bool, message: str)
        
        Raises:
            ValidationError if signal invalid
            ExportError if export fails
        """
        
        try:
            signal_id = signal.get('signal_id', 'UNKNOWN')
            self.logger.debug(f"Exporting signal: {signal_id}")
            
            # Validate
            is_valid, msg = validate_signal(signal)
            if not is_valid:
                self.logger.error(f"Signal validation failed: {msg}")
                raise SMCBridgeException(f"Validation failed: {msg}")
            
            # Export
            success, msg = self.exporter.export_signal(signal)
            
            if success:
                self.logger.info(f"Signal exported: {signal_id}")
            else:
                self.logger.warning(f"Signal export issue: {msg}")
            
            return success, msg
        
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            raise
    
    def export_signals_batch(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Export multiple signals in batch.
        
        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'errors': [...]
            }
        """
        
        results = {
            'total': len(signals),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for signal in signals:
            try:
                success, msg = self.export_signal(signal)
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'signal_id': signal.get('signal_id'),
                        'error': msg
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'signal_id': signal.get('signal_id'),
                    'error': str(e)
                })
        
        self.logger.info(f"Batch export: {results['successful']}/{results['total']} successful")
        return results
    
    def receive_results(self) -> List[Dict[str, Any]]:
        """
        Receive completed trade results from MT5.
        
        Returns:
            List of trade result dictionaries
        """
        
        try:
            results = self.receiver.receive_results()
            self.logger.info(f"Received {len(results)} results from MT5")
            return results
        
        except Exception as e:
            self.logger.error(f"Failed to receive results: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        
        return {
            'primary_method': self.config.method_primary.value,
            'fallback_method': self.config.method_fallback.value,
            'auto_failover': self.config.auto_failover,
            'current_method': self.exporter.method_current.value,
            'method_failures': {
                'method_a': self.exporter.method_failed_count['METHOD_A'],
                'method_b': self.exporter.method_failed_count['METHOD_B']
            }
        }
```

---

## 3. TEST SUITE OUTLINE

```python
# tests/test_bridge.py

class TestSignalExport:
    """Test signal export to MT5."""
    
    def test_export_valid_signal(self):
        """Valid signal exports successfully."""
        # Create valid signal
        # Call export
        # Assert success
    
    def test_export_invalid_signal(self):
        """Invalid signal raises ValidationError."""
        # Create invalid signal (missing field)
        # Assert raises ValidationError
    
    def test_export_fallback_method_b(self):
        """Falls back to Method B if Method A fails."""
        # Mock Method A to fail
        # Call export
        # Assert switches to Method B
        # Assert success

class TestResultImport:
    """Test trade result import from MT5."""
    
    def test_import_valid_result(self):
        """Valid result imports successfully."""
        # Create result CSV
        # Call receive_results
        # Assert result returned
    
    def test_validate_tp_hit_result(self):
        """TP_HIT result has correct P&L."""
        # Create TP_HIT result
        # Validate
        # Assert pnl_r ≈ 2.0

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_full_signal_lifecycle(self):
        """Signal export → MT5 execution → result import."""
        # Export signal
        # Simulate MT5 execution
        # Import result
        # Assert complete cycle
```

---

## 4. DEPLOYMENT CHECKLIST

- [ ] Directory structure created
- [ ] All 11 Python modules implemented
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Environment variables configured
- [ ] CSV directories created and permissioned
- [ ] Logging configured and tested
- [ ] Error handling tested (all exception paths)
- [ ] Failover tested (Method A ↔ Method B)
- [ ] Documentation written (docstrings, API docs)
- [ ] Code review completed
- [ ] Performance benchmarks met (<1s per signal)

---

## 5. SUCCESS CRITERIA

✅ All signals export without error  
✅ Fallover works if MT5 API unavailable  
✅ Trade results import correctly  
✅ Validation catches all invalid signals  
✅ Audit trail complete (all logged)  
✅ <1 second latency per signal  

---

**NEXT**: After bridge complete, proceed to FASE 6 (MQL5 EA development).
