"""Repeated Earth terrain illumination for explicit observation times."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator

import numpy as np

from ..spice_provenance import identify_spice_kernels
from ..windows.temporal import (
    RehearsalCriteria,
    RehearsalEvaluation,
    ScientificEvidence,
    aggregate_rehearsal,
    evaluation_intervals,
    observation_from_raster,
)
from .kernels import EarthKernelSet
from .terrain import (
    EarthIlluminationCode,
    EarthIlluminationRasterResult,
    EarthRayStatus,
    EarthTerrainPatch,
)


def _ordered_utc_times(observation_times_utc: Iterable[datetime]) -> list[datetime]:
    times = list(observation_times_utc)
    if not times:
        raise ValueError("observation_times_utc must contain at least one timestamp")
    normalized = []
    for index, instant in enumerate(times):
        if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError(f"observation time {index} must be a timezone-aware datetime")
        normalized.append(instant.astimezone(timezone.utc))
    if any(current <= previous for previous, current in zip(normalized, normalized[1:])):
        raise ValueError("observation_times_utc must be in strictly increasing order")
    return normalized


def iter_earth_illumination_series(
    terrain: EarthTerrainPatch,
    observation_times_utc: Iterable[datetime],
    *,
    kernels: EarthKernelSet,
    max_distance_m: float = 2500.0,
    tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 0.0,
    radius_pixels: int = 1,
    target_pixel: tuple[int, int] | None = None,
) -> Iterator[EarthIlluminationRasterResult]:
    """Stream ordered Earth classifications while reusing terrain normals."""
    utc_times = _ordered_utc_times(observation_times_utc)
    terrain.prepare_surface_normals(radius_pixels=radius_pixels)
    target = (
        (terrain.shape[0] // 2, terrain.shape[1] // 2)
        if target_pixel is None
        else target_pixel
    )
    row, col = target
    if (
        isinstance(row, bool) or isinstance(col, bool)
        or not isinstance(row, int) or not isinstance(col, int)
        or not 0 <= row < terrain.shape[0]
        or not 0 <= col < terrain.shape[1]
    ):
        raise ValueError("target_pixel must be an in-bounds (row, column) pair")
    for instant in utc_times:
        yield terrain.illumination_raster(
            instant,
            kernels=kernels,
            target_pixel=target,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            obstruction_tolerance_m=obstruction_tolerance_m,
            radius_pixels=radius_pixels,
        )


def run_earth_illumination_series(
    terrain: EarthTerrainPatch,
    observation_times_utc: Iterable[datetime],
    *,
    kernels: EarthKernelSet,
    max_distance_m: float = 2500.0,
    tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 0.0,
    radius_pixels: int = 1,
    target_pixel: tuple[int, int] | None = None,
) -> list[EarthIlluminationRasterResult]:
    """Calculate timestamped classifications, reusing normals for the same DEM."""
    return list(
        iter_earth_illumination_series(
            terrain,
            observation_times_utc,
            kernels=kernels,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            obstruction_tolerance_m=obstruction_tolerance_m,
            radius_pixels=radius_pixels,
            target_pixel=target_pixel,
        )
    )


def evaluate_earth_rehearsal_windows(
    terrain: EarthTerrainPatch,
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
    *,
    kernels: EarthKernelSet,
    criteria: RehearsalCriteria | None = None,
    target_pixel: tuple[int, int] | None = None,
    max_distance_m: float = 2500.0,
    tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 0.0,
    radius_pixels: int = 1,
    evidence: ScientificEvidence | None = None,
) -> RehearsalEvaluation:
    """Evaluate target-cell rehearsal intervals using Earth terrain illumination."""
    if not isinstance(terrain, EarthTerrainPatch):
        raise TypeError("terrain must be an EarthTerrainPatch")
    if not isinstance(kernels, EarthKernelSet):
        raise TypeError("kernels must be an EarthKernelSet")
    selected_criteria = criteria or RehearsalCriteria()
    intervals = evaluation_intervals(start_utc, end_utc, step)
    target = (
        (terrain.shape[0] // 2, terrain.shape[1] // 2)
        if target_pixel is None
        else target_pixel
    )
    row, col = target
    if (
        isinstance(row, bool) or isinstance(col, bool)
        or not isinstance(row, int) or not isinstance(col, int)
        or not 0 <= row < terrain.shape[0] or not 0 <= col < terrain.shape[1]
    ):
        raise ValueError("target_pixel must be an in-bounds (row, column) pair")
    target_longitude = float(terrain.longitudes_deg[row, col])
    target_latitude = float(terrain.latitudes_deg[row, col])
    if (
        not np.isfinite(target_longitude)
        or not np.isfinite(target_latitude)
        or not -90.0 <= target_latitude <= 90.0
    ):
        raise ValueError("target_pixel must have valid Earth geographic coordinates")
    kernel_identities = identify_spice_kernels(
        (
            ("leap-seconds kernel", kernels.leap_seconds),
            ("planetary ephemeris SPK", kernels.planetary_spk),
            ("Earth orientation binary PCK", kernels.earth_orientation_pck),
            ("planetary constants text PCK", kernels.generic_pck),
        )
    )

    observations = []
    for interval, result in zip(
        intervals,
        iter_earth_illumination_series(
            terrain,
            (item[0] for item in intervals),
            kernels=kernels,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            obstruction_tolerance_m=obstruction_tolerance_m,
            radius_pixels=radius_pixels,
            target_pixel=target,
        ),
    ):
        observations.append(
            observation_from_raster(
                interval=interval,
                classification=result.classification,
                valid_mask=result.valid_mask,
                coverage_mask=result.coverage_mask,
                class_codes=EarthIlluminationCode,
                ray_status=getattr(result, "ray_status", None),
                ray_status_codes=EarthRayStatus,
                target_pixel=target,
                solar_elevation_deg=result.solar_elevation_deg,
                solar_azimuth_deg=result.solar_azimuth_deg,
                source_dataset_id=result.source_dataset_id,
                source_metadata=result.source_metadata,
                solar_direction_fixed=result.solar_direction_ecef,
                solar_frame="ITRF93",
            )
        )

    first = observations[0]
    provenance = {
        "body": "earth",
        "frame": "ITRF93",
        "dataset_id": first.source_dataset_id,
        "vertical_reference": terrain.metadata.vertical_reference,
        "elevation_unit": terrain.metadata.elevation_unit,
        "metadata_source": terrain.metadata.metadata_source,
        "working_crs_wkt": terrain.working_crs_wkt,
        "native_crs": terrain.native_crs,
        "resampling": terrain.resampling,
        "terrain_sources": ";".join(terrain.sources),
        "missing_terrain_sources": ";".join(terrain.missing_sources),
        "pixel_size_m": str(terrain.pixel_size_m),
        "native_pixel_size_m": str(terrain.native_pixel_size_m),
        "affine_transform": ",".join(str(value) for value in terrain.transform),
        "vertical_scale_applied": str(terrain.metadata.vertical_scale_applied),
        "spice_kernel_paths": ";".join(str(path) for path in kernels.paths()),
        "solar_geometry_reference": f"selected target pixel ({row}, {col})",
        "solar_geometry_pixel": f"{row},{col}",
    }
    provenance.update(
        {f"source.{key}": value for key, value in first.source_metadata.items()}
    )
    return aggregate_rehearsal(
        body="earth",
        start_utc=start_utc,
        end_utc=end_utc,
        step=step,
        intervals=intervals,
        observations=observations,
        target_pixel=target,
        criteria=selected_criteria,
        provenance=provenance,
        source_grid_id="Layer 3 Earth working raster",
        target_longitude_deg=target_longitude,
        target_latitude_deg=target_latitude,
        target_coordinate_frame="ITRF93 geodetic longitude/latitude",
        kernel_identities=kernel_identities,
        evidence=evidence,
        scientific_limitations=(
            "Solar geometry is geometric SPICE output without atmospheric refraction.",
            "GLO-30 is a digital surface model; vegetation and structures may affect heights.",
            "Terrain illumination is limited to the configured ray distance and local patch coverage.",
            "No independent observational shadow-accuracy validation is included.",
        ),
    )
