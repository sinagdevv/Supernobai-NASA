"""File cache for API results, keyed by endpoint + request + engine version.

Local rasters are keyed with their modification time, so replacing a file invalidates its results.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

from pydantic import BaseModel

from . import __version__
from .config import get_settings


def _fingerprint(request: BaseModel) -> str:
    payload = request.model_dump(mode="json")
    stamps = []
    for side in ("dataset",):
        ds = payload.get(side) or {}
        for uri in ([ds.get("uri")] if ds.get("uri") else []) + (ds.get("uris") or []):
            if os.path.exists(uri):
                stamps.append(os.path.getmtime(uri))
    return json.dumps({"request": payload, "mtimes": stamps, "version": __version__}, sort_keys=True)


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
