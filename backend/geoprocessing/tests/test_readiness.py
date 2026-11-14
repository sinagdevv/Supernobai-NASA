"""Readiness is judged from the file, not from the manifest: the manifest is versioned, the rasters are not."""

import json

import pytest
from fastapi.testclient import TestClient

from terrawindow_geo import readiness
from terrawindow_geo.api.app import create_app
from terrawindow_geo.cli import main


def _store(tmp_path, datasets):
    (tmp_path / "manifest.json").write_text(json.dumps({"version": 1, "datasets": datasets}))


@pytest.fixture
def mixed(tmp_path, plane_tif):
    """One good raster, plus every way a manifest entry can fail to be usable."""
    (tmp_path / "corrupt.tif").write_bytes(b"II*\x00 this is not a raster " * 4)
    (tmp_path / "empty.tif").write_bytes(b"")
    full = {"name": "x", "body": "earth", "kind": "elevation", "ready": True, "citation": "c", "validation": {"summary": {}}}
    _store(tmp_path, {
        "good": {**full, "path": "plane.tif"},
        "missing": {**full, "path": "earth/regions/gone.tif", "region": {"name": "gone", "bbox_lonlat": [1, 2, 3, 4], "parent_dataset": "copernicus-glo30"}},
        "missing-lunar": {**full, "body": "moon", "path": "lunar/site/gone.tif"},
        "corrupt": {**full, "path": "corrupt.tif"},
        "empty": {**full, "path": "empty.tif"},
        "failed-validation": {**full, "path": "plane.tif", "ready": False},
        "minimal": {"path": "plane.tif", "body": "earth"},  # no citation, no validation, no ready flag
        "escapes": {**full, "path": "../outside.tif"},
        "no-path": {**full},
    })
    return tmp_path


def _status(dataset_id):
    from terrawindow_geo.io.sources import stored_datasets

    return readiness.check(dataset_id, stored_datasets()[dataset_id])


def test_an_available_dataset_is_ready(mixed):
    v = _status("good")
    assert v == {"status": "available", "detail": None, "setup": None}


def test_a_missing_raster_needs_setup_and_says_how(mixed):
    v = _status("missing")
    assert v["status"] == "missing" and "gone.tif" in v["detail"]
    assert v["setup"] == "terrawindow-data region copernicus-glo30 gone 1 2 3 4"
    assert _status("missing-lunar")["setup"] == "terrawindow-data fetch missing-lunar"


@pytest.mark.parametrize("dataset_id", ["corrupt", "empty"])
def test_a_corrupt_or_empty_raster_is_unreadable(mixed, dataset_id):
    v = _status(dataset_id)
    assert v["status"] == "unreadable" and "could not be read" in v["detail"]


def test_failed_layer2_validation_is_reported_even_though_the_file_opens(mixed):
    assert _status("failed-validation")["status"] == "not_validated"


def test_missing_optional_metadata_does_not_invalidate_usable_data(mixed):
    assert _status("minimal")["status"] == "available"


def test_a_manifest_path_cannot_leave_the_store(mixed):
    assert _status("escapes")["status"] == "unreadable"
    assert _status("no-path")["status"] == "unreadable"


def test_a_file_that_is_replaced_is_rechecked(mixed):
    assert _status("corrupt")["status"] == "unreadable"
    (mixed / "corrupt.tif").write_bytes((mixed / "plane.tif").read_bytes() + b" ")  # new size -> new cache key
    assert _status("corrupt")["status"] == "available"


def test_api_lists_true_availability(mixed):
    stored = {d["id"]: d for d in TestClient(create_app()).get("/v1/datasets").json()["stored_datasets"]}
    assert stored["good"]["ready"] is True and stored["good"]["availability"]["status"] == "available"
    for bad in ("missing", "corrupt", "failed-validation"):
        assert stored[bad]["ready"] is False and stored[bad]["availability"]["status"] != "available"
    assert stored["failed-validation"]["validated"] is False and stored["missing"]["validated"] is True  # the manifest verdict, kept apart
    assert stored["missing"]["availability"]["setup"].startswith("terrawindow-data region")


@pytest.mark.parametrize(
    "dataset_id, code, http",
    [("missing", "source_unavailable", 404), ("corrupt", "source_unreadable", 422), ("failed-validation", "dataset_not_validated", 409)],
)
def test_requests_fail_with_a_structured_error_before_any_processing(mixed, dataset_id, code, http):
    r = TestClient(create_app()).post("/v1/patches/profile", json={"dataset": {"id": dataset_id}, "scales_m": [30]})
    err = r.json()["error"]
    assert r.status_code == http and err["code"] == code
    assert err["details"]["dataset_id"] == dataset_id and err["details"]["setup"]


def test_the_usable_dataset_still_works_end_to_end(mixed):
    r = TestClient(create_app()).post("/v1/patches/profile", json={"dataset": {"id": "good"}, "scales_m": [30]})
    assert r.status_code == 200


def test_check_command_exit_codes(mixed, capsys):
    assert main(["check"]) == 1
    out = capsys.readouterr().out
    assert "missing" in out and "fix: terrawindow-data" in out and "available" in out
    _store(mixed, {"good": json.loads((mixed / "manifest.json").read_text())["datasets"]["good"]})
    assert main(["check"]) == 0
    _store(mixed, {})
    assert main(["check"]) == 1  # an empty store is a setup problem, not a pass


def test_the_service_reads_the_reference_manifest_overlaid_by_the_local_one(tmp_path, plane_tif):
    """Layer 2 writes a normal setup to local/, so a dataset set up on this machine must be visible without touching the tracked manifest."""
    from terrawindow_geo.io.sources import stored_datasets

    base = {"name": "x", "body": "earth", "kind": "elevation", "ready": True}
    _store(tmp_path, {"tracked": {**base, "path": "gone.tif"}, "both": {**base, "path": "gone.tif"}})
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "manifest.json").write_text(json.dumps({"version": 1, "datasets": {"here": {**base, "path": "plane.tif"}, "both": {**base, "path": "plane.tif"}}}))
    merged = stored_datasets()
    assert set(merged) == {"tracked", "both", "here"}
    assert merged["both"]["path"] == "plane.tif"  # local replaces the reference entry of the same id
    stored = {d["id"]: d for d in TestClient(create_app()).get("/v1/datasets").json()["stored_datasets"]}
    assert stored["here"]["ready"] and stored["both"]["ready"] and not stored["tracked"]["ready"]
    assert TestClient(create_app()).post("/v1/patches/profile", json={"dataset": {"id": "here"}, "scales_m": [30]}).status_code == 200
