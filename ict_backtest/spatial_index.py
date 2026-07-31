"""ict_backtest/spatial_index.py — Índice espacial 1D de intervalos de precio.

Uso ICT/SMC (sin indicadores):
  Indexar FVG u OB por su rango [lo, hi] para consultas de solape en O(k)
  candidatos en vez de O(n) lineal.

Estructura:
  - Buckets uniformes en el eje de precio (grid 1D).
  - Cada intervalo se inserta en todos los buckets que toca.
  - query_overlap(lo, hi, dir) → índices candidatos (puede haber falsos
    positivos de bucket; el caller confirma solape estricto).

Filtro temporal opcional: bar_min <= idx <= bar_max (lookback BPR).

NO usa ATR/RSI. Solo geometría de precio + índices de barra.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PriceIntervalIndex:
    """Grid 1D sobre el eje de precio.

    Parameters
    ----------
    p_min, p_max :
        Rango global de precios cubierto.
    bucket_size :
        Ancho de cada bucket en unidades de precio.
        Si <= 0 se deriva como (p_max-p_min) / n_buckets.
    n_buckets :
        Usado solo si bucket_size <= 0 (default 256).
    """

    p_min: float
    p_max: float
    bucket_size: float = 0.0
    n_buckets: int = 256
    # por bucket: listas paralelas idx, lo, hi, dir
    _idx: list[list[int]] = field(default_factory=list, repr=False)
    _lo: list[list[float]] = field(default_factory=list, repr=False)
    _hi: list[list[float]] = field(default_factory=list, repr=False)
    _dir: list[list[int]] = field(default_factory=list, repr=False)
    _ready: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if self.p_max < self.p_min:
            self.p_min, self.p_max = self.p_max, self.p_min
        span = self.p_max - self.p_min
        if span <= 0:
            span = 1e-12
            self.p_max = self.p_min + span
        if self.bucket_size <= 0:
            nb = max(1, int(self.n_buckets))
            object.__setattr__(self, "bucket_size", span / nb)
            object.__setattr__(self, "n_buckets", nb)
        else:
            nb = max(1, int(np.ceil(span / self.bucket_size)))
            object.__setattr__(self, "n_buckets", nb)
        object.__setattr__(self, "_idx", [[] for _ in range(self.n_buckets)])
        object.__setattr__(self, "_lo", [[] for _ in range(self.n_buckets)])
        object.__setattr__(self, "_hi", [[] for _ in range(self.n_buckets)])
        object.__setattr__(self, "_dir", [[] for _ in range(self.n_buckets)])
        object.__setattr__(self, "_ready", True)

    def _bucket(self, price: float) -> int:
        b = int((price - self.p_min) / self.bucket_size)
        if b < 0:
            return 0
        if b >= self.n_buckets:
            return self.n_buckets - 1
        return b

    def insert(self, idx: int, lo: float, hi: float, direction: int = 0) -> None:
        """Indexa un intervalo [lo, hi] en todos los buckets que intersecta."""
        if not (lo < hi):
            return
        b0 = self._bucket(lo)
        b1 = self._bucket(hi)
        if b1 < b0:
            b0, b1 = b1, b0
        for b in range(b0, b1 + 1):
            self._idx[b].append(idx)
            self._lo[b].append(lo)
            self._hi[b].append(hi)
            self._dir[b].append(int(direction))

    def insert_many(
        self,
        idxs: np.ndarray,
        los: np.ndarray,
        his: np.ndarray,
        dirs: np.ndarray,
    ) -> None:
        """Inserción batch desde arrays (solo entradas con dir!=0 y lo<hi)."""
        for k in range(len(idxs)):
            d = int(dirs[k])
            if d == 0:
                continue
            lo = float(los[k])
            hi = float(his[k])
            if lo < hi:
                self.insert(int(idxs[k]), lo, hi, d)

    def query_overlap(
        self,
        lo: float,
        hi: float,
        *,
        direction: int | None = None,
        bar_min: int | None = None,
        bar_max: int | None = None,
    ) -> list[tuple[int, float, float, int]]:
        """Candidatos que pueden solapar [lo, hi].

        Returns
        -------
        list of (idx, cand_lo, cand_hi, dir)
        Deduplica por idx. Confirmar solape estricto en el caller.
        """
        if not (lo < hi):
            return []
        b0 = self._bucket(lo)
        b1 = self._bucket(hi)
        if b1 < b0:
            b0, b1 = b1, b0
        seen: set[int] = set()
        out: list[tuple[int, float, float, int]] = []
        for b in range(b0, b1 + 1):
            for k, idx in enumerate(self._idx[b]):
                if idx in seen:
                    continue
                d = self._dir[b][k]
                if direction is not None and d != direction:
                    continue
                if bar_min is not None and idx < bar_min:
                    continue
                if bar_max is not None and idx > bar_max:
                    continue
                clo, chi = self._lo[b][k], self._hi[b][k]
                # rechazo barato antes de dedup costoso
                if clo < hi and chi > lo:
                    seen.add(idx)
                    out.append((idx, clo, chi, d))
        return out

    def query_best_overlap(
        self,
        lo: float,
        hi: float,
        *,
        direction: int,
        bar_min: int | None = None,
        bar_max: int | None = None,
        min_depth: float = 0.0,
    ) -> tuple[float, float, float] | None:
        """Mejor solape estricto por depth relativo al intervalo query.

        Returns (ov_lo, ov_hi, depth) o None.
        """
        size = hi - lo
        if size <= 0:
            return None
        best = None
        best_depth = -1.0
        for _idx, clo, chi, _d in self.query_overlap(
            lo, hi, direction=direction, bar_min=bar_min, bar_max=bar_max
        ):
            ov_lo = clo if clo > lo else lo
            ov_hi = chi if chi < hi else hi
            if ov_lo < ov_hi:
                depth = (ov_hi - ov_lo) / size
                if depth >= min_depth and depth > best_depth:
                    best_depth = depth
                    best = (ov_lo, ov_hi, depth)
        return best


def build_fvg_price_index(
    f_lo: np.ndarray,
    f_hi: np.ndarray,
    f_dir: np.ndarray,
    *,
    n_buckets: int = 256,
    bucket_size: float = 0.0,
) -> PriceIntervalIndex:
    """Construye índice espacial solo con FVG (dir != 0)."""
    mask = f_dir != 0
    if not np.any(mask):
        return PriceIntervalIndex(p_min=0.0, p_max=1.0, n_buckets=1)
    los = f_lo[mask]
    his = f_hi[mask]
    p_min = float(np.nanmin(los))
    p_max = float(np.nanmax(his))
    index = PriceIntervalIndex(
        p_min=p_min, p_max=p_max, bucket_size=bucket_size, n_buckets=n_buckets
    )
    idxs = np.nonzero(mask)[0].astype(np.int64)
    index.insert_many(idxs, f_lo, f_hi, f_dir)
    return index


def build_ob_price_index(
    o_lo: np.ndarray,
    o_hi: np.ndarray,
    o_dir: np.ndarray,
    *,
    n_buckets: int = 256,
    bucket_size: float = 0.0,
) -> PriceIntervalIndex:
    """Construye índice espacial de Order Blocks (dir != 0)."""
    return build_fvg_price_index(
        o_lo, o_hi, o_dir, n_buckets=n_buckets, bucket_size=bucket_size
    )
