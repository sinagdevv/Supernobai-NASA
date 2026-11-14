"""Mars-specific temporal rehearsal evaluation on native MOLA windows."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

import numpy as np

from ..windows.temporal import (
    RehearsalCriteria,
    RehearsalEvaluation,
    ScientificEvidence,
    aggregate_rehearsal,
    evaluation_intervals,
    observation_from_raster,
)
from ..spice_provenance import identify_spice_kernels
from .illumination import (
    MarsIlluminationClass,
    MarsRayStatus,
    mars_mola_illumination_raster,
)
from .mola import MOLA_PIXELS_PER_DEGREE, MOLA_SHAPE, MarsMolaGeometricWindow
from .mola_frame import MarsMolaFrameTransform
from .reference import MarsKernelSet


def _mola_source_pixel(
    windows: Sequence[MarsMolaGeometricWindow],
    target_pixel: tuple[int, int],
) -> tuple[int, int]:
    row, col = target_pixel
    first = windows[0]
    source_row = first.row_offset + row
    if source_row >= MOLA_SHAPE[0]:
        raise ValueError("target row maps outside the global MOLA grid")
    remaining_column = col
    for window in windows:
        if window.row_offset != first.row_offset:
            raise ValueError("MOLA windows must have identical source row offsets")
        if window.terrain_patch.shape[0] != first.terrain_patch.shape[0]:
            raise ValueError("MOLA windows must have identical source row coverage")
        width = window.terrain_patch.shape[1]
        if remaining_column < width:
            return source_row, (
                window.column_offset + remaining_column
            ) % MOLA_SHAPE[1]
        remaining_column -= width
    raise ValueError("target column does not map to a source MOLA window")


def evaluate_mars_rehearsal_windows(
    terrain: MarsMolaGeometricWindow | Sequence[MarsMolaGeometricWindow],
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
    *,
    kernels: MarsKernelSet,
    frame_transform: MarsMolaFrameTransform,
    criteria: RehearsalCriteria | None = None,
    target_pixel: tuple[int, int] | None = None,
    max_distance_m: float = 50000.0,
    dot_tolerance: float = 1e-9,
    obstruction_tolerance_m: float = 1.0,
    evidence: ScientificEvidence | None = None,
) -> RehearsalEvaluation:
    """Transform and illuminate only the selected Mars MOLA terrain per epoch."""
    if isinstance(terrain, MarsMolaGeometricWindow):
        windows = (terrain,)
    else:
        windows = tuple(terrain)
    if not windows or not all(
        isinstance(window, MarsMolaGeometricWindow) for window in windows
    ):
        raise TypeError("terrain must contain one or more native MOLA geometric windows")
    if not isinstance(kernels, MarsKernelSet):
        raise TypeError("kernels must be a MarsKernelSet")
    if not isinstance(frame_transform, MarsMolaFrameTransform):
        raise TypeError("frame_transform must be a MarsMolaFrameTransform")

    intervals = evaluation_intervals(start_utc, end_utc, step)
    selected_criteria = criteria or RehearsalCriteria()
    shape = (
        windows[0].terrain_patch.shape[0],
        sum(window.terrain_patch.shape[1] for window in windows),
    )
    target = (shape[0] // 2, shape[1] // 2) if target_pixel is None else target_pixel
    row, col = target
    if (
        isinstance(row, bool) or isinstance(col, bool)
        or not isinstance(row, int) or not isinstance(col, int)
        or not 0 <= row < shape[0] or not 0 <= col < shape[1]
    ):
        raise ValueError("target_pixel must be an in-bounds (row, column) pair")
    source_row, source_column = _mola_source_pixel(windows, target)
    target_longitude = (source_column + 0.5) / MOLA_PIXELS_PER_DEGREE
    target_latitude = 90.0 - (source_row + 0.5) / MOLA_PIXELS_PER_DEGREE
    frame_kernels = frame_transform.kernels
    kernel_identities = identify_spice_kernels(
        (
            ("leap-seconds kernel", frame_kernels.leap_seconds),
            ("MOLA orientation PCK", frame_kernels.mola_orientation_pck),
            ("current Mars orientation PCK", frame_kernels.current_orientation_pck),
            ("planetary ephemeris SPK", kernels.planetary_spk),
            ("Mars center ephemeris SPK", kernels.mars_system_spk),
        )
    )

    observations = []
    provenance: dict[str, str] = {
        "body": "mars",
        "source_dataset_id": "MGS MOLA MEGR90N000FB",
        "frame": "IAU_MARS",
        "frame_center": "NAIF 499",
        "surface": "MEGR absolute mean planetary radius",
        "coverage": "MEGC observation-count mask retained independently",
        "elevation": "MEGT GMM3-areoid-relative values not added to MEGR radii",
        "max_distance_m": str(max_distance_m),
        "target_source_grid": "MGS MOLA MEGR90N000FB, global 32-pixel-per-degree grid",
        "target_source_row": str(source_row),
        "target_source_column": str(source_column),
        "target_grid_index_convention": (
            "zero-based row southward from 90N; zero-based column eastward from 0E; "
            "pixel centres at (index + 0.5) / 32 degrees"
        ),
    }

    for interval in intervals:
        result = mars_mola_illumination_raster(
            windows,
            interval[0],
            kernels,
            frame_transform,
            max_distance_m=max_distance_m,
            dot_tolerance=dot_tolerance,
            obstruction_tolerance_m=obstruction_tolerance_m,
        )
        if result.classification.shape != shape:
            raise ValueError("Mars illumination output shape does not match the MOLA windows")
        metadata = {str(key): str(value) for key, value in result.source_metadata.items()}
        for key, value in metadata.items():
            provenance.setdefault(f"source.{key}", value)
        elevation = float(result.solar_elevation_deg[row, col])
        azimuth = float(result.solar_azimuth_deg[row, col])
        observations.append(
            observation_from_raster(
                interval=interval,
                classification=result.classification,
                valid_mask=result.surface_valid_mask,
                coverage_mask=result.coverage_mask,
                elevation_valid_mask=result.elevation_valid_mask,
                class_codes=MarsIlluminationClass,
                ray_status=getattr(result, "ray_status", None),
                ray_status_codes=MarsRayStatus,
                observation_coverage_mask=result.observation_coverage_mask,
                target_pixel=target,
                solar_elevation_deg=elevation if np.isfinite(elevation) else None,
                solar_azimuth_deg=azimuth if np.isfinite(azimuth) else None,
                source_dataset_id=result.source_dataset_id,
                source_metadata=metadata,
                solar_direction_fixed=result.solar_direction_fixed,
                solar_frame=result.frame,
                sun_distance_km=result.sun_distance_km,
            )
        )
        for key, value in windows[0].terrain_patch.metadata.provenance.items():
            provenance.setdefault(f"mola.{key}", str(value))

    return aggregate_rehearsal(
        body="mars",
        start_utc=start_utc,
        end_utc=end_utc,
        step=step,
        intervals=intervals,
        observations=observations,
        target_pixel=target,
        criteria=selected_criteria,
        provenance=provenance,
        source_grid_id="MGS MOLA MEGR90N000FB global 32-pixel-per-degree grid",
        source_row=source_row,
        source_column=source_column,
        target_longitude_deg=target_longitude,
        target_latitude_deg=target_latitude,
        target_coordinate_frame="IAU2000_MARS planetocentric, east-positive",
        kernel_identities=kernel_identities,
        evidence=evidence,
        scientific_limitations=(
            "The MOLA-origin to NAIF-center-499 tie is assumed and remains unverified.",
            "MEGT GMM3-areoid-relative elevation is retained separately and is not added to MEGR radii.",
            "Zero-observation MEGC cells are not treated as observed terrain.",
            "Terrain-horizon search is limited to 50 km by default; patch edges and observation gaps remain unsupported.",
            "No independent observational shadow-accuracy validation is included.",
        ),
    )
