"""Retrieve catalogued files into the store, with checksums and a provenance record each."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .catalog import CatalogEntry, get_entry
from .store import data_dir, provenance_path, read_provenance, register, relative
from .validate import validate_raster

USER_AGENT = f"terrawindow-data/{__version__}"
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path, *, progress=None) -> None:
    """Download to a temporary file and move it into place only when complete."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, tmp.open("wb") as fh:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while block := response.read(CHUNK):
            fh.write(block)
            done += len(block)
            if progress:
                progress(done, total)
        if total and done != total:
            raise IOError(f"Incomplete download of {url}: got {done} of {total} bytes")
    tmp.replace(dest)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# What must match for a local retrieval to be the same data as the reference record describes. Timestamps never count.
REFERENCE_FIELDS = ("sha256", "bytes", "source_urls")


def compare_to_reference(record: dict, reference: dict | None) -> dict:
    """Is this retrieval the one the version-controlled provenance describes? Reported, never enforced.

    `matches`: same checksum, size and sources. `differs`: at least one differs (for a region cut locally, a different GDAL build
    can change the bytes of an identical pixel grid, so this is a flag to read, not an error). `no_reference`: nothing to compare to.
    """
    if reference is None:
        return {"status": "no_reference"}
    differing = [f for f in REFERENCE_FIELDS if record.get(f) != reference.get(f)]
    if not differing:
        return {"status": "matches"}
    return {"status": "differs", "fields": differing, "reference_sha256": reference.get("sha256"), "reference_bytes": reference.get("bytes")}


def provenance_record(entry: CatalogEntry, *, product: str, quantity: str, unit: str, source: list[str], path: Path, validation: dict, extra: dict | None = None, reference: bool = False) -> dict:
    """Describe a retrieved file and write the record: under local/ by default, beside the raster (version-controlled) with reference=True."""
    record = {
        "dataset_id": entry.id,
        "dataset_name": entry.name,
        "product": product,
        "quantity": quantity,
        "unit": unit,
        "body": entry.body,
        "source_urls": source,
        "source_page": entry.source_page,
        "citation": entry.citation,
        "license": entry.license,
        "vertical_datum": entry.vertical_datum,
        "retrieved_at": _now(),
        "retrieved_by": USER_AGENT,
        "file": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        "validation": validation,
        "limitations": list(entry.limitations),
    }
    record.update(extra or {})
    if not reference:
        ref_path = provenance_path(record["file"], reference=True)
        record["reference_check"] = compare_to_reference(record, json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else None)
    target = provenance_path(record["file"], reference=reference)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def fetch_dataset(dataset_id: str, products: list[str] | None = None, *, force: bool = False, progress=None, reference: bool = False) -> dict:
    """Download a file dataset, validate it, write provenance and register it in the manifest.

    products: which rasters to get (default: the primary one). Returns the manifest record.
    Files already in the store with a provenance record (local or reference) are reused unless force=True.
    Records go to the local, uncommitted part of the store; reference=True writes the version-controlled files instead.
    """
    entry = get_entry(dataset_id)
    if entry.access != "file":
        raise ValueError(f"{dataset_id} is a tiled dataset: cut a region with prepare_region() instead of fetching it whole.")
    available = {p.key: p for p in entry.products}
    wanted = products or [entry.primary]
    unknown = [k for k in wanted if k not in available]
    if unknown:
        raise ValueError(f"{dataset_id} has no product {unknown}. Available: {', '.join(available)}")
    if entry.primary not in wanted:
        wanted = [entry.primary, *wanted]

    folder = data_dir() / ("lunar" if entry.body == "moon" else entry.body) / entry.id
    fetched: dict[str, dict] = {}
    for key in wanted:
        product = available[key]
        path = folder / product.url.rsplit("/", 1)[1]
        rel = relative(path)
        known = read_provenance(rel)
        if path.exists() and known is not None and not force:
            fetched[key] = known
            continue
        download(product.url, path, progress=progress)
        kind = entry.kind if key == entry.primary else "derived"
        validation = validate_raster(str(path), body=entry.body, kind=kind, nominal_resolution_m=entry.nominal_resolution_m)
        fetched[key] = provenance_record(entry, product=key, quantity=product.quantity, unit=product.unit, source=[product.url], path=path, validation=validation, reference=reference)

    # Keep products fetched on an earlier call.
    from .store import load_manifest

    previous = load_manifest()["datasets"].get(entry.id, {}).get("products", {})
    products_out = {**previous, **{k: {"path": r["file"], "quantity": r["quantity"], "unit": r["unit"], "sha256": r["sha256"]} for k, r in fetched.items()}}
    primary = fetched[entry.primary]
    record = {
        "path": primary["file"],
        "name": entry.name,
        "body": entry.body,
        "kind": entry.kind,
        "vertical_scale": 1.0,
        "nominal_resolution_m": entry.nominal_resolution_m,
        "citation": entry.citation,
        "license": entry.license,
        "source_page": entry.source_page,
        "vertical_datum": entry.vertical_datum,
        "products": products_out,
        "ready": primary["validation"]["ready"],
        "validation": primary["validation"],
        "limitations": list(entry.limitations),
        "registered_at": _now(),
        "reference_check": primary.get("reference_check", {"status": "no_reference"}),
        **({"site": entry.extra} if entry.extra else {}),
    }
    register(entry.id, record, reference=reference)
    return record
