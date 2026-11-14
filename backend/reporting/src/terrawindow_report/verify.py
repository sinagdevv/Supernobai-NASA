"""Recompute stored hashes. A mismatch is reported and nothing is rewritten."""

from __future__ import annotations

import hashlib
from pathlib import Path

from psycopg import Connection

from .canonical import canonical_json, sha256_bytes, sha256_text
from .files import data_dir
from .registry import get_run, reports_for_run


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_run(conn: Connection, run_id: str) -> dict:
    run = get_run(conn, run_id)
    checks: list[dict] = []

    if run["status"] != "completed" or not run.get("result_hash"):
        checks.append({"check": "result_hash", "status": "fail", "detail": f"Run status is {run['status']}."})
    else:
        again = sha256_text(canonical_json(run["result"]))
        checks.append(
            {
                "check": "result_hash",
                "status": "pass" if again == run["result_hash"] else "fail",
                "detail": "Stored result hash matches the stored result." if again == run["result_hash"] else "Stored result hash does not match the stored result.",
            }
        )

    root = data_dir()
    if not run["datasets"] and run["status"] == "completed":
        checks.append({"check": "dataset_checksum", "status": "fail", "detail": "The completed run has no input datasets."})
    for item in run["datasets"]:
        registry = item.get("registry_sha256")
        recorded = item["sha256"]
        same = registry == recorded
        checks.append(
            {
                "check": "dataset_checksum",
                "status": "pass" if same else "fail",
                "role": item["role"],
                "dataset_id": item["dataset_id"],
                "detail": "Registry checksum matches the checksum recorded for this run." if same else "Registry checksum differs from the checksum recorded for this run.",
            }
        )
        relative = item.get("file_path")
        if not relative:
            checks.append(
                {
                    "check": "file_checksum",
                    "status": "absent",
                    "role": item["role"],
                    "dataset_id": item["dataset_id"],
                    "detail": "The registry has no file path for this dataset.",
                }
            )
            continue
        path = root / relative
        if not path.is_file():
            checks.append(
                {
                    "check": "file_checksum",
                    "status": "absent",
                    "role": item["role"],
                    "dataset_id": item["dataset_id"],
                    "detail": "The GeoTIFF is not on disk. The recorded checksum was not compared with a file.",
                }
            )
            continue
        digest = _file_sha256(path)
        checks.append(
            {
                "check": "file_checksum",
                "status": "pass" if digest == recorded else "fail",
                "role": item["role"],
                "dataset_id": item["dataset_id"],
                "detail": "File checksum matches the checksum recorded for this run." if digest == recorded else "File checksum differs from the checksum recorded for this run.",
            }
        )

    reports = reports_for_run(conn, run_id)
    if not reports:
        checks.append({"check": "pdf_checksum", "status": "absent", "detail": "This run has no stored dossier."})
    for report in reports:
        digest = sha256_bytes(report["pdf"])
        header = report["pdf"].startswith(b"%PDF")
        ok = digest == report["pdf_sha256"] and header
        checks.append(
            {
                "check": "pdf_checksum",
                "status": "pass" if ok else "fail",
                "report_id": report["report_id"],
                "template_version": report["template_version"],
                "detail": "PDF checksum matches the stored bytes." if ok else "PDF checksum or header does not match the stored bytes.",
            }
        )

    failed = any(item["status"] == "fail" for item in checks)
    return {"run_id": run_id, "ok": not failed, "checks": checks}
