from __future__ import annotations

import time

import pytest

from _progress import ProgressTracker


class TestProgressTracker:
    def test_init_defaults(self):
        p = ProgressTracker(total=100, desc="test")
        assert p.total == 100
        assert p.desc == "test"
        assert p.n == 0

    def test_update_increments(self):
        p = ProgressTracker(total=100)
        p.update(5)
        assert p.n == 5

    def test_update_multiple(self):
        p = ProgressTracker(total=100)
        p.update(10)
        p.update(20)
        assert p.n == 30

    def test_set_postfix(self):
        p = ProgressTracker(total=100)
        p.set_postfix(loss=0.5, acc=0.9)
        assert p._postfix == {"loss": 0.5, "acc": 0.9}

    def test_close_does_not_raise(self):
        p = ProgressTracker(total=10)
        p.update(10)
        p.close()

    def test_zero_total_does_not_divide_by_zero(self):
        p = ProgressTracker(total=0)
        p.update(1)
        p.close()

    def test_throttling_skips_render(self):
        p = ProgressTracker(total=100)
        p._last_print = time.time()
        p.update(1)
        assert p.n == 1

    def test_ascii_bar_format(self):
        p = ProgressTracker(total=10, ascii=True)
        assert p._ascii is True

    def test_non_ascii_bar_format(self):
        p = ProgressTracker(total=10, ascii=False)
        assert p._ascii is False
