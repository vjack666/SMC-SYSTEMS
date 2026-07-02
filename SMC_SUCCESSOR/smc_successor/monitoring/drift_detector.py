from __future__ import annotations

import math
from typing import Any


class DriftDetector:
    def __init__(self, threshold: float = 0.2, n_bins: int = 10) -> None:
        self._threshold = threshold
        self._n_bins = n_bins

    def check(
        self, features: dict[str, list[float]], reference: dict[str, list[float]]
    ) -> dict[str, float]:
        result: dict[str, float] = {}
        for key in features:
            if key not in reference:
                continue
            result[key] = self._psi(reference[key], features[key])
        return result

    def is_drift(self, psi_values: dict[str, float]) -> bool:
        return any(v > self._threshold for v in psi_values.values())

    def _psi(self, reference: list[float], actual: list[float]) -> float:
        if not reference or not actual:
            return 0.0

        sorted_ref = sorted(reference)
        n = len(sorted_ref)
        n_bins = min(self._n_bins, n)
        bins: list[float] = []
        for i in range(1, n_bins):
            idx = int(i * n / n_bins)
            if idx >= n:
                idx = n - 1
            bins.append(sorted_ref[idx])
        bins.append(math.inf)

        ref_counts = [0] * n_bins
        act_counts = [0] * n_bins

        for val in reference:
            for i, b in enumerate(bins[:-1]):
                if val <= b:
                    ref_counts[i] += 1
                    break
            else:
                ref_counts[-1] += 1

        for val in actual:
            for i, b in enumerate(bins[:-1]):
                if val <= b:
                    act_counts[i] += 1
                    break
            else:
                act_counts[-1] += 1

        psi = 0.0
        for i in range(n_bins):
            ref_pct = ref_counts[i] / n
            act_pct = act_counts[i] / len(actual)
            if ref_pct == 0.0:
                ref_pct = 0.0001
            if act_pct == 0.0:
                act_pct = 0.0001
            psi += (act_pct - ref_pct) * math.log(act_pct / ref_pct)

        return round(psi, 6)
