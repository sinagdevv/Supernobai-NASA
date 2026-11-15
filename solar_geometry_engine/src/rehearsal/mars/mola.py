"""Native-grid access to the PDS MGS MOLA 32-pixel-per-degree MEGDR products."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from math import floor, isfinite
from pathlib import Path
from types import TracebackType
from typing import Any

import numpy as np
from pyproj import CRS

from .terrain import MarsTerrainMetadata, MarsTerrainPatch, _Layer3Patch


MOLA_SHAPE = (5760, 11520)
MOLA_PIXELS_PER_DEGREE = 32
MOLA_PIXEL_SIZE_M = 1852.2306687
MOLA_MAP_RADIUS_M = 3_396_000.0
MOLA_UPPER_LEFT_X_M = -10_668_848.652
MOLA_UPPER_LEFT_Y_M = 5_334_424.326
MOLA_RADIUS_SCALE_FACTOR = 1.0
MOLA_RADIUS_VALUE_OFFSET_M = 3_396_000.0
MOLA_SOURCE_BASE_URL = (
    "https://pds-geosciences.wustl.edu/mgs/"
    "urn-nasa-pds-mgs_mola_topography_derived"
)

_MOLA_CRS = CRS.from_proj4(
    "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 "
    "+a=3396000 +b=3396000 +units=m +no_defs +type=crs"
)
_TOPOGRAPHY_FILE = "megt90n000fb.img"
_COUNTS_FILE = "megc90n000fb.img"
_RADIUS_FILE = "megr90n000fb.img"
_EXPECTED_IMAGE_BYTES = MOLA_SHAPE[0] * MOLA_SHAPE[1] * 2
_AREOID_REFERENCE = (
    "GMM3 (mgm1025) areoid, degree and order 50; "
    "MOLA topography is planetary radius minus areoid radius"
)


class _MolaLayer3View(_Layer3Patch):
    """Structural Layer 3 patch view for an untouched native MOLA window."""

    body: str
    z: np.ndarray
    observation_counts: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    crs: CRS
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    sources: list[str]
    missing_sources: list[str]
    resampling: str

    def __init__(
        self,
        z: np.ndarray,
        observation_counts: np.ndarray,
        transform: tuple[float, float, float, float, float, float],
        sources: list[str],
    ) -> None:
        self.body = "mars"
        self.z = z
        self.observation_counts = observation_counts
        self.transform = transform
        self.crs = _MOLA_CRS
        self.native_crs = (
            "PDS IAU2000_MARS planetocentric equirectangular; "
            "3396 km sphere; east-positive longitude"
        )
        self.pixel_size_m = MOLA_PIXEL_SIZE_M
        self.native_pixel_size_m = MOLA_PIXEL_SIZE_M
        self.sources = sources
        self.missing_sources: list[str] = []
        self.resampling = "none; native source pixels copied"


@dataclass(frozen=True)
class MarsMolaGeometricWindow:
    """Unmodified terrain patch plus the original radius samples for geometry."""

    terrain_patch: MarsTerrainPatch
    row_offset: int
    column_offset: int
    radius_samples: np.ndarray
    radius_source: str
    radius_scale_factor: float = MOLA_RADIUS_SCALE_FACTOR
    radius_value_offset_m: float = MOLA_RADIUS_VALUE_OFFSET_M

    def __post_init__(self) -> None:
        if isinstance(self.row_offset, bool) or not isinstance(
            self.row_offset, (int, np.integer)
        ):
            raise ValueError("MOLA row_offset must be an integer")
        if isinstance(self.column_offset, bool) or not isinstance(
            self.column_offset, (int, np.integer)
        ):
            raise ValueError("MOLA column_offset must be an integer")
        if self.radius_samples.shape != self.terrain_patch.shape:
            raise ValueError("MOLA radius samples must match the terrain patch shape")
        if not np.issubdtype(self.radius_samples.dtype, np.integer):
            raise ValueError("MOLA radius samples must remain integer source samples")
        if (
            self.row_offset < 0
            or self.column_offset < 0
            or self.row_offset + self.terrain_patch.shape[0] > MOLA_SHAPE[0]
            or self.column_offset + self.terrain_patch.shape[1] > MOLA_SHAPE[1]
        ):
            raise ValueError("MOLA geometric window is outside the global raster")
        if not self.radius_source.strip():
            raise ValueError("MOLA radius source must be specified")
        if Path(self.radius_source).name != _RADIUS_FILE:
            raise ValueError(f"MOLA radius source must be {_RADIUS_FILE}")
        if not np.isfinite(self.radius_scale_factor) or self.radius_scale_factor <= 0.0:
            raise ValueError("MOLA radius scale factor must be finite and positive")
        if not np.isfinite(self.radius_value_offset_m):
            raise ValueError("MOLA radius value offset must be finite")
        if (
            self.radius_scale_factor != MOLA_RADIUS_SCALE_FACTOR
            or self.radius_value_offset_m != MOLA_RADIUS_VALUE_OFFSET_M
        ):
            raise ValueError("MOLA geometric conversion requires the verified MEGR scale and offset")
        metadata = self.terrain_patch.metadata
        if (
            metadata.body_fixed_frame != "IAU2000_MARS"
            or metadata.coordinate_reference_model != "IAU2000_MARS"
            or metadata.latitude_type != "planetocentric"
            or metadata.longitude_direction != "east-positive"
            or metadata.longitude_domain != "[0, 360) degrees"
        ):
            raise ValueError("MOLA geometric window has incompatible coordinate metadata")
        provenance = metadata.provenance
        if provenance.get("radius_product") != (
            "MEGR90N000FB, PDS3 version 2.0; PDS4 label 1.1"
        ):
            raise ValueError("MOLA geometric window must use the verified MEGR90N000FB product")
        for key in ("topography_sha256", "observation_counts_sha256", "radius_sha256"):
            digest = provenance.get(key, "")
            if len(digest) != 64 or any(
                character not in "0123456789abcdefABCDEF" for character in digest
            ):
                raise ValueError(f"MOLA geometric window provenance is missing {key}")
        if not np.all(np.isfinite(self.planetary_radius_m)) or np.any(
            self.planetary_radius_m <= 0.0
        ):
            raise ValueError("decoded MOLA planetary radii must be finite and positive")
        self.radius_samples.setflags(write=False)

    @property
    def planetary_radius_m(self) -> np.ndarray:
        """Decode the PDS radius value without changing the retained source samples."""
        return (
            self.radius_samples.astype(np.float64) * self.radius_scale_factor
            + self.radius_value_offset_m
        )


def _integer_index(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MarsMolaMegdr32ppd:
    """Read verified MOLA topography/count windows and adapt them to MarsTerrainPatch.

    The source is opened read-only as signed big-endian 16-bit data. No resampling,
    interpolation, NoData substitution, or frame rotation is performed.
    """

    def __init__(self, source_directory: str | Path) -> None:
        self.source_directory = Path(source_directory).resolve()
        self._topography: np.memmap | None = None
        self._counts: np.memmap | None = None
        self._radius: np.memmap | None = None
        self._source_hashes: dict[str, str] = {}

    def __enter__(self) -> "MarsMolaMegdr32ppd":
        if (
            self._topography is not None
            and self._counts is not None
            and self._radius is not None
        ):
            return self

        provenance_path = self.source_directory.parent / "PROVENANCE.json"
        if not provenance_path.is_file():
            raise FileNotFoundError(
                f"Required MOLA provenance record is missing: {provenance_path}"
            )
        provenance: Any = json.loads(provenance_path.read_text(encoding="utf-8"))
        records = provenance.get("files")
        if not isinstance(records, list):
            raise ValueError("MOLA provenance record must contain a files list")
        by_name = {
            entry.get("filename"): entry
            for entry in records
            if isinstance(entry, dict) and isinstance(entry.get("filename"), str)
        }

        image_paths: list[Path] = []
        source_hashes: dict[str, str] = {}
        for filename in (_TOPOGRAPHY_FILE, _COUNTS_FILE, _RADIUS_FILE):
            path = self.source_directory / filename
            if not path.is_file():
                raise FileNotFoundError(f"Required MOLA image is missing: {path}")
            if path.stat().st_size != _EXPECTED_IMAGE_BYTES:
                raise ValueError(
                    f"{filename} has {path.stat().st_size} bytes; expected "
                    f"{_EXPECTED_IMAGE_BYTES} for {MOLA_SHAPE} signed 16-bit samples"
                )
            record = by_name.get(filename)
            if record is None or not isinstance(record.get("sha256"), str):
                raise ValueError(f"MOLA provenance has no SHA-256 for {filename}")
            actual_hash = _sha256(path)
            if actual_hash.lower() != record["sha256"].lower():
                raise ValueError(f"SHA-256 mismatch for MOLA source image {filename}")
            image_paths.append(path)
            source_hashes[filename] = actual_hash.lower()

        topography = np.memmap(
            image_paths[0], dtype=">i2", mode="r", shape=MOLA_SHAPE
        )
        counts = np.memmap(image_paths[1], dtype=">i2", mode="r", shape=MOLA_SHAPE)
        radius = np.memmap(image_paths[2], dtype=">i2", mode="r", shape=MOLA_SHAPE)
        self._topography = topography
        self._counts = counts
        self._radius = radius
        self._source_hashes = source_hashes
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        for array in (self._topography, self._counts, self._radius):
            if array is not None and array._mmap is not None:
                array._mmap.close()
        self._topography = None
        self._counts = None
        self._radius = None
        self._source_hashes = {}

    @staticmethod
    def pixel_to_lonlat(row: int, column: int) -> tuple[float, float]:
        """Return the native pixel-center longitude [0,360) and planetocentric latitude."""
        row = _integer_index(row, "row")
        column = _integer_index(column, "column")
        if not 0 <= row < MOLA_SHAPE[0] or not 0 <= column < MOLA_SHAPE[1]:
            raise ValueError("MOLA pixel index is outside the global raster")
        longitude = (column + 0.5) / MOLA_PIXELS_PER_DEGREE
        latitude = 90.0 - (row + 0.5) / MOLA_PIXELS_PER_DEGREE
        return longitude, latitude

    @staticmethod
    def lonlat_to_pixel(longitude_deg: float, latitude_deg: float) -> tuple[int, int]:
        """Map east-positive [0,360) longitude and planetocentric latitude to a pixel."""
        if isinstance(longitude_deg, bool) or isinstance(latitude_deg, bool):
            raise ValueError("longitude and latitude must be finite numbers")
        longitude = float(longitude_deg)
        latitude = float(latitude_deg)
        if not isfinite(longitude) or not isfinite(latitude):
            raise ValueError("longitude and latitude must be finite")
        if not -90.0 <= latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90 degrees")
        longitude = longitude % 360.0
        column = min(floor(longitude * MOLA_PIXELS_PER_DEGREE), MOLA_SHAPE[1] - 1)
        row = min(
            max(floor((90.0 - latitude) * MOLA_PIXELS_PER_DEGREE), 0),
            MOLA_SHAPE[0] - 1,
        )
        return row, column

    def read_window(
        self,
        row_offset: int,
        column_offset: int,
        height: int,
        width: int,
    ) -> MarsTerrainPatch:
        """Return a native-grid window; windows do not wrap across the longitude seam."""
        if self._topography is None or self._counts is None or self._radius is None:
            raise RuntimeError("Open MarsMolaMegdr32ppd with a with statement before reading")
        row_offset = _integer_index(row_offset, "row_offset")
        column_offset = _integer_index(column_offset, "column_offset")
        height = _integer_index(height, "height")
        width = _integer_index(width, "width")
        if height <= 0 or width <= 0:
            raise ValueError("window height and width must be positive")
        if (
            row_offset < 0
            or column_offset < 0
            or row_offset + height > MOLA_SHAPE[0]
            or column_offset + width > MOLA_SHAPE[1]
        ):
            raise ValueError("MOLA window is outside the global raster")

        z = np.asarray(
            self._topography[row_offset : row_offset + height, column_offset : column_offset + width],
            dtype=np.float64,
        )
        counts = np.asarray(
            self._counts[row_offset : row_offset + height, column_offset : column_offset + width],
            dtype=np.int16,
        )
        transform = (
            MOLA_PIXEL_SIZE_M,
            0.0,
            MOLA_UPPER_LEFT_X_M + column_offset * MOLA_PIXEL_SIZE_M,
            0.0,
            -MOLA_PIXEL_SIZE_M,
            MOLA_UPPER_LEFT_Y_M - row_offset * MOLA_PIXEL_SIZE_M,
        )
        topography_path = self.source_directory / _TOPOGRAPHY_FILE
        counts_path = self.source_directory / _COUNTS_FILE
        view = _MolaLayer3View(
            z=z,
            observation_counts=counts,
            transform=transform,
            sources=[str(topography_path), str(counts_path)],
        )
        metadata = MarsTerrainMetadata(
            body_fixed_frame="IAU2000_MARS",
            elevation_reference=_AREOID_REFERENCE,
            reference_radius_m=MOLA_MAP_RADIUS_M,
            provenance={
                "dataset": "MGS MOLA MEGDR global topography and observation counts",
                "source_url": f"{MOLA_SOURCE_BASE_URL}/meg032/",
                "topography_product": "MEGT90N000FB, PDS3 version 2.0; PDS4 label 1.1",
                "topography_sha256": self._source_hashes[_TOPOGRAPHY_FILE],
                "observation_count_product": "MEGC90N000FB, PDS3 version 2.0; PDS4 label 1.1",
                "observation_counts_sha256": self._source_hashes[_COUNTS_FILE],
                "elevation_unit": "m",
                "elevation_reference": _AREOID_REFERENCE,
                "reference_radius_semantics": (
                    "3396000 m MOLA map-projection sphere; not the PCK ellipsoid "
                    "or the elevation datum"
                ),
                "coordinate_reference_model": "IAU2000_MARS",
                "latitude_type": "planetocentric",
                "longitude_direction": "east-positive",
                "longitude_domain": "[0, 360) degrees",
                "no_data": "No NoData constant declared; raw elevations preserved",
                "observation_coverage": "MEGC90N000FB count value; zero means no observations",
            },
            elevation_unit="m",
            latitude_type="planetocentric",
            longitude_direction="east-positive",
            longitude_domain="[0, 360) degrees",
            coordinate_reference_model="IAU2000_MARS",
        )
        return MarsTerrainPatch.from_layer3_patch(view, metadata)

    def read_geometric_window(
        self,
        row_offset: int,
        column_offset: int,
        height: int,
        width: int,
    ) -> MarsMolaGeometricWindow:
        """Read a terrain window and the matching mean-radius source samples."""
        if self._radius is None:
            raise RuntimeError("Open MarsMolaMegdr32ppd with a with statement before reading")
        row_offset = _integer_index(row_offset, "row_offset")
        column_offset = _integer_index(column_offset, "column_offset")
        height = _integer_index(height, "height")
        width = _integer_index(width, "width")
        terrain = self.read_window(row_offset, column_offset, height, width)
        radius_samples = np.asarray(
            self._radius[
                row_offset : row_offset + height,
                column_offset : column_offset + width,
            ],
            dtype=np.int16,
        )
        radius_path = self.source_directory / _RADIUS_FILE
        provenance = dict(terrain.metadata.provenance)
        provenance.update(
            {
                "radius_product": "MEGR90N000FB, PDS3 version 2.0; PDS4 label 1.1",
                "radius_source": str(radius_path),
                "radius_sha256": self._source_hashes[_RADIUS_FILE],
                "radius_encoding": (
                    "signed 16-bit big-endian metres; physical radius = "
                    "sample * 1 + 3396000 m"
                ),
                "radius_statistic": "mean planetary radius per bin; empty bins interpolated",
            }
        )
        metadata = replace(terrain.metadata, provenance=provenance)
        terrain = replace(terrain, metadata=metadata, provenance=provenance)
        return MarsMolaGeometricWindow(
            terrain_patch=terrain,
            row_offset=row_offset,
            column_offset=column_offset,
            radius_samples=radius_samples,
            radius_source=str(radius_path),
        )
