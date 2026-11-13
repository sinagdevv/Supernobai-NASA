"""Which analysis scales a dataset can honestly support.

Principle from the proposal: a 5 m lunar model and a 30 m Earth DEM cannot be compared at 5 m.
A scale is supported only if it is no finer than the dataset's native pixel size; finer data is
aggregated up, coarser data is never refined.
"""

from __future__ import annotations

from .io.raster import SCALE_SLACK
from .models import SkippedItem

COMMON_SCALES_M = [30.0, 60.0, 120.0, 240.0]


def is_supported(scale_m: float, native_pixel_size_m: float) -> bool:
    return scale_m >= SCALE_SLACK * native_pixel_size_m


def default_scales(native_pixel_size_m: float) -> list[float]:
    scales = [s for s in COMMON_SCALES_M if is_supported(s, native_pixel_size_m)]
    if scales:
        return scales
    base = float(round(native_pixel_size_m))
    return [base, base * 2, base * 4]


def choose_scales(requested: list[float] | None, native_pixel_size_m: float) -> tuple[list[float], list[SkippedItem]]:
    """Split requested scales into supported ones and skipped ones (with the reason)."""
    if not requested:
        return default_scales(native_pixel_size_m), []
    supported, skipped = [], []
    for s in sorted(set(float(x) for x in requested)):
        if s <= 0:
            skipped.append(SkippedItem(item=f"scale {s:g} m", code="invalid_request", reason="Scale must be positive."))
        elif is_supported(s, native_pixel_size_m):
            supported.append(s)
        else:
            skipped.append(
                SkippedItem(
                    item=f"scale {s:g} m",
                    code="scale_not_supported",
                    reason=f"Finer than the dataset's native pixel size ({native_pixel_size_m:.1f} m); not computed.",
                )
            )
    return supported, skipped
