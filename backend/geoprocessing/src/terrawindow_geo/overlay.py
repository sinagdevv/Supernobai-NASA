"""Render a terrain layer as a PNG the map can drape over the basemap."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from .models import OverlayRequest, OverlayResponse
from .profile import extract_dem, provenance
from .scale import default_scales
from .io.raster import native_pixel_size
from .io.sources import materialize, resolve_bbox, resolve_uris
from .terrain.slope import hillshade, slope_aspect

# Colour ramps as (position 0..1, R, G, B). Slope: pale yellow to dark red; elevation: green to white.
RAMPS = {
    "slope": [(0.0, 255, 255, 204), (0.25, 254, 217, 118), (0.5, 253, 141, 60), (0.75, 227, 26, 28), (1.0, 128, 0, 38)],
    "elevation": [(0.0, 38, 115, 77), (0.35, 222, 210, 140), (0.7, 150, 100, 60), (1.0, 250, 250, 250)],
    "hillshade": [(0.0, 20, 20, 20), (1.0, 245, 245, 245)],
}


def _colorize(values: np.ndarray, lo: float, hi: float, ramp) -> np.ndarray:
    t = np.nan_to_num(np.clip((values - lo) / (hi - lo if hi > lo else 1.0), 0, 1))
    pos = [p[0] for p in ramp]
    rgba = np.zeros(values.shape + (4,), dtype=np.uint8)
    for ch in range(3):
        rgba[..., ch] = np.interp(t, pos, [p[ch + 1] for p in ramp]).astype(np.uint8)
    rgba[..., 3] = np.where(np.isfinite(values), 255, 0)  # no data stays transparent
    return rgba


def render_overlay(request: OverlayRequest) -> OverlayResponse:
    dataset = materialize(request.dataset)
    request = request.model_copy(update={"dataset": dataset, "bbox": resolve_bbox(dataset, request.bbox)})
    scale = request.scale_m
    if scale is None:
        scale = default_scales(native_pixel_size(resolve_uris(request.dataset, request.bbox), request.bbox))[0]
    patch = extract_dem(request.dataset, request.bbox, scale)

    if request.layer == "slope":
        values, _ = slope_aspect(patch.z, patch.pixel_size_m)
        lo, hi, unit = 0.0, request.slope_max_deg, "degrees"
    elif request.layer == "hillshade":
        values = hillshade(patch.z, patch.pixel_size_m, request.sun_azimuth_deg, request.sun_elevation_deg)
        lo, hi, unit = 0.0, 1.0, "relative illumination (no cast shadows)"
    else:
        values = patch.z
        finite = values[np.isfinite(values)]
        lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
        unit = "metres"

    ramp = RAMPS[request.layer]
    buf = io.BytesIO()
    Image.fromarray(_colorize(values, lo, hi, ramp), "RGBA").save(buf, format="PNG", optimize=True)

    ring = patch.ring_lonlat()
    return OverlayResponse(
        layer=request.layer,
        image_base64=base64.b64encode(buf.getvalue()).decode("ascii"),
        coordinates=ring[:4],
        width=patch.shape[1],
        height=patch.shape[0],
        scale_m=patch.pixel_size_m,
        value_range=[round(lo, 3), round(hi, 3)],
        unit=unit,
        legend=[{"value": round(lo + p[0] * (hi - lo), 3), "color": "#{:02x}{:02x}{:02x}".format(*p[1:])} for p in ramp],
        provenance=provenance(request.dataset, patch),
    )
