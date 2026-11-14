"""Dataset registry, run registry, candidate storage, and result reuse."""

from __future__ import annotations

import json
import os
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from .canonical import input_fingerprint, request_document, request_hash, result_hash, sanitize
from .files import dataset_records
from .shapes import Kind, ReportError, candidate_features, dataset_refs, derive_request, engine_version_of


def _json(value: Any) -> Jsonb:
    return Jsonb(sanitize(value))


def _message(exc: BaseException) -> str:
    text = str(exc).splitlines()[0][:500] if str(exc) else exc.__class__.__name__
    url = os.environ.get("TERRAWINDOW_DATABASE_URL", "")
    if url and url in text:
        text = text.replace(url, "[redacted]")
    return text


def upsert_datasets(conn: Connection, rows: list[dict] | None = None) -> int:
    records = dataset_records() if rows is None else rows
    for row in records:
        lonlat = row.get("center")
        conn.execute(
            """
            INSERT INTO terrawindow.datasets (
                id, name, body, kind, product, citation, license, source_urls, file_path, bytes, sha256,
                limitations, validation, native_bounds, center, provenance
            )
            VALUES (
                %(id)s, %(name)s, %(body)s, %(kind)s, %(product)s, %(citation)s, %(license)s,
                %(source_urls)s, %(file_path)s, %(bytes)s, %(sha256)s, %(limitations)s, %(validation)s,
                %(native_bounds)s,
                CASE WHEN %(lon)s::float8 IS NULL THEN NULL
                     ELSE ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography END,
                %(provenance)s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                body = EXCLUDED.body,
                kind = EXCLUDED.kind,
                product = EXCLUDED.product,
                citation = EXCLUDED.citation,
                license = EXCLUDED.license,
                source_urls = EXCLUDED.source_urls,
                file_path = EXCLUDED.file_path,
                bytes = EXCLUDED.bytes,
                sha256 = EXCLUDED.sha256,
                limitations = EXCLUDED.limitations,
                validation = EXCLUDED.validation,
                native_bounds = EXCLUDED.native_bounds,
                center = EXCLUDED.center,
                provenance = EXCLUDED.provenance,
                recorded_at = now()
            """,
            {
                "id": row["id"],
                "name": row.get("name"),
                "body": row.get("body"),
                "kind": row.get("kind"),
                "product": row.get("product"),
                "citation": row.get("citation"),
                "license": row.get("license"),
                "source_urls": _json(row.get("source_urls") or []),
                "file_path": row.get("file_path"),
                "bytes": row.get("bytes"),
                "sha256": row.get("sha256"),
                "limitations": _json(row.get("limitations") or []),
                "validation": _json(row.get("validation")) if row.get("validation") is not None else None,
                "native_bounds": _json(row.get("native_bounds")) if row.get("native_bounds") is not None else None,
                "lon": None if lonlat is None else lonlat[0],
                "lat": None if lonlat is None else lonlat[1],
                "provenance": _json(row.get("provenance") or {}),
            },
        )
    conn.commit()
    return len(records)


def _config_id(conn: Connection, kind: str, request: dict, req_hash: str) -> str:
    row = conn.execute(
        """
        INSERT INTO terrawindow.analysis_configs (kind, request, request_hash)
        VALUES (%s, %s, %s)
        ON CONFLICT (request_hash) DO UPDATE SET kind = terrawindow.analysis_configs.kind
        RETURNING id::text
        """,
        (kind, _json(request_document(kind, request)), req_hash),
    ).fetchone()
    return row[0]


def _find_completed(conn: Connection, req_hash: str, engine_version: str, fingerprint: list[list[str]]) -> tuple[str, str] | None:
    row = conn.execute(
        """
        SELECT r.id::text, r.result_hash
        FROM terrawindow.runs r
        JOIN terrawindow.analysis_configs c ON c.id = r.config_id
        WHERE c.request_hash = %s
          AND r.engine_version = %s
          AND r.status = 'completed'
          AND (
            SELECT coalesce(jsonb_agg(jsonb_build_array(d.role, d.dataset_id, d.sha256) ORDER BY d.role, d.dataset_id), '[]'::jsonb)
            FROM terrawindow.run_datasets d
            WHERE d.run_id = r.id
          ) = %s::jsonb
        LIMIT 1
        """,
        (req_hash, engine_version, _json(fingerprint)),
    ).fetchone()
    return None if row is None else (row[0], row[1])


def _fail_unfinished(conn: Connection, req_hash: str, engine_version: str) -> None:
    conn.execute(
        """
        UPDATE terrawindow.runs r
        SET status = 'failed',
            failure_message = 'recording did not finish',
            completed_at = now()
        FROM terrawindow.analysis_configs c
        WHERE r.config_id = c.id
          AND c.request_hash = %s
          AND r.engine_version = %s
          AND r.status = 'pending'
        """,
        (req_hash, engine_version),
    )


def _snapshots(conn: Connection, refs: list[tuple[str, str]], claimed: dict[tuple[str, str], str | None]) -> list[dict]:
    if not refs:
        raise ReportError("missing_dataset", "A run needs at least one input dataset.")
    roles = [role for role, _ in refs]
    if len(roles) != len(set(roles)):
        raise ReportError("duplicate_role", "Each run can record one dataset per role.")
    ids = [dataset_id for _, dataset_id in refs]
    found = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT id, sha256 FROM terrawindow.datasets WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
    }
    missing = [dataset_id for dataset_id in ids if dataset_id not in found]
    if missing:
        raise ReportError("dataset_not_registered", "Register datasets before recording a run: " + ", ".join(missing))
    links = []
    for role, dataset_id in refs:
        recorded = found[dataset_id]
        if not recorded:
            raise ReportError("missing_checksum", f"Dataset '{dataset_id}' has no checksum in the registry.")
        given = claimed.get((role, dataset_id))
        if given and given != recorded:
            raise ReportError(
                "checksum_mismatch",
                f"The checksum supplied for '{dataset_id}' does not match the dataset registry.",
            )
        links.append({"role": role, "dataset_id": dataset_id, "sha256": recorded})
    return links


def _insert_run(conn: Connection, config_id: str, engine_version: str, status: str, failure: str | None) -> str:
    row = conn.execute(
        """
        INSERT INTO terrawindow.runs (config_id, engine_version, status, failure_message, completed_at)
        VALUES (%s, %s, %s, %s, CASE WHEN %s = 'failed' THEN now() ELSE NULL END)
        RETURNING id::text
        """,
        (config_id, engine_version, status, failure, status),
    ).fetchone()
    return row[0]


def _insert_links(conn: Connection, run_id: str, links: list[dict]) -> None:
    for link in links:
        conn.execute(
            """
            INSERT INTO terrawindow.run_datasets (run_id, dataset_id, role, sha256)
            VALUES (%s, %s, %s, %s)
            """,
            (run_id, link["dataset_id"], link["role"], link["sha256"]),
        )


def _insert_candidates(conn: Connection, run_id: str, result: dict) -> None:
    for feature in candidate_features(result):
        center = feature["center"]
        conn.execute(
            """
            INSERT INTO terrawindow.candidates (run_id, patch_id, status, geom, center, metrics, criteria)
            VALUES (
                %s, %s, %s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                CASE WHEN %s::float8 IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography END,
                %s, %s
            )
            """,
            (
                run_id,
                feature["patch_id"],
                feature["status"],
                json.dumps(sanitize(feature["geometry"]), separators=(",", ":")),
                None if center is None else center[0],
                None if center is None else center[0],
                None if center is None else center[1],
                _json(feature["metrics"]),
                _json(feature["criteria"]),
            ),
        )


def _complete(conn: Connection, run_id: str, result: dict, res_hash: str) -> None:
    conn.execute(
        """
        UPDATE terrawindow.runs
        SET status = 'completed', result = %s, result_hash = %s, failure_message = NULL, completed_at = now()
        WHERE id = %s
        """,
        (_json(result), res_hash, run_id),
    )


def _fail(conn: Connection, run_id: str, message: str) -> None:
    conn.execute(
        """
        UPDATE terrawindow.runs
        SET status = 'failed', failure_message = %s, completed_at = now()
        WHERE id = %s AND status <> 'completed'
        """,
        (message, run_id),
    )


def record_run(
    conn: Connection,
    *,
    kind: Kind,
    result: dict,
    request: dict | None = None,
    engine_version: str | None = None,
    datasets: list[dict] | None = None,
) -> dict:
    """Record one analysis execution. A completed run with the same inputs is reused."""
    result = sanitize(result)
    version = engine_version or engine_version_of(result)
    if not version:
        raise ReportError("missing_engine_version", "The result has no engine version.")
    body = sanitize(request) if request is not None else derive_request(kind, result)
    req_hash = request_hash(kind, body)
    res_hash = result_hash(result)
    if datasets:
        refs = [(item["role"], item["dataset_id"]) for item in datasets]
        claimed = {(item["role"], item["dataset_id"]): item.get("sha256") for item in datasets}
    else:
        refs = dataset_refs(kind, result)
        claimed = {}

    conn.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (req_hash,))
    run_id: str | None = None
    try:
        config_id = _config_id(conn, kind, body, req_hash)
        try:
            links = _snapshots(conn, refs, claimed)
        except ReportError as exc:
            run_id = _insert_run(conn, config_id, version, "failed", exc.message)
            conn.commit()
            exc.run_id = run_id
            raise
        fingerprint = input_fingerprint(links)
        existing = _find_completed(conn, req_hash, version, fingerprint)
        if existing:
            conn.commit()
            return {
                "run_id": existing[0],
                "status": "completed",
                "reused": True,
                "request_hash": req_hash,
                "result_hash": existing[1],
                "result_matches_stored": existing[1] == res_hash,
            }
        _fail_unfinished(conn, req_hash, version)
        run_id = _insert_run(conn, config_id, version, "pending", None)
        conn.commit()
        try:
            _insert_links(conn, run_id, links)
            if kind == "screen":
                _insert_candidates(conn, run_id, result)
            _complete(conn, run_id, result, res_hash)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            _fail(conn, run_id, _message(exc))
            conn.commit()
            failed = ReportError("record_failed", _message(exc), 422)
            failed.run_id = run_id
            raise failed from exc
        return {
            "run_id": run_id,
            "status": "completed",
            "reused": False,
            "request_hash": req_hash,
            "result_hash": res_hash,
        }
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (req_hash,))
        conn.commit()


def get_run(conn: Connection, run_id: str) -> dict:
    row = conn.execute(
        """
        SELECT r.id::text, r.status, r.engine_version, r.failure_message, r.result, r.result_hash,
               r.started_at, r.completed_at, c.kind, c.request, c.request_hash
        FROM terrawindow.runs r
        JOIN terrawindow.analysis_configs c ON c.id = r.config_id
        WHERE r.id = %s
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        raise ReportError("run_not_found", "No run has that id.", 404)
    links = conn.execute(
        """
        SELECT d.role, d.dataset_id, d.sha256, s.name, s.file_path, s.citation, s.sha256
        FROM terrawindow.run_datasets d
        JOIN terrawindow.datasets s ON s.id = d.dataset_id
        WHERE d.run_id = %s
        ORDER BY d.role
        """,
        (run_id,),
    ).fetchall()
    return {
        "run_id": row[0],
        "status": row[1],
        "engine_version": row[2],
        "failure_message": row[3],
        "result": row[4],
        "result_hash": row[5],
        "started_at": row[6],
        "completed_at": row[7],
        "kind": row[8],
        "request": row[9],
        "request_hash": row[10],
        "datasets": [
            {
                "role": item[0],
                "dataset_id": item[1],
                "sha256": item[2],
                "name": item[3],
                "file_path": item[4],
                "citation": item[5],
                "registry_sha256": item[6],
            }
            for item in links
        ],
    }


def insert_report(conn: Connection, *, run_id: str, title: str, template_version: str, generated_at, markdown: str, pdf: bytes, pdf_sha256: str) -> str:
    row = conn.execute(
        """
        INSERT INTO terrawindow.reports (run_id, title, template_version, generated_at, markdown, pdf, pdf_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (run_id, title, template_version, generated_at, markdown, pdf, pdf_sha256),
    ).fetchone()
    conn.commit()
    return row[0]


def get_report(conn: Connection, report_id: str) -> dict:
    row = conn.execute(
        """
        SELECT id::text, run_id::text, title, template_version, generated_at, markdown, pdf, pdf_sha256
        FROM terrawindow.reports
        WHERE id = %s
        """,
        (report_id,),
    ).fetchone()
    if row is None:
        raise ReportError("report_not_found", "No report has that id.", 404)
    pdf = row[6]
    return {
        "report_id": row[0],
        "run_id": row[1],
        "title": row[2],
        "template_version": row[3],
        "generated_at": row[4],
        "markdown": row[5],
        "pdf": bytes(pdf) if pdf is not None else b"",
        "pdf_sha256": row[7],
    }


def reports_for_run(conn: Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id::text, pdf, pdf_sha256, template_version, generated_at
        FROM terrawindow.reports
        WHERE run_id = %s
        ORDER BY generated_at
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "report_id": row[0],
            "pdf": bytes(row[1]) if row[1] is not None else b"",
            "pdf_sha256": row[2],
            "template_version": row[3],
            "generated_at": row[4],
        }
        for row in rows
    ]
