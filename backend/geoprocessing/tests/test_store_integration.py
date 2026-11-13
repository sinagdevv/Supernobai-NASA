"""Layer 3 reading datasets that Layer 2 registered in the store manifest."""

import json

import pytest
from fastapi.testclient import TestClient

from terrawindow_geo import build_profile, extract_dem, screen_region
from terrawindow_geo.errors import GeoError
from terrawindow_geo.models import DatasetRef, PatchRequest, ScreenRequest


@pytest.fixture
def store(tmp_path, lunar_tif, plane_tif):
    """A manifest like the one terrawindow-data writes, pointing at the synthetic fixtures."""
    manifest = {
        "version": 1,
        "datasets": {
            "lola-test-site": {
                "path": "lunar.tif", "name": "Test lunar site", "body": "moon", "kind": "elevation", "vertical_scale": 1.0,
                "citation": "Test et al. (2021)", "limitations": ["Interpolated pixels are smoother than the real surface."],
                "nominal_resolution_m": 5.0, "ready": True, "validation": {"summary": {"pixel_size_m": 5.0}}, "products": {"surface": {}},
            },
            "km-site": {"path": "plane.tif", "name": "Heights in km", "body": "earth", "kind": "elevation", "vertical_scale": 1000.0},
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_stored_id_needs_no_path_body_or_bbox(store):
    p = build_profile(PatchRequest(dataset=DatasetRef(id="lola-test-site"), scales_m=[30]))
    assert p.patch.body == "moon" and p.patch.bbox.crs == "native"
    assert p.patch.width_m == 3000 and p.patch.center_lat < -89.9  # the whole 3 km raster
    assert p.provenance.dataset_id == "lola-test-site" and p.provenance.dataset_name == "Test lunar site"
    assert p.provenance.citation == "Test et al. (2021)"
    assert "Interpolated pixels are smoother than the real surface." in p.limitations
    assert p.scales[0].slope.stats.median == pytest.approx(5.711, abs=0.05)


def test_vertical_scale_from_the_manifest_is_applied(store):
    dem = extract_dem(DatasetRef(id="km-site"))
    assert dem.z.min() > 999_000  # 1000 stored, read as km


def test_screening_a_stored_dataset(store):
    fc = screen_region(ScreenRequest(dataset=DatasetRef(id="lola-test-site"), patch_size_m=600, scale_m=30))
    assert fc["summary"]["cells"] == 25 and all(f["properties"]["center_lat"] < -89.9 for f in fc["features"])


def test_unknown_and_global_ids(store):
    with pytest.raises(GeoError) as err:
        build_profile(PatchRequest(dataset=DatasetRef(id="not-fetched")))
    assert err.value.code == "dataset_not_found" and "lola-test-site" in err.value.details["known_ids"]
    with pytest.raises(GeoError) as err:
        build_profile(PatchRequest(dataset=DatasetRef(id="copernicus-glo30")))
    assert err.value.code == "invalid_request" and "bbox is required" in err.value.message


def test_api_lists_and_serves_stored_datasets(store):
    from terrawindow_geo.api.app import create_app

    client = TestClient(create_app())
    stored = client.get("/v1/datasets").json()["stored_datasets"]
    assert {d["id"] for d in stored} == {"lola-test-site", "km-site"}
    moon = next(d for d in stored if d["id"] == "lola-test-site")
    assert moon["body"] == "moon" and moon["ready"] and moon["summary"]["pixel_size_m"] == 5.0

    r = client.post("/v1/patches/profile", json={"dataset": {"id": "lola-test-site"}, "scales_m": [30, 60]})
    assert r.status_code == 200 and r.json()["patch"]["body"] == "moon"
    r = client.post("/v1/patches/overlay", json={"dataset": {"id": "lola-test-site"}, "layer": "hillshade", "sun_elevation_deg": 7})
    assert r.status_code == 200 and r.json()["width"] == 100
    body = {"reference": {"dataset": {"id": "lola-test-site"}}, "candidate": {"dataset": {"id": "lola-test-site"}}, "scales_m": [30]}
    r = client.post("/v1/patches/compare", json=body)
    assert r.status_code == 200 and r.json()["counts"]["outside_tolerance"] == 0
