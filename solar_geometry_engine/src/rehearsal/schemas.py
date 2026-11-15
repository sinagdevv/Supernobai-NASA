"""Data contracts for Layer 4. Agree on these with the Layer 3 and Layer 5 owners."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import numpy as np


@dataclass(frozen=True)
class Site:
    id: str
    lat: float            # degrees, north positive
    lon: float            # degrees, EAST positive
    tz: str               # IANA name, e.g. "America/Phoenix"
    elevation_m: float = 0.0


@dataclass
class SunSeries:
    """Sun series; azimuth is north-clockwise degrees, NaN if geometrically undefined."""
    site: Site
    times_utc: np.ndarray       # datetime64[s]
    elevation_deg: np.ndarray   # geometric (no refraction), sun centre
    azimuth_deg: np.ndarray
    step_minutes: float


@dataclass(frozen=True)
class Window:
    start_utc: datetime         # tz-aware UTC
    end_utc: datetime           # last qualifying sample
    duration_min: float         # n_samples * step
    mean_azimuth_deg: float     # circular mean, north-clockwise
    min_elevation_deg: float
    max_elevation_deg: float
    truncated_start: bool       # window runs into the start of the analysed range
    truncated_end: bool         # ... or the end; true length may be longer
