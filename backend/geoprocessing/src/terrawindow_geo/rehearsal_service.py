"""HTTP-facing wrapper for Layer 4 (solar geometry and rehearsal windows).

Layer 4 is the separate `rehearsal` package. This module only builds its inputs from stored data
(Layer 3 patches for Earth and the Moon, native MOLA windows for Mars), bounds the work, calls the
package's own evaluator, and returns its result unchanged. It performs no solar or illumination
calculation itself, and it never substitutes one body's assumptions for another's.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import get_settings
from .errors import GeoError
from .models import PatchRequest

# Work bounds. Layer 4 ray-traces the whole patch once per sample, so cost is patch size x samples.
MAX_SAMPLES = 96
MAX_SPAN = timedelta(days=30)
MAX_EARTH_MOON_PIXELS = 200_000
MARS_WINDOW_CELLS = 61  # native 32 ppd cells (about 113 km square), as in Layer 4's own retained execution
KERNEL_FILES = {
    "lsk": "naif0012.tls",
    "de440s": "de440s.bsp",
    "mar099s": "mar099s.bsp",
    "pck00011": "pck00011.tpc",
    "mars_iau2000": "mars_iau2000_v1.tpc",
    "earth_bpc": "earth_000101_270208_261113.bpc",
    "moon_bpc": "moon_pa_de440_200625.bpc",
    "moon_fk": "moon_de440_250416.tf",
}


class RehearsalCriteriaIn(BaseModel):
    """Thresholds applied to each continuous illumination interval. Assumptions, not mission standards."""

    model_config = ConfigDict(extra="forbid")

    minimum_continuous_illumination_minutes: float = Field(0.0, ge=0, le=60 * 24 * 30, allow_inf_nan=False)
    minimum_valid_terrain_coverage_percent: float = Field(0.0, ge=0, le=100, allow_inf_nan=False)
    solar_elevation_min_deg: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    solar_elevation_max_deg: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    solar_azimuth_min_deg: float | None = Field(None, ge=0, le=360, allow_inf_nan=False)
    solar_azimuth_max_deg: float | None = Field(None, ge=0, le=360, allow_inf_nan=False)
    maximum_terrain_obstruction_percent: float = Field(100.0, ge=0, le=100, allow_inf_nan=False)


class RehearsalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: PatchRequest = Field(description="The Layer 3 patch (Earth, Moon) or the Mars region whose centre is the target.")
    start_utc: datetime
    end_utc: datetime
    step_minutes: float = Field(gt=0, allow_inf_nan=False)
    criteria: RehearsalCriteriaIn = RehearsalCriteriaIn()
    max_distance_m: float | None = Field(None, gt=0, le=100_000, allow_inf_nan=False, description="Horizon search range. Defaults: 2.5 km Earth/Moon, 50 km Mars.")
    scale_m: float | None = Field(None, gt=0, allow_inf_nan=False, description="Earth/Moon analysis grid spacing. Default: the finest of candidate.scales_m, else native.")

    @model_validator(mode="after")
    def _times(self) -> "RehearsalRequest":
        for name in ("start_utc", "end_utc"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} must include a UTC offset")
        span = self.end_utc - self.start_utc
        if span <= timedelta(0):
            raise ValueError("end_utc must be later than start_utc")
        if span > MAX_SPAN:
            raise ValueError("the evaluation span is limited to 30 days")
        samples = span / timedelta(minutes=self.step_minutes)
        if samples > MAX_SAMPLES:
            raise ValueError(f"at most {MAX_SAMPLES} samples; widen step_minutes or shorten the span")
        return self


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4] if here.parents[3].name == "backend" else Path.cwd()


def kernel_dir() -> Path:
    env = os.environ.get("TWGEO_KERNEL_DIR")
    return Path(env).resolve() if env else _repo_root() / "solar_geometry_engine" / "kernels" / "kernels"


def mars_source_dir() -> Path:
    env = os.environ.get("TWGEO_MARS_MEGDR32_DIR")
    return Path(env).resolve() if env else get_settings().data_dir / "local" / "rehearsal" / "mars" / "mola_megdr" / "source"


def _kernel(name: str) -> Path:
    path = kernel_dir() / KERNEL_FILES[name]
    if not path.is_file() or path.stat().st_size == 0:
        raise GeoError("layer4_unavailable", "A required SPICE kernel is not on this machine.", status=503, details={"missing": path.name})
    return path


def _layer4():
    try:
        import rehearsal  # noqa: F401
    except ImportError as exc:
        raise GeoError("layer4_unavailable", "The Layer 4 package (rehearsal) is not installed.", status=503) from exc


def status() -> dict[str, Any]:
    """What Layer 4 needs and whether it is here. Reported by /v1/rehearsal/status, never guessed."""
    try:
        import rehearsal  # noqa: F401
        import spiceypy  # noqa: F401
        package = True
    except ImportError:
        package = False
    kernels = {name: (kernel_dir() / file).is_file() for name, file in KERNEL_FILES.items()}
    mars_dir = mars_source_dir()
    mars_ok = all((mars_dir / f).is_file() and (mars_dir / f).stat().st_size == 132_710_400 for f in ("megt90n000fb.img", "megc90n000fb.img", "megr90n000fb.img"))
    return {
        "package_installed": package,
        "kernels_present": kernels,
        "bodies": {
            "earth": package and all(kernels[k] for k in ("lsk", "de440s", "earth_bpc", "pck00011")),
            "moon": package and all(kernels[k] for k in ("lsk", "de440s", "moon_bpc", "moon_fk", "pck00011")),
            "mars": package and mars_ok and all(kernels[k] for k in ("lsk", "de440s", "mar099s", "pck00011", "mars_iau2000")),
        },
        "mars_native_source": {"ready": mars_ok, "grid": "MOLA MEGDR 32 pixels/degree (about 1.85 km)"},
        "observational_validation": "NOT_VALIDATED",
    }


def _criteria(c: RehearsalCriteriaIn):
    from rehearsal.windows import RehearsalCriteria

    return RehearsalCriteria(
        minimum_continuous_illumination=timedelta(minutes=c.minimum_continuous_illumination_minutes),
        minimum_valid_terrain_coverage_percent=c.minimum_valid_terrain_coverage_percent,
        solar_elevation_min_deg=c.solar_elevation_min_deg,
        solar_elevation_max_deg=c.solar_elevation_max_deg,
        solar_azimuth_min_deg=c.solar_azimuth_min_deg,
        solar_azimuth_max_deg=c.solar_azimuth_max_deg,
        maximum_terrain_obstruction_percent=c.maximum_terrain_obstruction_percent,
    )


def _evidence(dataset_id: str, grid: str):
    """This run executed on stored terrain; nothing here has been compared with observed illumination."""
    from rehearsal.windows.temporal import EvidenceStatus, ScientificEvidence

    return ScientificEvidence(
        real_terrain_execution_status=EvidenceStatus.PASS,
        details={
            "status_semantics": "Implementation PASS means this temporal evaluation returned successfully; it does not assert independent correctness or observational accuracy.",
            "real_terrain_execution": f"Executed by the TERRAWINDOW service on stored dataset '{dataset_id}' ({grid}).",
        },
    )


def _grid(patch) -> dict[str, Any]:
    return {"shape": list(patch.z.shape), "pixel_size_m": round(float(patch.pixel_size_m), 3), "native_pixel_size_m": round(float(patch.native_pixel_size_m), 3), "resampling": patch.resampling}


def _earth_moon(request: RehearsalRequest, body: str, dataset) -> tuple[Any, dict[str, Any]]:
    from .profile import extract_dem

    # Layer 3 profiles are cut on their finest requested scale; defaulting to it makes Layer 4 run on the same grid,
    # which is what lets Layer 5 pair the two results.
    scales = request.candidate.scales_m
    scale = request.scale_m or (min(scales) if scales else None)
    patch = extract_dem(dataset, request.candidate.bbox, scale)
    if patch.z.size > MAX_EARTH_MOON_PIXELS:
        raise GeoError("patch_too_large", f"Layer 4 patches are limited to {MAX_EARTH_MOON_PIXELS:,} cells; choose a smaller area or a coarser scale_m.", status=422, details={"cells": int(patch.z.size)})
    kernels_args = dict(max_distance_m=request.max_distance_m or 2500.0, evidence=_evidence(dataset.id or "unregistered", "Layer 3 patch"))
    if body == "earth":
        if not dataset.id:
            raise GeoError("invalid_request", "Earth rehearsal needs a registered Copernicus GLO-30 dataset id; Layer 4 will not assume an unregistered raster is GLO-30.", status=422)
        from rehearsal.earth.kernels import EarthKernelSet
        from rehearsal.earth.terrain import EarthTerrainMetadata, EarthTerrainPatch

        terrain = EarthTerrainPatch.from_layer3_patch(patch, EarthTerrainMetadata.copernicus_glo30(dataset.id, vertical_scale_applied=dataset.vertical_scale))
        kernels = EarthKernelSet(_kernel("lsk"), _kernel("de440s"), _kernel("earth_bpc"), _kernel("pck00011"))
    else:
        from rehearsal.lunar.kernels import LunarKernelSet
        from rehearsal.lunar.terrain import LunarTerrainMetadata, LunarTerrainPatch

        terrain = LunarTerrainPatch.from_layer3_patch(
            patch,
            LunarTerrainMetadata(
                body_fixed_frame="MOON_ME",
                frame_realization="MOON_ME (DE421 realization of the LOLA product), mapped through MOON_ME_DE440_ME421",
                frame_alignment_note="DE440 frame maps the DE421 MOON_ME; NAIF documents up to about 0.54 m difference at the surface over 2000-2040. Close alignment, not identity.",
                elevation_reference="Height above the 1737.4 km lunar reference sphere",
                reference_radius_m=1_737_400.0,
                provenance={"dataset_id": dataset.id or "unregistered", "source": "NASA LOLA via Layer 2/3"},
            ),
        )
        kernels = LunarKernelSet(_kernel("lsk"), _kernel("de440s"), _kernel("moon_bpc"), _kernel("moon_fk"), _kernel("pck00011"))
    return (terrain, kernels, kernels_args), _grid(patch)


def evaluate(request: RehearsalRequest) -> dict[str, Any]:
    """Run Layer 4 for the candidate's body and return its JSON result, with the grid it ran on."""
    _layer4()
    from .io.sources import materialize

    dataset = materialize(request.candidate.dataset)
    body = dataset.body
    step = timedelta(minutes=request.step_minutes)
    criteria = _criteria(request.criteria)
    from rehearsal.windows import evaluate_selected_body

    try:
        if body in ("earth", "moon"):
            (terrain, kernels, options), grid = _earth_moon(request, body, dataset)
            result = evaluate_selected_body(body, terrain, request.start_utc, request.end_utc, step, kernels=kernels, criteria=criteria, body_options=options)
        elif body == "mars":
            result, grid = _mars(request, step, criteria)
        else:
            raise GeoError("invalid_request", f"Layer 4 does not support body '{body}'.", status=422)
    except GeoError:
        raise
    except FileNotFoundError as exc:
        raise GeoError("layer4_unavailable", "A Layer 4 input file is not on this machine.", status=503, details={"file": Path(str(exc).split(": ")[-1]).name}) from exc
    except (ValueError, TypeError) as exc:
        # Layer 4 validates its own inputs (kernel coverage, frame metadata, coordinates); say so rather than guess.
        raise GeoError("rehearsal_rejected", str(exc), status=422) from exc
    out = result.to_dict()
    out["analysis_grid"] = grid
    out["generated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def _mars(request: RehearsalRequest, step: timedelta, criteria) -> tuple[Any, dict[str, Any]]:
    from rehearsal.mars.mola import MarsMolaMegdr32ppd
    from rehearsal.mars.mola_frame import MarsMolaFrameKernels, MarsMolaFrameTransform
    from rehearsal.mars.reference import MarsKernelSet

    bbox = request.candidate.bbox
    if bbox is None or bbox.crs != "geographic":
        raise GeoError("invalid_request", "Mars rehearsal needs a geographic bbox; its centre is the target.", status=422)
    source = mars_source_dir()
    if not (source / "megr90n000fb.img").is_file():
        raise GeoError("layer4_unavailable", "The MOLA 32 pixel/degree source images are not on this machine.", status=503)
    lon = ((bbox.west + bbox.east) / 2.0) % 360.0
    lat = (bbox.south + bbox.north) / 2.0
    kernels = MarsKernelSet(_kernel("lsk"), _kernel("de440s"), _kernel("mar099s"), _kernel("pck00011"), _kernel("pck00011"))
    transform = MarsMolaFrameTransform(MarsMolaFrameKernels(_kernel("lsk"), _kernel("mars_iau2000"), _kernel("pck00011")))
    from rehearsal.mars.temporal import evaluate_mars_rehearsal_windows

    with MarsMolaMegdr32ppd(source) as mola:
        row, col = mola.lonlat_to_pixel(lon, lat)
        half = MARS_WINDOW_CELLS // 2
        window = mola.read_geometric_window(row - half, col - half, MARS_WINDOW_CELLS, MARS_WINDOW_CELLS)
        result = evaluate_mars_rehearsal_windows(
            window, request.start_utc, request.end_utc, step,
            kernels=kernels, frame_transform=transform, criteria=criteria,
            target_pixel=(half, half), max_distance_m=request.max_distance_m or 50_000.0,
            evidence=_evidence(request.candidate.dataset.id or "mola-megdr", "native MOLA MEGDR 32 ppd window"),
        )
    grid = {"shape": [MARS_WINDOW_CELLS, MARS_WINDOW_CELLS], "pixel_size_m": 1852.231, "native_pixel_size_m": 1852.231, "resampling": "none (native MOLA MEGDR 32 ppd)", "target_lonlat": [round(lon, 4), round(lat, 4)]}
    return result, grid
