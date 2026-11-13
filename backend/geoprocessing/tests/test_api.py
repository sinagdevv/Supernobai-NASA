import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import ORIGIN_E, ORIGIN_N
from terrawindow_geo.io import sources
from terrawindow_geo.models import BBox, DatasetRef


@pytest.fixture
def client(settings_env):
    from terrawindow_geo.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def native(x0, y0, x1, y1, res):
    return {"west": ORIGIN_E + x0 * res, "south": ORIGIN_N - y1 * res, "east": ORIGIN_E + x1 * res, "north": ORIGIN_N - y0 * res, "crs": "native"}


PLANE = {"dataset": {"uri": "plane.tif"}, "bbox": native(0, 0, 200, 200, 10)}


def test_health_and_datasets(client):
    assert client.get("/health").json()["status"] == "ok"
    body = client.get("/v1/datasets").json()
    assert {d["id"] for d in body["datasets"]} == {"copernicus-glo30", "esa-worldcover"}
    assert body["default_scales_m"] == [30, 60, 120, 240]


def test_profile_endpoint(client, plane_tif):
    r = client.post("/v1/patches/profile", json={**PLANE, "scales_m": [10, 20]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["scale_m"] for s in body["scales"]] == [10, 20]
    assert body["scales"][0]["slope"]["stats"]["mean"] == pytest.approx(5.711, abs=0.001)
    assert body["provenance"]["native_pixel_size_m"] == 10 and body["limitations"]


def test_compare_endpoint_computes_or_accepts_profiles(client, plane_tif, flat_tif):
    r = client.post(
        "/v1/patches/compare",
        json={"reference": PLANE, "candidate": {**PLANE, "dataset": {"uri": "flat.tif"}}, "scales_m": [20]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["common_scales_m"] == [20]
    slope = next(c for c in body["criteria"] if c["metric"] == "slope_mean")
    assert slope["status"] == "outside_tolerance" and slope["difference"] == pytest.approx(-5.711, abs=0.001)
    assert "score" not in body

    again = client.post(
        "/v1/patches/compare",
        json={"reference_profile": body["reference_profile"], "candidate_profile": body["reference_profile"]},
    )
    assert again.status_code == 200 and again.json()["counts"]["outside_tolerance"] == 0

    both = client.post("/v1/patches/compare", json={"reference": PLANE, "reference_profile": body["reference_profile"], "candidate": PLANE})
    assert both.status_code == 422 and both.json()["error"]["code"] == "invalid_request"


def test_screen_endpoint_returns_geojson(client, rough_tif):
    r = client.post(
        "/v1/discovery/screen",
        json={
            "dataset": {"uri": "rough.tif"},
            "bbox": native(0, 0, 400, 200, 30),
            "patch_size_m": 1500,
            "criteria": {"slope_mean_deg": {"max": 5}},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "FeatureCollection" and body["summary"]["candidate"] == 16
    feature = body["features"][0]
    assert feature["geometry"]["type"] == "Polygon" and feature["properties"]["metrics"]["coverage_fraction"] == 1


@pytest.mark.parametrize("layer", ["slope", "hillshade", "elevation"])
def test_overlay_endpoint_returns_a_png(client, plane_tif, layer):
    r = client.post("/v1/patches/overlay", json={**PLANE, "layer": layer, "scale_m": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    image = Image.open(io.BytesIO(base64.b64decode(body["image_base64"])))
    assert image.size == (100, 100) == (body["width"], body["height"]) and image.mode == "RGBA"
    assert len(body["coordinates"]) == 4 and all(-112 < lon < -111 and 35 < lat < 36 for lon, lat in body["coordinates"])
    assert body["coordinates"][0][1] > body["coordinates"][3][1]  # top-left is north of bottom-left
    assert body["legend"] and body["scale_m"] == 20


def test_errors_share_one_shape(client, plane_tif):
    r = client.post("/v1/patches/profile", json={**PLANE, "scales_m": [1]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "scale_not_supported" and "native_pixel_size_m" in r.json()["error"]["details"]

    r = client.post("/v1/patches/profile", json={"dataset": {"uri": "nope.tif"}, "bbox": PLANE["bbox"]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "source_unavailable"

    r = client.post("/v1/patches/profile", json={"dataset": {"id": "no-such-dataset"}, "bbox": {"west": 0, "south": 0, "east": 1, "north": 1}})
    assert r.status_code == 404 and r.json()["error"]["code"] == "dataset_not_found"

    r = client.post("/v1/patches/profile", json={"dataset": {"uri": "plane.tif"}, "bbox": {"west": 2, "south": 0, "east": 1, "north": 1}})
    assert r.status_code == 422 and r.json()["error"]["details"]["issues"]


@pytest.mark.parametrize("uri", ["../outside.tif", "C:/Windows/win.ini", "/etc/passwd", "s3://bucket/x.tif", "/vsicurl/http://x/y.tif", "file:///etc/passwd"])
def test_api_refuses_sources_outside_the_data_folder(client, uri):
    r = client.post("/v1/patches/profile", json={"dataset": {"uri": uri}, "bbox": PLANE["bbox"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "source_not_allowed"


def test_results_are_cached_on_disk(client, plane_tif, tmp_path, monkeypatch):
    from terrawindow_geo.config import get_settings

    monkeypatch.setenv("TWGEO_CACHE", "1")
    get_settings.cache_clear()
    first = client.post("/v1/patches/profile", json={**PLANE, "scales_m": [10]}).json()
    assert len(list((tmp_path / "cache" / "profile").glob("*.json"))) == 1
    second = client.post("/v1/patches/profile", json={**PLANE, "scales_m": [10]}).json()
    assert second == first  # same generated_at: served from the cache


def test_openapi_lists_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {"/health", "/v1/datasets", "/v1/patches/profile", "/v1/patches/compare", "/v1/discovery/screen", "/v1/patches/overlay"}


def test_tile_urls():
    bbox = BBox(west=-111.7, south=35.4, east=-110.9, north=36.2)
    assert sources.glo30_urls(bbox) == [
        f"https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
        for n in (
            "Copernicus_DSM_COG_10_N35_00_W112_00_DEM",
            "Copernicus_DSM_COG_10_N35_00_W111_00_DEM",
            "Copernicus_DSM_COG_10_N36_00_W112_00_DEM",
            "Copernicus_DSM_COG_10_N36_00_W111_00_DEM",
        )
    ]
    assert sources.worldcover_urls(bbox) == [
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N33W114_Map.tif",
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N33W111_Map.tif",
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N36W114_Map.tif",
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N36W111_Map.tif",
    ]
    south = sources.glo30_urls(BBox(west=17.2, south=-24.8, east=17.4, north=-24.6))
    assert south == ["https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S25_00_E017_00_DEM/Copernicus_DSM_COG_10_S25_00_E017_00_DEM.tif"]
    assert len(sources.resolve_uris(DatasetRef(id="copernicus-glo30"), BBox(west=-111.66, south=35.55, east=-111.60, north=35.61))) == 1
