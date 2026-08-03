"""T7 — Warm-up y disponibilidad del sesgo."""

from __future__ import annotations

import pytest

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.motor_cable.warmup import WarmupTracker


def test_not_available_before_warmup():
    tracker = WarmupTracker(SesgoConfig())
    state = tracker.state()

    for _ in range(19):
        state = tracker.record_closure("D1")

    assert state.available is False
    assert state.available_since is None


def test_available_after_warmup():
    tracker = WarmupTracker(SesgoConfig())

    for _ in range(20):
        tracker.record_closure("D1")
    for _ in range(60):
        tracker.record_closure("H4")
    for _ in range(100):
        tracker.record_closure("H1")
    state = tracker.record_closure("H1")

    assert state.available is True
    assert state.available_since is not None
    assert state.closed_counts == {"D1": 20, "H4": 60, "H1": 101}


def test_warmup_registers_activation_moment():
    tracker = WarmupTracker(SesgoConfig())
    before = tracker.state()
    assert before.available is False

    for _ in range(20):
        tracker.record_closure("D1")
    for _ in range(60):
        tracker.record_closure("H4")
    for _ in range(100):
        tracker.record_closure("H1")

    after = tracker.record_closure("H1")
    assert after.available is True
    assert after.available_since is not None
