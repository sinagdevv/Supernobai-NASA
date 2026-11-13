"""Scale-dependent surface roughness.

rms_height: the surface is detrended by subtracting its moving-window mean, then the RMS of what
is left is taken over the same window. A uniformly tilted plane therefore has zero roughness:
regional slope is reported by the slope metrics, not double-counted here.

Roughness always belongs to a scale. The value at a 30 m grid says nothing about boulders.
"""

from __future__ import annotations

import numpy as np

from .._util import mask_border, nan_uniform, stats
from ..models import RoughnessMetrics

DEFAULT_WINDOW_PX = 5


def rms_height(z: np.ndarray, window_px: int = DEFAULT_WINDOW_PX) -> np.ndarray:
    residual = z - nan_uniform(z, window_px)
    return np.sqrt(np.maximum(nan_uniform(residual**2, window_px), 0.0))


def tri(z: np.ndarray) -> np.ndarray:
    """Terrain Ruggedness Index: root of summed squared differences to the 8 neighbours (Riley et al. 1999)."""
    out = np.full(z.shape, np.nan)
    if z.shape[0] < 3 or z.shape[1] < 3:
        return out
    centre = z[1:-1, 1:-1]
    total = np.zeros_like(centre)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            if dr == 1 and dc == 1:
                continue
            total += (z[dr : dr + centre.shape[0], dc : dc + centre.shape[1]] - centre) ** 2
    out[1:-1, 1:-1] = np.sqrt(total)
    return mask_border(out, 1)


def roughness_metrics(z: np.ndarray, pixel_size_m: float, window_px: int = DEFAULT_WINDOW_PX) -> RoughnessMetrics:
    return RoughnessMetrics(
        window_m=window_px * pixel_size_m,
        rms_height_m=stats(rms_height(z, window_px), 3),
        tri_m=stats(tri(z), 3),
    )
