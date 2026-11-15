"""Lunar reference geometry for TERRAWINDOW Layer 4."""
from .kernels import LunarKernelSet
from .reference import (
    LunarSolarGeometry,
    LunarSunDirection,
    lunar_sun_direction_fixed,
    lunar_sun_direction_series_fixed,
    lunar_sun_geometry,
    lunar_sun_series,
)
from .terrain import (
    LunarTerrainMetadata,
    LunarTerrainPatch,
    LunarTerrainSample,
    LunarTerrainWindow,
    TerrainHorizonObservation,
    TerrainHorizonProfile,
    TerrainIlluminationCode,
    TerrainIlluminationCache,
    TerrainIlluminationRasterResult,
    TerrainObstructionResult,
    TerrainRayStatus,
    TerrainSurfaceNormal,
)
from .temporal import (
    evaluate_lunar_rehearsal_windows,
    run_terrain_illumination_series,
)

__all__ = [
    "LunarKernelSet",
    "LunarSolarGeometry",
    "LunarSunDirection",
    "LunarTerrainMetadata",
    "LunarTerrainPatch",
    "LunarTerrainSample",
    "LunarTerrainWindow",
    "TerrainHorizonObservation",
    "TerrainHorizonProfile",
    "TerrainIlluminationCode",
    "TerrainIlluminationCache",
    "TerrainIlluminationRasterResult",
    "TerrainObstructionResult",
    "TerrainRayStatus",
    "TerrainSurfaceNormal",
    "evaluate_lunar_rehearsal_windows",
    "run_terrain_illumination_series",
    "lunar_sun_direction_fixed",
    "lunar_sun_direction_series_fixed",
    "lunar_sun_geometry",
    "lunar_sun_series",
]
