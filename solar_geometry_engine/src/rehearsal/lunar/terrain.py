"""Layer 4 terrain input adapted from a Layer 3 in-memory elevation patch."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from math import acos, atan2, cos, degrees, isfinite, radians, sin, sqrt
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

import numpy as np
import pyproj

from . import _illumination_numba
from .reference import _local_basis


class _Layer3CRS(Protocol):
    def to_wkt(self) -> str: ...


class _Layer3Patch(Protocol):
    body: str
    z: np.ndarray
    transform: Iterable[float]
    crs: _Layer3CRS
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    sources: list[str]
    resampling: str


@dataclass(frozen=True)
class LunarTerrainMetadata:
    """Scientific metadata that cannot be inferred from a raster CRS alone."""

    body_fixed_frame: str
    frame_realization: str
    frame_alignment_note: str
    elevation_reference: str
    reference_radius_m: float
    provenance: Mapping[str, str]


@dataclass(frozen=True)
class LunarTerrainWindow:
    """A clipped, north-up-orientation-preserving view around a terrain pixel."""

    elevations_m: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    row_offset: int
    col_offset: int

    @property
    def valid_mask(self) -> np.ndarray:
        return np.isfinite(self.elevations_m)


@dataclass(frozen=True)
class LunarTerrainSample:
    """One pixel-centre terrain location in selenographic and body-fixed form."""

    row: int
    col: int
    longitude_deg: float
    latitude_deg: float
    elevation_m: float
    position_fixed_km: tuple[float, float, float]


@dataclass(frozen=True)
class TerrainSurfaceNormal:
    """Finite-difference terrain normal expressed in the lunar body-fixed frame."""

    row: int
    col: int
    frame: str
    normal_fixed: tuple[float, float, float]
    method: str
    coverage: str
    valid: bool
    dot_to_sun: float | None = None


@dataclass(frozen=True)
class TerrainObstructionResult:
    """Structured direct-illumination and terrain-obstruction evaluation."""

    status: str
    row: int
    col: int
    frame: str
    surface_normal_fixed: tuple[float, float, float]
    solar_direction_fixed: tuple[float, float, float]
    incidence_deg: float | None
    dot_product: float | None
    obstruction_distance_km: float | None
    samples_examined: int
    coverage: str
    tolerance: float
    detail: str


@dataclass(frozen=True)
class TerrainHorizonObservation:
    """A single azimuth sector's maximum apparent terrain-elevation angle."""

    azimuth_deg: float
    apparent_elevation_deg: float | None
    distance_m: float | None
    sample_row: int | None
    sample_col: int | None
    coverage: str
    status: str
    detail: str
    frame: str


@dataclass(frozen=True)
class TerrainHorizonProfile:
    """A full directional horizon profile for one observer location."""

    observer_row: int
    observer_col: int
    frame: str
    azimuth_step_deg: float
    observations: tuple[TerrainHorizonObservation, ...]

    @property
    def coverage_mask(self) -> tuple[bool, ...]:
        """Return one complete-coverage flag for each azimuth observation."""
        return tuple(observation.coverage == "valid" for observation in self.observations)

    @property
    def incomplete_azimuths_deg(self) -> tuple[float, ...]:
        """Return azimuths whose horizon estimates are partial or unavailable."""
        return tuple(
            observation.azimuth_deg
            for observation in self.observations
            if observation.coverage != "valid"
        )


class TerrainIlluminationCode(IntEnum):
    """Integer codes used in a single-time direct-illumination classification raster."""

    UNKNOWN = 0
    ILLUMINATED = 1
    TERRAIN_OBSTRUCTED = 2
    SURFACE_FACING_AWAY = 3
    INSUFFICIENT_COVERAGE = 4
    NO_DATA = -1


class TerrainRayStatus(IntEnum):
    """Reason the illumination classification was or was not supported."""

    NO_DATA = _illumination_numba.RAY_STATUS_NO_DATA
    UNKNOWN = _illumination_numba.RAY_STATUS_UNKNOWN
    SEARCH_LIMIT_REACHED = _illumination_numba.RAY_STATUS_SEARCH_LIMIT_REACHED
    OBSTRUCTION_FOUND = _illumination_numba.RAY_STATUS_OBSTRUCTION_FOUND
    DEM_BOUNDARY = _illumination_numba.RAY_STATUS_DEM_BOUNDARY
    TERRAIN_NODATA = _illumination_numba.RAY_STATUS_TERRAIN_NODATA
    SURFACE_FACING_AWAY = _illumination_numba.RAY_STATUS_SURFACE_FACING_AWAY
    VERTICAL_SUN = _illumination_numba.RAY_STATUS_VERTICAL_SUN


@dataclass(frozen=True)
class TerrainIlluminationRasterResult:
    """Whole-patch direct-illumination classification for one observation time.

    ``coverage_mask`` means the classification is supported by a valid terrain
    normal. It is not a claim that every supported pixel traversed the full ray
    distance; ``ray_status`` records the per-pixel search outcome.
    """

    classification: np.ndarray
    valid_mask: np.ndarray
    normal_valid_mask: np.ndarray
    coverage_mask: np.ndarray
    ray_status: np.ndarray
    observation_time_utc: datetime | None
    solar_direction_fixed: tuple[float, float, float]
    solar_frame: str
    source_dataset_id: str
    source_metadata: Mapping[str, str]
    working_crs_wkt: str
    transform: tuple[float, float, float, float, float, float]
    tolerance: float
    step_size_m: float
    max_distance_m: float
    chunk_rows: int
    chunk_cols: int

    @staticmethod
    def status_for_code(code: int) -> str:
        for member in TerrainIlluminationCode:
            if int(member) == int(code):
                return member.name
        raise ValueError(f"unsupported illumination code: {code}")

    @staticmethod
    def code_for_status(status: str) -> int:
        code = getattr(TerrainIlluminationCode, status.upper(), None)
        if code is None:
            raise ValueError(f"unsupported illumination status: {status}")
        return int(code)


@dataclass(frozen=True)
class TerrainIlluminationCache:
    """Reusable terrain-only normals, tied to the exact source grid and values."""

    normals_fixed: np.ndarray
    normal_valid_mask: np.ndarray
    dataset_identity: str
    cache_key: str
    radius_pixels: int


@dataclass(frozen=True)
class LunarTerrainPatch:
    """Layer 4's explicit terrain contract; arrays remain in Layer 3's working grid.

    Elevations are metres above ``elevation_reference``. The complete working CRS
    WKT and source CRS identifier are retained; frame identity and provenance are
    supplied separately because they are not reliably encoded in planetary WKT.
    """

    elevations_m: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    working_crs_wkt: str
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    resampling: str
    sources: tuple[str, ...]
    body_fixed_frame: str
    frame_realization: str
    frame_alignment_note: str
    elevation_reference: str
    reference_radius_m: float
    provenance: Mapping[str, str]
    _to_lonlat: pyproj.Transformer = field(repr=False, compare=False)
    observation_counts: np.ndarray | None = field(default=None, repr=False, compare=False)
    observation_counts_sources: tuple[str, ...] = ()

    @classmethod
    def from_layer3_patch(
        cls,
        patch: _Layer3Patch,
        metadata: LunarTerrainMetadata,
        observation_counts_patch: _Layer3Patch | None = None,
    ) -> "LunarTerrainPatch":
        """Adapt elevations and only accept count data proven to share the same grid."""
        if patch.body != "moon":
            raise ValueError("Layer 3 patch body must be 'moon'")

        elevations = np.asarray(patch.z)
        if elevations.ndim != 2 or not np.issubdtype(elevations.dtype, np.number):
            raise ValueError("patch.z must be a two-dimensional numeric elevation array")
        if not np.isfinite(elevations).any():
            raise ValueError("patch.z must contain at least one valid elevation")

        if metadata.body_fixed_frame not in ("MOON_ME", "MOON_PA"):
            raise ValueError("body_fixed_frame must be 'MOON_ME' or 'MOON_PA'")
        if not metadata.frame_realization.strip():
            raise ValueError("frame_realization must be specified explicitly")
        if not metadata.frame_alignment_note.strip():
            raise ValueError("frame_alignment_note must be specified explicitly")
        if not metadata.elevation_reference.strip():
            raise ValueError("elevation_reference must be specified explicitly")
        if not isfinite(metadata.reference_radius_m) or metadata.reference_radius_m <= 0:
            raise ValueError("reference_radius_m must be finite and positive")

        crs = pyproj.CRS.from_wkt(patch.crs.to_wkt())
        if not crs.is_projected:
            raise ValueError("Layer 4 terrain requires a projected working CRS")
        if not crs.axis_info or any(
            axis.unit_conversion_factor is None
            or abs(axis.unit_conversion_factor - 1.0) > 1e-9
            for axis in crs.axis_info[:2]
        ):
            raise ValueError("Layer 4 terrain working CRS must use metres")
        geodetic_crs = crs.geodetic_crs
        if geodetic_crs is None:
            raise ValueError("Layer 3 working CRS must define a geodetic CRS")
        crs_radius = geodetic_crs.ellipsoid.semi_major_metre
        if abs(crs_radius - metadata.reference_radius_m) > 1.0:
            raise ValueError(
                "CRS reference radius does not match the supplied lunar elevation reference"
            )

        transform_values = tuple(patch.transform)
        if len(transform_values) < 6:
            raise ValueError("Layer 3 patch must contain a six-parameter affine transform")
        transform = tuple(float(value) for value in transform_values[:6])
        if not all(isfinite(value) for value in transform):
            raise ValueError("patch transform must contain only finite values")
        determinant = transform[0] * transform[4] - transform[1] * transform[3]
        if abs(determinant) < 1e-15:
            raise ValueError("patch transform must be invertible")

        pixel_size = float(patch.pixel_size_m)
        native_pixel_size = float(patch.native_pixel_size_m)
        if not isfinite(pixel_size) or pixel_size <= 0:
            raise ValueError("patch.pixel_size_m must be finite and positive")
        if not isfinite(native_pixel_size) or native_pixel_size <= 0:
            raise ValueError("patch.native_pixel_size_m must be finite and positive")

        native_crs = patch.native_crs.strip()
        if not native_crs:
            raise ValueError("Layer 3 patch must retain its native CRS")
        resampling = patch.resampling.strip()
        if not resampling:
            raise ValueError("Layer 3 patch must identify its resampling method")
        sources = tuple(str(source).strip() for source in patch.sources)
        if not sources or any(not source for source in sources):
            raise ValueError("Layer 3 patch must retain at least one source URI")
        provenance = dict(metadata.provenance)
        if not provenance or any(not key or not value for key, value in provenance.items()):
            raise ValueError("provenance must contain non-empty keys and values")

        observation_counts = None
        observation_count_sources: tuple[str, ...] = ()
        if observation_counts_patch is not None:
            if observation_counts_patch.body != "moon":
                raise ValueError("observation-count patch body must be 'moon'")
            count_values = np.ma.asarray(
                observation_counts_patch.z, dtype=np.float64
            )
            if (
                count_values.ndim != 2
                or not np.issubdtype(count_values.dtype, np.number)
                or count_values.shape != elevations.shape
            ):
                raise ValueError(
                    "observation-count patch must be a numeric array matching the elevation shape"
                )
            count_crs = pyproj.CRS.from_wkt(observation_counts_patch.crs.to_wkt())
            if not count_crs.equals(crs):
                raise ValueError("observation-count patch CRS must match the elevation patch CRS")
            count_transform = tuple(float(value) for value in observation_counts_patch.transform)
            if len(count_transform) < 6 or not np.allclose(
                count_transform[:6], transform, rtol=0.0, atol=1e-9
            ):
                raise ValueError(
                    "observation-count patch affine transform must match the elevation patch"
                )
            observation_counts = np.asarray(count_values.filled(np.nan))
            known_counts = np.isfinite(observation_counts)
            if np.any(
                known_counts
                & (
                    (observation_counts < 0.0)
                    | (observation_counts != np.floor(observation_counts))
                )
            ):
                raise ValueError("known observation counts must be non-negative integers")
            observation_counts.setflags(write=False)
            observation_count_sources = tuple(
                str(source).strip() for source in observation_counts_patch.sources
            )
            if not observation_count_sources or any(
                not source for source in observation_count_sources
            ):
                raise ValueError("observation-count patch must retain its source URI")
            provenance["observation_coverage_status"] = (
                "AVAILABLE" if known_counts.all() else "PARTIAL"
            )
            provenance["observation_counts_sources"] = ";".join(
                observation_count_sources
            )
        else:
            provenance["observation_coverage_status"] = "UNAVAILABLE"
            provenance["observation_coverage_reason"] = (
                "No spatially aligned LOLA observation-count patch was supplied."
            )

        return cls(
            elevations_m=elevations,
            transform=transform,
            working_crs_wkt=crs.to_wkt(),
            native_crs=native_crs,
            pixel_size_m=pixel_size,
            native_pixel_size_m=native_pixel_size,
            resampling=resampling,
            sources=sources,
            body_fixed_frame=metadata.body_fixed_frame,
            frame_realization=metadata.frame_realization,
            frame_alignment_note=metadata.frame_alignment_note,
            elevation_reference=metadata.elevation_reference,
            reference_radius_m=float(metadata.reference_radius_m),
            provenance=MappingProxyType(provenance),
            _to_lonlat=pyproj.Transformer.from_crs(crs, geodetic_crs, always_xy=True),
            observation_counts=observation_counts,
            observation_counts_sources=observation_count_sources,
        )

    def __post_init__(self) -> None:
        if self.observation_counts is not None:
            masked_counts = np.ma.asarray(
                self.observation_counts, dtype=np.float64
            )
            counts = np.asarray(masked_counts.filled(np.nan))
            if counts.shape != self.elevations_m.shape:
                raise ValueError("observation counts must match the elevation array shape")
            known = np.isfinite(counts)
            if np.any(
                known & ((counts < 0.0) | (counts != np.floor(counts)))
            ):
                raise ValueError("known observation counts must be non-negative integers")
            counts.setflags(write=False)
            object.__setattr__(self, "observation_counts", counts)

    @property
    def valid_mask(self) -> np.ndarray:
        """True for elevations available to terrain geometry; invalid cells are NaN."""
        return np.isfinite(self.elevations_m)

    @property
    def observation_coverage_known_mask(self) -> np.ndarray | None:
        """True where a spatially aligned count value is available."""
        if self.observation_counts is None:
            return None
        return np.isfinite(self.observation_counts)

    @property
    def observation_coverage_mask(self) -> np.ndarray | None:
        """True where a count product reports one or more laser observations."""
        if self.observation_counts is None:
            return None
        return np.isfinite(self.observation_counts) & (self.observation_counts > 0.0)

    @property
    def measured_elevation_mask(self) -> np.ndarray | None:
        """True where both elevation and observation-count evidence are available."""
        measured = self.observation_coverage_mask
        if measured is None:
            return None
        return self.valid_mask & measured

    @property
    def unobserved_valid_elevation_mask(self) -> np.ndarray | None:
        """Valid elevation cells explicitly reporting zero laser observations."""
        known = self.observation_coverage_known_mask
        covered = self.observation_coverage_mask
        if known is None or covered is None:
            return None
        return self.valid_mask & known & ~covered

    @property
    def shape(self) -> tuple[int, int]:
        return self.elevations_m.shape

    def pixel_to_lonlat(self, row: int, col: int) -> tuple[float, float]:
        """Return the east-positive, planetocentric lon/lat at a pixel centre."""
        self._check_pixel(row, col)
        a, b, c, d, e, f = self.transform
        pixel_col, pixel_row = col + 0.5, row + 0.5
        x = a * pixel_col + b * pixel_row + c
        y = d * pixel_col + e * pixel_row + f
        longitude, latitude = self._to_lonlat.transform(x, y)
        if not isfinite(longitude) or not isfinite(latitude):
            raise ValueError("pixel coordinate could not be transformed to lunar longitude/latitude")
        return float(longitude), float(latitude)

    def lonlat_to_pixel(self, longitude_deg: float, latitude_deg: float) -> tuple[int, int]:
        """Find the containing raster pixel for east-positive planetocentric lon/lat."""
        if not isfinite(longitude_deg) or not isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
            raise ValueError("longitude/latitude must be finite and latitude within [-90, 90]")
        x, y = self._to_lonlat.transform(
            longitude_deg,
            latitude_deg,
            direction=pyproj.enums.TransformDirection.INVERSE,
        )
        a, b, c, d, e, f = self.transform
        determinant = a * e - b * d
        pixel_col = (e * (x - c) - b * (y - f)) / determinant
        pixel_row = (-d * (x - c) + a * (y - f)) / determinant
        row, col = int(np.floor(pixel_row)), int(np.floor(pixel_col))
        if not 0 <= row < self.shape[0] or not 0 <= col < self.shape[1]:
            raise ValueError("longitude/latitude lies outside this terrain patch")
        return row, col

    def sample(self, row: int, col: int) -> LunarTerrainSample:
        """Get a valid pixel's centre coordinates and spherical body-fixed position."""
        self._check_pixel(row, col)
        elevation_m = float(self.elevations_m[row, col])
        if not isfinite(elevation_m):
            raise ValueError("cannot sample a NoData terrain pixel")
        longitude, latitude = self.pixel_to_lonlat(row, col)
        radius_km = (self.reference_radius_m + elevation_m) / 1000.0
        if radius_km <= 0:
            raise ValueError("elevation places the sample at or below the lunar centre")
        lat, lon = radians(latitude), radians(longitude)
        position = (
            radius_km * cos(lat) * cos(lon),
            radius_km * cos(lat) * sin(lon),
            radius_km * sin(lat),
        )
        return LunarTerrainSample(
            row=row,
            col=col,
            longitude_deg=longitude,
            latitude_deg=latitude,
            elevation_m=elevation_m,
            position_fixed_km=position,
        )

    def window_around(self, row: int, col: int, radius_pixels: int) -> LunarTerrainWindow:
        """Return the clipped local elevation window and its translated affine."""
        self._check_pixel(row, col)
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 0:
            raise ValueError("radius_pixels must be a non-negative integer")
        row0 = max(0, row - radius_pixels)
        row1 = min(self.shape[0], row + radius_pixels + 1)
        col0 = max(0, col - radius_pixels)
        col1 = min(self.shape[1], col + radius_pixels + 1)
        a, b, c, d, e, f = self.transform
        translated = (
            a, b, a * col0 + b * row0 + c,
            d, e, d * col0 + e * row0 + f,
        )
        return LunarTerrainWindow(
            elevations_m=self.elevations_m[row0:row1, col0:col1],
            transform=translated,
            row_offset=row0,
            col_offset=col0,
        )

    def _projected_xy(self, row: int, col: int) -> tuple[float, float]:
        a, b, c, d, e, f = self.transform
        pixel_col, pixel_row = col + 0.5, row + 0.5
        return (a * pixel_col + b * pixel_row + c, d * pixel_col + e * pixel_row + f)

    def _pixel_lonlat_window(
        self, row0: int, row1: int, col0: int, col1: int
    ) -> tuple[np.ndarray, np.ndarray]:
        a, b, c, d, e, f = self.transform
        cols = np.arange(col0, col1, dtype=np.float64) + 0.5
        rows = np.arange(row0, row1, dtype=np.float64) + 0.5
        x = a * cols[np.newaxis, :] + b * rows[:, np.newaxis] + c
        y = d * cols[np.newaxis, :] + e * rows[:, np.newaxis] + f
        longitude, latitude = self._to_lonlat.transform(x, y)
        longitude = np.asarray(longitude, dtype=np.float64)
        latitude = np.asarray(latitude, dtype=np.float64)
        if not np.all(np.isfinite(longitude)) or not np.all(np.isfinite(latitude)):
            raise ValueError("terrain pixel coordinates could not be transformed to longitude/latitude")
        return longitude, latitude

    def _projected_ray_direction(
        self, row: int, col: int, east_component: float, north_component: float
    ) -> tuple[float, float]:
        """Map a local tangent direction to projected map units per metre."""
        longitude, latitude = self._pixel_lonlat_window(
            row - 1, row + 2, col - 1, col + 2
        )
        longitude_rad = np.radians(longitude)
        latitude_rad = np.radians(latitude)
        radius_m = self.reference_radius_m + float(self.elevations_m[row, col])
        positions = radius_m * np.stack(
            (
                np.cos(latitude_rad) * np.cos(longitude_rad),
                np.cos(latitude_rad) * np.sin(longitude_rad),
                np.sin(latitude_rad),
            ),
            axis=-1,
        )
        east, north, _ = self._surface_local_basis(row, col)
        col_tangent = (positions[1, 2] - positions[1, 0]) / 2.0
        row_tangent = (positions[2, 1] - positions[0, 1]) / 2.0
        col_east, col_north = float(np.dot(col_tangent, east)), float(np.dot(col_tangent, north))
        row_east, row_north = float(np.dot(row_tangent, east)), float(np.dot(row_tangent, north))
        determinant = col_east * row_north - row_east * col_north
        if abs(determinant) <= 1e-15:
            raise ValueError("local raster grid is degenerate in the lunar tangent plane")

        col_per_m = (east_component * row_north - row_east * north_component) / determinant
        row_per_m = (col_east * north_component - col_north * east_component) / determinant
        a, b, _, d, e, _ = self.transform
        return (
            a * col_per_m + b * row_per_m,
            d * col_per_m + e * row_per_m,
        )

    def _illumination_cache_key(self, radius_pixels: int) -> tuple[str, str]:
        elevations = np.ascontiguousarray(self.elevations_m)
        content_hash = hashlib.sha256(memoryview(elevations).cast("B")).hexdigest()
        identity = str(
            self.provenance.get("dataset_id")
            or self.provenance.get("source_path")
            or self.sources[0]
        )
        key_material = repr((
            identity,
            content_hash,
            elevations.shape,
            elevations.dtype.str,
            self.transform,
            self.working_crs_wkt,
            self.body_fixed_frame,
            self.frame_realization,
            self.reference_radius_m,
            radius_pixels,
        )).encode("utf-8")
        return identity, hashlib.sha256(key_material).hexdigest()

    def prepare_illumination_cache(
        self,
        *,
        chunk_rows: int = 256,
        chunk_cols: int = 256,
        radius_pixels: int = 1,
    ) -> TerrainIlluminationCache:
        """Precompute static terrain normals for reuse across observation times."""
        if not _illumination_numba.is_available():
            raise RuntimeError(
                "Numba is required for terrain illumination preprocessing; "
                "install the 'performance' extra"
            )
        if isinstance(chunk_rows, bool) or not isinstance(chunk_rows, int) or chunk_rows <= 0:
            raise ValueError("chunk_rows must be a positive integer")
        if isinstance(chunk_cols, bool) or not isinstance(chunk_cols, int) or chunk_cols <= 0:
            raise ValueError("chunk_cols must be a positive integer")
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
            raise ValueError("radius_pixels must be an integer >= 1")

        normals = np.zeros((*self.shape, 3), dtype=np.float64)
        normal_valid = np.zeros(self.shape, dtype=bool)
        for row0 in range(0, self.shape[0], chunk_rows):
            row1 = min(row0 + chunk_rows, self.shape[0])
            for col0 in range(0, self.shape[1], chunk_cols):
                col1 = min(col0 + chunk_cols, self.shape[1])
                longitude, latitude = self._pixel_lonlat_window(
                    row0 - radius_pixels,
                    row1 + radius_pixels,
                    col0 - radius_pixels,
                    col1 + radius_pixels,
                )
                tile_normals, tile_valid = _illumination_numba.compute_normal_window(
                    self.elevations_m,
                    longitude,
                    latitude,
                    row0,
                    col0,
                    self.reference_radius_m,
                    radius_pixels,
                )
                normals[row0:row1, col0:col1] = tile_normals
                normal_valid[row0:row1, col0:col1] = tile_valid
        normals.setflags(write=False)
        normal_valid.setflags(write=False)
        identity, cache_key = self._illumination_cache_key(radius_pixels)
        return TerrainIlluminationCache(
            normals_fixed=normals,
            normal_valid_mask=normal_valid,
            dataset_identity=identity,
            cache_key=cache_key,
            radius_pixels=radius_pixels,
        )

    def _surface_local_basis(self, row: int, col: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sample = self.sample(row, col)
        site = np.asarray(sample.position_fixed_km, dtype=float)
        radius = float(np.linalg.norm(site))
        if radius <= 0.0:
            raise ValueError("sample position has zero length")
        up = site / radius
        east, north = _local_basis(sample.longitude_deg, up)
        return east, north, up

    def terrain_surface_normal(self, row: int, col: int, *, radius_pixels: int = 1) -> TerrainSurfaceNormal:
        """Estimate a terrain normal from neighboring body-fixed terrain positions."""
        self._check_pixel(row, col)
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
            raise ValueError("radius_pixels must be an integer >= 1")

        center = self.sample(row, col)
        center_position = np.asarray(center.position_fixed_km, dtype=float)
        up = center_position / float(np.linalg.norm(center_position))

        def valid_neighbour(r: int, c: int) -> tuple[int, int] | None:
            try:
                self._check_pixel(r, c)
            except IndexError:
                return None
            if not isfinite(float(self.elevations_m[r, c])):
                return None
            return (r, c)

        options = [
            valid_neighbour(row, col - radius_pixels),
            valid_neighbour(row, col + radius_pixels),
            valid_neighbour(row - radius_pixels, col),
            valid_neighbour(row + radius_pixels, col),
        ]
        if not any(value is not None for value in options):
            raise ValueError("no valid neighbouring terrain cells are available for a normal estimate")

        center_elevation = center.elevation_m

        def fixed_position(target_row: int, target_col: int, elevation_m: float) -> np.ndarray:
            longitude, latitude = self._pixel_lonlat_window(
                target_row, target_row + 1, target_col, target_col + 1
            )
            longitude_rad = radians(float(longitude[0, 0]))
            latitude_rad = radians(float(latitude[0, 0]))
            radius_km = (self.reference_radius_m + elevation_m) / 1000.0
            if radius_km <= 0.0:
                raise ValueError("elevation places a normal sample at or below the lunar centre")
            return radius_km * np.array(
                [
                    cos(latitude_rad) * cos(longitude_rad),
                    cos(latitude_rad) * sin(longitude_rad),
                    sin(latitude_rad),
                ],
                dtype=float,
            )

        def endpoint_position(target_row: int, target_col: int) -> np.ndarray:
            neighbor = valid_neighbour(target_row, target_col)
            elevation = (
                center_elevation
                if neighbor is None
                else float(self.elevations_m[neighbor[0], neighbor[1]])
            )
            return fixed_position(target_row, target_col, elevation)

        radius = radius_pixels
        tangent_col = (
            endpoint_position(row, col + radius)
            - endpoint_position(row, col - radius)
        )
        tangent_row = (
            endpoint_position(row + radius, col)
            - endpoint_position(row - radius, col)
        )
        normal = np.cross(tangent_col, tangent_row)
        if float(np.dot(normal, up)) < 0.0:
            normal = -normal
        normal_norm = float(np.linalg.norm(normal))
        if normal_norm <= 1e-15:
            raise ValueError("terrain positions produced a zero-length normal")
        normal /= normal_norm

        return TerrainSurfaceNormal(
            row=row,
            col=col,
            frame=self.body_fixed_frame,
            normal_fixed=tuple(float(value) for value in normal),
            method="finite-difference body-fixed positions",
            coverage="valid",
            valid=True,
        )

    def surface_normal(self, row: int, col: int, *, radius_pixels: int = 1) -> TerrainSurfaceNormal:
        return self.terrain_surface_normal(row, col, radius_pixels=radius_pixels)

    def local_terrain_normal(self, row: int, col: int, *, radius_pixels: int = 1) -> TerrainSurfaceNormal:
        return self.terrain_surface_normal(row, col, radius_pixels=radius_pixels)

    @staticmethod
    def _sun_direction_and_distance(
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
    ) -> tuple[np.ndarray, float]:
        """Return a unit direction and range; bare vectors are far-field directions."""
        if hasattr(sun_direction_fixed, "direction_fixed"):
            direction = np.asarray(sun_direction_fixed.direction_fixed, dtype=float)
            if not hasattr(sun_direction_fixed, "sun_distance_km"):
                raise ValueError("Sun position objects must provide sun_distance_km")
            distance = float(sun_direction_fixed.sun_distance_km)
            if not isfinite(distance) or distance <= 0.0:
                raise ValueError("sun_distance_km must be finite and positive")
        else:
            direction = np.asarray(sun_direction_fixed, dtype=float)
            distance = 0.0
        if direction.shape != (3,) or not np.all(np.isfinite(direction)):
            raise ValueError("sun_direction_fixed must be a three-component finite vector")
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm <= 0.0:
            raise ValueError("sun_direction_fixed must not be zero-length")
        return direction / direction_norm, float(distance)

    def surface_faces_sun(
        self,
        row: int,
        col: int,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
        *,
        radius_pixels: int = 1,
        tolerance: float = 1e-9,
    ) -> tuple[bool, float, TerrainSurfaceNormal]:
        normal = self.terrain_surface_normal(row, col, radius_pixels=radius_pixels)
        sun, sun_distance_km = self._sun_direction_and_distance(sun_direction_fixed)
        site = np.asarray(self.sample(row, col).position_fixed_km, dtype=float)
        site_to_sun = sun * sun_distance_km - site if sun_distance_km > 0.0 else sun
        if np.linalg.norm(site_to_sun) == 0.0:
            raise ValueError("Sun vector at the sample is degenerate")
        site_to_sun /= float(np.linalg.norm(site_to_sun))
        dot = float(np.dot(np.asarray(normal.normal_fixed), site_to_sun))
        return dot > tolerance, dot, normal

    def terrain_direct_illumination(
        self,
        row: int,
        col: int,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
        *,
        radius_pixels: int = 1,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
    ) -> TerrainObstructionResult:
        self._check_pixel(row, col)
        if not np.isfinite(step_size_m) or step_size_m <= 0:
            raise ValueError("step_size_m must be finite and positive")
        if not np.isfinite(max_distance_m) or max_distance_m <= 0:
            raise ValueError("max_distance_m must be finite and positive")

        sample = self.sample(row, col)
        normal = self.terrain_surface_normal(row, col, radius_pixels=radius_pixels)
        sun, sun_distance_km = self._sun_direction_and_distance(sun_direction_fixed)
        site = np.asarray(sample.position_fixed_km, dtype=float)
        site_to_sun = sun * sun_distance_km - site if sun_distance_km > 0.0 else sun
        if np.linalg.norm(site_to_sun) == 0.0:
            raise ValueError("Sun vector at the sample is degenerate")
        sun_dir = site_to_sun / float(np.linalg.norm(site_to_sun))
        dot = float(np.dot(np.asarray(normal.normal_fixed), sun_dir))

        if dot <= tolerance:
            return TerrainObstructionResult(
                status="SURFACE_FACING_AWAY",
                row=row,
                col=col,
                frame=self.body_fixed_frame,
                surface_normal_fixed=normal.normal_fixed,
                solar_direction_fixed=tuple(float(value) for value in sun),
                incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                dot_product=dot,
                obstruction_distance_km=None,
                samples_examined=0,
                coverage="valid",
                tolerance=tolerance,
                detail="terrain normal is tilted away from the direct solar direction",
            )

        east, north, up = self._surface_local_basis(row, col)
        sun_local = np.array([
            float(np.dot(sun_dir, east)),
            float(np.dot(sun_dir, north)),
            float(np.dot(sun_dir, up)),
        ], dtype=float)
        horizontal_mag = float(np.hypot(sun_local[0], sun_local[1]))
        if horizontal_mag <= tolerance:
            return TerrainObstructionResult(
                status="ILLUMINATED",
                row=row,
                col=col,
                frame=self.body_fixed_frame,
                surface_normal_fixed=normal.normal_fixed,
                solar_direction_fixed=tuple(float(value) for value in sun),
                incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                dot_product=dot,
                obstruction_distance_km=None,
                samples_examined=0,
                coverage="valid",
                tolerance=tolerance,
                detail="the solar direction is effectively normal to the local surface and has no horizontal terrain profile",
            )

        checked = 0
        x0, y0 = self._projected_xy(row, col)
        direction_x, direction_y = self._projected_ray_direction(
            row,
            col,
            float(sun_local[0] / horizontal_mag),
            float(sun_local[1] / horizontal_mag),
        )
        max_steps = max(1, int(max_distance_m / step_size_m))
        for step in range(1, max_steps + 1):
            distance_m = step * step_size_m
            x = x0 + distance_m * direction_x
            y = y0 + distance_m * direction_y
            a, b, c, d, e, f = self.transform
            determinant = a * e - b * d
            if abs(determinant) <= 1e-15:
                return TerrainObstructionResult(
                    status="UNKNOWN",
                    row=row,
                    col=col,
                    frame=self.body_fixed_frame,
                    surface_normal_fixed=normal.normal_fixed,
                    solar_direction_fixed=tuple(float(value) for value in sun),
                    incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                    dot_product=dot,
                    obstruction_distance_km=None,
                    samples_examined=checked,
                    coverage="unknown",
                    tolerance=tolerance,
                    detail="affine transform is degenerate for projected ray marching",
                )
            col_idx = (e * (x - c) - b * (y - f)) / determinant
            row_idx = (-d * (x - c) + a * (y - f)) / determinant
            r = int(np.floor(row_idx))
            c_idx = int(np.floor(col_idx))
            if not 0 <= r < self.shape[0] or not 0 <= c_idx < self.shape[1]:
                return TerrainObstructionResult(
                    status="INSUFFICIENT_COVERAGE",
                    row=row,
                    col=col,
                    frame=self.body_fixed_frame,
                    surface_normal_fixed=normal.normal_fixed,
                    solar_direction_fixed=tuple(float(value) for value in sun),
                    incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                    dot_product=dot,
                    obstruction_distance_km=None,
                    samples_examined=checked,
                    coverage="insufficient",
                    tolerance=tolerance,
                    detail="the solar ray exits the local DEM before a definitive obstruction result",
                )
            checked += 1
            if not isfinite(float(self.elevations_m[r, c_idx])):
                return TerrainObstructionResult(
                    status="INSUFFICIENT_COVERAGE",
                    row=row,
                    col=col,
                    frame=self.body_fixed_frame,
                    surface_normal_fixed=normal.normal_fixed,
                    solar_direction_fixed=tuple(float(value) for value in sun),
                    incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                    dot_product=dot,
                    obstruction_distance_km=None,
                    samples_examined=checked,
                    coverage="insufficient",
                    tolerance=tolerance,
                    detail="NoData encountered along the direct solar path",
                )
            terrain_elevation = float(self.elevations_m[r, c_idx])
            if terrain_elevation > sample.elevation_m + max(1.0, 5.0 * step_size_m / 1000.0):
                return TerrainObstructionResult(
                    status="TERRAIN_OBSTRUCTED",
                    row=row,
                    col=col,
                    frame=self.body_fixed_frame,
                    surface_normal_fixed=normal.normal_fixed,
                    solar_direction_fixed=tuple(float(value) for value in sun),
                    incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
                    dot_product=dot,
                    obstruction_distance_km=distance_m / 1000.0,
                    samples_examined=checked,
                    coverage="valid",
                    tolerance=tolerance,
                    detail="projected terrain elevation exceeds the local ray path in the DEM",
                )

        return TerrainObstructionResult(
            status="ILLUMINATED",
            row=row,
            col=col,
            frame=self.body_fixed_frame,
            surface_normal_fixed=normal.normal_fixed,
            solar_direction_fixed=tuple(float(value) for value in sun),
            incidence_deg=degrees(acos(max(-1.0, min(1.0, dot)))),
            dot_product=dot,
            obstruction_distance_km=None,
            samples_examined=checked,
            coverage="valid",
            tolerance=tolerance,
            detail="no intervening terrain was found before the ray left the local patch",
        )

    def terrain_obstruction(
        self,
        row: int,
        col: int,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray,
        *,
        radius_pixels: int = 1,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
    ) -> TerrainObstructionResult:
        return self.terrain_direct_illumination(
            row,
            col,
            sun_direction_fixed,
            radius_pixels=radius_pixels,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
        )

    def terrain_horizon_profile(
        self,
        row: int,
        col: int,
        *,
        azimuth_step_deg: float = 5.0,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
    ) -> TerrainHorizonProfile:
        """Return the local terrain horizon expressed as apparent elevation by azimuth.

        Azimuth follows the Moon-local convention used elsewhere in Layer 4:
        0° = north, 90° = east, 180° = south, 270° = west.
        """
        self._check_pixel(row, col)
        if not np.isfinite(azimuth_step_deg) or azimuth_step_deg <= 0.0 or azimuth_step_deg > 360.0:
            raise ValueError("azimuth_step_deg must be finite and between (0, 360]")
        if not np.isfinite(step_size_m) or step_size_m <= 0.0:
            raise ValueError("step_size_m must be finite and positive")
        if not np.isfinite(max_distance_m) or max_distance_m <= 0.0:
            raise ValueError("max_distance_m must be finite and positive")

        sample = self.sample(row, col)
        x0, y0 = self._projected_xy(row, col)
        max_steps = max(1, int(max_distance_m / step_size_m))
        observations: list[TerrainHorizonObservation] = []

        for azimuth_deg in [float(value) for value in np.arange(0.0, 360.0, azimuth_step_deg)]:
            azimuth_rad = radians(azimuth_deg)
            direction_x, direction_y = self._projected_ray_direction(
                row, col, sin(azimuth_rad), cos(azimuth_rad)
            )
            max_apparent_deg = None
            max_distance_m_seen = None
            best_row = None
            best_col = None
            status = "HORIZON_CLEAR"
            coverage = "valid"
            detail = "no terrain rise was found above the local horizontal plane"

            for step in range(1, max_steps + 1):
                distance_m = step * step_size_m
                x = x0 + distance_m * direction_x
                y = y0 + distance_m * direction_y
                a, b, c, d, e, f = self.transform
                determinant = a * e - b * d
                if abs(determinant) <= 1e-15:
                    status = "UNKNOWN"
                    coverage = "unknown"
                    detail = "affine transform is degenerate for projected horizon marching"
                    break
                col_idx = (e * (x - c) - b * (y - f)) / determinant
                row_idx = (-d * (x - c) + a * (y - f)) / determinant
                r = int(np.floor(row_idx))
                c_idx = int(np.floor(col_idx))
                if not 0 <= r < self.shape[0] or not 0 <= c_idx < self.shape[1]:
                    if max_apparent_deg is not None:
                        status = "PARTIAL_COVERAGE"
                        coverage = "partial"
                        detail = "the horizon ray left the patch after a partial terrain profile was sampled"
                        break
                    status = "INSUFFICIENT_COVERAGE"
                    coverage = "insufficient"
                    detail = "the horizon ray exits the local DEM patch before a definitive terrain horizon"
                    break
                if not isfinite(float(self.elevations_m[r, c_idx])):
                    if max_apparent_deg is not None:
                        status = "PARTIAL_COVERAGE"
                        coverage = "partial"
                        detail = "NoData interrupted the horizon ray after a partial terrain profile was sampled"
                        break
                    status = "INSUFFICIENT_COVERAGE"
                    coverage = "insufficient"
                    detail = "NoData encountered before a definitive local horizon estimate"
                    break
                terrain_elevation = float(self.elevations_m[r, c_idx])
                apparent_elevation_deg = degrees(atan2(terrain_elevation - sample.elevation_m, distance_m))
                if max_apparent_deg is None or apparent_elevation_deg > max_apparent_deg:
                    max_apparent_deg = apparent_elevation_deg
                    max_distance_m_seen = float(distance_m)
                    best_row = int(r)
                    best_col = int(c_idx)
                if apparent_elevation_deg > 0.0:
                    status = "TERRAIN_RISE_DETECTED"
                    coverage = "valid"
                    detail = "terrain rises above the local horizontal plane in this azimuth sector"

            if max_apparent_deg is None:
                observations.append(
                    TerrainHorizonObservation(
                        azimuth_deg=azimuth_deg,
                        apparent_elevation_deg=None,
                        distance_m=None,
                        sample_row=None,
                        sample_col=None,
                        coverage=coverage,
                        status=status,
                        detail=detail,
                        frame=self.body_fixed_frame,
                    )
                )
                continue

            if coverage == "partial":
                status = "PARTIAL_COVERAGE"
            elif max_apparent_deg > 0.0:
                status = "TERRAIN_RISE_DETECTED"
                coverage = "valid"
                detail = "the maximum apparent terrain elevation in this azimuth sector rises above the local horizon"
            else:
                status = "HORIZON_CLEAR"
                coverage = "valid"
                detail = "the maximum apparent terrain elevation in this azimuth sector remains at or below the local horizon"

            observations.append(
                TerrainHorizonObservation(
                    azimuth_deg=azimuth_deg,
                    apparent_elevation_deg=float(max_apparent_deg),
                    distance_m=max_distance_m_seen,
                    sample_row=best_row,
                    sample_col=best_col,
                    coverage=coverage,
                    status=status,
                    detail=detail,
                    frame=self.body_fixed_frame,
                )
            )

        return TerrainHorizonProfile(
            observer_row=row,
            observer_col=col,
            frame=self.body_fixed_frame,
            azimuth_step_deg=float(azimuth_step_deg),
            observations=tuple(observations),
        )

    def terrain_horizon(
        self,
        row: int,
        col: int,
        *,
        azimuth_step_deg: float = 5.0,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
    ) -> TerrainHorizonProfile:
        return self.terrain_horizon_profile(
            row,
            col,
            azimuth_step_deg=azimuth_step_deg,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
        )

    def local_horizon_profile(
        self,
        row: int,
        col: int,
        *,
        azimuth_step_deg: float = 5.0,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
    ) -> TerrainHorizonProfile:
        return self.terrain_horizon_profile(
            row,
            col,
            azimuth_step_deg=azimuth_step_deg,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
        )

    def terrain_illumination_raster(
        self,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
        *,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
        chunk_rows: int = 256,
        chunk_cols: int = 256,
        radius_pixels: int = 1,
        observation_time_utc: datetime | None = None,
        source_dataset_id: str = "unknown",
        source_metadata: Mapping[str, str] | None = None,
        precomputation: TerrainIlluminationCache | None = None,
    ) -> TerrainIlluminationRasterResult:
        """Compute a single-time direct-illumination classification raster over the patch.

        Classification codes are encoded as integers so they can be written to GeoTIFF
        without ambiguity:
          0 = UNKNOWN
          1 = ILLUMINATED
          2 = TERRAIN_OBSTRUCTED
          3 = SURFACE_FACING_AWAY
          4 = INSUFFICIENT_COVERAGE
         -1 = NO_DATA
        """
        if not _illumination_numba.is_available():
            raise RuntimeError(
                "Numba is required for terrain illumination; install the 'performance' extra"
            )
        if not np.isfinite(step_size_m) or step_size_m <= 0:
            raise ValueError("step_size_m must be finite and positive")
        if not np.isfinite(max_distance_m) or max_distance_m <= 0:
            raise ValueError("max_distance_m must be finite and positive")
        if isinstance(chunk_rows, bool) or not isinstance(chunk_rows, int) or chunk_rows <= 0:
            raise ValueError("chunk_rows must be a positive integer")
        if isinstance(chunk_cols, bool) or not isinstance(chunk_cols, int) or chunk_cols <= 0:
            raise ValueError("chunk_cols must be a positive integer")
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
            raise ValueError("radius_pixels must be an integer >= 1")
        if observation_time_utc is not None and not isinstance(observation_time_utc, datetime):
            raise TypeError("observation_time_utc must be a datetime or None")
        if precomputation is not None:
            identity, cache_key = self._illumination_cache_key(precomputation.radius_pixels)
            if (
                precomputation.dataset_identity != identity
                or precomputation.cache_key != cache_key
                or precomputation.normals_fixed.shape != (*self.shape, 3)
                or precomputation.normal_valid_mask.shape != self.shape
                or precomputation.radius_pixels != radius_pixels
            ):
                raise ValueError("terrain illumination cache does not match this terrain patch")

        sun_vector, sun_distance_km = self._sun_direction_and_distance(sun_direction_fixed)
        solar_frame = getattr(sun_direction_fixed, "frame", self.body_fixed_frame)
        classification = np.full(
            self.shape, int(TerrainIlluminationCode.NO_DATA), dtype=np.int16
        )
        valid_mask = self.valid_mask.copy()
        normal_valid_mask = np.zeros(self.shape, dtype=bool)
        coverage_mask = np.zeros(self.shape, dtype=bool)
        ray_status = np.full(
            self.shape, _illumination_numba.RAY_STATUS_NO_DATA, dtype=np.int8
        )
        empty_normals = np.empty((0, 0, 3), dtype=np.float64)
        empty_valid = np.empty((0, 0), dtype=bool)
        cached_normals = (
            empty_normals if precomputation is None else precomputation.normals_fixed
        )
        cached_valid = (
            empty_valid if precomputation is None else precomputation.normal_valid_mask
        )
        for row0 in range(0, self.shape[0], chunk_rows):
            row1 = min(row0 + chunk_rows, self.shape[0])
            for col0 in range(0, self.shape[1], chunk_cols):
                col1 = min(col0 + chunk_cols, self.shape[1])
                longitude, latitude = self._pixel_lonlat_window(row0, row1, col0, col1)
                normal_longitude, normal_latitude = self._pixel_lonlat_window(
                    row0 - radius_pixels,
                    row1 + radius_pixels,
                    col0 - radius_pixels,
                    col1 + radius_pixels,
                )
                tile_class, tile_normals_valid, tile_coverage, tile_ray_status = (
                    _illumination_numba.classify_window(
                        self.elevations_m,
                        longitude,
                        latitude,
                        normal_longitude,
                        normal_latitude,
                        row0,
                        col0,
                        self.transform,
                        self.reference_radius_m,
                        radius_pixels,
                        float(sun_vector[0]),
                        float(sun_vector[1]),
                        float(sun_vector[2]),
                        sun_distance_km,
                        step_size_m,
                        max_distance_m,
                        tolerance,
                        cached_normals,
                        cached_valid,
                        precomputation is not None,
                    )
                )
                classification[row0:row1, col0:col1] = tile_class
                normal_valid_mask[row0:row1, col0:col1] = tile_normals_valid
                coverage_mask[row0:row1, col0:col1] = tile_coverage
                ray_status[row0:row1, col0:col1] = tile_ray_status

        if observation_time_utc is not None:
            observation_time_utc = observation_time_utc.astimezone(timezone.utc)
        return TerrainIlluminationRasterResult(
            classification=classification,
            valid_mask=valid_mask,
            normal_valid_mask=normal_valid_mask,
            coverage_mask=coverage_mask,
            ray_status=ray_status,
            observation_time_utc=observation_time_utc,
            solar_direction_fixed=tuple(float(value) for value in sun_vector),
            solar_frame=solar_frame,
            source_dataset_id=source_dataset_id,
            source_metadata={} if source_metadata is None else dict(source_metadata),
            working_crs_wkt=self.working_crs_wkt,
            transform=self.transform,
            tolerance=float(tolerance),
            step_size_m=float(step_size_m),
            max_distance_m=float(max_distance_m),
            chunk_rows=int(chunk_rows),
            chunk_cols=int(chunk_cols),
        )

    def illumination_raster(
        self,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
        *,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
        chunk_rows: int = 256,
        chunk_cols: int = 256,
        radius_pixels: int = 1,
        observation_time_utc: datetime | None = None,
        source_dataset_id: str = "unknown",
        source_metadata: Mapping[str, str] | None = None,
        precomputation: TerrainIlluminationCache | None = None,
    ) -> TerrainIlluminationRasterResult:
        return self.terrain_illumination_raster(
            sun_direction_fixed,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            chunk_rows=chunk_rows,
            chunk_cols=chunk_cols,
            radius_pixels=radius_pixels,
            observation_time_utc=observation_time_utc,
            source_dataset_id=source_dataset_id,
            source_metadata=source_metadata,
            precomputation=precomputation,
        )

    def terrain_shadow_raster(
        self,
        sun_direction_fixed: tuple[float, float, float] | np.ndarray | object,
        *,
        step_size_m: float = 5.0,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
        chunk_rows: int = 256,
        chunk_cols: int = 256,
        radius_pixels: int = 1,
        observation_time_utc: datetime | None = None,
        source_dataset_id: str = "unknown",
        source_metadata: Mapping[str, str] | None = None,
        precomputation: TerrainIlluminationCache | None = None,
    ) -> TerrainIlluminationRasterResult:
        return self.terrain_illumination_raster(
            sun_direction_fixed,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            chunk_rows=chunk_rows,
            chunk_cols=chunk_cols,
            radius_pixels=radius_pixels,
            observation_time_utc=observation_time_utc,
            source_dataset_id=source_dataset_id,
            source_metadata=source_metadata,
            precomputation=precomputation,
        )

    def _check_pixel(self, row: int, col: int) -> None:
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < self.shape[0]:
            raise IndexError("row is outside the terrain array")
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col < self.shape[1]:
            raise IndexError("column is outside the terrain array")
