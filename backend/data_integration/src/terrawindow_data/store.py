"""The data store: what is version-controlled, what is local, and how they combine.

Layout (default backend/data/, override with TERRAWINDOW_DATA_DIR):

    manifest.json                          REFERENCE index of datasets (version-controlled, changed only on purpose)
    <body>/.../<file>.tif.provenance.json  REFERENCE provenance beside each raster (version-controlled)
    <body>/.../<file>.tif                  the rasters (never committed)
    local/manifest.json                    this machine's registrations: validation results, timestamps (not committed)
    local/provenance/<path>.json           this machine's retrieval records (not committed)

Setting up data (terrawindow-data fetch / region) writes only under local/, so it never dirties a clean checkout.
`load_manifest()` is the reference overlaid with the local entries, per dataset id; that merged view is what Layer 3 reads.
`--update-reference` (reference=True) is the deliberate way to change the version-controlled files.

Each manifest record looks like:

    {"path": "<relative to the store>", "body": "moon", "kind": "elevation", "name": ..., "citation": ...,
     "products": {...}, "validation": {...}, "ready": true, ...}
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


LOCAL = "local"


def local_dir() -> Path:
    return data_dir() / LOCAL


def manifest_path(*, reference: bool = True) -> Path:
    """The reference manifest, or (reference=False) this machine's local one."""
    return data_dir() / "manifest.json" if reference else local_dir() / "manifest.json"


def _read(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def load_reference_manifest() -> dict:
    return _read(manifest_path(reference=True))


def load_local_manifest() -> dict:
    return _read(manifest_path(reference=False))


def load_manifest() -> dict:
    """Every dataset this store knows: the reference entries, with local entries replacing the reference ones of the same id."""
    ref, loc = load_reference_manifest(), load_local_manifest()
    return {"version": MANIFEST_VERSION, "datasets": {**ref.get("datasets", {}), **loc.get("datasets", {})}}


def register(dataset_id: str, record: dict, *, reference: bool = False) -> dict:
    """Add or replace one dataset in the local manifest (or, with reference=True, the version-controlled one). Atomic write."""
    path = manifest_path(reference=reference)
    manifest = _read(path)
    manifest["version"] = MANIFEST_VERSION
    manifest["datasets"][dataset_id] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(path)
    return load_manifest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(data_dir()).as_posix()


def provenance_path(rel_file: str, *, reference: bool) -> Path:
    """Where the provenance record of a raster lives: beside it (reference) or under local/provenance/."""
    name = rel_file + ".provenance.json"
    return data_dir() / name if reference else local_dir() / "provenance" / name


def read_provenance(rel_file: str) -> dict | None:
    """The provenance record of a raster: this machine's own if there is one, else the reference record."""
    for ref in (False, True):
        path = provenance_path(rel_file, reference=ref)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None
