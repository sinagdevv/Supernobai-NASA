"""HTTP endpoints. Thin wrappers: every one validates access, then calls the library."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .. import __version__
from ..cache import cached
from ..compare import compare_profiles
from ..discovery import screen_region
from ..io.sources import REGISTRY, check_api_access, localize
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
from ..scale import COMMON_SCALES_M

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
    """Built-in datasets, plus the analysis scales the engine uses by default."""
    return {
        "datasets": [d.model_dump() for d in REGISTRY.values()],
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


__all__ = ["router", "DatasetInfo"]
