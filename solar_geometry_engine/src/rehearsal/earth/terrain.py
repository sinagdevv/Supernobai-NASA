"""Earth-specific terrain geometry and direct-illumination products."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from math import cos, isfinite, radians, sin, sqrt
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

import numpy as np
import pyproj

from ..schemas import Site
from . import _illumination_numba
from .geometry import (
    WGS84_INVERSE_FLATTENING,
    WGS84_SEMI_MAJOR_M,
    EarthSolarGeometry,
    earth_sun_geometry,
)
from .kernels import EarthKernelSet

COPERNICUS_GLO30_METADATA_URL = (
    "https://dataspace.copernicus.eu/explore-data/data-collections/"
    "copernicus-contributing-missions/collections-description/COP-DEM"
)
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
    missing_sources: list[str]
    resampling: str


@dataclass(frozen=True)
class EarthTerrainMetadata:
    """Verified Layer 2/product metadata required for the supported GLO-30 path."""

    dataset_id: str
    vertical_reference: str
    elevation_unit: str
    metadata_source: str
    vertical_scale_applied: float = 1.0

    def __post_init__(self) -> None:
        if not self._is_glo30_id(self.dataset_id):
            raise ValueError("Earth illumination v1 currently supports Copernicus GLO-30 only")
        if "egm2008" not in self.vertical_reference.casefold():
            raise ValueError("Copernicus GLO-30 vertical reference must explicitly identify EGM2008")
        if self.elevation_unit.casefold() not in ("m", "metre", "metres", "meter", "meters"):
            raise ValueError("Copernicus GLO-30 elevations must be expressed in metres")
        if not self.metadata_source.strip():
            raise ValueError("vertical-reference metadata source must be specified")
        if not np.isfinite(self.vertical_scale_applied) or self.vertical_scale_applied <= 0.0:
            raise ValueError("vertical_scale_applied must be finite and positive")

    @staticmethod
    def _is_glo30_id(dataset_id: str) -> bool:
        return dataset_id == "copernicus-glo30" or dataset_id.endswith("-copernicus-glo30")

    @classmethod
    def copernicus_glo30(
        cls,
        dataset_id: str = "copernicus-glo30",
        *,
        vertical_scale_applied: float = 1.0,
    ) -> "EarthTerrainMetadata":
        """Create metadata from the checked official GLO-30 product specification.

        The product handbook specifies EGM2008 (EPSG:3855) vertical coordinates
        in metres. Callers must still pass the ID of the dataset used to make the
        Layer 3 patch; the patch itself does not carry that ID.
        """
        return cls(
            dataset_id=dataset_id,
            vertical_reference="EGM2008 orthometric height (EPSG:3855)",
            elevation_unit="m",
            metadata_source=COPERNICUS_GLO30_METADATA_URL,
            vertical_scale_applied=vertical_scale_applied,
        )

    @classmethod
    def from_layer2_record(
        cls,
        dataset_id: str,
        record: Mapping[str, object],
    ) -> "EarthTerrainMetadata":
        if record.get("body") != "earth" or record.get("kind") != "elevation":
            raise ValueError("Layer 2 record must describe an Earth elevation dataset")
        vertical_reference = str(record.get("vertical_datum", ""))
        products = record.get("products")
        units = {
            str(product.get("unit", ""))
            for product in products.values()
            if isinstance(product, Mapping)
        } if isinstance(products, Mapping) else set()
        if not units or not any(unit.casefold() in ("m", "metre", "metres", "meter", "meters") for unit in units):
            raise ValueError("Layer 2 record does not verify metre elevation units")
        return cls(
            dataset_id=dataset_id,
            vertical_reference=vertical_reference,
            elevation_unit="m",
            metadata_source="Layer 2 manifest record",
            vertical_scale_applied=float(record.get("vertical_scale", 1.0)),
        )


class EarthIlluminationCode(IntEnum):
    UNKNOWN = 0
    ILLUMINATED = 1
    TERRAIN_OBSTRUCTED = 2
    SURFACE_FACING_AWAY = 3
    INSUFFICIENT_COVERAGE = 4
    NO_DATA = -1


class EarthRayStatus(IntEnum):
    NO_DATA = _illumination_numba.RAY_NO_DATA
    UNKNOWN = _illumination_numba.RAY_UNKNOWN
    SEARCH_LIMIT_REACHED = _illumination_numba.RAY_SEARCH_LIMIT
    OBSTRUCTION_FOUND = _illumination_numba.RAY_OBSTRUCTION
    DEM_BOUNDARY = _illumination_numba.RAY_DEM_BOUNDARY
    TERRAIN_NODATA = _illumination_numba.RAY_TERRAIN_NODATA
    NORMAL_BOUNDARY = _illumination_numba.RAY_NORMAL_BOUNDARY
    NORMAL_NODATA = _illumination_numba.RAY_NORMAL_NODATA
    SURFACE_FACING_AWAY = _illumination_numba.RAY_SURFACE_AWAY
    VERTICAL_SUN = _illumination_numba.RAY_VERTICAL_SUN


@dataclass(frozen=True)
class EarthTerrainSurfaceNormal:
    row: int
    col: int
    normal_ecef: tuple[float, float, float] | None
    method: str
    neighborhood_radius_pixels: int
    neighborhood_diameter_m: float
    valid: bool
    coverage: str


@dataclass(frozen=True)
class EarthHorizonObservation:
    azimuth_deg: float
    apparent_elevation_deg: float | None
    distance_m: float | None
    samples_examined: int
    coverage: str
    ray_status: str


@dataclass(frozen=True)
class EarthHorizonProfile:
    observer_row: int
    observer_col: int
    azimuth_step_deg: float
    max_distance_m: float
    observations: tuple[EarthHorizonObservation, ...]

    @property
    def coverage_mask(self) -> tuple[bool, ...]:
        return tuple(item.coverage == "valid" for item in self.observations)


@dataclass(frozen=True)
class EarthIlluminationRasterResult:
    classification: np.ndarray
    valid_mask: np.ndarray
    normal_valid_mask: np.ndarray
    coverage_mask: np.ndarray
    ray_status: np.ndarray
    observation_time_utc: datetime
    solar_elevation_deg: float
    solar_azimuth_deg: float | None
    solar_direction_ecef: tuple[float, float, float]
    source_dataset_id: str
    source_metadata: Mapping[str, str]
    working_crs_wkt: str
    native_crs: str
    transform: tuple[float, float, float, float, float, float]
    pixel_size_m: float
    native_pixel_size_m: float
    elevation_unit: str
    vertical_reference: str
    processing_parameters: Mapping[str, float | int | str]
    solar_geometry_pixel: tuple[int, int] | None = None

    @property
    def valid_cell_count(self) -> int:
        return int(np.count_nonzero(self.valid_mask))

    @property
    def illuminated_cell_count(self) -> int:
        return int(np.count_nonzero(
            self.classification == int(EarthIlluminationCode.ILLUMINATED)
        ))

    @property
    def terrain_obstructed_cell_count(self) -> int:
        return int(np.count_nonzero(
            self.classification == int(EarthIlluminationCode.TERRAIN_OBSTRUCTED)
        ))

    @property
    def surface_facing_away_count(self) -> int:
        return int(np.count_nonzero(
            self.classification == int(EarthIlluminationCode.SURFACE_FACING_AWAY)
        ))

    @property
    def insufficient_coverage_count(self) -> int:
        return int(np.count_nonzero(
            self.classification == int(EarthIlluminationCode.INSUFFICIENT_COVERAGE)
        ))

    @property
    def no_data_count(self) -> int:
        return int(np.count_nonzero(
            self.classification == int(EarthIlluminationCode.NO_DATA)
        ))

    @property
    def classification_counts(self) -> dict[str, int]:
        return {
            code.name: int(np.count_nonzero(self.classification == int(code)))
            for code in EarthIlluminationCode
        }

    @property
    def ray_status_counts(self) -> dict[str, int]:
        return {
            status.name: int(np.count_nonzero(self.ray_status == int(status)))
            for status in EarthRayStatus
        }


_RAY_STATUS_NAMES = {int(status): status.name for status in EarthRayStatus}


def _ecef_position(
    longitude_deg: float,
    latitude_deg: float,
    elevation_m: float,
) -> np.ndarray:
    longitude = radians(longitude_deg)
    latitude = radians(latitude_deg)
    flattening = 1.0 / WGS84_INVERSE_FLATTENING
    eccentricity_squared = flattening * (2.0 - flattening)
    sin_latitude = sin(latitude)
    cos_latitude = cos(latitude)
    prime_vertical = WGS84_SEMI_MAJOR_M / sqrt(
        1.0 - eccentricity_squared * sin_latitude * sin_latitude
    )
    return np.array(
        [
            (prime_vertical + elevation_m) * cos_latitude * cos(longitude),
            (prime_vertical + elevation_m) * cos_latitude * sin(longitude),
            (prime_vertical * (1.0 - eccentricity_squared) + elevation_m) * sin_latitude,
        ],
        dtype=np.float64,
    )


@dataclass
class EarthTerrainPatch:
    elevations_m: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    working_crs_wkt: str
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    resampling: str
    sources: tuple[str, ...]
    missing_sources: tuple[str, ...]
    metadata: EarthTerrainMetadata
    longitudes_deg: np.ndarray = field(repr=False)
    latitudes_deg: np.ndarray = field(repr=False)
    _normals: np.ndarray | None = field(default=None, repr=False)
    _normal_valid: np.ndarray | None = field(default=None, repr=False)
    _normal_radius_pixels: int | None = field(default=None, repr=False)

    @classmethod
    def from_layer3_patch(
        cls,
        patch: _Layer3Patch,
        metadata: EarthTerrainMetadata,
    ) -> "EarthTerrainPatch":
        if patch.body != "earth":
            raise ValueError("Layer 3 patch body must be 'earth'")
        if not isinstance(metadata, EarthTerrainMetadata):
            raise TypeError("metadata must be an EarthTerrainMetadata instance")
        masked_elevations = np.ma.asarray(patch.z, dtype=np.float64)
        if masked_elevations.ndim != 2 or not np.issubdtype(masked_elevations.dtype, np.number):
            raise ValueError("patch.z must be a two-dimensional numeric elevation array")
        elevations = np.asarray(masked_elevations.filled(np.nan))
        if not np.isfinite(elevations).any():
            raise ValueError("patch.z must contain at least one valid elevation")

        crs = pyproj.CRS.from_wkt(patch.crs.to_wkt())
        geodetic = crs.geodetic_crs
        if geodetic is None or geodetic.ellipsoid is None:
            raise ValueError("Layer 3 working CRS must define an Earth geodetic ellipsoid")
        ellipsoid = geodetic.ellipsoid
        if (
            abs(ellipsoid.semi_major_metre - WGS84_SEMI_MAJOR_M) > 0.01
            or abs(ellipsoid.inverse_flattening - WGS84_INVERSE_FLATTENING) > 1e-6
        ):
            raise ValueError("Earth illumination v1 requires the WGS84 ellipsoid used by GLO-30")

        affine_values = tuple(patch.transform)
        if len(affine_values) < 6:
            raise ValueError("Layer 3 patch must contain a six-parameter affine transform")
        transform = tuple(float(value) for value in affine_values[:6])
        if not all(isfinite(value) for value in transform):
            raise ValueError("patch transform must contain only finite values")
        determinant = transform[0] * transform[4] - transform[1] * transform[3]
        if abs(determinant) < 1e-15:
            raise ValueError("patch transform must be invertible")

        pixel_size = float(patch.pixel_size_m)
        native_pixel_size = float(patch.native_pixel_size_m)
        if not isfinite(pixel_size) or pixel_size <= 0.0:
            raise ValueError("patch.pixel_size_m must be a positive metric spacing")
        if not isfinite(native_pixel_size) or native_pixel_size <= 0.0:
            raise ValueError("patch.native_pixel_size_m must be finite and positive")
        if not patch.native_crs.strip() or not patch.resampling.strip():
            raise ValueError("Layer 3 patch must retain its native CRS and resampling method")

        working_crs_wkt = crs.to_wkt()
        to_geographic = pyproj.Transformer.from_crs(crs, geodetic, always_xy=True)
        rows, cols = np.indices(elevations.shape, dtype=np.float64)
        a, b, c, d, e, f = transform
        x = a * (cols + 0.5) + b * (rows + 0.5) + c
        y = d * (cols + 0.5) + e * (rows + 0.5) + f
        longitude, latitude = to_geographic.transform(x, y)
        longitude = np.asarray(longitude, dtype=np.float64)
        latitude = np.asarray(latitude, dtype=np.float64)
        if (
            not np.isfinite(longitude[np.isfinite(elevations)]).all()
            or not np.isfinite(latitude[np.isfinite(elevations)]).all()
            or np.any(np.abs(latitude[np.isfinite(elevations)]) > 90.0)
        ):
            raise ValueError("valid terrain pixels must transform to finite Earth longitude/latitude")

        source_uris = tuple(str(uri) for uri in patch.sources)
        if not source_uris:
            raise ValueError("Layer 3 patch must retain at least one source URI")
        return cls(
            elevations_m=elevations.astype(np.float64, copy=False),
            transform=transform,
            working_crs_wkt=working_crs_wkt,
            native_crs=patch.native_crs,
            pixel_size_m=pixel_size,
            native_pixel_size_m=native_pixel_size,
            resampling=patch.resampling,
            sources=source_uris,
            missing_sources=tuple(str(uri) for uri in getattr(patch, "missing_sources", ())),
            metadata=metadata,
            longitudes_deg=longitude,
            latitudes_deg=latitude,
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.elevations_m.shape

    @property
    def valid_mask(self) -> np.ndarray:
        return np.isfinite(self.elevations_m)

    @property
    def coverage_fraction(self) -> float:
        return float(self.valid_mask.mean()) if self.elevations_m.size else 0.0

    def center_lonlat(self) -> tuple[float, float]:
        row, col = self.shape[0] // 2, self.shape[1] // 2
        return float(self.longitudes_deg[row, col]), float(self.latitudes_deg[row, col])

    def _require_numba(self) -> None:
        if not _illumination_numba.is_available():
            raise RuntimeError(
                "Numba is required for Earth terrain illumination; install the 'performance' extra"
            )

    def prepare_surface_normals(
        self,
        *,
        radius_pixels: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        self._require_numba()
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
            raise ValueError("radius_pixels must be an integer >= 1")
        if (
            self._normals is None
            or self._normal_valid is None
            or self._normal_radius_pixels != radius_pixels
        ):
            self._normals, self._normal_valid = _illumination_numba.compute_normals(
                self.elevations_m,
                self.longitudes_deg,
                self.latitudes_deg,
                radius_pixels,
                WGS84_SEMI_MAJOR_M,
                WGS84_INVERSE_FLATTENING,
            )
            self._normal_radius_pixels = radius_pixels
        return self._normals, self._normal_valid

    def terrain_surface_normal(
        self,
        row: int,
        col: int,
        *,
        radius_pixels: int = 1,
    ) -> EarthTerrainSurfaceNormal:
        if not 0 <= row < self.shape[0] or not 0 <= col < self.shape[1]:
            raise IndexError("pixel is outside the Earth terrain patch")
        if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
            raise ValueError("radius_pixels must be an integer >= 1")
        if not self.valid_mask[row, col]:
            return EarthTerrainSurfaceNormal(
                row, col, None, "WGS84 ECEF central differences", radius_pixels,
                2.0 * radius_pixels * self.pixel_size_m, False, "no_data",
            )
        r0, r1 = row - radius_pixels, row + radius_pixels
        c0, c1 = col - radius_pixels, col + radius_pixels
        if r0 < 0 or r1 >= self.shape[0] or c0 < 0 or c1 >= self.shape[1]:
            return EarthTerrainSurfaceNormal(
                row, col, None, "WGS84 ECEF central differences", radius_pixels,
                2.0 * radius_pixels * self.pixel_size_m, False, "insufficient",
            )
        if not all(
            self.valid_mask[r, c]
            for r, c in ((row, c0), (row, c1), (r0, col), (r1, col))
        ):
            return EarthTerrainSurfaceNormal(
                row, col, None, "WGS84 ECEF central differences", radius_pixels,
                2.0 * radius_pixels * self.pixel_size_m, False, "insufficient",
            )
        center = _ecef_position(
            float(self.longitudes_deg[row, col]),
            float(self.latitudes_deg[row, col]),
            0.0,
        )
        points = [
            _ecef_position(
                float(self.longitudes_deg[r, c]),
                float(self.latitudes_deg[r, c]),
                0.0,
            )
            for r, c in ((row, c0), (row, c1), (r0, col), (r1, col))
        ]
        lat = radians(float(self.latitudes_deg[row, col]))
        lon = radians(float(self.longitudes_deg[row, col]))
        up = np.array([cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)])
        offsets = [
            points[index] - center
            + (float(self.elevations_m[r, c]) - float(self.elevations_m[row, col])) * up
            for index, (r, c) in enumerate(
                ((row, c0), (row, c1), (r0, col), (r1, col))
            )
        ]
        tangent_col = offsets[1] - offsets[0]
        tangent_row = offsets[3] - offsets[2]
        normal = np.cross(tangent_col, tangent_row)
        if float(np.dot(normal, up)) < 0.0:
            normal = -normal
        norm = float(np.linalg.norm(normal))
        if not isfinite(norm) or norm <= 1e-12:
            return EarthTerrainSurfaceNormal(
                row, col, None, "WGS84 ECEF central differences", radius_pixels,
                2.0 * radius_pixels * self.pixel_size_m, False, "insufficient",
            )
        normal /= norm
        return EarthTerrainSurfaceNormal(
            row,
            col,
            tuple(float(value) for value in normal),
            "WGS84 ECEF central differences",
            radius_pixels,
            2.0 * radius_pixels * self.pixel_size_m,
            True,
            "valid",
        )

    def horizon_profile(
        self,
        row: int,
        col: int,
        *,
        azimuth_step_deg: float = 5.0,
        max_distance_m: float = 2500.0,
    ) -> EarthHorizonProfile:
        self._require_numba()
        self._check_pixel(row, col)
        if not isfinite(azimuth_step_deg) or not 0.0 < azimuth_step_deg <= 360.0:
            raise ValueError("azimuth_step_deg must be finite and in (0, 360]")
        if not isfinite(max_distance_m) or max_distance_m <= 0.0:
            raise ValueError("max_distance_m must be finite and positive")
        azimuths = np.arange(0.0, 360.0, azimuth_step_deg, dtype=np.float64)
        apparent, distance, status, samples = _illumination_numba.horizon_rays(
            self.elevations_m,
            self.longitudes_deg,
            self.latitudes_deg,
            row,
            col,
            np.radians(azimuths),
            WGS84_SEMI_MAJOR_M,
            WGS84_INVERSE_FLATTENING,
            max_distance_m,
        )
        observations = []
        for index, azimuth in enumerate(azimuths):
            code = int(status[index])
            complete = code == _illumination_numba.RAY_SEARCH_LIMIT
            angle = float(apparent[index]) if np.isfinite(apparent[index]) else None
            ray_distance = (
                min(float(distance[index]), max_distance_m)
                if np.isfinite(distance[index]) else None
            )
            observations.append(
                EarthHorizonObservation(
                    azimuth_deg=float(azimuth),
                    apparent_elevation_deg=angle,
                    distance_m=ray_distance,
                    samples_examined=int(samples[index]),
                    coverage="valid" if complete else "insufficient",
                    ray_status=_RAY_STATUS_NAMES.get(code, "UNKNOWN"),
                )
            )
        return EarthHorizonProfile(
            observer_row=row,
            observer_col=col,
            azimuth_step_deg=float(azimuth_step_deg),
            max_distance_m=float(max_distance_m),
            observations=tuple(observations),
        )

    def illumination_raster(
        self,
        observation_time_utc: datetime,
        *,
        kernels: EarthKernelSet,
        target_pixel: tuple[int, int] | None = None,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
        obstruction_tolerance_m: float = 0.0,
        radius_pixels: int = 1,
    ) -> EarthIlluminationRasterResult:
        self._require_numba()
        if not isfinite(max_distance_m) or max_distance_m <= 0.0:
            raise ValueError("max_distance_m must be finite and positive")
        if not isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("tolerance must be finite and nonnegative")
        if not isfinite(obstruction_tolerance_m) or obstruction_tolerance_m < 0.0:
            raise ValueError("obstruction_tolerance_m must be finite and nonnegative")
        if not isinstance(observation_time_utc, datetime):
            raise TypeError("observation_time_utc must be a datetime instance")
        if observation_time_utc.tzinfo is None or observation_time_utc.utcoffset() is None:
            raise ValueError("observation_time_utc must be timezone-aware")
        geometry_pixel = (
            (self.shape[0] // 2, self.shape[1] // 2)
            if target_pixel is None
            else target_pixel
        )
        self._check_pixel(*geometry_pixel)
        longitude = float(self.longitudes_deg[geometry_pixel])
        latitude = float(self.latitudes_deg[geometry_pixel])
        if not isfinite(longitude) or not isfinite(latitude):
            raise ValueError("solar geometry target must have finite geographic coordinates")
        solar = earth_sun_geometry(
            Site(
                id=self.metadata.dataset_id,
                lat=latitude,
                lon=longitude,
                tz="UTC",
                elevation_m=0.0,
            ),
            observation_time_utc,
            kernels,
        )
        return self.illumination_with_solar_geometry(
            solar,
            target_pixel=geometry_pixel,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            obstruction_tolerance_m=obstruction_tolerance_m,
            radius_pixels=radius_pixels,
        )

    def illumination_with_solar_geometry(
        self,
        solar: EarthSolarGeometry,
        *,
        target_pixel: tuple[int, int] | None = None,
        max_distance_m: float = 2500.0,
        tolerance: float = 1e-9,
        obstruction_tolerance_m: float = 0.0,
        radius_pixels: int = 1,
    ) -> EarthIlluminationRasterResult:
        """Classify the patch using solar geometry at the selected target cell."""
        self._require_numba()
        if not isfinite(max_distance_m) or max_distance_m <= 0.0:
            raise ValueError("max_distance_m must be finite and positive")
        if not isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("tolerance must be finite and nonnegative")
        if not isfinite(obstruction_tolerance_m) or obstruction_tolerance_m < 0.0:
            raise ValueError("obstruction_tolerance_m must be finite and nonnegative")
        if solar.frame != "ITRF93":
            raise ValueError("Earth illumination requires an ITRF93 solar direction")
        if solar.time_utc.tzinfo is None or solar.time_utc.utcoffset() is None:
            raise ValueError("solar geometry time must be timezone-aware")
        geometry_pixel = (
            (self.shape[0] // 2, self.shape[1] // 2)
            if target_pixel is None
            else target_pixel
        )
        self._check_pixel(*geometry_pixel)
        target_lon = float(self.longitudes_deg[geometry_pixel])
        target_lat = float(self.latitudes_deg[geometry_pixel])
        if not isfinite(target_lon) or not isfinite(target_lat):
            raise ValueError("solar geometry target must have finite geographic coordinates")
        if (
            abs(solar.latitude_deg - target_lat) > 1e-7
            or abs(((solar.longitude_deg - target_lon + 180.0) % 360.0) - 180.0) > 1e-7
        ):
            raise ValueError("solar geometry location must match the selected target pixel")
        direction = np.asarray(solar.direction_ecef, dtype=np.float64)
        if direction.shape != (3,) or not np.isfinite(direction).all():
            raise ValueError("solar direction must contain three finite Earth-fixed components")
        direction_norm = float(np.linalg.norm(direction))
        if not isfinite(direction_norm) or direction_norm == 0.0:
            raise ValueError("solar direction must be a nonzero vector")
        direction /= direction_norm

        normals, normal_valid = self.prepare_surface_normals(radius_pixels=radius_pixels)
        classes, valid, normal_mask, coverage, ray_status = _illumination_numba.classify_grid(
            self.elevations_m,
            self.longitudes_deg,
            self.latitudes_deg,
            normals,
            normal_valid,
            *direction,
            WGS84_SEMI_MAJOR_M,
            WGS84_INVERSE_FLATTENING,
            max_distance_m,
            tolerance,
            obstruction_tolerance_m,
        )
        transform = tuple(float(value) for value in self.transform)
        return EarthIlluminationRasterResult(
            classification=classes,
            valid_mask=valid,
            normal_valid_mask=normal_mask,
            coverage_mask=coverage,
            ray_status=ray_status,
            observation_time_utc=solar.time_utc.astimezone(timezone.utc),
            solar_elevation_deg=solar.solar_elevation_deg,
            solar_azimuth_deg=solar.solar_azimuth_deg,
            solar_direction_ecef=tuple(float(value) for value in direction),
            source_dataset_id=self.metadata.dataset_id,
            source_metadata=MappingProxyType({
                "dataset_id": self.metadata.dataset_id,
                "sources": ";".join(self.sources),
                "missing_sources": ";".join(self.missing_sources),
                "metadata_source": self.metadata.metadata_source,
                "resampling": self.resampling,
                "vertical_reference": self.metadata.vertical_reference,
                "elevation_unit": self.metadata.elevation_unit,
            }),
            working_crs_wkt=self.working_crs_wkt,
            native_crs=self.native_crs,
            transform=transform,
            pixel_size_m=self.pixel_size_m,
            native_pixel_size_m=self.native_pixel_size_m,
            elevation_unit=self.metadata.elevation_unit,
            vertical_reference=self.metadata.vertical_reference,
            processing_parameters=MappingProxyType({
                "engine": "Numba parallel",
                "solar_geometry_reference": "selected target pixel",
                "solar_geometry_pixel": f"{geometry_pixel[0]},{geometry_pixel[1]}",
                "max_distance_m": float(max_distance_m),
                "dot_tolerance": float(tolerance),
                "obstruction_tolerance_m": float(obstruction_tolerance_m),
                "normal_radius_pixels": int(radius_pixels),
                "normal_neighborhood_diameter_m": float(
                    2.0 * radius_pixels * self.pixel_size_m
                ),
                "horizon_method": "supercover grid traversal with WGS84 ellipsoid curvature",
                "vertical_geometry": (
                    "EGM2008 orthometric relief relative to the patch center; "
                    "local geoid-undulation gradients are not modeled"
                ),
                "earth_location_height_for_solar_geometry_m": 0.0,
                "vertical_scale_applied": float(self.metadata.vertical_scale_applied),
            }),
            solar_geometry_pixel=geometry_pixel,
        )

    def _check_pixel(self, row: int, col: int) -> None:
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < self.shape[0]:
            raise IndexError("row is outside the Earth terrain patch")
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col < self.shape[1]:
            raise IndexError("column is outside the Earth terrain patch")
