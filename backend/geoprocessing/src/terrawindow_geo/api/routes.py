"""HTTP endpoints. Thin wrappers: every one validates access, then calls the library."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .. import __version__
from ..cache import cached
from ..compare import compare_profiles
from ..discovery import screen_region
from ..errors import GeoError
from .. import readiness
from ..io.sources import REGISTRY, check_api_access, localize, stored_datasets
from ..models import (
    CompareRequest,
    ComparisonResult,
    DatasetInfo,
    OverlayRequest,
    OverlayResponse,
    PatchRequest,
    ScreenRequest,
    TerrainProfile,
)
from ..overlay import render_overlay
from ..profile import build_profile
from .. import rehearsal_service
from ..scale import COMMON_SCALES_M
from ..suitability import (
    Layer5AssessmentRequest,
    MissionAssessment,
    assess_mission,
    suitability_metrics_response,
)

router = APIRouter()


def _prepare(request):
    """Enforce the API's source rules and resolve data-folder paths."""
    check_api_access(request.dataset)
    return request.model_copy(update={"dataset": localize(request.dataset)})


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "terrawindow-geo", "version": __version__}


@router.get("/v1/datasets", response_model=dict[str, Any], tags=["meta"])
def datasets() -> dict[str, Any]:
    """Built-in datasets, datasets Layer 2 has put in the store, and the default analysis scales."""
    stored = [
        {
            "id": key, "name": d.get("name", key), "body": d.get("body"), "kind": d.get("kind"),
            "nominal_resolution_m": d.get("nominal_resolution_m"), "citation": d.get("citation"), "license": d.get("license"),
            # `ready` means usable now: the file is in the store and opens. `validated` is Layer 2's recorded verdict, which can outlive the file.
            "ready": (avail := readiness.check(key, d))["status"] == "available", "availability": avail, "validated": d.get("ready"),
            "summary": (d.get("validation") or {}).get("summary"), "region": d.get("region"),
            "products": sorted(d.get("products", {})),
            # what a reader needs to judge the data: where it is, what it is relative to, and what it cannot show
            "limitations": d.get("limitations"), "vertical_datum": d.get("vertical_datum"), "source_page": d.get("source_page"), "details": d.get("details"),
        }
        for key, d in stored_datasets().items()
    ]
    return {
        "datasets": [d.model_dump() for d in REGISTRY.values()],
        "stored_datasets": stored,
        "default_scales_m": COMMON_SCALES_M,
        "custom_sources": "Any GeoTIFF/COG via dataset.uri: an http(s) URL, or a path inside the engine's data folder.",
    }


@router.post("/v1/patches/profile", response_model=TerrainProfile, tags=["terrain"])
def patch_profile(request: PatchRequest) -> Any:
    """Slope, roughness, relief and coverage of one patch, at each supported scale."""
    request = _prepare(request)
    return cached("profile", request, lambda: build_profile(request))


@router.post("/v1/patches/compare", response_model=ComparisonResult, tags=["terrain"])
def patch_compare(request: CompareRequest) -> Any:
    """Per-criterion comparison of a candidate against a reference. No overall score."""
    sides = {}
    for side in ("reference", "candidate"):
        profile = getattr(request, f"{side}_profile")
        if profile is None:
            patch = _prepare(getattr(request, side))
            if request.scales_m:
                patch = patch.model_copy(update={"scales_m": request.scales_m})
            profile = TerrainProfile.model_validate(cached("profile", patch, lambda p=patch: build_profile(p)))
        sides[side] = profile
    return compare_profiles(sides["reference"], sides["candidate"], request.tolerances)


@router.post("/v1/discovery/screen", tags=["discovery"])
def discovery_screen(request: ScreenRequest) -> dict[str, Any]:
    """Cut an area into patches and screen each one. Returns a GeoJSON FeatureCollection."""
    request = _prepare(request)
    return cached("screen", request, lambda: screen_region(request))


@router.post("/v1/patches/overlay", response_model=OverlayResponse, tags=["terrain"])
def patch_overlay(request: OverlayRequest) -> Any:
    """Slope, hillshade or elevation as a PNG with corner coordinates for a MapLibre image source."""
    request = _prepare(request)
    return cached("overlay", request, lambda: render_overlay(request))


@router.get("/v1/suitability/metrics", tags=["suitability"])
def suitability_metrics() -> dict[str, Any]:
    """Supported Layer 3 and Layer 4 assessment metrics and canonical units."""
    return suitability_metrics_response()


@router.post(
    "/v1/suitability/assess",
    response_model=MissionAssessment,
    tags=["suitability"],
)
def suitability_assess(request: Layer5AssessmentRequest) -> MissionAssessment:
    """Profile the selected Layer 3 candidate and assess it against supplied evidence."""
    candidate_request = _prepare(request.candidate)
    profile_payload = cached(
        "profile",
        candidate_request,
        lambda: build_profile(candidate_request),
    )
    profile = TerrainProfile.model_validate(profile_payload)
    if request.layer4_result is not None and request.layer4_result.body != profile.patch.body:
        raise GeoError(
            "invalid_request",
            "Layer 4 result body must match the Layer 3 candidate body.",
            status=422,
            details={
                "candidate_body": profile.patch.body,
                "layer4_body": request.layer4_result.body,
            },
        )
    return assess_mission(request, profile)


@router.get("/v1/rehearsal/status", tags=["rehearsal"])
def rehearsal_status() -> dict[str, Any]:
    """Whether Layer 4 and its kernels and Mars source are present, per body."""
    return rehearsal_service.status()


@router.post("/v1/rehearsal/evaluate", tags=["rehearsal"])
def rehearsal_evaluate(request: rehearsal_service.RehearsalRequest) -> dict[str, Any]:
    """Layer 4: sampled solar geometry, terrain illumination and rehearsal windows for the candidate's body."""
    request = request.model_copy(update={"candidate": _prepare(request.candidate)})
    return rehearsal_service.evaluate(request)


__all__ = ["router", "DatasetInfo"]
