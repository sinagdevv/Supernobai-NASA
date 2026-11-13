"""Small numeric helpers shared by the metric modules."""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from .models import Stats


def fnum(x, digits: int = 4) -> float | None:
    """JSON-safe float: NaN/inf become None so missing data never looks like a number."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    return round(x, digits)


def stats(a: np.ndarray, digits: int = 4) -> Stats:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return Stats()
    p = np.percentile(v, [10, 25, 50, 75, 90, 95, 99])
    return Stats(
        mean=fnum(v.mean(), digits),
        median=fnum(p[2], digits),
        std=fnum(v.std(), digits),
        p10=fnum(p[0], digits),
        p25=fnum(p[1], digits),
        p75=fnum(p[3], digits),
        p90=fnum(p[4], digits),
        p95=fnum(p[5], digits),
        p99=fnum(p[6], digits),
        min=fnum(v.min(), digits),
        max=fnum(v.max(), digits),
        n_valid=int(v.size),
    )


def nan_uniform(a: np.ndarray, size: int, min_valid: float = 0.75) -> np.ndarray:
    """Moving-window mean that ignores NaN.

    A cell is NaN in the output when fewer than `min_valid` of its window is valid, and the outer
    half-window border is always NaN so truncated (asymmetric) windows never bias the result.
    """
    valid = np.isfinite(a)
    total = ndimage.uniform_filter(np.where(valid, a, 0.0), size=size, mode="constant")
    weight = ndimage.uniform_filter(valid.astype(np.float64), size=size, mode="constant")
    out = np.full(a.shape, np.nan)
    ok = weight >= min_valid
    out[ok] = total[ok] / weight[ok]
    return mask_border(out, size // 2)


def mask_border(a: np.ndarray, n: int) -> np.ndarray:
    if n > 0:
        a[:n, :] = np.nan
        a[-n:, :] = np.nan
        a[:, :n] = np.nan
        a[:, -n:] = np.nan
    return a


def odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1
