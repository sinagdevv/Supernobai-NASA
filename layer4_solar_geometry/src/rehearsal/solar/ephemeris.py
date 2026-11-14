"""SPICE-backed Earth solar elevation and azimuth for time arrays."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from ..earth.geometry import earth_sun_series
from ..earth.kernels import EarthKernelSet
from ..schemas import Site


def _datetime64_to_utc_datetime(value: np.datetime64) -> datetime:
    if np.isnat(value):
        raise ValueError("times_utc must not contain NaT values")
    microseconds = int(value.astype("datetime64[us]").astype(np.int64))
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return epoch + timedelta(microseconds=microseconds)


def sun_alt_az(
    lat: float,
    lon: float,
    elevation_m: float,
    times_utc: np.ndarray,
    kernels: EarthKernelSet,
) -> tuple[np.ndarray, np.ndarray]:
    """Return geometric Sun elevation and north-clockwise azimuth in degrees.

    The input times are UTC ``datetime64`` values. Solar positions use SPICE
    geometric states and ITRF93 Earth orientation; refraction is not applied.
    Azimuth is NaN when the Sun is exactly vertical and azimuth is undefined.
    """
    times = np.asarray(times_utc).astype("datetime64[us]")
    instants = [_datetime64_to_utc_datetime(value) for value in times.reshape(-1)]
    site = Site(id="earth-solar-position", lat=lat, lon=lon, tz="UTC", elevation_m=elevation_m)
    geometries = earth_sun_series(site, instants, kernels)
    elevations = np.asarray(
        [geometry.solar_elevation_deg for geometry in geometries],
        dtype=float,
    ).reshape(times.shape)
    azimuths = np.asarray(
        [
            np.nan if geometry.solar_azimuth_deg is None else geometry.solar_azimuth_deg
            for geometry in geometries
        ],
        dtype=float,
    ).reshape(times.shape)
    return elevations, azimuths
