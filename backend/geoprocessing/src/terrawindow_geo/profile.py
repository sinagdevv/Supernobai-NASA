"""Build the terrain profile of one patch: the main product of Layer 3."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from . import coverage as cov
from . import landcover as lc
from ._util import fnum, stats
from .errors import GeoError
from .io.raster import Patch, extract_patch, native_pixel_size
from .io.sources import WORLDCOVER, describe, materialize, resolve_bbox, resolve_uris, stored_datasets
from .models import (
    BBox,
    DatasetRef,
    ElevationSummary,
    LandCoverRule,
    PatchInfo,
    PatchRequest,
    Provenance,
    ReliefMetrics,
    ScaleMetrics,
    SkippedItem,
    TerrainProfile,
)
from .scale import choose_scales
from .terrain.relief import local_relief, window_pixels
from .terrain.roughness import DEFAULT_WINDOW_PX, roughness_metrics
from .terrain.slope import slope_aspect, slope_metrics

# A scale needs enough cells for the statistics to mean something.
MIN_GRID_PX = 16

METHODS = {
    "slope": "Horn (1981) 3x3 finite difference on a metric grid; degrees from horizontal.",
    "rms_slope": "arctan of the root-mean-square of tan(slope).",
    "roughness_rms_height": f"RMS of elevation after subtracting the {DEFAULT_WINDOW_PX}x{DEFAULT_WINDOW_PX}-cell moving mean, over the same window.",
    "roughness_tri": "Terrain Ruggedness Index (Riley et al. 1999).",
    "relief": "Maximum minus minimum elevation in a square moving window.",
    "aggregation": "Coarser scales are area averages of the working grid; no scale is finer than the source.",
    "coverage": "Fraction of grid cells with a valid elevation; voids are never filled.",
}

BASE_LIMITATIONS = [
    "Remote-sensing terrain metrics cannot establish soil strength, wheel traction, or field safety.",
    "Features smaller than the analysis scale (rocks, small craters, ruts) are not resolved.",
    "Metrics are only comparable between sites when computed at the same scale.",
]


def extract_dem(dataset: DatasetRef, bbox: BBox | None = None, scale_m: float | None = None) -> Patch:
    """Elevation patch on a metric grid. Layer 4 can use this for horizon and shadow modelling."""
    dataset = materialize(dataset)
    bbox = resolve_bbox(dataset, bbox)
    uris = resolve_uris(dataset, bbox)
    return extract_patch(uris, bbox, body=dataset.body, resolution_m=scale_m, vertical_scale=dataset.vertical_scale)


def provenance(dataset: DatasetRef, patch: Patch) -> Provenance:
    from . import __version__

    name, citation = describe(dataset)
    return Provenance(
        dataset_id=dataset.id,
        dataset_name=name,
        sources=patch.sources,
        citation=citation,
        native_crs=patch.native_crs,
        native_pixel_size_m=round(patch.native_pixel_size_m, 3),
        working_crs=patch.crs.to_string(),
        working_pixel_size_m=round(patch.pixel_size_m, 3),
        resampling=patch.resampling,
        methods=METHODS,
        engine_version=__version__,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def limitations(dataset: DatasetRef, patch: Patch) -> list[str]:
    out = list(BASE_LIMITATIONS)
    out.insert(1, f"Source data has a native pixel size of about {patch.native_pixel_size_m:.0f} m.")
    if dataset.id == "copernicus-glo30":
        out.append("Copernicus GLO-30 is a surface model: vegetation and buildings raise elevations and add apparent roughness.")
    record = stored_datasets().get(dataset.id) if dataset.id else None
    for note in (record or {}).get("limitations", []):
        if note not in out:
            out.append(note)
    if dataset.body != "earth" and not record:
        out.append("Interpolated or shadowed areas in planetary elevation models can look smoother than the real surface.")
    return out


def landcover_summary(bbox: BBox, rule: LandCoverRule | None = None, like: Patch | None = None):
    """WorldCover class fractions for a geographic bbox (optionally sampled onto an existing grid)."""
    ref = DatasetRef(id=WORLDCOVER)
    try:
        classes = extract_patch(resolve_uris(ref, bbox), bbox, categorical=True, like=like)
    except GeoError as exc:
        if exc.code != "source_unavailable":
            raise
        return None, classes_unavailable(exc)
    return classes, lc.summarize(classes.z, rule)


def classes_unavailable(exc: GeoError):
    from .models import LandCoverSummary

    return LandCoverSummary(dataset="ESA WorldCover 10 m 2021 v200", valid_fraction=0.0, classes=[], dominant_class=None, reason=exc.message)


def build_profile(request: PatchRequest) -> TerrainProfile:
    dataset = materialize(request.dataset)
    bbox = resolve_bbox(dataset, request.bbox)
    uris = resolve_uris(dataset, bbox)
    native = native_pixel_size(uris, bbox)
    scales, skipped = choose_scales(request.scales_m, native)
    if not scales:
        raise GeoError(
            "scale_not_supported",
            f"None of the requested scales is supported: the dataset's native pixel size is {native:.1f} m.",
            details={"requested_m": request.scales_m, "native_pixel_size_m": round(native, 3)},
        )

    base = extract_patch(uris, bbox, body=dataset.body, resolution_m=scales[0], vertical_scale=dataset.vertical_scale)
    coverage = cov.summarize(base.z, request.min_coverage, base.missing_sources)

    scale_results: list[ScaleMetrics] = []
    for s in scales:
        grid = base.at_scale(s)
        if min(grid.shape) < MIN_GRID_PX:
            skipped.append(
                SkippedItem(
                    item=f"scale {s:g} m",
                    code="patch_too_small",
                    reason=f"Patch is only {grid.shape[1]} x {grid.shape[0]} cells at this scale (need {MIN_GRID_PX}).",
                )
            )
            continue
        frac = cov.valid_fraction(grid.z)
        entry = ScaleMetrics(
            scale_m=s,
            status="assessed" if frac >= request.min_coverage else "insufficient_coverage",
            coverage_fraction=round(frac, 4),
            grid_shape=[grid.shape[0], grid.shape[1]],
        )
        if entry.status == "assessed":
            slope, _aspect = slope_aspect(grid.z, grid.pixel_size_m)
            entry.slope = slope_metrics(slope, grid.pixel_size_m, request.slope_thresholds_deg)
            entry.roughness = roughness_metrics(grid.z, grid.pixel_size_m)
        scale_results.append(entry)

    relief: list[ReliefMetrics] = []
    for window_m in request.relief_windows_m:
        px = window_pixels(window_m, base.pixel_size_m)
        item = f"relief window {window_m:g} m"
        if not coverage.sufficient:
            skipped.append(SkippedItem(item=item, code="insufficient_coverage", reason="Not enough valid elevation data."))
        elif px < 3:
            skipped.append(SkippedItem(item=item, code="scale_not_supported", reason=f"Window is under 3 cells of the {base.pixel_size_m:g} m grid."))
        elif min(base.shape) < 2 * px:
            skipped.append(SkippedItem(item=item, code="patch_too_small", reason="Patch is smaller than two windows."))
        else:
            relief.append(
                ReliefMetrics(window_m=px * base.pixel_size_m, grid_m=base.pixel_size_m, stats=stats(local_relief(base.z, px), 2))
            )

    landcover = None
    if request.include_landcover:
        if dataset.body != "earth" or bbox.crs != "geographic":
            skipped.append(SkippedItem(item="landcover", code="not_applicable", reason="Land cover is only available for Earth patches with a lon/lat bbox."))
        else:
            _classes, landcover = landcover_summary(bbox, LandCoverRule())

    v = base.z[np.isfinite(base.z)]
    elevation = ElevationSummary(
        min=fnum(v.min(), 2) if v.size else None,
        max=fnum(v.max(), 2) if v.size else None,
        mean=fnum(v.mean(), 2) if v.size else None,
        std=fnum(v.std(), 2) if v.size else None,
        range=fnum(v.max() - v.min(), 2) if v.size else None,
    )

    h, w = base.shape
    lon, lat = base.center_lonlat()
    notes = limitations(dataset, base)
    if not coverage.sufficient:
        notes.append(
            f"Only {coverage.valid_fraction:.0%} of the patch has elevation data (minimum {coverage.min_required:.0%}); "
            "metrics are withheld rather than computed on partial data."
        )

    return TerrainProfile(
        patch=PatchInfo(
            body=dataset.body,
            bbox=bbox,
            center_lon=round(lon, 6),
            center_lat=round(lat, 6),
            polygon_lonlat=base.ring_lonlat(),
            width_m=w * base.pixel_size_m,
            height_m=h * base.pixel_size_m,
            area_km2=round(w * h * base.pixel_size_m**2 / 1e6, 4),
        ),
        provenance=provenance(dataset, base),
        coverage=coverage,
        elevation=elevation,
        scales=scale_results,
        relief=relief,
        landcover=landcover,
        skipped=skipped,
        limitations=notes,
    )
