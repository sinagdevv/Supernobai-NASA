"""Whether a dataset in the Layer 2 store can actually be used, judged from the file and not from the manifest alone.

The manifest records what Layer 2's validation concluded when the file was fetched. It is versioned; the rasters are not. So
on a fresh checkout it lists datasets whose files are absent. This module looks at the disk:

    available      the file exists, opens as a raster, and Layer 2 did not mark it invalid
    missing        the manifest lists it but the file is not in the store (setup required)
    unreadable     the file exists but is not a usable raster (truncated, corrupt, not a GeoTIFF)
    not_validated  the file is fine but Layer 2's validation explicitly failed

Metadata the engine does not need (citation, validation summary, limitations) never makes a readable raster unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rasterio

from .config import get_settings

# (resolved path, mtime_ns, size) -> verdict from opening the file. A changed file is a new key.
_OPENED: dict[tuple[str, int, int], str | None] = {}


def _setup_hint(dataset_id: str, record: dict[str, Any]) -> str:
    region = record.get("region")
    if isinstance(region, dict) and region.get("bbox_lonlat") and region.get("parent_dataset") and region.get("name"):
        w, s, e, n = region["bbox_lonlat"]
        return f"terrawindow-data region {region['parent_dataset']} {region['name']} {w} {s} {e} {n}"
    return f"terrawindow-data fetch {dataset_id}"


def _open_problem(path: Path) -> str | None:
    """None if the file opens as a raster with data; otherwise why not. Cached on the file's identity."""
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _OPENED:
        try:
            with rasterio.open(path) as ds:
                _OPENED[key] = None if ds.count >= 1 and ds.width > 0 and ds.height > 0 else "the file has no raster bands"
        except Exception as exc:  # rasterio raises RasterioIOError, but a corrupt file can surface other types
            _OPENED[key] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
    return _OPENED[key]


def check(dataset_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """The availability of one manifest record: `{status, detail, setup}` (`setup` only when something needs doing)."""
    rel = record.get("path")
    if not rel:
        return {"status": "unreadable", "detail": "The manifest entry has no file path.", "setup": _setup_hint(dataset_id, record)}
    data_dir = get_settings().data_dir
    path = (data_dir / rel).resolve()
    if data_dir not in path.parents:
        return {"status": "unreadable", "detail": "The manifest path points outside the data store.", "setup": _setup_hint(dataset_id, record)}
    if not path.is_file():
        return {"status": "missing", "detail": f"{rel} is not in the data store.", "setup": _setup_hint(dataset_id, record)}
    problem = _open_problem(path)
    if problem:
        return {"status": "unreadable", "detail": f"{rel} could not be read: {problem}", "setup": _setup_hint(dataset_id, record)}
    if record.get("ready") is False:  # an absent flag (older manifests) does not count against the data
        return {"status": "not_validated", "detail": "Layer 2 validation failed for this dataset; see its validation report.", "setup": _setup_hint(dataset_id, record)}
    return {"status": "available", "detail": None, "setup": None}


def is_available(dataset_id: str, record: dict[str, Any]) -> bool:
    return check(dataset_id, record)["status"] == "available"
