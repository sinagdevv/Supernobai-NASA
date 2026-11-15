"""Earth-specific solar geometry and terrain illumination."""

from .geometry import EarthSolarGeometry, earth_sun_geometry, earth_sun_series
from .kernels import EarthKernelSet
from .terrain import (
    EarthHorizonObservation,
    EarthHorizonProfile,
    EarthIlluminationCode,
    EarthIlluminationRasterResult,
    EarthRayStatus,
    EarthTerrainMetadata,
    EarthTerrainPatch,
    EarthTerrainSurfaceNormal,
)
from .temporal import (
    evaluate_earth_rehearsal_windows,
    iter_earth_illumination_series,
    run_earth_illumination_series,
)

__all__ = [
    "EarthHorizonObservation",
    "EarthHorizonProfile",
    "EarthIlluminationCode",
    "EarthIlluminationRasterResult",
    "EarthKernelSet",
    "EarthRayStatus",
    "EarthSolarGeometry",
    "EarthTerrainMetadata",
    "EarthTerrainPatch",
    "EarthTerrainSurfaceNormal",
    "earth_sun_geometry",
    "earth_sun_series",
    "evaluate_earth_rehearsal_windows",
    "iter_earth_illumination_series",
    "run_earth_illumination_series",
]
