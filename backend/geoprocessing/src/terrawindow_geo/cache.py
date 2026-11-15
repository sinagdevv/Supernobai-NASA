"""File cache for API results, keyed by endpoint + request + engine version.

Local rasters are keyed with their modification time, so replacing a file invalidates its results.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from . import __version__
from .config import get_settings

CACHE_SCHEMA_VERSION = 2


def _file_stamp(path: str | Path) -> dict[str, Any]:
    try:
        stat = Path(path).stat()
    except OSError:
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _fingerprint(request: BaseModel) -> str:
    payload = request.model_dump(mode="json")
    dataset = payload.get("dataset") or {}
    stamps = []
    for uri in ([dataset.get("uri")] if dataset.get("uri") else []) + (dataset.get("uris") or []):
        if os.path.exists(uri):
            stamps.append(_file_stamp(uri))

    stored_source: dict[str, Any] | None = None
    dataset_id = dataset.get("id")
    if dataset_id:
        from .io.sources import stored_datasets

        settings = get_settings()
        manifest_path = settings.data_dir / "manifest.json"
        manifest_stamp = _file_stamp(manifest_path)
        record = stored_datasets().get(dataset_id)
        stored_paths = []
        if record:
            for value in (record.get("path"),):
                if isinstance(value, str):
                    stored_paths.append(value)
            for product in (record.get("products") or {}).values():
                if isinstance(product, dict) and isinstance(product.get("path"), str):
                    stored_paths.append(product["path"])
        stored_source = {
            "manifest": manifest_stamp,
            "version": record.get("version") if record else None,
            "sha256": record.get("sha256") if record else None,
            "files": [
                _file_stamp(settings.data_dir / path) for path in stored_paths
            ],
        }

    return json.dumps(
        {
            "request": payload,
            "local_files": stamps,
            "stored_source": stored_source,
            "cache_schema": CACHE_SCHEMA_VERSION,
            "version": __version__,
        },
        sort_keys=True,
    )


def cached(endpoint: str, request: BaseModel, compute: Callable[[], Any]) -> Any:
    """Return the cached JSON for this request, or compute, store and return it."""
    settings = get_settings()
    if not settings.cache_enabled:
        return _plain(compute())
    key = hashlib.sha256(f"{endpoint}|{_fingerprint(request)}".encode()).hexdigest()[:32]
    path = settings.cache_dir / endpoint / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass  # unreadable entry: recompute and overwrite
    result = _plain(compute())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # a read-only disk must not break the request
    return result


def _plain(result: Any) -> Any:
    return result.model_dump(mode="json") if isinstance(result, BaseModel) else result
