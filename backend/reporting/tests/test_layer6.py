from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from terrawindow_report.canonical import canonical_json, input_fingerprint, request_hash, result_hash, sanitize, sha256_bytes
from terrawindow_report.files import dataset_records, read_provenance
from terrawindow_report.report import build_markdown, build_pdf, render_report
from terrawindow_report.shapes import ReportError, candidate_features, closed_ring, dataset_refs, derive_request, detect_kind

ROOT = Path(__file__).resolve().parents[2]
COMPARE = ROOT / "data" / "results" / "compare_lola-5mpp-site01_vs_sp-crater.json"
SCREEN = ROOT / "data" / "results" / "screen_sf-volcanic-field_vs_lola-5mpp-site01.geojson"


def _run(**overrides):
    base = {
        "run_id": "run-1",
        "status": "completed",
        "kind": "compare",
        "engine_version": "0.1.0",
        "request_hash": "a" * 64,
        "result_hash": "b" * 64,
        "request": {"kind": "compare", "request": {"derived_from_result": True}},
        "datasets": [
            {"role": "reference", "dataset_id": "lola-5mpp-site01", "sha256": "abc"},
            {"role": "candidate", "dataset_id": "sp-crater-copernicus-glo30", "sha256": "def"},
        ],
        "result": {
            "criteria": [
                {"metric": "slope_mean", "scale_m": 30, "reference": 12.29, "candidate": 4.51, "difference": -7.78, "status": "outside_tolerance"}
            ],
            "counts": {"outside_tolerance": 1},
            "notes": ["Counts are a tally of criteria."],
            "limitations": ["A 30 m grid cannot resolve rover-scale rocks."],
        },
    }
    base.update(overrides)
    return base


def test_canonical_json_ignores_key_order_and_nan():
    left = {"b": 1, "a": float("nan")}
    right = {"a": None, "b": 1.0}
    assert canonical_json(left) == canonical_json(right)
    assert result_hash(left) == result_hash(right)
    assert sanitize(30.0) == 30


def test_request_hash_covers_kind_and_body():
    body = {"dataset_id": "lola-5mpp-site01", "scales_m": [60, 30]}
    assert request_hash("profile", body) == request_hash("profile", {"scales_m": [60, 30], "dataset_id": "lola-5mpp-site01"})
    assert request_hash("profile", body) != request_hash("screen", body)


def test_input_fingerprint_sorts_roles():
    links = [
        {"role": "candidate", "dataset_id": "earth", "sha256": "e"},
        {"role": "reference", "dataset_id": "moon", "sha256": "m"},
    ]
    assert input_fingerprint(links) == [["candidate", "earth", "e"], ["reference", "moon", "m"]]


def test_store_reader_uses_layer2_checksums():
    rows = {row["id"]: row for row in dataset_records()}
    assert "lola-5mpp-site01" in rows
    provenance = read_provenance(rows["lola-5mpp-site01"]["file_path"])
    assert rows["lola-5mpp-site01"]["sha256"] == provenance["sha256"]
    assert len(rows["lola-5mpp-site01"]["sha256"]) == 64
    assert rows["sp-crater-copernicus-glo30"]["center"] is not None


def test_compare_file_names_both_inputs():
    import json

    result = json.loads(COMPARE.read_text(encoding="utf-8"))
    assert detect_kind(result) == "compare"
    assert dataset_refs("compare", result) == [
        ("reference", "lola-5mpp-site01"),
        ("candidate", "sp-crater-copernicus-glo30"),
    ]
    derived = derive_request("compare", result)
    assert derived["derived_from_result"] is True
    assert derived["common_scales_m"]


def test_screen_polygon_is_closed():
    feature = {
        "type": "Feature",
        "properties": {"id": "r0c0", "status": "candidate", "center_lon": 1.5, "center_lat": 2.5, "metrics": {}, "criteria": []},
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
    }
    rows = candidate_features({"type": "FeatureCollection", "features": [feature]})
    ring = rows[0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert closed_ring([[0, 0], [1, 0]])[-1] == [0, 0]


def test_markdown_and_pdf_come_from_the_stored_run():
    when = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    rendered = render_report(_run(), when)
    text = rendered["markdown"]
    assert "Template version: 1" in text
    assert "lola-5mpp-site01" in text
    assert "abc" in text
    assert "outside_tolerance" in text
    assert "2026-11-14T12:00:00Z" in text
    assert rendered["pdf"].startswith(b"%PDF")
    assert rendered["pdf_sha256"] == sha256_bytes(rendered["pdf"])
    assert "terrain shadow" in text.lower() or "does not calculate terrain shadows" in text


def test_dossier_refuses_an_unfinished_run():
    with pytest.raises(ReportError) as caught:
        build_markdown(_run(status="pending"), datetime.now(timezone.utc))
    assert caught.value.code == "run_not_completed"


def test_pdf_round_trip_is_stable_for_the_same_instant():
    when = datetime(2026, 11, 14, tzinfo=timezone.utc)
    first = build_pdf(build_markdown(_run(), when))
    second = build_pdf(build_markdown(_run(), when))
    assert first == second


def test_health_does_not_require_a_database(monkeypatch):
    monkeypatch.delenv("TERRAWINDOW_DATABASE_URL", raising=False)
    from terrawindow_report.api import create_app

    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "terrawindow-report"


def test_screen_file_is_a_screen():
    import json

    result = json.loads(SCREEN.read_text(encoding="utf-8"))
    assert detect_kind(result) == "screen"
    assert dataset_refs("screen", result)[0][0] == "input"
    assert result["summary"]["candidate"] == 5
