"""Local topographic relief: highest minus lowest elevation inside a moving window."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .._util import mask_border, odd


def window_pixels(window_m: float, pixel_size_m: float) -> int:
    return odd(max(1, round(window_m / pixel_size_m)))


def local_relief(z: np.ndarray, window_px: int) -> np.ndarray:
    """Relief map in metres. NaN where the centre is NaN or the window runs off the patch."""
    valid = np.isfinite(z)
    hi = ndimage.maximum_filter(np.where(valid, z, -np.inf), size=window_px, mode="nearest")
    lo = ndimage.minimum_filter(np.where(valid, z, np.inf), size=window_px, mode="nearest")
    out = np.where(valid & np.isfinite(hi) & np.isfinite(lo), hi - lo, np.nan)
    return mask_border(out, window_px // 2)
