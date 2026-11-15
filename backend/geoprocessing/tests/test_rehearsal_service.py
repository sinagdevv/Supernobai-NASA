"""The Layer 4 service wrapper: request bounds, failure reporting, and one real run on synthetic terrain.

The real run needs the `rehearsal` package, spiceypy, numba and the SPICE kernels. Without them the test is
skipped and reported as skipped; it is never counted as passed.
"""

import importlib.util
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import ORIGIN_E, ORIGIN_N
from terrawindow_geo import rehearsal_service


@pytest.fixture
def client(settings_env):
    from terrawindow_geo.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def plane_store(tmp_path, plane_tif):
    """The synthetic plane registered the way Layer 2 registers a Copernicus GLO-30 region."""
    manifest = {"version": 1, "datasets": {"plane-copernicus-glo30": {"path": "plane.tif", "name": "Plane", "body": "earth", "kind": "elevation", "vertical_scale": 1.0, "nominal_resolution_m": 10.0}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def small_bbox():
    return {"west": ORIGIN_E + 800, "south": ORIGIN_N - 1200, "east": ORIGIN_E + 1200, "north": ORIGIN_N - 800, "crs": "native"}


def body(**over):
    base = {
        "candidate": {"dataset": {"id": "plane-copernicus-glo30"}, "bbox": small_bbox(), "scales_m": [10]},
        "start_utc": "2026-11-16T00:00:00Z", "end_utc": "2026-11-17T00:00:00Z", "step_minutes": 120,
    }
    base.update(over)
    return base


def test_requests_are_bounded(client, plane_store):
    cases = {
        "naive start": body(start_utc="2026-11-16T00:00:00"),
        "end before start": body(end_utc="2026-11-15T00:00:00Z"),
        "span over 30 days": body(end_utc="2026-12-30T00:00:00Z", step_minutes=1440),
        "more than 96 samples": body(step_minutes=5),
        "zero step": body(step_minutes=0),
        "unknown field": body(kernel_path="C:/secret.bsp"),
        "huge search range": body(max_distance_m=1e9),
    }
    for name, payload in cases.items():
        r = client.post("/v1/rehearsal/evaluate", json=payload)
        assert r.status_code == 422, name
        assert r.json()["error"]["code"] == "invalid_request", name


def test_oversized_patch_is_refused_before_any_work(client, plane_store, monkeypatch):
    monkeypatch.setattr(rehearsal_service, "MAX_EARTH_MOON_PIXELS", 100)
    r = client.post("/v1/rehearsal/evaluate", json=body())
    assert r.status_code == 422 and r.json()["error"]["code"] == "patch_too_large"


def test_missing_kernels_are_reported_as_unavailable_not_guessed(client, plane_store, tmp_path, monkeypatch):
    empty = tmp_path / "no-kernels"
    empty.mkdir()
    monkeypatch.setenv("TWGEO_KERNEL_DIR", str(empty))
    r = client.post("/v1/rehearsal/evaluate", json=body())
    assert r.status_code == 503 and r.json()["error"]["code"] == "layer4_unavailable"
    status = client.get("/v1/rehearsal/status").json()
    assert status["bodies"] == {"earth": False, "moon": False, "mars": False}
    assert status["observational_validation"] == "NOT_VALIDATED"


def test_mars_needs_a_geographic_bbox(client, plane_store):
    payload = body(candidate={"dataset": {"uri": "plane.tif", "body": "mars"}, "bbox": small_bbox()})
    r = client.post("/v1/rehearsal/evaluate", json=payload)
    assert r.status_code in (422, 503)  # refused: nothing is computed from a native-metre box or a missing source


READY = (
    importlib.util.find_spec("rehearsal") is not None
    and importlib.util.find_spec("spiceypy") is not None
    and importlib.util.find_spec("numba") is not None
    and rehearsal_service.status()["bodies"]["earth"]
)


@pytest.mark.skipif(not READY, reason="Layer 4 package, spiceypy, numba or SPICE kernels not installed")
def test_real_run_on_synthetic_terrain_follows_the_sun(client, plane_store):
    r = client.post("/v1/rehearsal/evaluate", json=body(max_distance_m=300))
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["body"] == "earth" and result["evidence"]["observational_validation_status"] == "NOT_VALIDATED"
    assert result["evidence"]["real_terrain_execution_status"] == "PASS"
    assert result["analysis_grid"]["shape"] == [40, 40]
    observations = result["observations"]
    assert len(observations) == 12
    assert result["scientific_limitations"]
    for obs in observations:
        when = datetime.fromisoformat(obs["time_utc"]).astimezone(timezone.utc)
        if obs["solar_elevation_deg"] < -1:
            # Night: nothing may be reported as lit.
            assert obs["target_classification"] != "ILLUMINATED", when
    noon = max(observations, key=lambda o: o["solar_elevation_deg"])
    assert 30 < noon["solar_elevation_deg"] < 40  # Flagstaff, mid-November
    assert noon["target_classification"] in {"ILLUMINATED", "INSUFFICIENT_COVERAGE"}


def _assess(client, layer4):
    criteria = [
        {"id": "cover", "name": "cover", "category": "terrain", "description": "c", "source_layer": "layer3", "source_metric": "terrain.coverage.valid_fraction", "operator": "gte", "target_value": 0.9, "unit": "fraction", "required": True, "missing_data_behavior": "INDETERMINATE", "rationale": "test"},
        {"id": "sun", "name": "sun", "category": "terrain", "description": "s", "source_layer": "layer4", "source_metric": "rehearsal.total_illumination_duration_seconds", "operator": "gte", "target_value": 3600, "unit": "seconds", "required": True, "missing_data_behavior": "INDETERMINATE", "rationale": "test"},
    ]
    payload = {"candidate_id": "t", "candidate": body()["candidate"], "layer4_result": layer4,
               "mission_profile": {"id": "p", "name": "p", "description": "p", "required_categories": ["terrain"], "criteria": criteria}}
    r = client.post("/v1/suitability/assess", json=payload)
    assert r.status_code == 200, r.text
    out = r.json()
    return out, {c["criterion_id"]: c for c in out["criterion_results"]}


@pytest.mark.skipif(not READY, reason="Layer 4 package, spiceypy, numba or SPICE kernels not installed")
def test_layer4_evidence_pairs_with_layer3_and_stays_an_unverified_claim(client, plane_store):
    layer4 = client.post("/v1/rehearsal/evaluate", json=body(max_distance_m=300)).json()
    out, rows = _assess(client, layer4)
    # Same grid, same source: the pairing is recognised, but the value is still only a claim.
    assert out["spatial_association"]["status"] == "MATCHED_METADATA_UNVERIFIED", out["spatial_association"]["checks"]
    assert rows["sun"]["status"] == "UNVERIFIED" and rows["sun"]["measured_value"] is None
    assert rows["sun"]["claimed_value"] == layer4["total_illumination_duration_seconds"]
    assert out["overall_status"] in {"INDETERMINATE", "PARTIALLY_ASSESSED"}  # never SUITABLE on a Layer 4 claim


@pytest.mark.skipif(not READY, reason="Layer 4 package, spiceypy, numba or SPICE kernels not installed")
def test_layer4_evidence_from_another_grid_is_not_assessed_even_if_it_claims_validation(client, plane_store):
    layer4 = client.post("/v1/rehearsal/evaluate", json=body(max_distance_m=300)).json()
    layer4["provenance"] = {**layer4["provenance"], "affine_transform": "1.0,0.0,0.0,0.0,-1.0,0.0", "dataset_id": "somewhere-else"}
    layer4["evidence"]["observational_validation_status"] = "PASS"  # a caller's claim; nothing here can check it
    out, rows = _assess(client, layer4)
    assert out["spatial_association"]["status"] == "MISMATCHED"
    assert rows["sun"]["status"] == "NOT_ASSESSED" and rows["sun"]["measured_value"] is None
    assert out["overall_status"] != "SUITABLE"


def test_unregistered_earth_raster_is_not_assumed_to_be_glo30(client, plane_store):
    payload = body(candidate={"dataset": {"uri": "plane.tif"}, "bbox": small_bbox(), "scales_m": [10]})
    r = client.post("/v1/rehearsal/evaluate", json=payload)
    assert r.status_code == 422 and "registered" in r.json()["error"]["message"]
