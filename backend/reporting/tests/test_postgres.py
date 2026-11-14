import os

import pytest

pytest.importorskip("psycopg")

from terrawindow_report.db import apply_schema, connect
from terrawindow_report.registry import record_run, upsert_datasets
from terrawindow_report.report import render_report
from terrawindow_report.registry import get_run, insert_report
from terrawindow_report.shapes import ReportError
from terrawindow_report.verify import verify_run

pytestmark = pytest.mark.postgres


def _wipe(conn) -> None:
    rows = conn.execute(
        """
        SELECT DISTINCT run_id::text FROM terrawindow.run_datasets
        WHERE dataset_id = ANY(%s)
        UNION
        SELECT r.id::text
        FROM terrawindow.runs r
        JOIN terrawindow.analysis_configs c ON c.id = r.config_id
        WHERE c.request::text LIKE %s OR c.request::text LIKE %s
        """,
        (["layer6-moon", "layer6-earth"], "%layer6-%", "%missing-dataset%"),
    ).fetchall()
    run_ids = [row[0] for row in rows]
    if run_ids:
        conn.execute("DELETE FROM terrawindow.reports WHERE run_id = ANY(%s)", (run_ids,))
        conn.execute("DELETE FROM terrawindow.candidates WHERE run_id = ANY(%s)", (run_ids,))
        conn.execute("DELETE FROM terrawindow.run_datasets WHERE run_id = ANY(%s)", (run_ids,))
        conn.execute("DELETE FROM terrawindow.runs WHERE id = ANY(%s)", (run_ids,))
    conn.execute(
        """
        DELETE FROM terrawindow.analysis_configs c
        WHERE NOT EXISTS (SELECT 1 FROM terrawindow.runs r WHERE r.config_id = c.id)
          AND (c.request::text LIKE %s OR c.request::text LIKE %s)
        """,
        ("%layer6-%", "%missing-dataset%"),
    )
    conn.execute("DELETE FROM terrawindow.datasets WHERE id = ANY(%s)", (["layer6-moon", "layer6-earth"],))
    conn.commit()


@pytest.fixture()
def conn():
    url = os.environ.get("TERRAWINDOW_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TERRAWINDOW_DATABASE_URL is not set")
    try:
        connection = connect()
    except Exception as exc:
        pytest.skip(f"database unreachable: {exc.__class__.__name__}")
    apply_schema(connection)
    yield connection
    try:
        _wipe(connection)
    finally:
        connection.close()


def test_same_inputs_reuse_the_completed_run(conn):
    upsert_datasets(
        conn,
        [
            {
                "id": "layer6-moon",
                "name": "Moon fixture",
                "body": "moon",
                "kind": "elevation",
                "product": "surface",
                "citation": "fixture",
                "license": "fixture",
                "source_urls": [],
                "file_path": None,
                "bytes": 1,
                "sha256": "a" * 64,
                "limitations": [],
                "validation": None,
                "native_bounds": None,
                "center": None,
                "provenance": {"sha256": "a" * 64},
            },
            {
                "id": "layer6-earth",
                "name": "Earth fixture",
                "body": "earth",
                "kind": "elevation",
                "product": "surface",
                "citation": "fixture",
                "license": "fixture",
                "source_urls": [],
                "file_path": None,
                "bytes": 1,
                "sha256": "b" * 64,
                "limitations": [],
                "validation": None,
                "native_bounds": None,
                "center": None,
                "provenance": {"sha256": "b" * 64},
            },
        ],
    )
    result = {
        "reference_profile": {"provenance": {"dataset_id": "layer6-moon", "engine_version": "0.1.0"}},
        "candidate_profile": {"provenance": {"dataset_id": "layer6-earth", "engine_version": "0.1.0"}},
        "criteria": [{"metric": "slope_mean", "scale_m": 30, "status": "outside_tolerance"}],
        "counts": {"outside_tolerance": 1},
    }
    request = {"reference_dataset_id": "layer6-moon", "candidate_dataset_id": "layer6-earth"}
    first = record_run(conn, kind="compare", result=result, request=request, engine_version="0.1.0")
    second = record_run(conn, kind="compare", result=result, request=request, engine_version="0.1.0")
    assert first["status"] == "completed"
    assert first["reused"] is False
    assert second["reused"] is True
    assert second["run_id"] == first["run_id"]
    stored = get_run(conn, first["run_id"])
    assert [(item["role"], item["sha256"]) for item in stored["datasets"]] == [
        ("candidate", "b" * 64),
        ("reference", "a" * 64),
    ]
    rendered = render_report(stored)
    report_id = insert_report(
        conn,
        run_id=stored["run_id"],
        title=rendered["title"],
        template_version=rendered["template_version"],
        generated_at=rendered["generated_at"],
        markdown=rendered["markdown"],
        pdf=rendered["pdf"],
        pdf_sha256=rendered["pdf_sha256"],
    )
    outcome = verify_run(conn, first["run_id"])
    assert outcome["ok"] is True
    conn.execute("UPDATE terrawindow.reports SET pdf_sha256 = %s WHERE id = %s", ("0" * 64, report_id))
    conn.commit()
    assert verify_run(conn, first["run_id"])["ok"] is False


def test_unregistered_dataset_is_a_failed_run(conn):
    with pytest.raises(ReportError) as caught:
        record_run(
            conn,
            kind="profile",
            result={"provenance": {"dataset_id": "missing-dataset", "engine_version": "0.1.0"}, "patch": {}, "scales": []},
            request={"dataset_id": "missing-dataset"},
            engine_version="0.1.0",
        )
    assert caught.value.code == "dataset_not_registered"
    assert caught.value.run_id
    row = conn.execute("SELECT status FROM terrawindow.runs WHERE id = %s", (caught.value.run_id,)).fetchone()
    assert row[0] == "failed"
