"""Mars-specific geometry foundation for TERRAWINDOW Layer 4.

This module is intentionally isolated from the Earth and lunar implementations.
It documents and exposes the body-fixed Mars reference model required before any
Mars terrain illumination or suitability work can be added.
"""

from .reference import (
    MarsBodyModel,
    MarsKernelSet,
    MarsSolarGeometry,
    furnished_kernels,
    mars_solar_geometry,
    mars_solar_series,
)
from .mola import MarsMolaGeometricWindow, MarsMolaMegdr32ppd
from .mola_frame import (
    MarsMolaCurrentFrameWindow,
    MarsMolaFrameKernels,
    MarsMolaFrameSolution,
    MarsMolaFrameTransform,
)
from .illumination import (
    MarsIlluminationClass,
    MarsIlluminationResult,
    MarsIlluminationTerrain,
    MarsRayStatus,
    MarsSunDirectionFixed,
    mars_illumination_raster,
    mars_mola_illumination_raster,
    mars_sun_direction_fixed,
)
from .terrain import MarsTerrainMetadata, MarsTerrainPatch
from .temporal import evaluate_mars_rehearsal_windows

__all__ = [
    "MarsBodyModel",
    "MarsIlluminationClass",
    "MarsIlluminationResult",
    "MarsIlluminationTerrain",
    "MarsMolaCurrentFrameWindow",
    "MarsMolaFrameKernels",
    "MarsMolaFrameSolution",
    "MarsMolaFrameTransform",
    "MarsMolaGeometricWindow",
    "MarsKernelSet",
    "MarsMolaMegdr32ppd",
    "MarsRayStatus",
    "MarsSolarGeometry",
    "MarsSunDirectionFixed",
    "MarsTerrainMetadata",
    "MarsTerrainPatch",
    "furnished_kernels",
    "evaluate_mars_rehearsal_windows",
    "mars_solar_geometry",
    "mars_solar_series",
    "mars_illumination_raster",
    "mars_mola_illumination_raster",
    "mars_sun_direction_fixed",
]
