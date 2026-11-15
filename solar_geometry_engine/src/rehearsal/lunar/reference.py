"""Topocentric solar geometry for a selected point on the lunar surface.

Angles are geometric (no atmospheric refraction), and azimuth is measured
clockwise from lunar-frame north: 0=N, 90=E, 180=S, 270=W.
The default frame is MOON_ME (Mean Earth / rotation-axis), suitable for the
common selenographic mapping convention. MOON_PA is also supported when the
input coordinates are defined in that frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, radians, sin, sqrt
from typing import Iterable, Literal

import numpy as np

from .kernels import LunarKernelSet, furnished_kernels
from ..solar.spice_geometry import (
    azimuth_elevation as _azimuth_elevation,
    local_basis as _local_basis,
    subsolar_coordinates,
    sun_position_fixed,
    utc_spice_string as _utc_spice_string,
)

LunarLatitudeType = Literal["planetocentric", "planetographic"]


@dataclass(frozen=True)
class LunarSolarGeometry:
    """Solar geometry seen by an observer at one lunar surface location."""

    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    frame: str
    latitude_type: str
    solar_elevation_deg: float
    solar_azimuth_deg: float | None
    solar_zenith_deg: float
    solar_incidence_deg: float
    sun_above_geometric_horizon: bool
    subsolar_latitude_deg: float
    subsolar_longitude_deg: float
    sun_distance_km: float


@dataclass(frozen=True)
class LunarSunDirection:
    """Moon-to-Sun unit vector expressed in a lunar body-fixed frame."""

    time_utc: datetime
    frame: str
    direction_fixed: tuple[float, float, float]
    sun_distance_km: float
    ephemeris_time_seconds: float | None = None


def _surface_point_and_normal(
    lat_deg: float,
    lon_deg: float,
    altitude_m: float,
    radii_km: np.ndarray,
    latitude_type: LunarLatitudeType,
    spice,
) -> tuple[np.ndarray, np.ndarray]:
    """Return body-fixed site position (km) and ellipsoid outward normal."""
    if not np.isfinite(lat_deg) or not -90.0 <= lat_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(lon_deg):
        raise ValueError("longitude_deg must be finite")
    if not np.isfinite(altitude_m):
        raise ValueError("altitude_m must be finite")
    if latitude_type not in ("planetocentric", "planetographic"):
        raise ValueError("latitude_type must be 'planetocentric' or 'planetographic'")

    radii = np.asarray(radii_km, dtype=float)
    if radii.shape != (3,) or not np.all(np.isfinite(radii)) or np.any(radii <= 0.0):
        raise ValueError("radii_km must contain three finite, positive radii")
    a, b, c = (float(v) for v in radii)
    lat, lon = radians(lat_deg), radians(lon_deg)
    altitude_km = altitude_m / 1000.0

    if latitude_type == "planetographic":
        # georec accepts geodetic latitude, east-positive longitude, altitude,
        # equatorial radius, and flattening. The Moon's reference ellipsoid is
        # rotationally symmetric to the precision used by the PCK radii.
        if not np.isclose(a, b, rtol=0.0, atol=1e-9):
            raise ValueError("planetographic conversion requires equal equatorial radii")
        point = np.asarray(spice.georec(lon, lat, altitude_km, a, (a - c) / a), dtype=float)
    else:
        # Selenographic planetocentric latitude/longitude define a ray from the
        # body centre. Intersect that ray with the triaxial reference ellipsoid.
        direction = np.array([cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)])
        scale = 1.0 / sqrt(
            (direction[0] / a) ** 2
            + (direction[1] / b) ** 2
            + (direction[2] / c) ** 2
        )
        point = direction * (scale + altitude_km)

    normal = np.asarray(spice.surfnm(a, b, c, point), dtype=float)
    normal /= np.linalg.norm(normal)
    return point, normal


def _geometry_with_loaded_kernels(
    latitude_deg: float,
    longitude_deg: float,
    time_utc: datetime,
    *,
    altitude_m: float,
    frame: str,
    latitude_type: LunarLatitudeType,
    spice,
) -> LunarSolarGeometry:
    utc_text = _utc_spice_string(time_utc)
    et = float(spice.str2et(utc_text))
    radii_dim, radii = spice.bodvrd("MOON", "RADII", 3)
    if int(radii_dim) != 3:
        raise ValueError(f"SPICE returned {radii_dim} lunar radii; expected 3")
    radii = np.asarray(radii, dtype=float)
    site_fixed, up = _surface_point_and_normal(
        latitude_deg, longitude_deg, altitude_m, radii, latitude_type, spice
    )

    sun_fixed = sun_position_fixed(spice, et, frame, "MOON")
    sun_from_site = sun_fixed - site_fixed

    east, north = _local_basis(longitude_deg, up)
    local = np.array([
        float(np.dot(sun_from_site, east)),
        float(np.dot(sun_from_site, north)),
        float(np.dot(sun_from_site, up)),
    ])
    elevation, azimuth = _azimuth_elevation(local)

    # Subsolar coordinates are the direction from lunar centre to Sun, expressed
    # in the same body-fixed frame (planetocentric convention).
    sun_norm = float(np.linalg.norm(sun_from_site))
    subsolar_lat, subsolar_lon = subsolar_coordinates(sun_fixed)

    return LunarSolarGeometry(
        time_utc=time_utc.astimezone(timezone.utc),
        latitude_deg=float(latitude_deg),
        longitude_deg=float(longitude_deg),
        altitude_m=float(altitude_m),
        frame=frame,
        latitude_type=latitude_type,
        solar_elevation_deg=float(elevation),
        solar_azimuth_deg=None if azimuth is None else float(azimuth),
        solar_zenith_deg=float(90.0 - elevation),
        solar_incidence_deg=float(90.0 - elevation),
        sun_above_geometric_horizon=bool(elevation > 0.0),
        subsolar_latitude_deg=float(subsolar_lat),
        subsolar_longitude_deg=float(subsolar_lon),
        sun_distance_km=sun_norm,
    )


def lunar_sun_geometry(
    latitude_deg: float,
    longitude_deg: float,
    time_utc: datetime,
    kernels: LunarKernelSet,
    *,
    altitude_m: float = 0.0,
    frame: Literal["MOON_ME", "MOON_PA"] = "MOON_ME",
    latitude_type: LunarLatitudeType = "planetocentric",
) -> LunarSolarGeometry:
    """Calculate the Sun's local geometric elevation and azimuth on the Moon.

    The Sun's SPICE position is calculated relative to the Moon at the requested
    epoch (no light-time or stellar-aberration correction), transformed into the
    selected high-accuracy lunar body-fixed frame, and differenced against the
    actual observer position. This gives a surface-topocentric direction rather
    than treating the observer as being at the lunar centre.

    The selected frame must match the coordinate reference of the supplied
    latitude/longitude. For high-accuracy orientation, load a DE-matched binary
    lunar PCK and lunar FK; do not substitute IAU_MOON.
    """
    if frame not in ("MOON_ME", "MOON_PA"):
        raise ValueError("frame must be 'MOON_ME' or 'MOON_PA'")
    if latitude_type not in ("planetocentric", "planetographic"):
        raise ValueError("latitude_type must be 'planetocentric' or 'planetographic'")
    if not np.isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg):
        raise ValueError("longitude_deg must be finite")
    if not np.isfinite(altitude_m):
        raise ValueError("altitude_m must be finite")
    if not isinstance(time_utc, datetime):
        raise TypeError("time_utc must be a datetime instance")
    _utc_spice_string(time_utc)  # validate timezone before loading global kernels

    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise RuntimeError("Install spiceypy to calculate lunar reference geometry") from exc

    with furnished_kernels(kernels):
        return _geometry_with_loaded_kernels(
            latitude_deg, longitude_deg, time_utc,
            altitude_m=altitude_m, frame=frame,
            latitude_type=latitude_type, spice=spice,
        )

def lunar_sun_series(
    latitude_deg: float,
    longitude_deg: float,
    times_utc: Iterable[datetime],
    kernels: LunarKernelSet,
    **kwargs,
) -> list[LunarSolarGeometry]:
    """Calculate lunar solar geometry for multiple instants.

    The supplied kernels are furnished once for the entire series, avoiding
    repeated global kernel-pool mutation. The results retain UTC timestamps.
    """
    frame = kwargs.pop("frame", "MOON_ME")
    latitude_type = kwargs.pop("latitude_type", "planetocentric")
    altitude_m = kwargs.pop("altitude_m", 0.0)
    if kwargs:
        raise TypeError(f"unexpected keyword argument(s): {', '.join(kwargs)}")
    if frame not in ("MOON_ME", "MOON_PA"):
        raise ValueError("frame must be 'MOON_ME' or 'MOON_PA'")
    if latitude_type not in ("planetocentric", "planetographic"):
        raise ValueError("latitude_type must be 'planetocentric' or 'planetographic'")
    if not np.isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg) or not np.isfinite(altitude_m):
        raise ValueError("longitude_deg and altitude_m must be finite")
    instants = list(times_utc)
    for instant in instants:
        if not isinstance(instant, datetime):
            raise TypeError("every item in times_utc must be a datetime instance")
        _utc_spice_string(instant)
    if not instants:
        return []
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise RuntimeError("Install spiceypy to calculate lunar reference geometry") from exc
    with furnished_kernels(kernels):
        return [
            _geometry_with_loaded_kernels(
                latitude_deg, longitude_deg, instant,
                altitude_m=altitude_m, frame=frame,
                latitude_type=latitude_type, spice=spice,
            )
            for instant in instants
        ]


def lunar_sun_direction_fixed(
    time_utc: datetime,
    kernels: LunarKernelSet,
    *,
    frame: Literal["MOON_ME", "MOON_PA"] = "MOON_ME",
) -> LunarSunDirection:
    """Return the geometric Moon-to-Sun direction in a lunar fixed frame."""
    return lunar_sun_direction_series_fixed((time_utc,), kernels, frame=frame)[0]


def lunar_sun_direction_series_fixed(
    times_utc: Iterable[datetime],
    kernels: LunarKernelSet,
    *,
    frame: Literal["MOON_ME", "MOON_PA"] = "MOON_ME",
) -> list[LunarSunDirection]:
    """Return Moon-to-Sun vectors for multiple instants with one kernel load."""
    if frame not in ("MOON_ME", "MOON_PA"):
        raise ValueError("frame must be 'MOON_ME' or 'MOON_PA'")
    instants = list(times_utc)
    for instant in instants:
        if not isinstance(instant, datetime):
            raise TypeError("every item in times_utc must be a datetime instance")
        _utc_spice_string(instant)
    if not instants:
        return []
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise RuntimeError("Install spiceypy to calculate lunar reference geometry") from exc

    with furnished_kernels(kernels):
        results = []
        for instant in instants:
            et = float(spice.str2et(_utc_spice_string(instant)))
            vector = sun_position_fixed(spice, et, frame, "MOON")
            if vector.shape != (3,) or not np.all(np.isfinite(vector)):
                raise ValueError("SPICE returned an invalid Moon-to-Sun position")
            distance = float(np.linalg.norm(vector))
            if not np.isfinite(distance) or distance == 0.0:
                raise ValueError("SPICE returned a zero or invalid Moon-to-Sun distance")
            direction = tuple(float(value) for value in vector / distance)
            results.append(
                LunarSunDirection(
                    time_utc=instant.astimezone(timezone.utc),
                    frame=frame,
                    direction_fixed=direction,
                    sun_distance_km=distance,
                    ephemeris_time_seconds=et,
                )
            )
        return results
