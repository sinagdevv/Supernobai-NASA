"""Shared SPICE state, kernel, and local-angle mechanics."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
from threading import RLock
from typing import Iterator

import numpy as np

from .conventions import normalize_azimuth


_SPICE_POOL_LOCK = RLock()


def utc_spice_string(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware; pass an explicit UTC offset")
    utc = value.astimezone(timezone.utc)
    if utc.microsecond:
        return utc.strftime("%Y %b %d %H:%M:%S.%f UTC")
    return utc.strftime("%Y %b %d %H:%M:%S UTC")


@contextmanager
def furnished_spice_kernels(
    paths: tuple[Path, ...],
    *,
    allow_duplicate_paths: bool = False,
    missing_dependency_message: str = "SPICE geometry requires spiceypy.",
) -> Iterator[object]:
    """Furnish a validated kernel list under one process-wide SPICE lock."""
    resolved_paths = tuple(Path(path).resolve() for path in paths)
    if len(set(resolved_paths)) != len(resolved_paths):
        if not allow_duplicate_paths:
            raise ValueError("A SPICE kernel path was supplied more than once")
        resolved_paths = tuple(dict.fromkeys(resolved_paths))

    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(missing_dependency_message) from exc

    with _SPICE_POOL_LOCK:
        loaded: list[Path] = []
        try:
            for path in resolved_paths:
                spice.furnsh(str(path))
                loaded.append(path)
            yield spice
        finally:
            cleanup_errors: list[tuple[Path, Exception]] = []
            for path in reversed(loaded):
                try:
                    spice.unload(str(path))
                except Exception as exc:  # pragma: no cover
                    cleanup_errors.append((path, exc))
            if cleanup_errors:
                details = "; ".join(f"{path}: {error}" for path, error in cleanup_errors)
                import sys

                if sys.exc_info()[0] is None:
                    raise RuntimeError(f"Failed to unload SPICE kernel(s): {details}")


def sun_position_fixed(spice, et: float, frame: str, observer: str) -> np.ndarray:
    """Return the observer-centred Sun position in a body-fixed frame, km."""
    position, _ = spice.spkpos("SUN", et, frame, "NONE", observer)
    return np.asarray(position, dtype=float)


def local_basis(longitude_deg: float, up: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build east/north unit vectors tangent to a body's surface."""
    up = np.asarray(up, dtype=float)
    up_norm = np.linalg.norm(up)
    if not np.isfinite(up_norm) or up_norm == 0.0:
        raise ValueError("surface normal must be finite and nonzero")
    up = up / up_norm

    lon = radians(longitude_deg)
    east_reference = np.array([-sin(lon), cos(lon), 0.0])
    east = east_reference - np.dot(east_reference, up) * up
    east_norm = np.linalg.norm(east)
    if east_norm < 1e-12:
        raise ValueError("could not construct a local east direction")
    east /= east_norm
    north = np.cross(up, east)
    north /= np.linalg.norm(north)
    return east, north


def azimuth_elevation(vector_local: np.ndarray) -> tuple[float, float | None]:
    """Convert local [east, north, up] to elevation and north-clockwise azimuth."""
    components = np.asarray(vector_local, dtype=float)
    if components.shape != (3,) or not np.all(np.isfinite(components)):
        raise ValueError("local direction must contain three finite components")

    east, north_axis, up = (float(value) for value in components)
    horizontal = hypot(east, north_axis)
    magnitude = float(np.linalg.norm(components))
    if magnitude == 0.0:
        raise ValueError("local direction vector must be nonzero")
    elevation = degrees(atan2(up, horizontal))
    if horizontal <= 8.0 * np.finfo(float).eps * magnitude:
        return float(elevation), None
    azimuth = float(normalize_azimuth(degrees(atan2(east, north_axis))))
    return float(elevation), float(azimuth)


def subsolar_coordinates(sun_position_fixed: np.ndarray) -> tuple[float, float]:
    """Return planetocentric subsolar latitude and east-positive longitude."""
    vector = np.asarray(sun_position_fixed, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError("body-centred Sun position must contain three finite components")
    latitude = degrees(atan2(vector[2], hypot(vector[0], vector[1])))
    longitude = degrees(atan2(vector[1], vector[0]))
    return float(latitude), float(longitude)
