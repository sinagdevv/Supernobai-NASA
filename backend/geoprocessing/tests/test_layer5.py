"""Layer 5 behaviour that must hold whatever the data: missing evidence is never a positive result,
Layer 4 values are never promoted to a pass or fail, and mission criteria stay with their own body."""

import pytest
from fastapi.testclient import TestClient

from conftest import ORIGIN_E, ORIGIN_N
from terrawindow_geo.suitability import _affine6, _same_crs


@pytest.fixture
def client(settings_env):
    from terrawindow_geo.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def native(x0, y0, x1, y1, res):
    return {"west": ORIGIN_E + x0 * res, "south": ORIGIN_N - y1 * res, "east": ORIGIN_E + x1 * res, "north": ORIGIN_N - y0 * res, "crs": "native"}


def criterion(cid, metric, op, value, unit, *, required=True, layer="layer3", **selectors):
    return {
        "id": cid, "name": cid, "category": "terrain" if layer == "layer3" else "power", "description": cid,
        "source_layer": layer, "source_metric": metric, "operator": op, "target_value": value, "unit": unit,
        "required": required, "missing_data_behavior": "INDETERMINATE", "rationale": "test assumption", **selectors,
    }


def request(uri, criteria, **extra):
    return {
        "candidate_id": "t1", "candidate": {"dataset": {"uri": uri}, "bbox": native(0, 0, 200, 200, 10), "scales_m": [10]},
        "mission_profile": {"id": "p", "name": "p", "description": "p", "required_categories": ["terrain"], "criteria": criteria},
        **extra,
    }


SLOPE = ("terrain.slope.p90_deg", "degrees")
COVER = ("terrain.coverage.valid_fraction", "fraction")


def statuses(body):
    return {r["criterion_id"]: r["status"] for r in body["criterion_results"]}


def test_supported_layer3_evidence_gives_a_definite_pass_and_fail(client, plane_tif):
    easy = [criterion("slope", SLOPE[0], "lte", 10, SLOPE[1], scale_m=10), criterion("cover", COVER[0], "gte", 0.9, COVER[1])]
    ok = client.post("/v1/suitability/assess", json=request("plane.tif", easy)).json()
    assert ok["overall_status"] == "SUITABLE" and statuses(ok) == {"slope": "PASS", "cover": "PASS"}
    hard = [criterion("slope", SLOPE[0], "lte", 3, SLOPE[1], scale_m=10), criterion("cover", COVER[0], "gte", 0.9, COVER[1])]
    bad = client.post("/v1/suitability/assess", json=request("plane.tif", hard)).json()
    assert bad["overall_status"] == "NOT_SUITABLE" and statuses(bad)["slope"] == "FAIL"


def test_missing_layer4_evidence_never_becomes_a_pass(client, plane_tif):
    criteria = [criterion("cover", COVER[0], "gte", 0.9, COVER[1]), criterion("sun", "rehearsal.total_illumination_duration_seconds", "gte", 3600, "seconds", layer="layer4")]
    body = client.post("/v1/suitability/assess", json=request("plane.tif", criteria)).json()
    assert statuses(body)["sun"] in {"INDETERMINATE", "NOT_ASSESSED"}
    assert body["overall_status"] == "INDETERMINATE"
    assert body["suitability_gaps"]


def test_insufficient_terrain_coverage_is_not_suitable(client, holes_tif):
    # 40 % of the patch is void: coverage is below the 0.9 the request insists on.
    criteria = [criterion("slope", SLOPE[0], "lte", 30, SLOPE[1], scale_m=10)]
    body = client.post("/v1/suitability/assess", json=request("holes.tif", criteria)).json()
    assert body["overall_status"] != "SUITABLE"
    assert statuses(body)["slope"] in {"INDETERMINATE", "NOT_ASSESSED"}


def test_layer4_result_for_another_body_is_refused(client, plane_tif):
    claim = {"body": "moon", "start_utc": "2026-11-16T00:00:00Z", "end_utc": "2026-11-17T00:00:00Z", "step_seconds": 7200,
             "boundary_uncertainty_seconds": 7200, "target_pixel": [1, 1], "observations": [], "continuous_illumination_intervals": [],
             "candidate_windows": [], "total_illumination_duration_seconds": 0, "total_qualifying_illumination_duration_seconds": 0,
             "criteria": {}, "provenance": {}, "scientific_limitations": [], "kernel_identities": [],
             "evidence": {"implementation_status": "PASS", "synthetic_verification_status": "NOT_RUN", "real_terrain_execution_status": "NOT_AVAILABLE", "observational_validation_status": "NOT_VALIDATED"}}
    criteria = [criterion("cover", COVER[0], "gte", 0.9, COVER[1])]
    r = client.post("/v1/suitability/assess", json=request("plane.tif", criteria, layer4_result=claim))
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_unknown_metric_and_wrong_unit_are_rejected(client, plane_tif):
    bad_metric = [criterion("x", "terrain.invented", "lte", 1, "degrees")]
    assert client.post("/v1/suitability/assess", json=request("plane.tif", bad_metric)).status_code == 422
    wrong_unit = [criterion("x", SLOPE[0], "lte", 10, "radians", scale_m=10)]
    assert client.post("/v1/suitability/assess", json=request("plane.tif", wrong_unit)).status_code == 422


def test_affine_forms_describe_the_same_transform():
    nine = (40.0, 0.0, -19000.0, 0.0, -40.0, -4000.0, 0.0, 0.0, 1.0)
    assert _affine6(nine) == nine[:6] and _affine6(nine[:6]) == nine[:6]
    assert _affine6((1, 0, 0, 0, 1, 0, 9, 9, 9)) is None  # a projective tail is not an affine transform
    assert _affine6(None) is None


def test_crs_equality_is_semantic_not_textual():
    from pyproj import CRS

    wkt = CRS.from_epsg(32612).to_wkt()
    assert _same_crs(wkt, wkt) is True
    assert _same_crs(CRS.from_epsg(32612).to_wkt(version="WKT1_GDAL"), wkt) is True
    assert _same_crs(CRS.from_epsg(32613).to_wkt(), wkt) is False
    assert _same_crs(None, wkt) is None and _same_crs("not wkt", wkt) is None
