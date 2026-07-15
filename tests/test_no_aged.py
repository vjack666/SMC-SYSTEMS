import pandas as pd

from detectors.bos import _track_bos_validity
from detectors.choch import _track_choch_validity
from detectors.ob import _track_ob_validity


def _bos_data(n=40):
    # BOS alcista en vela 1 (nivel 100); el low NUNCA baja de 100.
    # Nota: _track_bos_validity itera desde i=1 (range(1,n)), asi que el
    # BOS debe marcarse en i>=1, no en i=0. Sin cruce -> queda "active".
    df = pd.DataFrame({
        "bos_direction": [0, 1] + [0] * (n - 2),
        "bos_level": [float("nan"), 100.0] + [float("nan")] * (n - 2),
        "low": [99.0, 100.5] + [101.0 + i for i in range(n - 2)],
        "high": [100.0, 101.0] + [102.0 + i for i in range(n - 2)],
    })
    return df


def _choch_data(n=40):
    df = pd.DataFrame({
        "choch_signal": ["NONE", "CHOCH_BULLISH"] + ["NONE"] * (n - 2),
        "last_swing_low": [float("nan"), 100.0] + [float("nan")] * (n - 2),
        "last_swing_high": [float("nan")] * n,
        "close": [99.5, 100.5] + [101.0 + i for i in range(n - 2)],
    })
    return df


def _ob_data(n=40):
    df = pd.DataFrame({
        "ob_bullish": [False, True] + [False] * (n - 2),
        "ob_bearish": [False] * n,
        "ob_bottom": [float("nan"), 100.0] + [float("nan")] * (n - 2),
        "ob_top": [float("nan")] * n,
        "close": [99.5, 100.5] + [101.0 + i for i in range(n - 2)],
    })
    return df


def test_bos_sin_aged_queda_active():
    status, _ = _track_bos_validity(_bos_data(40))
    assert "aged" not in set(status.to_numpy()), f"aparecio aged: {set(status)}"
    assert status.iloc[-1] == "active", f"final={status.iloc[-1]}"


def test_choch_sin_aged_queda_active():
    status, _ = _track_choch_validity(_choch_data(40), swing_lookback=20)
    assert "aged" not in set(status.to_numpy())


def test_ob_sin_aged_queda_active():
    status, _ = _track_ob_validity(_ob_data(40))
    assert "aged" not in set(status.to_numpy())
