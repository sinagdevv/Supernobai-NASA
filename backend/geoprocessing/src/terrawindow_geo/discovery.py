"""Screen an area of interest for candidate terrain patches.

The area is read once, slope and roughness maps are computed once, then the area is cut into
square cells and each cell is checked against the criteria. Output is GeoJSON for the map.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import landcover as lc
from ._util import fnum
from .config import get_settings
from .errors import GeoError
from .io.raster import extract_patch, native_pixel_size
from .io.sources import resolve_uris
from .models import Range, ScreeningCriteria, ScreenRequest, TerrainProfile, Tolerances
from .profile import MIN_GRID_PX, landcover_summary, limitations, provenance
from .scale import default_scales, is_supported
from .terrain.roughness import DEFAULT_WINDOW_PX, rms_height
from .terrain.slope import slope_aspect


def criteria_from_reference(profile: TerrainProfile, scale_m: float, tol: Tolerances, base: ScreeningCriteria) -> ScreeningCriteria:
    """Fill slope/roughness ranges the user left empty with 'reference value +/- tolerance'."""
    ref = next((s for s in profile.scales if abs(s.scale_m - scale_m) <= 0.01 * scale_m and s.status == "assessed"), None)
    if ref is None:
        return base
    out = base.model_copy(deep=True)
    if out.slope_mean_deg is None and ref.slope.stats.mean is not None:
        m = ref.slope.stats.mean
        out.slope_mean_deg = Range(min=max(0.0, m - tol.slope_mean_deg), max=m + tol.slope_mean_deg)
    if out.slope_p90_deg is None and ref.slope.stats.p90 is not None:
        p = ref.slope.stats.p90
        out.slope_p90_deg = Range(min=max(0.0, p - tol.slope_p90_deg), max=p + tol.slope_p90_deg)
    if out.roughness_rms_height_m is None and ref.roughness.rms_height_m.median is not None:
        r = ref.roughness.rms_height_m.median
        out.roughness_rms_height_m = Range(min=r * (1 - tol.roughness_rel), max=r * (1 + tol.roughness_rel))
    return out


def _check(name: str, value: float | None, rng: Range | None, unit: str) -> dict[str, Any] | None:
    if rng is None:
        return None
    result = {"criterion": name, "unit": unit, "value": fnum(value), "min": fnum(rng.min), "max": fnum(rng.max)}
    if value is None:
        return {**result, "status": "not_assessed", "reason": "No value could be computed."}
    ok = (rng.min is None or value >= rng.min) and (rng.max is None or value <= rng.max)
    return {**result, "status": "pass" if ok else "fail", "reason": None}


def _nan(fn, a):
    v = a[np.isfinite(a)]
    return float(fn(v)) if v.size else None


def screen_region(request: ScreenRequest) -> dict[str, Any]:
    settings = get_settings()
    dataset, bbox = request.dataset, request.bbox
    uris = resolve_uris(dataset, bbox)
    native = native_pixel_size(uris, bbox)

    scale = request.scale_m or default_scales(native)[0]
    if not is_supported(scale, native):
        raise GeoError(
            "scale_not_supported",
            f"Requested scale {scale:g} m is finer than the dataset's native pixel size ({native:.1f} m).",
            details={"requested_m": scale, "native_pixel_size_m": round(native, 3)},
        )
    n = round(request.patch_size_m / scale)
    if n < MIN_GRID_PX:
        raise GeoError(
            "patch_too_small",
            f"patch_size_m must be at least {MIN_GRID_PX} cells of the analysis grid ({MIN_GRID_PX * scale:g} m at {scale:g} m).",
            details={"patch_size_m": request.patch_size_m, "scale_m": scale},
        )

    area = extract_patch(uris, bbox, body=dataset.body, resolution_m=scale, vertical_scale=dataset.vertical_scale)
    rows, cols = area.shape[0] // n, area.shape[1] // n
    if rows == 0 or cols == 0:
        raise GeoError("patch_too_small", "The bbox is smaller than one patch. Use a larger bbox or a smaller patch_size_m.")
    if rows * cols > settings.max_screen_cells:
        raise GeoError(
            "patch_too_large",
            f"The bbox would be cut into {rows * cols} patches; the limit is {settings.max_screen_cells}.",
            details={"cells": rows * cols, "limit": settings.max_screen_cells},
        )

    criteria = request.criteria
    if request.reference_profile is not None:
        criteria = criteria_from_reference(request.reference_profile, scale, request.tolerances, criteria)

    slope, _aspect = slope_aspect(area.z, scale)
    rough = rms_height(area.z, DEFAULT_WINDOW_PX)

    classes = None
    notes = limitations(dataset, area)
    if criteria.landcover is not None:
        if dataset.body != "earth" or bbox.crs != "geographic":
            notes.append("Land-cover screening was skipped: it needs an Earth dataset and a lon/lat bbox.")
        else:
            classes, summary = landcover_summary(bbox, like=area)
            if classes is None:
                notes.append(f"Land-cover screening was not assessed: {summary.reason}")
            else:
                notes.append("Land cover was sampled (nearest neighbour) from 10 m WorldCover onto the analysis grid.")

    features = []
    tally = {"candidate": 0, "rejected": 0, "insufficient_data": 0}
    for r in range(rows):
        for c in range(cols):
            win = (slice(r * n, (r + 1) * n), slice(c * n, (c + 1) * n))
            z = area.z[win]
            coverage = float(np.isfinite(z).mean())
            enough = coverage >= criteria.min_coverage
            s, ro = slope[win], rough[win]
            sv = s[np.isfinite(s)]

            metrics = {
                "coverage_fraction": round(coverage, 4),
                "slope_mean_deg": fnum(_nan(np.mean, s), 3) if enough else None,
                "slope_median_deg": fnum(_nan(np.median, s), 3) if enough else None,
                "slope_p90_deg": fnum(np.percentile(sv, 90), 3) if enough and sv.size else None,
                "slope_max_deg": fnum(_nan(np.max, s), 3) if enough else None,
                "roughness_rms_height_m": fnum(_nan(np.median, ro), 3) if enough else None,
                "relief_m": fnum(_nan(np.max, z) - _nan(np.min, z), 2) if enough else None,
                "elevation_mean_m": fnum(_nan(np.mean, z), 2) if enough else None,
            }
            checks = [
                {
                    "criterion": "coverage", "unit": "fraction", "value": round(coverage, 4), "min": criteria.min_coverage, "max": None,
                    "status": "pass" if enough else "fail",
                    "reason": None if enough else "Not enough valid elevation data; terrain metrics withheld.",
                }
            ]
            for name, rng, unit in (
                ("slope_mean_deg", criteria.slope_mean_deg, "degrees"),
                ("slope_median_deg", criteria.slope_median_deg, "degrees"),
                ("slope_p90_deg", criteria.slope_p90_deg, "degrees"),
                ("roughness_rms_height_m", criteria.roughness_rms_height_m, "metres"),
                ("relief_m", criteria.relief_m, "metres"),
            ):
                check = _check(name, metrics[name], rng, unit)
                if check:
                    checks.append(check)
            if criteria.fraction_steeper_than is not None:
                rule = criteria.fraction_steeper_than
                frac = float((sv > rule.threshold_deg).mean()) if enough and sv.size else None
                metrics[f"fraction_steeper_than_{rule.threshold_deg:g}deg"] = fnum(frac)
                checks.append(_check(f"fraction_steeper_than_{rule.threshold_deg:g}deg", frac, rule.range, "fraction"))

            if criteria.landcover is not None and classes is not None:
                cover = lc.summarize(classes.z[win], criteria.landcover)
                metrics["landcover_dominant"] = lc.WORLDCOVER_CLASSES.get(cover.dominant_class) if cover.dominant_class else None
                metrics["landcover_excluded_fraction"] = cover.excluded_fraction
                checks.append(
                    {
                        "criterion": "landcover", "unit": "fraction", "value": cover.excluded_fraction, "min": None,
                        "max": criteria.landcover.max_excluded_fraction, "status": cover.screen, "reason": cover.reason,
                    }
                )

            if not enough:
                status = "insufficient_data"
            elif any(ch["status"] == "fail" for ch in checks):
                status = "rejected"
            else:
                status = "candidate"
            tally[status] += 1
            if status != "candidate" and not request.include_rejected:
                continue

            ring = area.ring_lonlat(c * n, r * n, (c + 1) * n, (r + 1) * n)
            lon = sum(p[0] for p in ring[:4]) / 4
            lat = sum(p[1] for p in ring[:4]) / 4
            features.append(
                {
                    "type": "Feature",
                    "id": f"r{r}c{c}",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "id": f"r{r}c{c}",
                        "status": status,
                        "center_lon": round(lon, 6),
                        "center_lat": round(lat, 6),
                        "patch_size_m": n * scale,
                        "scale_m": scale,
                        "metrics": metrics,
                        "criteria": checks,
                        "not_assessed": [ch["criterion"] for ch in checks if ch["status"] == "not_assessed"],
                    },
                }
            )

    notes.append("A 'candidate' passed every criterion that could be assessed. It is a shortlist entry for further study, not a verdict of suitability.")
    return {
        "type": "FeatureCollection",
        "features": features,
        "summary": {"cells": rows * cols, **tally, "scale_m": scale, "patch_size_m": n * scale},
        "criteria": criteria.model_dump(),
        "provenance": provenance(dataset, area).model_dump(),
        "limitations": notes,
    }
