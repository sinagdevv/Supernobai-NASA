"""Read the Layer 2 file store. This package does not write that store."""

from __future__ import annotations

import json
import os
from pathlib import Path

MANIFEST_VERSION = 1
LOCAL = "local"


class StoreError(Exception):
    pass


def data_dir() -> Path:
    env = os.environ.get("TERRAWINDOW_DATA_DIR")
    if env:
        return Path(env).resolve()
    backend = Path(__file__).resolve().parents[3]
    if backend.name == "backend":
        return backend / "data"
    return (Path.cwd() / "data").resolve()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoreError(f"{path} is not valid JSON.") from exc


def _manifest(reference: bool) -> dict:
    path = data_dir() / "manifest.json" if reference else data_dir() / LOCAL / "manifest.json"
    if not path.exists():
        return {"version": MANIFEST_VERSION, "datasets": {}}
    return _read_json(path)


def load_manifest() -> dict:
    """Reference manifest overlaid, per dataset id, by this machine's local manifest."""
    ref, loc = _manifest(True), _manifest(False)
    return {"version": MANIFEST_VERSION, "datasets": {**ref.get("datasets", {}), **loc.get("datasets", {})}}


def _provenance_path(rel_file: str, *, reference: bool) -> Path:
    name = rel_file + ".provenance.json"
    return data_dir() / name if reference else data_dir() / LOCAL / "provenance" / name


def read_provenance(rel_file: str) -> dict | None:
    for reference in (False, True):
        path = _provenance_path(rel_file, reference=reference)
        if path.exists():
            return _read_json(path)
    return None


def _primary_path(record: dict) -> str | None:
    products = record.get("products") or {}
    surface = products.get("surface") or {}
    return record.get("path") or surface.get("path")


def _checksum(record: dict, provenance: dict | None) -> str | None:
    if provenance and provenance.get("sha256"):
        return provenance["sha256"]
    surface = (record.get("products") or {}).get("surface") or {}
    return surface.get("sha256") or record.get("sha256")


def _center(provenance: dict | None) -> tuple[float, float] | None:
    summary = ((provenance or {}).get("validation") or {}).get("summary") or {}
    pair = summary.get("center_lonlat")
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return None
    try:
        lon, lat = float(pair[0]), float(pair[1])
    except (TypeError, ValueError):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lon, lat


def dataset_records() -> list[dict]:
    """One registry row per dataset in the merged manifest."""
    rows = []
    for dataset_id, record in load_manifest().get("datasets", {}).items():
        if not isinstance(record, dict):
            continue
        rel = _primary_path(record)
        provenance = read_provenance(rel) if rel else None
        summary = ((provenance or {}).get("validation") or {}).get("summary") or {}
        source_urls = (provenance or {}).get("source_urls") or []
        if not source_urls and record.get("source_page"):
            source_urls = [record["source_page"]]
        rows.append(
            {
                "id": dataset_id,
                "name": (provenance or {}).get("dataset_name") or record.get("name"),
                "body": (provenance or {}).get("body") or record.get("body"),
                "kind": record.get("kind"),
                "product": (provenance or {}).get("product") or "surface",
                "citation": (provenance or {}).get("citation") or record.get("citation"),
                "license": (provenance or {}).get("license") or record.get("license"),
                "source_urls": source_urls,
                "file_path": (provenance or {}).get("file") or rel,
                "bytes": (provenance or {}).get("bytes"),
                "sha256": _checksum(record, provenance),
                "limitations": (provenance or {}).get("limitations") or record.get("limitations") or [],
                "validation": (provenance or {}).get("validation") or record.get("validation"),
                "native_bounds": summary.get("bounds_native"),
                "center": _center(provenance),
                "provenance": provenance or record,
            }
        )
    return rows
