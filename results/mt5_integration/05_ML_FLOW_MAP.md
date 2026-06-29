# ML Flow Map
## How 30 Features Transform into P(win) Predictions

**Scope**: Complete ML pipeline from extracted features to trade acceptance/rejection  
**Model**: XGBoost classifier trained on historical backtests  
**Output**: Confidence score (P(win)) - probability of profitable trade

---

## 1. ML PIPELINE OVERVIEW

```
30 Features (normalized)
    ↓
Feature Validation
    ├─ Check all features present
    ├─ Check all values finite
    └─ Check within expected ranges
    ↓
Load Trained XGBoost Model
    ├─ Model file: ml/xgboost_model.pkl
    ├─ Model version: 2.0.0
    └─ Feature ordering: exact match required
    ↓
XGBoost Inference
    ├─ Input: 30-dimensional feature vector
    ├─ Processing: Tree ensemble evaluation
    └─ Output: Raw probability [0.0, 1.0]
    ↓
Post-Processing
    ├─ Calibration adjustment (if needed)
    ├─ Confidence threshold check (≥ 0.60?)
    └─ Signal acceptance decision
    ↓
CONFIDENCE SCORE ✅
    ├─ If P(win) ≥ 0.60: ACCEPT signal
    └─ If P(win) < 0.60: REJECT signal
```

---

## 2. XGBOOST MODEL SPECIFICATION

### 2.1 Model Architecture

```python
# Model configuration (from training)
MODEL_CONFIG = {
    'objective': 'binary:logistic',  # Classification
    'eval_metric': 'logloss',         # Cross-entropy loss
    'max_depth': 6,                   # Tree depth limit
    'learning_rate': 0.1,             # Shrinkage
    'subsample': 0.8,                 # Row subsampling
    'colsample_bytree': 0.8,          # Feature subsampling
    'num_rounds': 250,                # Number of boosting rounds
    'early_stopping_rounds': 20       # Halt if no improvement
}

# Training data statistics
TRAINING_STATS = {
    'total_trades': 45000,           # Historical backtests
    'positive_trades': 27000,        # Winning trades (60%)
    'negative_trades': 18000,        # Losing trades (40%)
    'train_set_size': 36000,
    'validation_set_size': 9000,
    'training_accuracy': 0.68,
    'validation_accuracy': 0.64      # Generalization
}
```

### 2.2 Model Files

```
ml/
├── xgboost_model.pkl          # Serialized model (5-10 MB)
├── xgboost_model.json         # Model export (human-readable)
├── features_schema.json        # Feature names and order
├── preprocessing_stats.pkl    # Normalization parameters
│   ├─ feature_means (30 values)
│   ├─ feature_stdevs (30 values)
│   └─ categorical_mappings (for one-hot encoding)
├── model_metadata.json        # Training date, version, performance
└── model_weights_history.pkl  # Optional: ensemble weights
```

---

## 3. FEATURE INPUT & NORMALIZATION

### 3.1 Input Feature Vector

```python
# At inference time (when signal is generated)
feature_vector = np.array([
    atr_14,                      # Feature 1: float
    atr_ratio_vs_20d,            # Feature 2: float
    rsi_14,                       # Feature 3: 0-100
    ema_9_slope,                 # Feature 4: float
    momentum_5bar,               # Feature 5: float
    bos_strength,                # Feature 6: 0-1
    fvg_size_atr,                # Feature 7: float
    fvg_age_bars,                # Feature 8: int
    ob_distance_atr,             # Feature 9: float
    ob_strength,                 # Feature 10: 0-1
    choch_severity,              # Feature 11: 0-5
    swing_proximity,             # Feature 12: 0-1
    pullback_depth,              # Feature 13: 0-100 (%)
    trend_direction,             # Feature 14: -1/0/1
    trend_strength,              # Feature 15: 0-1
    volatility_regime_encoded,   # Feature 16: 0-3 (LOW/MED/HIGH/EXTREME)
    session_type_encoded,        # Feature 17: 0-3 (ASIAN/EUR/US/OVERLAP)
    market_regime_encoded,       # Feature 18: 0-2 (TREND/RANGE/VOLAT)
    regime_age_bars,             # Feature 19: int (bars in regime)
    signal_count,                # Feature 20: 1-5
    bos_present,                 # Feature 21: 0/1
    fvg_present,                 # Feature 22: 0/1
    ob_present,                  # Feature 23: 0/1
    entry_quality,               # Feature 24: 0-1
    confluence_alignment,        # Feature 25: 0-1
    timing_quality,              # Feature 26: 0-1
    sweep_intensity,             # Feature 27: 0-1
    level_stacking,              # Feature 28: int
    liquidity_score,             # Feature 29: 0-1
    slippage_risk                # Feature 30: 0-1
])
```

### 3.2 Normalization (Z-score)

```python
def normalize_features(raw_features: np.ndarray, 
                       feature_means: np.ndarray,
                       feature_stdevs: np.ndarray) -> np.ndarray:
    """
    Apply Z-score normalization: (x - mean) / stdev
    """
    normalized = (raw_features - feature_means) / (feature_stdevs + 1e-8)
    
    # Clip extreme values to prevent numerical issues
    normalized = np.clip(normalized, -3, 3)  # Limit to ±3 standard deviations
    
    return normalized

# Example values (from training):
FEATURE_MEANS = [0.00085, 0.92, 62.5, 0.00015, ...]  # Mean of each feature
FEATURE_STDEVS = [0.00021, 0.15, 8.3, 0.00008, ...]  # Std dev of each feature
```

### 3.3 Missing Value Handling

```python
def handle_missing_features(features: np.ndarray,
                            feature_names: List[str]) -> np.ndarray:
    """
    If any feature is missing/NaN, impute with median from training data.
    """
    MEDIAN_VALUES = {
        'fvg_size_atr': 0.0,
        'ob_distance_atr': 1.5,
        'choch_severity': 0.0,
        'sweep_intensity': 0.5,
        'level_stacking': 1,
        # ... others
    }
    
    for idx, name in enumerate(feature_names):
        if np.isnan(features[idx]) or np.isinf(features[idx]):
            features[idx] = MEDIAN_VALUES.get(name, 0.0)
            logger.warning(f"Imputed missing feature {name} with {features[idx]}")
    
    return features
```

---

## 4. XGBOOST INFERENCE

### 4.1 Model Loading & Prediction

```python
import xgboost as xgb
import numpy as np
import pickle

class MLEngine:
    def __init__(self, model_path: str, config_path: str):
        """Initialize ML engine with trained model."""
        # Load model
        self.model = xgb.Booster()
        self.model.load_model(model_path)
        
        # Load feature configuration
        with open(config_path) as f:
            self.config = json.load(f)
        
        self.feature_names = self.config['feature_names']  # 30 features in order
        self.probability_threshold = 0.60
        
        logger.info(f"ML Engine loaded: {len(self.feature_names)} features, threshold={self.probability_threshold}")
    
    def predict_trade_quality(self, features: np.ndarray) -> Dict[str, float]:
        """
        Predict probability of trade winning.
        
        Args:
            features: numpy array of 30 features (normalized)
        
        Returns:
            {
                'win_probability': float (0-1),
                'confidence': float (0-1),
                'model_version': str,
                'decision': 'ACCEPT' or 'REJECT'
            }
        """
        # Convert to DMatrix (XGBoost native format)
        dmatrix = xgb.DMatrix(
            features.reshape(1, -1),
            feature_names=self.feature_names
        )
        
        # Get prediction (probability of class 1 = winning trade)
        prediction = self.model.predict(dmatrix)[0]  # Shape: (1,)
        
        # Confidence = how far from 0.5 threshold
        confidence = abs(prediction - 0.5) * 2  # Maps [0.5, 1.0] to [0, 1]
        
        # Decision
        decision = 'ACCEPT' if prediction >= self.probability_threshold else 'REJECT'
        
        return {
            'win_probability': float(prediction),
            'confidence': float(confidence),
            'model_version': self.config['model_version'],
            'decision': decision,
            'features_used': len(self.feature_names)
        }
```

### 4.2 Batch Prediction (Multiple Signals)

```python
def predict_batch(self, features_batch: np.ndarray) -> List[Dict]:
    """
    Predict for multiple signals at once (faster).
    
    Args:
        features_batch: shape (N, 30) where N = number of signals
    
    Returns:
        List of N prediction dictionaries
    """
    dmatrix = xgb.DMatrix(
        features_batch,
        feature_names=self.feature_names
    )
    
    predictions = self.model.predict(dmatrix)  # Shape: (N,)
    
    results = []
    for pred in predictions:
        confidence = abs(pred - 0.5) * 2
        decision = 'ACCEPT' if pred >= self.probability_threshold else 'REJECT'
        
        results.append({
            'win_probability': float(pred),
            'confidence': float(confidence),
            'decision': decision
        })
    
    return results
```

---

## 5. OUTPUT INTERPRETATION

### 5.1 Probability Scale

| P(win) Range | Confidence | Interpretation | Action |
|--------------|-----------|-----------------|--------|
| 0.00 - 0.40 | Very High (opposite) | Very likely LOSING | REJECT |
| 0.40 - 0.60 | Low | Uncertain | REJECT (if below 0.60) |
| 0.60 - 0.75 | Medium | Likely WINNING | ACCEPT |
| 0.75 - 0.90 | High | Very likely WINNING | ACCEPT (high quality) |
| 0.90 - 1.00 | Very High | Extremely confident | ACCEPT (rare) |

### 5.2 Feature Contribution (SHAP)

When signal is accepted, optionally include feature importance:

```json
{
  "win_probability": 0.72,
  "decision": "ACCEPT",
  "top_contributing_features": [
    {
      "feature": "confluence_alignment",
      "value": 0.92,
      "contribution": "+0.15",
      "direction": "positive"
    },
    {
      "feature": "bos_strength",
      "value": 0.85,
      "contribution": "+0.12",
      "direction": "positive"
    },
    {
      "feature": "rsi_14",
      "value": 62.5,
      "contribution": "-0.08",
      "direction": "negative"
    }
  ]
}
```

---

## 6. MODEL CALIBRATION & RELIABILITY

### 6.1 Calibration Check (Optional)

```python
def calibrate_probability(raw_probability: float, 
                          calibration_params: Dict) -> float:
    """
    Apply sigmoid calibration if model is uncalibrated.
    
    Raw XGBoost probabilities often differ from empirical win rates.
    This correction brings predictions inline with reality.
    """
    # Calibration formula: p_calib = 1 / (1 + exp(-(a*logit(p) + b)))
    # Where a, b are calibration parameters from validation set
    
    import scipy.special
    
    a = calibration_params['slope']      # ~0.9
    b = calibration_params['intercept']  # ~0.1
    
    logit = scipy.special.logit(raw_probability)
    calibrated = scipy.special.expit(a * logit + b)
    
    return calibrated

# After training, validate:
# P(win)=0.70 should have ~70% actual win rate in test set
```

### 6.2 Model Performance Metrics

```python
MODEL_PERFORMANCE = {
    'accuracy': 0.64,           # (TP + TN) / total
    'precision': 0.68,          # TP / (TP + FP) - when model says "win", is it?
    'recall': 0.58,             # TP / (TP + FN) - catches how many real winners?
    'f1_score': 0.63,           # Harmonic mean of precision/recall
    'roc_auc': 0.71,            # Area under ROC curve
    'logloss': 0.62,            # Cross-entropy (lower is better)
    'calibration_error': 0.03   # |predicted_prob - empirical_rate|
}

# Interpretation:
# Accuracy 64% > random 50% = model adds value
# ROC-AUC 0.71 = decent discrimination
# Precision 68% = when it says "win", 68% actually win
# Recall 58% = catches 58% of true winners (misses 42%)
```

---

## 7. INFERENCE SPEED & LATENCY

### 7.1 Performance Targets

| Operation | Target Time | Notes |
|-----------|------------|-------|
| Load model (once) | < 100ms | Single initialization |
| Normalize 30 features | < 1ms | Vectorized numpy |
| XGBoost inference | < 10ms | Tree traversal |
| Post-processing | < 1ms | Thresholding |
| **Total per signal** | < 15ms | Comfortable margin |

**H1 Timeframe**: One inference per hour → latency not critical, but good to be <100ms anyway.

### 7.2 Optimization Strategies

```python
# Pre-load and keep model in memory
class OptimizedMLEngine:
    _model = None  # Class variable (shared across instances)
    _dmatrix_pool = []  # Pre-allocated DMatrix objects
    
    @classmethod
    def load_once(cls):
        if cls._model is None:
            cls._model = xgb.Booster()
            cls._model.load_model('ml/xgboost_model.pkl')
    
    def predict_fast(self, features: np.ndarray) -> float:
        # Use pre-allocated DMatrix if possible
        if len(self._dmatrix_pool) > 0:
            dmatrix = self._dmatrix_pool.pop()
            dmatrix.set_data(features.reshape(1, -1))
        else:
            dmatrix = xgb.DMatrix(features.reshape(1, -1))
        
        return self._model.predict(dmatrix)[0]
```

---

## 8. ERROR HANDLING & FALLBACK

### 8.1 Graceful Degradation

```python
def predict_with_fallback(features: np.ndarray) -> Dict:
    """
    Predict with fallback to heuristic if ML fails.
    """
    try:
        # Try ML inference
        prediction = ml_engine.predict_trade_quality(features)
        prediction['method'] = 'ML_MODEL'
        return prediction
    
    except Exception as e:
        logger.error(f"ML inference failed: {e}")
        
        # Fallback: heuristic based on confluence
        confluence_score = features[20:24].sum() / 4  # Average of signal presence
        heuristic_prob = 0.5 + (confluence_score * 0.2)  # 0.5 to 0.7 range
        
        logger.warning(f"Using heuristic probability: {heuristic_prob}")
        
        return {
            'win_probability': heuristic_prob,
            'confidence': 0.3,  # Low confidence in fallback
            'decision': 'ACCEPT' if heuristic_prob >= 0.60 else 'REJECT',
            'method': 'HEURISTIC_FALLBACK',
            'error': str(e)
        }
```

### 8.2 Model Staleness Check

```python
def validate_model_freshness(model_metadata: Dict) -> bool:
    """
    Check if model is too old (retrain if > 3 months).
    """
    from datetime import datetime, timedelta
    
    training_date = datetime.fromisoformat(model_metadata['training_date'])
    model_age = datetime.now() - training_date
    
    if model_age > timedelta(days=90):
        logger.warning(f"Model is {model_age.days} days old - consider retraining")
        return False
    
    return True
```

---

## 9. REAL-TIME MONITORING

### 9.1 Prediction Distribution Tracking

```python
class MLMonitor:
    def __init__(self):
        self.predictions_today = []
        self.acceptance_rate = 0.0
        self.avg_confidence = 0.0
    
    def track_prediction(self, prediction: Dict):
        """Log each prediction for monitoring."""
        self.predictions_today.append(prediction)
        
        # Update stats
        n = len(self.predictions_today)
        accepted = sum(1 for p in self.predictions_today if p['decision'] == 'ACCEPT')
        self.acceptance_rate = accepted / n
        self.avg_confidence = np.mean([p['confidence'] for p in self.predictions_today])
        
        # Alert if unusual
        if self.acceptance_rate > 0.90:
            logger.warning(f"High acceptance rate: {self.acceptance_rate:.1%}")
        if self.avg_confidence < 0.20:
            logger.warning(f"Low average confidence: {self.avg_confidence:.2f}")
    
    def get_daily_stats(self) -> Dict:
        return {
            'predictions': len(self.predictions_today),
            'acceptance_rate': self.acceptance_rate,
            'avg_confidence': self.avg_confidence,
            'timestamp': datetime.now().isoformat()
        }
```

---

## 10. MODEL VERSIONING & RETRAINING

### 10.1 Version Management

```python
MODEL_VERSIONS = {
    '1.0': {
        'training_date': '2025-09-01',
        'num_features': 30,
        'accuracy': 0.62,
        'status': 'DEPRECATED'
    },
    '1.5': {
        'training_date': '2025-12-01',
        'num_features': 30,
        'accuracy': 0.64,
        'status': 'CURRENT'
    },
    '2.0': {
        'training_date': '2026-03-01',
        'num_features': 30,
        'accuracy': 0.66,
        'status': 'CURRENT_PRODUCTION'
    }
}

# Use latest stable version for production
ACTIVE_MODEL = '2.0'
```

### 10.2 A/B Testing Framework

```python
def select_model_version(ab_test_config: Dict) -> str:
    """
    Route predictions to different model versions for A/B testing.
    """
    import hashlib
    
    signal_id = ab_test_config['signal_id']
    
    # Consistent hashing: same signal always uses same model
    hash_val = int(hashlib.md5(signal_id.encode()).hexdigest(), 16)
    
    if hash_val % 100 < 90:  # 90% to v2.0, 10% to v1.5
        return '2.0'  # Production
    else:
        return '1.5'  # Testing

# Track results separately for each model version
```

---

## 11. INTEGRATION WITH BRIDGE

ML engine will be wrapped in bridge module:

```python
# integration/mt5_bridge/ml_predictor.py

from ml.ml_engine import MLEngine

class BridgeMLPredictor:
    def __init__(self):
        self.ml_engine = MLEngine(
            model_path='ml/xgboost_model.pkl',
            config_path='ml/features_schema.json'
        )
    
    def score_signal(self, signal: Signal) -> SignalWithScore:
        """
        Wrapper for MT5 integration.
        Takes SMC signal, scores it, returns acceptance decision.
        """
        # Extract features
        features = signal.get_feature_vector()
        
        # Normalize
        normalized = normalize_features(features, self.means, self.stdevs)
        
        # Predict
        prediction = self.ml_engine.predict_trade_quality(normalized)
        
        # Attach to signal
        signal.ml_score = prediction['win_probability']
        signal.ml_decision = prediction['decision']
        signal.ml_confidence = prediction['confidence']
        
        return signal
```

---

## 12. NEXT STEPS

1. **FASE 2**: ML integration options documented in communication_comparison.md
2. **FASE 3**: ML engine placement in architecture diagram
3. **FASE 4**: ML schema defined (input/output contracts)
4. **FASE 5**: ml_predictor.py integrated in bridge module
5. **FASE 6**: MT5 EA receives P(win) score
6. **FASE 7**: Backtest validates ML predictions match Python
7. **FASE 8**: Roadmap includes ML model retraining schedule
