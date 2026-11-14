"""Mars solar geometry with explicit body-fixed frame and SPICE metadata.

This module does not try to reuse the Earth WGS84 or lunar MOON_ME assumptions.
It establishes the Mars-specific reference contract first: body-fixed frame,
reference radii from the active SPICE PCK, and geometry in Mars-centered local
coordinates.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, radians, sin, sqrt
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from ..solar.spice_geometry import (
    azimuth_elevation as _azimuth_elevation,
    furnished_spice_kernels,
    local_basis as _local_basis,
    subsolar_coordinates,
    sun_position_fixed,
    utc_spice_string as _utc_spice_string,
)


@dataclass(frozen=True)
class MarsKernelSet:
    """Required local SPICE kernels for Mars reference geometry.

    The user must supply the files. This package does not silently download large
    planetary kernels or assume a generic frame can be used without a proper
    matching PCK. A single local PCK may satisfy both the orientation and radii
    metadata when the active kernel set uses one combined file. The frame name
    must still match the orientation information in that kernel set.

    The Mars ephemeris must include the Mars center state (NAIF body 499). The
    stock DE440S solar-system ephemeris only covers the barycenter chain; it does
    not satisfy the required Mars center state for direct Sun-to-Mars geometry.
    """

    leap_seconds: Path
    planetary_spk: Path
    mars_system_spk: Path | None = None
    orientation_pck: Path | None = None
    generic_pck: Path | None = None
    frame: str = "IAU_MARS"

    def paths(self) -> tuple[Path, ...]:
        file_values: list[Path] = [
            Path(self.leap_seconds),
            Path(self.planetary_spk),
        ]
        for value in (self.mars_system_spk, self.orientation_pck, self.generic_pck):
            if value is not None:
                file_values.append(Path(value))
        unique_paths: list[Path] = []
        seen: set[Path] = set()
        for path in file_values:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)
        return tuple(unique_paths)

    def validate(self) -> None:
        if not self.frame.strip():
            raise ValueError("frame must be specified")
        if self.mars_system_spk is None:
            raise ValueError(
                "Mars kernel sets must include a Mars system SPK with the Mars center state "
                "(for example, mar099s.bsp)"
            )
        if self.orientation_pck is None and self.generic_pck is None:
            raise ValueError("At least one Mars PCK file must be supplied")
        missing = [str(path) for path in self.paths() if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError("Missing SPICE kernel file(s): " + ", ".join(missing))
        empty = [str(path) for path in self.paths() if Path(path).stat().st_size == 0]
        if empty:
            raise ValueError("Empty SPICE kernel file(s): " + ", ".join(empty))


@contextmanager
def furnished_kernels(kernel_set: MarsKernelSet) -> Iterator[None]:
    """Load and unload a Mars kernel set in a process-global SPICE pool."""
    kernel_set.validate()
    with furnished_spice_kernels(
        kernel_set.paths(),
        allow_duplicate_paths=True,
        missing_dependency_message="Install spiceypy to calculate Mars reference geometry",
    ):
        yield


@dataclass(frozen=True)
class MarsBodyModel:
    """Mars body model and reference metadata from the active SPICE kernel set."""

    frame: str = "IAU_MARS"
    source: str = "SPICE PCK / NAIF planetary kernels"
    equatorial_radius_km: float | None = None
    polar_radius_km: float | None = None
    reference_radius_km: float | None = None
    notes: str = (
        "Use the radii from the active SPICE PCK and the body-fixed frame supplied by that "
        "same PCK. Do not assume Earth WGS84 or lunar frame definitions."
    )


@dataclass(frozen=True)
class MarsSolarGeometry:
    """Solar geometry seen by an observer on the Martian surface."""

    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    frame: str
    solar_elevation_deg: float
    solar_azimuth_deg: float | None
    solar_zenith_deg: float
    solar_incidence_deg: float
    sun_above_geometric_horizon: bool
    subsolar_latitude_deg: float
    subsolar_longitude_deg: float
    sun_distance_km: float


def _surface_point_and_normal(
    lat_deg: float,
    lon_deg: float,
    altitude_m: float,
    radii_km: np.ndarray,
    spice,
) -> tuple[np.ndarray, np.ndarray]:
    """Return body-fixed site position and outward normal for a triaxial ellipsoid."""
    if not np.isfinite(lat_deg) or not -90.0 <= lat_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(lon_deg):
        raise ValueError("longitude_deg must be finite")
    if not np.isfinite(altitude_m):
        raise ValueError("altitude_m must be finite")

    radii = np.asarray(radii_km, dtype=float)
    if radii.shape != (3,) or not np.all(np.isfinite(radii)) or np.any(radii <= 0.0):
        raise ValueError("radii_km must contain three finite, positive radii")

    a, b, c = (float(v) for v in radii)
    lat = radians(lat_deg)
    lon = radians(lon_deg)
    altitude_km = altitude_m / 1000.0

    direction = np.array([
        cos(lat) * cos(lon),
        cos(lat) * sin(lon),
        sin(lat),
    ])
    denom = sqrt((direction[0] / a) ** 2 + (direction[1] / b) ** 2 + (direction[2] / c) ** 2)
    if denom == 0.0:
        raise ValueError("could not compute the Mars surface intersection direction")
    point = direction * ((1.0 / denom) + altitude_km)
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
    spice,
) -> MarsSolarGeometry:
    """Compute Mars solar geometry using the currently loaded SPICE kernels."""
    utc_text = _utc_spice_string(time_utc)
    et = float(spice.str2et(utc_text))

    radii_dim, radii = spice.bodvrd("MARS", "RADII", 3)
    if int(radii_dim) != 3:
        raise ValueError(f"SPICE returned {radii_dim} Mars radii; expected 3")

    radii = np.asarray(radii, dtype=float)
    point, normal = _surface_point_and_normal(latitude_deg, longitude_deg, altitude_m, radii, spice)
    sun_fixed = sun_position_fixed(spice, et, frame, "MARS")
    sun_from_site = sun_fixed - point

    east, north = _local_basis(longitude_deg, normal)
    local = np.array([
        float(np.dot(sun_from_site, east)),
        float(np.dot(sun_from_site, north)),
        float(np.dot(sun_from_site, normal)),
    ])
    elevation, azimuth = _azimuth_elevation(local)
    sun_norm = float(np.linalg.norm(sun_from_site))
    subsolar_lat, subsolar_lon = subsolar_coordinates(sun_fixed)

    return MarsSolarGeometry(
        time_utc=time_utc.astimezone(timezone.utc),
        latitude_deg=float(latitude_deg),
        longitude_deg=float(longitude_deg),
        altitude_m=float(altitude_m),
        frame=frame,
        solar_elevation_deg=float(elevation),
        solar_azimuth_deg=None if azimuth is None else float(azimuth),
        solar_zenith_deg=float(90.0 - elevation),
        solar_incidence_deg=float(90.0 - elevation),
        sun_above_geometric_horizon=bool(elevation > 0.0),
        subsolar_latitude_deg=float(subsolar_lat),
        subsolar_longitude_deg=float(subsolar_lon),
        sun_distance_km=float(sun_norm),
    )


def mars_solar_geometry(
    latitude_deg: float,
    longitude_deg: float,
    time_utc: datetime,
    kernels: MarsKernelSet,
    *,
    altitude_m: float = 0.0,
    frame: str | None = None,
) -> MarsSolarGeometry:
    """Compute the Mars local solar geometry for a single observer instant.

    The kernel set must match the frame and PCK used for the Mars reference.
    Values are geometric and do not include atmospheric refraction.
    """
    if not isinstance(kernels, MarsKernelSet):
        raise TypeError("kernels must be a MarsKernelSet instance")
    if frame is None:
        frame = kernels.frame
    if frame != kernels.frame:
        raise ValueError(
            f"frame {frame!r} does not match the MarsKernelSet frame {kernels.frame!r}"
        )
    if not isinstance(time_utc, datetime):
        raise TypeError("time_utc must be a datetime instance")
    if not np.isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg):
        raise ValueError("longitude_deg must be finite")
    if not np.isfinite(altitude_m):
        raise ValueError("altitude_m must be finite")

    with furnished_kernels(kernels):
        try:
            import spiceypy as spice
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise RuntimeError("Install spiceypy to calculate Mars reference geometry") from exc
        return _geometry_with_loaded_kernels(
            latitude_deg, longitude_deg, time_utc,
            altitude_m=altitude_m,
            frame=frame,
            spice=spice,
        )


def mars_solar_series(
    latitude_deg: float,
    longitude_deg: float,
    times_utc: Iterable[datetime],
    kernels: MarsKernelSet,
    *,
    altitude_m: float = 0.0,
    frame: str | None = None,
) -> list[MarsSolarGeometry]:
    """Return a list of Mars solar values for a sequence of UTC instants."""
    if not isinstance(kernels, MarsKernelSet):
        raise TypeError("kernels must be a MarsKernelSet instance")
    if frame is None:
        frame = kernels.frame
    if frame != kernels.frame:
        raise ValueError(
            f"frame {frame!r} does not match the MarsKernelSet frame {kernels.frame!r}"
        )
    if not np.isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg):
        raise ValueError("longitude_deg must be finite")
    if not np.isfinite(altitude_m):
        raise ValueError("altitude_m must be finite")

    observations = list(times_utc)
    for instant in observations:
        if not isinstance(instant, datetime):
            raise TypeError("every element of times_utc must be a datetime instance")
        _utc_spice_string(instant)

    if not observations:
        return []

    with furnished_kernels(kernels):
        try:
            import spiceypy as spice
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise RuntimeError("Install spiceypy to calculate Mars reference geometry") from exc
        return [
            _geometry_with_loaded_kernels(
                latitude_deg,
                longitude_deg,
                instant,
                altitude_m=altitude_m,
                frame=frame,
                spice=spice,
            )
            for instant in observations
        ]
