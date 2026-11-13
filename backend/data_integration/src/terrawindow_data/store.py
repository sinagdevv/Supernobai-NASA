"""The local data store and its manifest.

Layout (default backend/data/, override with TERRAWINDOW_DATA_DIR):

    manifest.json                       index of every analysis-ready dataset (the Layer 3 contract)
    lunar/<dataset id>/<file>.tif       fetched files, each with a <file>.tif.provenance.json
    earth/regions/<name>_<dataset>.tif  regions cut from tiled datasets

manifest.json is the only thing Layer 3 needs from Layer 2:

    {"version": 1, "datasets": {"<id>": {"path": "<relative to the store>", "body": "moon",
     "kind": "elevation", "name": ..., "citation": ..., "products": {...}, "validation": {...}}}}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MANIFEST_VERSION = 1


def data_dir() -> Path:
    env = os.environ.get("TERRAWINDOW_DATA_DIR")
    if env:
        return Path(env).resolve()
    # src/terrawindow_data/store.py -> backend/ when installed in editable mode from the repo
    backend = Path(__file__).resolve().parents[3]
    if backend.name == "backend":
        return backend / "data"
    return (Path.cwd() / "data").resolve()


def manifest_path() -> Path:
    return data_dir() / "manifest.json"


def load_manifest() -> dict:
    path = manifest_path()
    if not path.exists():
        return {"version": MANIFEST_VERSION, "datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def register(dataset_id: str, record: dict) -> dict:
    """Add or replace one dataset in the manifest (atomic write)."""
    manifest = load_manifest()
    manifest["version"] = MANIFEST_VERSION
    manifest["datasets"][dataset_id] = record
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(path)
    return manifest


def relative(path: Path) -> str:
    return path.resolve().relative_to(data_dir()).as_posix()
