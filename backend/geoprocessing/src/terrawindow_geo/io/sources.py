"""Where rasters come from.

Layer 2 owns dataset retrieval. This module only (a) resolves tile URLs for two public,
credential-free cloud-optimised datasets so the engine runs standalone, and (b) decides which
URIs the HTTP API is allowed to open.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlparse

from .. import readiness
from ..config import get_settings
from ..errors import GeoError
from ..models import BBox, DatasetInfo, DatasetRef

GLO30 = "copernicus-glo30"
WORLDCOVER = "esa-worldcover"

REGISTRY: dict[str, DatasetInfo] = {
    GLO30: DatasetInfo(
        id=GLO30,
        name="Copernicus DEM GLO-30 (public COGs on AWS Open Data)",
        body="earth",
        kind="elevation",
        nominal_resolution_m=30.0,
        coverage="Global land, 1 x 1 degree tiles. A digital surface model: includes vegetation and buildings.",
        citation="European Space Agency (2024). Copernicus Global Digital Elevation Model. Distributed by OpenTopography. https://doi.org/10.5069/G9028PQB",
        license="Copernicus DEM licence: free of charge, attribution required.",
    ),
    WORLDCOVER: DatasetInfo(
        id=WORLDCOVER,
        name="ESA WorldCover 10 m 2021 v200",
        body="earth",
        kind="landcover",
        nominal_resolution_m=10.0,
        coverage="Global land, 3 x 3 degree tiles, 11 land-cover classes.",
        citation="Zanaga, D., et al. (2022). ESA WorldCover 10 m 2021 v200. https://doi.org/10.5281/zenodo.7254221",
        license="CC BY 4.0",
    ),
}


def _manifest(path) -> dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("datasets", {})
    except (OSError, json.JSONDecodeError):
        return {}


def stored_datasets() -> dict[str, dict]:
    """Datasets in the Layer 2 store: the version-controlled manifest.json overlaid, per id, by local/manifest.json.

    Layer 2 writes a normal setup to local/ so it never dirties a clean checkout, and this is the same merge its
    load_manifest() performs. Layer 3 does not import Layer 2, so the few lines are repeated here on purpose.
    """
    root = get_settings().data_dir
    return {**_manifest(root / "manifest.json"), **_manifest(root / "local" / "manifest.json")}


def materialize(dataset: DatasetRef) -> DatasetRef:
    """Fill in body and vertical scale for an id that Layer 2 registered in the store."""
    if dataset.id is None or dataset.id in REGISTRY:
        return dataset
    record = stored_datasets().get(dataset.id)
    if record is None:
        return dataset
    return dataset.model_copy(update={"body": record.get("body", dataset.body), "vertical_scale": record.get("vertical_scale", 1.0)})


def _tiles(bbox: BBox, step: int) -> list[tuple[int, int]]:
    eps = 1e-9
    lat0 = math.floor(bbox.south / step) * step
    lon0 = math.floor(bbox.west / step) * step
    out = []
    lat = lat0
    while lat < bbox.north - eps:
        lon = lon0
        while lon < bbox.east - eps:
            out.append((lat, lon))
            lon += step
        lat += step
    return out


def _ns(lat: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"


def _ew(lon: int) -> str:
    return f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def glo30_urls(bbox: BBox) -> list[str]:
    urls = []
    for lat, lon in _tiles(bbox, 1):
        name = f"Copernicus_DSM_COG_10_{_ns(lat)}_00_{_ew(lon)}_00_DEM"
        urls.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif")
    return urls


def worldcover_urls(bbox: BBox) -> list[str]:
    base = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
    return [f"{base}/ESA_WorldCover_10m_2021_v200_{_ns(lat)}{_ew(lon)}_Map.tif" for lat, lon in _tiles(bbox, 3)]


def _padded(bbox: BBox, frac: float = 0.05) -> BBox:
    """The metric grid is slightly larger than the lon/lat box, so look one step past its edges."""
    dx, dy = (bbox.east - bbox.west) * frac, (bbox.north - bbox.south) * frac
    return BBox(
        west=max(-180.0, bbox.west - dx),
        east=min(180.0, bbox.east + dx),
        south=max(-90.0, bbox.south - dy),
        north=min(90.0, bbox.north + dy),
    )


# availability status -> (error code, HTTP status)
_UNAVAILABLE = {"missing": ("source_unavailable", 404), "unreadable": ("source_unreadable", 422), "not_validated": ("dataset_not_validated", 409)}


def resolve_uris(dataset: DatasetRef, bbox: BBox) -> list[str]:
    """Turn a dataset reference into the list of raster URIs covering `bbox`."""
    if dataset.uri is not None:
        return [dataset.uri]
    if dataset.uris is not None:
        if not dataset.uris:
            raise GeoError("invalid_request", "dataset.uris is empty.")
        return list(dataset.uris)
    if dataset.id not in REGISTRY:
        stored = stored_datasets()
        if dataset.id in stored:
            verdict = readiness.check(dataset.id, stored[dataset.id])
            if verdict["status"] != "available":
                code, status = _UNAVAILABLE[verdict["status"]]
                raise GeoError(code, f"Dataset '{dataset.id}' cannot be used: {verdict['detail']}", status=status,
                               details={"dataset_id": dataset.id, "availability": verdict["status"], "setup": verdict["setup"]})
            return [str((get_settings().data_dir / stored[dataset.id]["path"]).resolve())]
        raise GeoError(
            "dataset_not_found",
            f"Unknown dataset id '{dataset.id}'. Built-in ids and datasets fetched by Layer 2 are accepted.",
            status=404,
            details={"known_ids": sorted([*REGISTRY, *stored])},
        )
    if bbox.crs != "geographic":
        raise GeoError("invalid_request", "Registry datasets need a geographic (lon/lat) bbox.")
    padded = _padded(bbox)
    return glo30_urls(padded) if dataset.id == GLO30 else worldcover_urls(padded)


def resolve_bbox(dataset: DatasetRef, bbox: BBox | None) -> BBox:
    """The requested bbox, or the full extent of a single-file dataset when none was given."""
    if bbox is not None:
        return bbox
    if dataset.id in REGISTRY:
        raise GeoError("invalid_request", f"'{dataset.id}' is a global dataset: a bbox is required.")
    import rasterio
    from rasterio.errors import RasterioIOError

    from .raster import GDAL_ENV

    uris = resolve_uris(dataset, BBox(west=0, south=0, east=1, north=1, crs="native"))
    if len(uris) != 1:
        raise GeoError("invalid_request", "A bbox is required when the dataset has more than one raster.")
    try:
        with rasterio.Env(**GDAL_ENV), rasterio.open(uris[0]) as ds:
            b = ds.bounds
    except RasterioIOError as exc:
        raise GeoError("source_unavailable", "The source raster could not be opened.", status=404, details={"sources": [str(exc).splitlines()[0][:160]]}) from None
    return BBox(west=b.left, south=b.bottom, east=b.right, north=b.top, crs="native")


def describe(dataset: DatasetRef) -> tuple[str, str | None]:
    """(display name, citation) for provenance."""
    if dataset.id in REGISTRY:
        info = REGISTRY[dataset.id]
        return info.name, info.citation
    record = stored_datasets().get(dataset.id) if dataset.id else None
    if record:
        return record.get("name", dataset.id), record.get("citation")
    return dataset.name or "User-supplied raster", None


def check_api_access(dataset: DatasetRef) -> None:
    """The HTTP API may open http(s) rasters and local files inside the data folder only."""
    settings = get_settings()
    for uri in ([dataset.uri] if dataset.uri else []) + (dataset.uris or []):
        scheme = urlparse(uri).scheme.lower()
        if scheme in {"http", "https"}:
            continue
        if scheme and len(scheme) > 1:  # s3://, /vsi..., file:// and friends; a 1-letter scheme is a Windows drive
            raise GeoError("source_not_allowed", f"Only http(s) URLs and files in the data folder are allowed: {uri}", status=403)
        if uri.startswith("/vsi"):
            raise GeoError("source_not_allowed", f"GDAL virtual paths are not allowed through the API: {uri}", status=403)
        if settings.allow_any_local_path:
            continue
        path = Path(uri)
        resolved = (path if path.is_absolute() else settings.data_dir / path).resolve()
        if not resolved.is_relative_to(settings.data_dir):
            raise GeoError(
                "source_not_allowed",
                "Local rasters must be inside the engine's data folder (TWGEO_DATA_DIR).",
                status=403,
                details={"data_dir": str(settings.data_dir)},
            )


def localize(dataset: DatasetRef) -> DatasetRef:
    """Resolve relative local paths against the data folder."""
    settings = get_settings()

    def fix(uri: str) -> str:
        if urlparse(uri).scheme.lower() in {"http", "https"} or uri.startswith("/vsi"):
            return uri
        path = Path(uri)
        return str(path if path.is_absolute() else (settings.data_dir / path).resolve())

    if dataset.uri is not None:
        return dataset.model_copy(update={"uri": fix(dataset.uri)})
    if dataset.uris is not None:
        return dataset.model_copy(update={"uris": [fix(u) for u in dataset.uris]})
    return dataset
