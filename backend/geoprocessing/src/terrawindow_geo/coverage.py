"""How much of a patch actually has data."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .models import Coverage


def valid_fraction(z: np.ndarray) -> float:
    return float(np.isfinite(z).mean()) if z.size else 0.0


def summarize(z: np.ndarray, min_required: float, missing_sources: list[str] | None = None) -> Coverage:
    frac = valid_fraction(z)
    void = ~np.isfinite(z)
    largest = 0.0
    if void.any():
        labels, n = ndimage.label(void)
        largest = float(np.bincount(labels.ravel())[1:].max() / z.size) if n else 0.0
    return Coverage(
        valid_fraction=round(frac, 4),
        min_required=min_required,
        sufficient=frac >= min_required,
        largest_void_fraction=round(largest, 4),
        missing_sources=missing_sources or [],
    )
