"""Earth solar geometry in local ENU and the high-precision ITRF93 frame."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, radians, sin
from typing import Iterable

import numpy as np

from ..solar.spice_geometry import (
    azimuth_elevation,
    local_basis,
    sun_position_fixed,
    utc_spice_string,
)
from ..schemas import Site
from .kernels import EarthKernelSet, furnished_kernels

WGS84_SEMI_MAJOR_M = 6378137.0
WGS84_INVERSE_FLATTENING = 298.257223563
WGS84_SEMI_MAJOR_KM = WGS84_SEMI_MAJOR_M / 1000.0
WGS84_FLATTENING = 1.0 / WGS84_INVERSE_FLATTENING
ITRF93_FRAME_ID = 13000


@dataclass(frozen=True)
class EarthSolarGeometry:
    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    solar_elevation_deg: float
    solar_azimuth_deg: float | None
    direction_ecef: tuple[float, float, float]
    frame: str = "ITRF93"


def _validate_site_and_time(site: Site, time_utc: datetime) -> None:
    if not isinstance(time_utc, datetime):
        raise TypeError("time_utc must be a datetime instance")
    if time_utc.tzinfo is None or time_utc.utcoffset() is None:
        raise ValueError("time_utc must be timezone-aware")
    if not np.isfinite(site.lat) or not -90.0 <= site.lat <= 90.0:
        raise ValueError("site latitude must be finite and between -90 and 90 degrees")
    if not np.isfinite(site.lon):
        raise ValueError("site longitude must be finite")
    if not np.isfinite(site.elevation_m):
        raise ValueError("site elevation must be finite")


def _coverage_contains(spice, coverage, et: float) -> bool:
    return any(
        float(spice.wnfetd(coverage, index)[0]) <= et
        <= float(spice.wnfetd(coverage, index)[1])
        for index in range(spice.wncard(coverage))
    )


def _validate_kernel_coverage(spice, kernels: EarthKernelSet, et: float, time_utc: datetime) -> None:
    for body_id, body_name in ((10, "Sun"), (399, "Earth")):
        coverage = spice.spkcov(str(kernels.planetary_spk), body_id)
        if not _coverage_contains(spice, coverage, et):
            raise ValueError(
                f"Earth planetary SPK {kernels.planetary_spk} does not cover {body_name} "
                f"(NAIF {body_id}) at {time_utc.isoformat()}"
            )
    orientation = spice.pckcov(str(kernels.earth_orientation_pck), 3000)
    if not _coverage_contains(spice, orientation, et):
        raise ValueError(
            f"Earth orientation PCK {kernels.earth_orientation_pck} does not cover "
            f"ITRF93 at {time_utc.isoformat()}"
        )


def _geometry_with_loaded_kernels(
    site: Site,
    time_utc: datetime,
    kernels: EarthKernelSet,
    spice,
) -> EarthSolarGeometry:
    utc = time_utc.astimezone(timezone.utc)
    et = float(spice.str2et(utc_spice_string(utc)))
    _validate_kernel_coverage(spice, kernels, et, utc)

    if spice.namfrm(kernels.frame) != ITRF93_FRAME_ID:
        raise ValueError("The furnished kernels do not resolve ITRF93 frame ID 13000")
    radii_dim, earth_radii = spice.bodvrd("EARTH", "RADII", 3)
    if int(radii_dim) != 3:
        raise ValueError(f"SPICE returned {radii_dim} Earth radii; expected 3")
    earth_radii = np.asarray(earth_radii, dtype=float)
    if earth_radii.shape != (3,) or not np.isfinite(earth_radii).all() or np.any(earth_radii <= 0):
        raise ValueError("SPICE returned invalid Earth radii from the generic PCK")

    latitude = radians(site.lat)
    longitude = radians(site.lon)
    site_fixed = np.asarray(
        spice.georec(
            longitude,
            latitude,
            site.elevation_m / 1000.0,
            WGS84_SEMI_MAJOR_KM,
            WGS84_FLATTENING,
        ),
        dtype=float,
    )
    sun_fixed = sun_position_fixed(spice, et, kernels.frame, "EARTH")
    sun_from_site = sun_fixed - site_fixed

    up = np.array([
        cos(latitude) * cos(longitude),
        cos(latitude) * sin(longitude),
        sin(latitude),
    ])
    east, north = local_basis(site.lon, up)
    local = np.array([
        float(np.dot(sun_from_site, east)),
        float(np.dot(sun_from_site, north)),
        float(np.dot(sun_from_site, up)),
    ])
    elevation, azimuth = azimuth_elevation(local)
    direction_norm = float(np.linalg.norm(sun_from_site))
    if not np.isfinite(direction_norm) or direction_norm == 0.0:
        raise ValueError("SPICE produced an invalid Earth-to-Sun direction")

    return EarthSolarGeometry(
        time_utc=utc,
        latitude_deg=float(site.lat),
        longitude_deg=float(site.lon),
        solar_elevation_deg=elevation,
        solar_azimuth_deg=azimuth,
        direction_ecef=tuple(float(value / direction_norm) for value in sun_from_site),
        frame=kernels.frame,
    )


def earth_sun_series(
    site: Site,
    times_utc: Iterable[datetime],
    kernels: EarthKernelSet,
) -> list[EarthSolarGeometry]:
    """Return geometric topocentric Earth solar geometry for UTC instants.

    Azimuth is clockwise from geodetic north, angles are degrees, and the Sun
    vector is geometric (no light-time, stellar-aberration, or atmospheric
    refraction correction). ``Site.elevation_m`` is WGS84 ellipsoidal height.
    """
    observations = list(times_utc)
    for instant in observations:
        _validate_site_and_time(site, instant)
        utc_spice_string(instant)
    if not observations:
        return []

    with furnished_kernels(kernels) as spice:
        return [
            _geometry_with_loaded_kernels(site, instant, kernels, spice)
            for instant in observations
        ]


def earth_sun_geometry(
    site: Site,
    time_utc: datetime,
    kernels: EarthKernelSet,
) -> EarthSolarGeometry:
    """Return geometric Sun elevation/azimuth and an ITRF93 unit direction.

    WGS84 geodetic coordinates are converted to ITRF93 rectangular coordinates
    using the WGS84 ellipsoid. Angles are geometric, without refraction.
    """
    return earth_sun_series(site, (time_utc,), kernels)[0]
