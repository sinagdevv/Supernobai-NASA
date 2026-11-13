"""Slope and aspect from a metric elevation grid (Horn 1981, the GDAL/ArcGIS default)."""

from __future__ import annotations

import numpy as np

from .._util import fnum, stats
from ..models import Histogram, SlopeMetrics

HIST_EDGES = np.arange(0.0, 91.0, 1.0)


def gradients(z: np.ndarray, pixel_size_m: float) -> tuple[np.ndarray, np.ndarray]:
    """(dz/d_east, dz/d_north). Row 0 is north. Border cells and cells touching NaN are NaN."""
    dzdx = np.full(z.shape, np.nan)
    dzdy = np.full(z.shape, np.nan)
    if z.shape[0] < 3 or z.shape[1] < 3:
        return dzdx, dzdy
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx[1:-1, 1:-1] = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel_size_m)
    dzdy[1:-1, 1:-1] = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * pixel_size_m)
    # The kernel skips the centre cell, so a void there must be masked explicitly.
    void = ~np.isfinite(z)
    dzdx[void] = np.nan
    dzdy[void] = np.nan
    return dzdx, dzdy


def slope_aspect(z: np.ndarray, pixel_size_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Slope in degrees from horizontal; aspect as the downslope azimuth, degrees clockwise from north."""
    dzdx, dzdy = gradients(z, pixel_size_m)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = np.degrees(np.arctan2(-dzdx, -dzdy)) % 360.0
    aspect[slope == 0] = np.nan  # flat cells have no direction
    return slope, aspect


def hillshade(z: np.ndarray, pixel_size_m: float, sun_azimuth_deg: float = 315.0, sun_elevation_deg: float = 45.0) -> np.ndarray:
    """Lambertian shading in [0, 1] for a sun at the given azimuth/elevation. No cast shadows (that is Layer 4)."""
    dzdx, dzdy = gradients(z, pixel_size_m)
    az, el = np.radians(sun_azimuth_deg), np.radians(sun_elevation_deg)
    sun = np.array([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)])
    norm = np.sqrt(dzdx**2 + dzdy**2 + 1)
    shade = (-dzdx * sun[0] - dzdy * sun[1] + sun[2]) / norm
    return np.clip(shade, 0, 1)


def slope_metrics(slope_deg: np.ndarray, pixel_size_m: float, thresholds_deg: list[float]) -> SlopeMetrics:
    v = slope_deg[np.isfinite(slope_deg)]
    counts, _ = np.histogram(v, bins=HIST_EDGES)
    total = max(1, v.size)
    rms = np.degrees(np.arctan(np.sqrt(np.mean(np.tan(np.radians(v)) ** 2)))) if v.size else None
    return SlopeMetrics(
        baseline_m=2 * pixel_size_m,
        stats=stats(slope_deg, 3),
        rms_slope_deg=fnum(rms, 3),
        fraction_steeper_than={f"{t:g}": round(float((v > t).sum() / total), 4) for t in thresholds_deg},
        histogram=Histogram(bin_edges_deg=HIST_EDGES.tolist(), fractions=[round(float(c / total), 5) for c in counts]),
    )
