from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

import numpy as np
import pandas as pd
from pytest import MonkeyPatch

from signals.pipeline import ScalpingConfig, build_scalping_signals


def _fake_context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-02 00:00:00Z", "2024-01-02 00:05:00Z"]),
            "close": [1.10, 1.101],
            "atr": [0.001, 0.001],
            "bos_dir": [1, -1],
            "choch_dir": [0, 0],
            "signal_direction": [1, -1],
            "signal_confidence": [0.8, 0.9],
            "macro_direction": ["BULLISH", "BEARISH"],
        }
    )


def test_flag_off_does_not_mutate_signal_meta(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr("signals.pipeline.build_scalping_context", lambda *args, **kwargs: _fake_context())
    signals = build_scalping_signals(
        "EURUSD",
        data_dir=tmp_path,
        config=ScalpingConfig(use_mtf_structure_align=False),
    )
    assert len(signals) == 2
    assert all(s.meta is None for s in signals)


def test_flag_on_injects_tf_level_when_alignment_available(monkeypatch: MonkeyPatch, tmp_path: Path):
    context = _fake_context()
    monkeypatch.setattr("signals.pipeline.build_scalping_context", lambda *args, **kwargs: context)
    monkeypatch.setattr(
        "signals.pipeline._align_signals_tf_level",
        lambda *args, **kwargs: pd.Series(["HTF", "LTF"], index=context.index),
    )
    signals = build_scalping_signals(
        "EURUSD",
        data_dir=tmp_path,
        config=ScalpingConfig(use_mtf_structure_align=True),
    )
    assert signals[0].meta == {"tf_level": "HTF", "structure_event": "BOS"}
    # row 1 has bos_dir=-1 => BOS; tf_level from alignment still injects
    assert signals[1].meta["tf_level"] == "LTF"
    assert signals[1].meta["structure_event"] in {"BOS", "CHOCH"}


def test_flag_on_score_suave_sin_hard_block(monkeypatch: MonkeyPatch, tmp_path: Path):
    context = _fake_context()
    monkeypatch.setattr("signals.pipeline.build_scalping_context", lambda *args, **kwargs: context)
    monkeypatch.setattr(
        "signals.pipeline._align_signals_tf_level",
        lambda *args, **kwargs: pd.Series(["HTF", "LTF"], index=context.index),
    )
    signals_on = build_scalping_signals(
        "EURUSD",
        data_dir=tmp_path,
        config=ScalpingConfig(use_mtf_structure_align=True, tf_level_score_weights={"HTF": 0.20, "ITF": 0.10, "LTF": 0.00}),
    )
    monkeypatch.setattr("signals.pipeline._align_signals_tf_level", lambda *args, **kwargs: pd.Series([""] * 2, index=context.index))
    signals_off = build_scalping_signals(
        "EURUSD",
        data_dir=tmp_path,
        config=ScalpingConfig(use_mtf_structure_align=True),
    )
    assert len(signals_on) == len(signals_off)
    for a, b in zip(signals_on, signals_off):
        assert abs(a.confidence - b.confidence) <= 0.20 + 1e-9
