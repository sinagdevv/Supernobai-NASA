"""Mars direct-solar illumination on the MEGR radial surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from ..solar.spice_geometry import (
    _SPICE_POOL_LOCK,
    furnished_spice_kernels,
    utc_spice_string,
)
from . import _illumination_numba as _numba
from .mola import (
    MOLA_PIXELS_PER_DEGREE,
    MOLA_SHAPE,
    MarsMolaGeometricWindow,
    _sha256,
)
from .mola_frame import (
    MarsMolaCurrentFrameWindow,
    MarsMolaFrameSolution,
    MarsMolaFrameTransform,
)
from .reference import MarsKernelSet


_CURRENT_FRAME = "IAU_MARS"
_CURRENT_FRAME_ID = 10014
_MARS_CENTER_ID = 499
_DEFAULT_SOURCE_ID = "unspecified Mars radial surface"


def _unmasked_array(value: np.ndarray, name: str, dtype: np.dtype) -> np.ndarray:
    masked = np.ma.asarray(value)
    if np.ma.getmaskarray(masked).any():
        raise ValueError(
            f"{name} must use explicit validity masks rather than masked-array cells"
        )
    if dtype == np.dtype(np.bool_) and not np.issubdtype(masked.dtype, np.bool_):
        raise ValueError(f"{name} must contain boolean values")
    return np.array(masked.data, dtype=dtype, copy=True)


class MarsIlluminationClass(IntEnum):
    """Direct-solar classification values, aligned with the other Layer 4 engines."""

    NO_DATA = -1
    UNKNOWN = 0
    ILLUMINATED = 1
    TERRAIN_OBSTRUCTED = 2
    SURFACE_FACING_AWAY = 3
    INSUFFICIENT_COVERAGE = 4


class MarsRayStatus(IntEnum):
    """Reason a direct-solar ray did or did not receive a definitive class."""

    NO_DATA = -1
    UNKNOWN = 0
    SEARCH_LIMIT_REACHED = 1
    OBSTRUCTION_FOUND = 2
    DEM_BOUNDARY = 3
    TERRAIN_NODATA = 4
    OBSERVATION_GAP = 5
    NORMAL_BOUNDARY = 6
    NORMAL_NODATA = 7
    SURFACE_FACING_AWAY = 8
    VERTICAL_SUN = 9
    GRID_DEGENERATE = 10
    RAY_STEP_LIMIT = 11


@dataclass(frozen=True)
class MarsSunDirectionFixed:
    """Geometric Mars-centered Sun position in the current SPICE body-fixed frame."""

    time_utc: datetime
    frame: str
    direction_fixed: tuple[float, float, float]
    sun_distance_km: float
    ephemeris_time_seconds: float
    spice_toolkit_version: str
    source_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.time_utc, datetime):
            raise TypeError("time_utc must be a datetime instance")
        utc_spice_string(self.time_utc)
        if self.frame != _CURRENT_FRAME:
            raise ValueError(f"frame must be {_CURRENT_FRAME!r}")
        direction = np.asarray(self.direction_fixed, dtype=np.float64)
        if direction.shape != (3,) or not np.all(np.isfinite(direction)):
            raise ValueError("direction_fixed must contain three finite components")
        norm = float(np.linalg.norm(direction))
        if not np.isfinite(norm) or abs(norm - 1.0) > 1e-10:
            raise ValueError("direction_fixed must be a normalized unit vector")
        if not np.isfinite(self.sun_distance_km) or self.sun_distance_km <= 0.0:
            raise ValueError("sun_distance_km must be finite and positive")
        if not np.isfinite(self.ephemeris_time_seconds):
            raise ValueError("ephemeris_time_seconds must be finite")
        if not self.spice_toolkit_version.strip():
            raise ValueError("spice_toolkit_version must be specified")
        object.__setattr__(
            self, "time_utc", self.time_utc.astimezone(timezone.utc)
        )
        object.__setattr__(
            self, "direction_fixed", tuple(float(value) for value in direction)
        )
        object.__setattr__(
            self, "source_metadata", MappingProxyType(dict(self.source_metadata))
        )

    @property
    def position_fixed_km(self) -> tuple[float, float, float]:
        return tuple(
            value * self.sun_distance_km for value in self.direction_fixed
        )


@dataclass(frozen=True)
class MarsIlluminationTerrain:
    """Epoch-specific current-frame radial surface and independent validity masks."""

    longitude_deg: np.ndarray
    latitude_deg: np.ndarray
    radial_distance_m: np.ndarray
    surface_valid_mask: np.ndarray
    observation_coverage_mask: np.ndarray
    elevation_valid_mask: np.ndarray
    reference_radii_m: tuple[float, float, float]
    frame: str = _CURRENT_FRAME
    source_dataset_id: str = _DEFAULT_SOURCE_ID
    source_metadata: Mapping[str, str] = field(default_factory=dict)
    source_windows: tuple[MarsMolaCurrentFrameWindow, ...] = ()

    def __post_init__(self) -> None:
        if self.frame != _CURRENT_FRAME:
            raise ValueError(f"frame must be {_CURRENT_FRAME!r}")
        arrays = {
            "longitude_deg": _unmasked_array(
                self.longitude_deg, "longitude_deg", np.dtype(np.float64)
            ),
            "latitude_deg": _unmasked_array(
                self.latitude_deg, "latitude_deg", np.dtype(np.float64)
            ),
            "radial_distance_m": _unmasked_array(
                self.radial_distance_m, "radial_distance_m", np.dtype(np.float64)
            ),
            "surface_valid_mask": _unmasked_array(
                self.surface_valid_mask, "surface_valid_mask", np.dtype(np.bool_)
            ),
            "observation_coverage_mask": _unmasked_array(
                self.observation_coverage_mask,
                "observation_coverage_mask",
                np.dtype(np.bool_),
            ),
            "elevation_valid_mask": _unmasked_array(
                self.elevation_valid_mask, "elevation_valid_mask", np.dtype(np.bool_)
            ),
        }
        shape = arrays["radial_distance_m"].shape
        if len(shape) != 2 or min(shape) < 3:
            raise ValueError("Mars illumination terrain must be at least 3 by 3")
        for name, array in arrays.items():
            if array.shape != shape:
                raise ValueError(f"{name} must match the radial surface shape")
            array.setflags(write=False)
            object.__setattr__(self, name, array)
        valid = arrays["surface_valid_mask"]
        if np.any(arrays["observation_coverage_mask"] & ~valid):
            raise ValueError("observed terrain cells must have a valid radial surface")
        if np.any(valid):
            if not np.isfinite(arrays["longitude_deg"][valid]).all():
                raise ValueError("valid surface cells require finite longitudes")
            latitudes = arrays["latitude_deg"][valid]
            if not np.isfinite(latitudes).all() or np.any(np.abs(latitudes) > 90.0):
                raise ValueError("valid surface cells require latitudes in [-90, 90]")
            radii = arrays["radial_distance_m"][valid]
            if not np.isfinite(radii).all() or np.any(radii <= 0.0):
                raise ValueError("valid surface cells require positive finite radii")
        reference_radii = tuple(float(value) for value in self.reference_radii_m)
        if (
            len(reference_radii) != 3
            or not np.all(np.isfinite(reference_radii))
            or min(reference_radii) <= 0.0
        ):
            raise ValueError("reference_radii_m must contain three positive finite radii")
        if not self.source_dataset_id.strip():
            raise ValueError("source_dataset_id must be specified")
        object.__setattr__(self, "reference_radii_m", reference_radii)
        object.__setattr__(
            self, "source_metadata", MappingProxyType(dict(self.source_metadata))
        )
        object.__setattr__(self, "source_windows", tuple(self.source_windows))

    @property
    def shape(self) -> tuple[int, int]:
        return self.radial_distance_m.shape

    @classmethod
    def from_mola_windows(
        cls, windows: Sequence[MarsMolaCurrentFrameWindow]
    ) -> "MarsIlluminationTerrain":
        """Join contiguous MOLA windows, including separate sides of the 0/360 seam."""
        windows = tuple(windows)
        if not windows:
            raise ValueError("at least one current-frame MOLA window is required")
        first = windows[0]
        if not isinstance(first, MarsMolaCurrentFrameWindow):
            raise TypeError("windows must contain MarsMolaCurrentFrameWindow values")
        first_source = first.source_window
        first_solution = first.solution
        if (
            first_solution.source_frame_id != _CURRENT_FRAME_ID
            or first_solution.target_frame_id != _CURRENT_FRAME_ID
            or first_solution.source_center_id != _MARS_CENTER_ID
            or first_solution.target_center_id != _MARS_CENTER_ID
            or first_solution.source_frame_class != 2
            or first_solution.target_frame_class != 2
        ):
            raise ValueError("MOLA windows must be transformed into current IAU_MARS/499")
        next_column = first_source.column_offset
        total_width = 0
        longitude: list[np.ndarray] = []
        latitude: list[np.ndarray] = []
        radius: list[np.ndarray] = []
        surface_valid: list[np.ndarray] = []
        coverage: list[np.ndarray] = []
        elevation_valid: list[np.ndarray] = []
        for index, window in enumerate(windows):
            if not isinstance(window, MarsMolaCurrentFrameWindow):
                raise TypeError("windows must contain MarsMolaCurrentFrameWindow values")
            source = window.source_window
            solution = window.solution
            if (
                solution.source_frame_id != _CURRENT_FRAME_ID
                or solution.target_frame_id != _CURRENT_FRAME_ID
                or solution.source_center_id != _MARS_CENTER_ID
                or solution.target_center_id != _MARS_CENTER_ID
                or solution.source_frame_class != 2
                or solution.target_frame_class != 2
            ):
                raise ValueError("MOLA windows must be transformed into current IAU_MARS/499")
            if (
                source.row_offset != first_source.row_offset
                or source.terrain_patch.shape[0] != first_source.terrain_patch.shape[0]
            ):
                raise ValueError("MOLA windows must have identical row coverage")
            if source.column_offset != next_column:
                raise ValueError(
                    "MOLA windows must be contiguous in west-to-east order, "
                    "with longitude wrapping at 360 degrees"
                )
            if window.solution.time_utc != first_solution.time_utc:
                raise ValueError("all MOLA windows must use the same transform epoch")
            if (
                window.solution.mola_pck_sha256 != first_solution.mola_pck_sha256
                or window.solution.current_pck_sha256
                != first_solution.current_pck_sha256
                or window.solution.leap_seconds_sha256
                != first_solution.leap_seconds_sha256
            ):
                raise ValueError("all MOLA windows must use the same pinned kernels")
            if not np.array_equal(
                window.solution.rotation_current_from_mola,
                first_solution.rotation_current_from_mola,
            ):
                raise ValueError("all MOLA windows must use the same frame rotation")
            counts_mask = window.observation_coverage_mask
            if counts_mask is None:
                raise ValueError(
                    "MOLA observation-count coverage is required for illumination"
                )
            radial = np.asarray(window.radial_distance_m, dtype=np.float64)
            lon = np.asarray(window.longitude_deg, dtype=np.float64)
            lat = np.asarray(window.latitude_deg, dtype=np.float64)
            is_valid = (
                np.isfinite(radial)
                & (radial > 0.0)
                & np.isfinite(lon)
                & np.isfinite(lat)
                & (np.abs(lat) <= 90.0)
            )
            longitude.append(lon)
            latitude.append(lat)
            radius.append(radial)
            surface_valid.append(is_valid)
            coverage.append(np.asarray(counts_mask, dtype=np.bool_))
            elevation_valid.append(window.terrain_patch.valid_mask)
            total_width += source.terrain_patch.shape[1]
            next_column = (source.column_offset + source.terrain_patch.shape[1]) % MOLA_SHAPE[1]
            if index < len(windows) - 1 and total_width > MOLA_SHAPE[1]:
                raise ValueError("MOLA windows may not repeat global columns")
        if total_width > MOLA_SHAPE[1]:
            raise ValueError("MOLA illumination terrain may not exceed one global wrap")

        provenance = dict(first.provenance)
        provenance.update(
            {
                "surface_position_source": "MEGR90N000FB mean planetary radius",
                "surface_position_units": "m",
                "surface_frame": _CURRENT_FRAME,
                "surface_frame_center": "NAIF 499",
                "elevation_use": (
                    "MEGT GMM3-areoid-relative values retained only as an independent "
                    "validity mask; never added to MEGR radii"
                ),
                "mola_origin_to_naif_center_tie": (
                    "assumed coincident by source/frame convention; independently "
                    "unverified, no translation applied"
                ),
                "mola_window_count": str(len(windows)),
                "mola_window_rows": ";".join(
                    f"{window.source_window.row_offset}:"
                    f"{window.source_window.row_offset + window.source_window.terrain_patch.shape[0]}"
                    for window in windows
                ),
                "mola_window_columns": ";".join(
                    f"{window.source_window.column_offset}:"
                    f"{window.source_window.column_offset + window.source_window.terrain_patch.shape[1]}"
                    for window in windows
                ),
                "mola_global_grid_shape": f"{MOLA_SHAPE[0]}x{MOLA_SHAPE[1]}",
                "mola_pixels_per_degree": str(MOLA_PIXELS_PER_DEGREE),
            }
        )
        return cls(
            longitude_deg=np.concatenate(longitude, axis=1),
            latitude_deg=np.concatenate(latitude, axis=1),
            radial_distance_m=np.concatenate(radius, axis=1),
            surface_valid_mask=np.concatenate(surface_valid, axis=1),
            observation_coverage_mask=np.concatenate(coverage, axis=1),
            elevation_valid_mask=np.concatenate(elevation_valid, axis=1),
            reference_radii_m=first_solution.current_radii_m,
            source_dataset_id="MGS MOLA MEGR90N000FB",
            source_metadata=provenance,
            source_windows=windows,
        )


@dataclass(frozen=True)
class MarsIlluminationResult:
    """Per-cell illumination, solar angles, coverage, and provenance."""

    classification: np.ndarray
    surface_valid_mask: np.ndarray
    elevation_valid_mask: np.ndarray
    observation_coverage_mask: np.ndarray
    normal_valid_mask: np.ndarray
    coverage_mask: np.ndarray
    ray_status: np.ndarray
    surface_normals_fixed: np.ndarray
    solar_elevation_deg: np.ndarray
    solar_azimuth_deg: np.ndarray
    solar_incidence_deg: np.ndarray
    observation_time_utc: datetime
    frame: str
    solar_direction_fixed: tuple[float, float, float]
    sun_distance_km: float
    ephemeris_time_seconds: float
    source_dataset_id: str
    source_metadata: Mapping[str, str]
    processing_parameters: Mapping[str, str | float | int]

    def __post_init__(self) -> None:
        if not isinstance(self.observation_time_utc, datetime):
            raise TypeError("observation_time_utc must be a datetime instance")
        utc_spice_string(self.observation_time_utc)
        if self.frame != _CURRENT_FRAME:
            raise ValueError(f"frame must be {_CURRENT_FRAME!r}")
        shape = np.asarray(self.classification).shape
        array_names = (
            "classification",
            "surface_valid_mask",
            "elevation_valid_mask",
            "observation_coverage_mask",
            "normal_valid_mask",
            "coverage_mask",
            "ray_status",
            "solar_elevation_deg",
            "solar_azimuth_deg",
            "solar_incidence_deg",
        )
        for name in array_names:
            array = np.asarray(getattr(self, name))
            if array.shape != shape:
                raise ValueError(f"{name} must match the classification shape")
            array.setflags(write=False)
            object.__setattr__(self, name, array)
        normals = np.asarray(self.surface_normals_fixed, dtype=np.float64)
        if normals.shape != shape + (3,):
            raise ValueError("surface_normals_fixed must have shape (rows, cols, 3)")
        normals.setflags(write=False)
        object.__setattr__(self, "surface_normals_fixed", normals)
        object.__setattr__(
            self,
            "observation_time_utc",
            self.observation_time_utc.astimezone(timezone.utc),
        )
        object.__setattr__(
            self, "solar_direction_fixed", tuple(float(v) for v in self.solar_direction_fixed)
        )
        if not np.isfinite(self.sun_distance_km) or self.sun_distance_km <= 0.0:
            raise ValueError("sun_distance_km must be finite and positive")
        if not np.isfinite(self.ephemeris_time_seconds):
            raise ValueError("ephemeris_time_seconds must be finite")
        object.__setattr__(self, "source_metadata", MappingProxyType(dict(self.source_metadata)))
        object.__setattr__(
            self, "processing_parameters", MappingProxyType(dict(self.processing_parameters))
        )

    @property
    def valid_mask(self) -> np.ndarray:
        return self.surface_valid_mask

    @property
    def shape(self) -> tuple[int, int]:
        return self.classification.shape

    @property
    def total_cells(self) -> int:
        return int(self.classification.size)

    @property
    def valid_terrain_cells(self) -> int:
        return int(np.count_nonzero(self.surface_valid_mask))

    @property
    def observed_terrain_cells(self) -> int:
        return int(
            np.count_nonzero(
                self.surface_valid_mask & self.observation_coverage_mask
            )
        )

    @property
    def illuminated_cells(self) -> int:
        return int(np.count_nonzero(self.classification == MarsIlluminationClass.ILLUMINATED))

    @property
    def terrain_obstructed_cells(self) -> int:
        return int(
            np.count_nonzero(self.classification == MarsIlluminationClass.TERRAIN_OBSTRUCTED)
        )

    @property
    def surface_facing_away_cells(self) -> int:
        return int(
            np.count_nonzero(self.classification == MarsIlluminationClass.SURFACE_FACING_AWAY)
        )

    @property
    def insufficient_coverage_cells(self) -> int:
        return int(
            np.count_nonzero(self.classification == MarsIlluminationClass.INSUFFICIENT_COVERAGE)
        )

    @property
    def no_data_cells(self) -> int:
        return int(np.count_nonzero(self.classification == MarsIlluminationClass.NO_DATA))

    @property
    def unknown_cells(self) -> int:
        return int(np.count_nonzero(self.classification == MarsIlluminationClass.UNKNOWN))


def _spk_covers_epoch(spice, spk_path: Path, body_id: int, et: float) -> bool:
    coverage = spice.spkcov(str(spk_path), body_id)
    return any(
        start <= et <= stop
        for start, stop in (
            spice.wnfetd(coverage, index)
            for index in range(int(spice.wncard(coverage)))
        )
    )


def mars_sun_direction_fixed(
    time_utc: datetime,
    kernels: MarsKernelSet,
    frame_transform: MarsMolaFrameTransform,
    *,
    frame_solution: MarsMolaFrameSolution | None = None,
) -> MarsSunDirectionFixed:
    """Return the SPICE geometric Sun vector in the exact current MOLA target frame.

    ET is obtained from the pinned MOLA frame solution. The current PCK is
    furnished alone with the supplied ephemeris SPKs so that a second PCK cannot
    override the current ``IAU_MARS`` orientation.
    """
    if not isinstance(kernels, MarsKernelSet):
        raise TypeError("kernels must be a MarsKernelSet instance")
    if not isinstance(frame_transform, MarsMolaFrameTransform):
        raise TypeError("frame_transform must be a MarsMolaFrameTransform instance")
    if not isinstance(time_utc, datetime):
        raise TypeError("time_utc must be a datetime instance")
    utc_spice_string(time_utc)
    if kernels.frame != _CURRENT_FRAME:
        raise ValueError(f"Mars kernel frame must be {_CURRENT_FRAME!r}")
    kernels.validate()
    if kernels.mars_system_spk is None:
        raise ValueError("Mars kernel set must include the center-499 Mars system SPK")
    solution = frame_solution or frame_transform.solution_at(time_utc)
    normalized_time = time_utc.astimezone(timezone.utc)
    if solution.time_utc != normalized_time:
        raise ValueError("frame_solution epoch must match time_utc")
    if (
        solution.source_frame_id != _CURRENT_FRAME_ID
        or solution.source_center_id != _MARS_CENTER_ID
        or solution.target_frame_id != _CURRENT_FRAME_ID
        or solution.target_center_id != _MARS_CENTER_ID
        or solution.source_frame_class != 2
        or solution.target_frame_class != 2
    ):
        raise ValueError("frame_solution does not describe the current Mars target frame")
    pinned_files = (
        (Path(frame_transform.kernels.leap_seconds), solution.leap_seconds_sha256),
        (Path(frame_transform.kernels.mola_orientation_pck), solution.mola_pck_sha256),
        (Path(frame_transform.kernels.current_orientation_pck), solution.current_pck_sha256),
    )
    for path, expected_hash in pinned_files:
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ValueError(f"pinned Mars frame kernel changed: {path}")
    current_pck = Path(frame_transform.kernels.current_orientation_pck).resolve()
    current_pck_hash = solution.current_pck_sha256
    supplied_pcks = tuple(
        Path(path).resolve()
        for path in (kernels.orientation_pck, kernels.generic_pck)
        if path is not None
    )
    if not any(path.is_file() and _sha256(path) == current_pck_hash for path in supplied_pcks):
        raise ValueError(
            "MarsKernelSet must include the same pck00011 orientation used by "
            "MarsMolaFrameTransform"
        )

    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise RuntimeError("Install spiceypy to calculate Mars solar geometry") from exc

    with _SPICE_POOL_LOCK:
        if int(spice.ktotal("ALL")) != 0:
            raise RuntimeError(
                "Mars solar geometry requires an empty SPICE kernel pool; unload existing "
                "kernels and retry"
            )
        paths = (
            Path(kernels.planetary_spk),
            Path(kernels.mars_system_spk),
            current_pck,
        )
        with furnished_spice_kernels(paths):
            frame_id = int(spice.namfrm(_CURRENT_FRAME))
            center_id, frame_class, class_id = spice.frinfo(frame_id)
            if (
                frame_id != _CURRENT_FRAME_ID
                or int(center_id) != _MARS_CENTER_ID
                or int(frame_class) != 2
                or int(class_id) != _MARS_CENTER_ID
            ):
                raise ValueError("furnished PCK does not realize the expected IAU_MARS frame")
            dimension, radii_km = spice.bodvrd("MARS", "RADII", 3)
            radii_m = tuple(float(value) * 1000.0 for value in radii_km)
            if int(dimension) != 3 or not np.allclose(
                radii_m, solution.current_radii_m, rtol=0.0, atol=1e-6
            ):
                raise ValueError("furnished current PCK has unexpected Mars radii")
            planetary_spk = Path(kernels.planetary_spk).resolve()
            mars_spk = Path(kernels.mars_system_spk).resolve()
            if not _spk_covers_epoch(spice, planetary_spk, 10, solution.et):
                raise ValueError(
                    f"planetary SPK has no Sun (10) coverage at {normalized_time.isoformat()}"
                )
            if not _spk_covers_epoch(spice, mars_spk, _MARS_CENTER_ID, solution.et):
                raise ValueError(
                    f"Mars system SPK has no center-499 coverage at {normalized_time.isoformat()}"
                )
            sun_position, _ = spice.spkpos(
                "SUN", solution.et, _CURRENT_FRAME, "NONE", "MARS"
            )
            sun_position = np.asarray(sun_position, dtype=np.float64)
            toolkit_version = str(spice.tkvrsn("TOOLKIT"))
    distance_km = float(np.linalg.norm(sun_position))
    if (
        sun_position.shape != (3,)
        or not np.all(np.isfinite(sun_position))
        or not np.isfinite(distance_km)
        or distance_km <= 0.0
    ):
        raise ValueError("SPICE returned an invalid Mars-centered Sun vector")
    direction = sun_position / distance_km
    return MarsSunDirectionFixed(
        time_utc=normalized_time,
        frame=_CURRENT_FRAME,
        direction_fixed=tuple(float(value) for value in direction),
        sun_distance_km=distance_km,
        ephemeris_time_seconds=solution.et,
        spice_toolkit_version=toolkit_version,
        source_metadata={
            "solar_ephemeris": str(Path(kernels.planetary_spk).resolve()),
            "mars_center_ephemeris": str(Path(kernels.mars_system_spk).resolve()),
            "current_orientation_pck": str(current_pck),
            "current_orientation_pck_sha256": current_pck_hash,
            "frame": _CURRENT_FRAME,
            "frame_id": str(_CURRENT_FRAME_ID),
            "observer": "MARS center, NAIF 499",
            "aberration_correction": "NONE; geometric",
            "ephemeris_time_source": "pinned naif0012.tls via MarsMolaFrameSolution",
            "spice_toolkit_version": toolkit_version,
        },
    )


def mars_illumination_raster(
    terrain: MarsIlluminationTerrain,
    sun: MarsSunDirectionFixed,
    *,
    max_distance_m: float = 50000.0,
    dot_tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 1.0,
) -> MarsIlluminationResult:
    """Classify a current-frame MOLA radial surface using Numba horizon rays."""
    if not isinstance(terrain, MarsIlluminationTerrain):
        raise TypeError("terrain must be a MarsIlluminationTerrain instance")
    if not isinstance(sun, MarsSunDirectionFixed):
        raise TypeError("sun must be a MarsSunDirectionFixed instance")
    if terrain.frame != sun.frame:
        raise ValueError("terrain and Sun direction must use the same body-fixed frame")
    if terrain.source_windows and any(
        window.solution.time_utc != sun.time_utc for window in terrain.source_windows
    ):
        raise ValueError("MOLA frame transformation and solar geometry epochs must match")
    if not np.isfinite(max_distance_m) or max_distance_m <= 0.0:
        raise ValueError("max_distance_m must be finite and positive")
    if not np.isfinite(dot_tolerance) or dot_tolerance < 0.0:
        raise ValueError("dot_tolerance must be finite and non-negative")
    if not np.isfinite(obstruction_tolerance_m) or obstruction_tolerance_m < 0.0:
        raise ValueError("obstruction_tolerance_m must be finite and non-negative")
    if not _numba.is_available():
        raise RuntimeError(
            "Numba is required for Mars terrain illumination; install the 'performance' extra"
        )

    positions = _numba.surface_positions(
        terrain.radial_distance_m,
        terrain.longitude_deg,
        terrain.latitude_deg,
        terrain.surface_valid_mask,
    )
    sun_position_m = np.asarray(sun.position_fixed_km, dtype=np.float64) * 1000.0
    (
        classification,
        normal_valid,
        coverage,
        ray_status,
        normals,
        solar_elevation,
        solar_azimuth,
        solar_incidence,
    ) = _numba.classify_grid(
        positions,
        terrain.longitude_deg,
        terrain.surface_valid_mask,
        terrain.observation_coverage_mask,
        sun_position_m,
        np.asarray(terrain.reference_radii_m, dtype=np.float64),
        float(max_distance_m),
        float(dot_tolerance),
        float(obstruction_tolerance_m),
    )
    source_metadata = dict(terrain.source_metadata)
    for key, value in sun.source_metadata.items():
        source_metadata[f"solar_{key}"] = value
    return MarsIlluminationResult(
        classification=classification,
        surface_valid_mask=terrain.surface_valid_mask,
        elevation_valid_mask=terrain.elevation_valid_mask,
        observation_coverage_mask=terrain.observation_coverage_mask,
        normal_valid_mask=normal_valid,
        coverage_mask=coverage,
        ray_status=ray_status,
        surface_normals_fixed=normals,
        solar_elevation_deg=solar_elevation,
        solar_azimuth_deg=solar_azimuth,
        solar_incidence_deg=solar_incidence,
        observation_time_utc=sun.time_utc,
        frame=terrain.frame,
        solar_direction_fixed=sun.direction_fixed,
        sun_distance_km=sun.sun_distance_km,
        ephemeris_time_seconds=sun.ephemeris_time_seconds,
        source_dataset_id=terrain.source_dataset_id,
        source_metadata=source_metadata,
        processing_parameters={
            "engine": "Mars-specific parallel Numba",
            "surface_source": "MEGR90N000FB absolute mean planetary radius",
            "surface_geometry": (
                "radial MOLA surface points; current Mars ellipsoid used only for "
                "local reference normals"
            ),
            "max_distance_m": float(max_distance_m),
            "dot_tolerance": float(dot_tolerance),
            "obstruction_tolerance_m": float(obstruction_tolerance_m),
            "normal_method": "four-neighbor 3D radial-surface cross product",
            "horizon_method": "supercover DDA in current-frame tangent coordinates",
            "coverage_policy": (
                "zero-observation cells are unknown; ray gaps and patch boundaries "
                "remain insufficient coverage"
            ),
            "elevation_policy": (
                "MEGT GMM3-areoid values are not combined with MEGR radii"
            ),
            "origin_tie": (
                "MOLA origin assumed coincident with NAIF center 499; unverified"
            ),
            "numba_available": int(_numba.is_available()),
            "numba_thread_count": _numba.thread_count() or 0,
        },
    )


def mars_mola_illumination_raster(
    windows: MarsMolaGeometricWindow | Sequence[MarsMolaGeometricWindow],
    time_utc: datetime,
    kernels: MarsKernelSet,
    frame_transform: MarsMolaFrameTransform,
    *,
    max_distance_m: float = 50000.0,
    dot_tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 1.0,
) -> MarsIlluminationResult:
    """Transform native MEGR windows and run the complete single-epoch pipeline."""
    if isinstance(windows, MarsMolaGeometricWindow):
        source_windows = (windows,)
    else:
        source_windows = tuple(windows)
    if not source_windows or not all(
        isinstance(window, MarsMolaGeometricWindow) for window in source_windows
    ):
        raise TypeError("windows must contain one or more MarsMolaGeometricWindow values")
    transformed = tuple(
        frame_transform.transform_window(window, time_utc)
        for window in source_windows
    )
    terrain = MarsIlluminationTerrain.from_mola_windows(transformed)
    sun = mars_sun_direction_fixed(
        time_utc,
        kernels,
        frame_transform,
        frame_solution=transformed[0].solution,
    )
    return mars_illumination_raster(
        terrain,
        sun,
        max_distance_m=max_distance_m,
        dot_tolerance=dot_tolerance,
        obstruction_tolerance_m=obstruction_tolerance_m,
    )
