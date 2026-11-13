"""Cut a region out of a tiled global dataset into one local, analysis-ready GeoTIFF.

Pixels are copied on the source grid (no resampling), so the file is the original data, only
smaller. This is what makes an Earth site usable offline and pins the exact input of an analysis.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.merge import merge
from rasterio.windows import from_bounds

from .catalog import get_entry, tile_urls
from .fetch import _now, provenance_record
from .store import data_dir, register
from .validate import validate_raster

GDAL_ENV = dict(
    AWS_NO_SIGN_REQUEST="YES",
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff,.TIF",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    GDAL_HTTP_TIMEOUT="30",
)
MAX_REGION_DEGREES = 3.0


def prepare_region(dataset_id: str, name: str, west: float, south: float, east: float, north: float, *, sources: list[str] | None = None) -> dict:
    """Write backend/data/earth/regions/<name>_<dataset>.tif and register it as '<name>-<dataset>'.

    sources: override the tile URLs (used by tests with local files). Returns the manifest record.
    """
    entry = get_entry(dataset_id)
    if entry.access != "tiled":
        raise ValueError(f"{dataset_id} is not tiled: use fetch_dataset().")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", name):
        raise ValueError("Region name must be lowercase letters, digits and hyphens.")
    if not (west < east and south < north):
        raise ValueError("Need west < east and south < north.")
    if east - west > MAX_REGION_DEGREES or north - south > MAX_REGION_DEGREES:
        raise ValueError(f"Region is larger than {MAX_REGION_DEGREES:g} degrees on a side; cut smaller regions.")

    urls = sources or tile_urls(entry, west, south, east, north)
    opened, missing = [], []
    with rasterio.Env(**GDAL_ENV):
        for url in urls:
            try:
                opened.append(rasterio.open(url))
            except RasterioIOError:
                missing.append(url)
        if not opened:
            raise FileNotFoundError(f"No {dataset_id} tile covers this region (open ocean, or the source is unreachable).")
        try:
            first = opened[0]
            if len(opened) == 1:
                window = from_bounds(west, south, east, north, first.transform).round_offsets().round_lengths()
                data = first.read(1, window=window, boundless=True, fill_value=first.nodata or 0)[np.newaxis]
                transform = first.window_transform(window)
            else:
                data, transform = merge(opened, bounds=(west, south, east, north))
            profile = dict(
                driver="GTiff", height=data.shape[1], width=data.shape[2], count=1, dtype=data.dtype,
                crs=first.crs, transform=transform, nodata=first.nodata, compress="deflate", tiled=True,
                predictor=2 if np.issubdtype(data.dtype, np.integer) else 3,
            )
        finally:
            for ds in opened:
                ds.close()

    region_id = f"{name}-{entry.id}"
    path: Path = data_dir() / entry.body / "regions" / f"{name}_{entry.id}.tif"
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    validation = validate_raster(str(path), body=entry.body, kind=entry.kind, nominal_resolution_m=entry.nominal_resolution_m)
    used = [u for u in urls if u not in missing]
    prov = provenance_record(
        entry, product=entry.primary, quantity=entry.kind, unit="metres" if entry.kind == "elevation" else "class code",
        source=used, path=path, validation=validation,
        extra={"region": {"name": name, "bbox_lonlat": [west, south, east, north]}, "missing_tiles": missing,
               "processing": "Pixels copied on the source grid; no resampling."},
    )
    record = {
        "path": prov["file"],
        "name": f"{entry.name}: region '{name}'",
        "body": entry.body,
        "kind": entry.kind,
        "vertical_scale": 1.0,
        "nominal_resolution_m": entry.nominal_resolution_m,
        "citation": entry.citation,
        "license": entry.license,
        "source_page": entry.source_page,
        "vertical_datum": entry.vertical_datum,
        "products": {entry.primary: {"path": prov["file"], "quantity": entry.kind, "unit": prov["unit"], "sha256": prov["sha256"]}},
        "ready": validation["ready"],
        "validation": validation,
        "limitations": list(entry.limitations),
        "region": {"name": name, "bbox_lonlat": [west, south, east, north], "parent_dataset": entry.id},
        "registered_at": _now(),
    }
    register(region_id, record)
    return {"id": region_id, **record}
