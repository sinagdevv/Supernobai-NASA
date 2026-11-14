"""Layer 2 tests on synthetic rasters. No network: downloads are served from local files."""

import json
import shutil

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from terrawindow_data import catalog, fetch, prepare, store, validate
from terrawindow_data.cli import main as cli

MOON = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs")


def write(path, z, transform, crs, nodata=None, dtype="float32"):
    with rasterio.open(
        path, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1, dtype=dtype, crs=crs, transform=transform, nodata=nodata
    ) as dst:
        dst.write(z.astype(dtype), 1)
    return str(path)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("TERRAWINDOW_DATA_DIR", str(tmp_path / "store"))
    return tmp_path / "store"


@pytest.fixture
def lunar_file(tmp_path):
    z = np.random.default_rng(0).normal(500, 50, (200, 200))
    return write(tmp_path / "moon.tif", z, Affine(5, 0, -19000, 0, -5, -4000), MOON, nodata=np.nan)


@pytest.fixture
def fake_download(monkeypatch, lunar_file):
    """Replace the HTTP download with a local copy and record the URLs asked for."""
    calls = []

    def copy(url, dest, *, progress=None):
        calls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(lunar_file, dest)

    monkeypatch.setattr(fetch, "download", copy)
    return calls


# ---------------------------------------------------------------- catalog


def test_catalog_lists_the_proposal_datasets():
    ids = set(catalog.CATALOG)
    assert {"copernicus-glo30", "esa-worldcover", "lola-5mpp-site01", "lola-5mpp-haworth"} <= ids
    assert sum(e.body == "moon" for e in catalog.CATALOG.values()) == 10
    for entry in catalog.CATALOG.values():
        assert entry.citation and entry.license and entry.source_page and entry.limitations
    site = catalog.get_entry("lola-5mpp-site01")
    urls = {p.key: p.url for p in site.products}
    assert urls["surface"] == "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif"
    assert set(urls) == {"surface", "uncertainty", "slope", "slope_uncertainty", "counts"}
    with pytest.raises(KeyError, match="Unknown dataset id"):
        catalog.get_entry("nope")


def test_tile_urls():
    urls = catalog.tile_urls(catalog.GLO30, -111.7, 35.4, -110.9, 35.6)
    assert [u.rsplit("/", 1)[1] for u in urls] == [
        "Copernicus_DSM_COG_10_N35_00_W112_00_DEM.tif",
        "Copernicus_DSM_COG_10_N35_00_W111_00_DEM.tif",
    ]
    assert catalog.tile_urls(catalog.WORLDCOVER, 17.2, -24.8, 17.4, -24.6)[0].endswith("ESA_WorldCover_10m_2021_v200_S27E015_Map.tif")
    with pytest.raises(ValueError):
        catalog.tile_urls(catalog.get_entry("lola-5mpp-site01"), 0, 0, 1, 1)


# ---------------------------------------------------------------- validation


def statuses(report):
    return {c["check"]: c["status"] for c in report["checks"]}


def test_valid_lunar_raster_is_ready(lunar_file):
    report = validate.validate_raster(lunar_file, body="moon", nominal_resolution_m=5)
    assert report["ready"] and set(statuses(report).values()) == {"pass"}
    s = report["summary"]
    assert s["pixel_size_m"] == 5 and s["valid_fraction"] == 1 and s["extent_km"] == [1.0, 1.0]
    assert s["center_lonlat"][1] < -89


def test_wrong_body_fails(lunar_file):
    report = validate.validate_raster(lunar_file, body="earth")
    assert not report["ready"] and statuses(report)["body_matches"] == "fail"


def test_unreadable_file_fails(tmp_path):
    junk = tmp_path / "junk.tif"
    junk.write_text("not a raster")
    report = validate.validate_raster(str(junk), body="earth")
    assert not report["ready"] and report["checks"][0] ["status"] == "fail"


def test_warnings_do_not_block_but_are_recorded(tmp_path):
    z = np.full((100, 100), 2.5)  # no nodata value, 20 m pixels where 5 m is catalogued
    path = write(tmp_path / "coarse.tif", z, Affine(20, 0, 0, 0, -20, 0), MOON)
    report = validate.validate_raster(path, body="moon", nominal_resolution_m=5)
    st = statuses(report)
    assert report["ready"]
    assert st["nodata_declared"] == "warn" and st["resolution_as_catalogued"] == "warn"

    far = write(tmp_path / "far.tif", np.full((50, 50), 250000.0), Affine(5, 0, 0, 0, -5, 0), MOON, nodata=np.nan)
    assert statuses(validate.validate_raster(far, body="moon"))["values_plausible_in_metres"] == "warn"

    empty = write(tmp_path / "empty.tif", np.full((50, 50), np.nan), Affine(5, 0, 0, 0, -5, 0), MOON, nodata=np.nan)
    report = validate.validate_raster(empty, body="moon")
    assert not report["ready"] and statuses(report)["has_data"] == "fail"


def test_geographic_earth_raster(tmp_path):
    step = 1 / 3600
    path = write(tmp_path / "earth.tif", np.full((120, 120), 1800.0), Affine(step, 0, -111.6, 0, -step, 35.6), CRS.from_epsg(4326), nodata=-32767)
    report = validate.validate_raster(path, body="earth", nominal_resolution_m=30)
    assert report["ready"] and report["summary"]["pixel_size_m"] == pytest.approx(30.9, abs=0.2)


# ---------------------------------------------------------------- fetch, provenance, manifest


def test_fetch_validates_records_provenance_and_registers(fake_download, isolated_store):
    record = fetch.fetch_dataset("lola-5mpp-site01", ["uncertainty"])
    # the primary product always comes along
    assert [u.rsplit("_", 1)[1] for u in fake_download] == ["surf.tif", "toterr.tif"]
    assert record["path"] == "lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif"
    assert record["body"] == "moon" and record["ready"] and set(record["products"]) == {"surface", "uncertainty"}

    surface = isolated_store / record["path"]
    prov = store.read_provenance(record["path"])  # a normal setup writes local provenance, not the version-controlled sidecar
    assert prov["source_urls"] == ["https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif"]
    assert prov["sha256"] == fetch.sha256_of(surface) and prov["bytes"] == surface.stat().st_size
    assert "Barker" in prov["citation"] and prov["retrieved_at"] and prov["validation"]["ready"] and prov["limitations"]

    manifest = store.load_manifest()
    assert manifest["version"] == 1 and manifest["datasets"]["lola-5mpp-site01"]["path"] == record["path"]


def test_fetch_reuses_files_and_keeps_earlier_products(fake_download):
    fetch.fetch_dataset("lola-5mpp-site01")
    fetch.fetch_dataset("lola-5mpp-site01", ["slope"])
    assert len(fake_download) == 2  # surface was not downloaded again
    assert set(store.load_manifest()["datasets"]["lola-5mpp-site01"]["products"]) == {"surface", "slope"}
    fetch.fetch_dataset("lola-5mpp-site01", force=True)
    assert len(fake_download) == 3


def test_fetch_rejects_bad_requests(fake_download):
    with pytest.raises(ValueError, match="tiled"):
        fetch.fetch_dataset("copernicus-glo30")
    with pytest.raises(ValueError, match="no product"):
        fetch.fetch_dataset("lola-5mpp-site01", ["thermal"])
    assert fake_download == []


def test_interrupted_download_leaves_no_file(tmp_path, monkeypatch):
    class Cut:
        headers = {"Content-Length": "1000"}

        def __init__(self):
            self.sent = False

        def read(self, n):
            if self.sent:
                return b""
            self.sent = True
            return b"x" * 10

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: Cut())
    dest = tmp_path / "out" / "file.tif"
    with pytest.raises(IOError, match="Incomplete"):
        fetch.download("https://example.invalid/file.tif", dest)
    assert not dest.exists()


# ---------------------------------------------------------------- regions


@pytest.fixture
def earth_tiles(tmp_path):
    """Two adjacent 0.1-degree tiles with different constant heights."""
    step = 0.001
    west = write(tmp_path / "w.tif", np.full((100, 100), 100.0), Affine(step, 0, 10.0, 0, -step, 50.1), CRS.from_epsg(4326), nodata=-9999)
    east = write(tmp_path / "e.tif", np.full((100, 100), 200.0), Affine(step, 0, 10.1, 0, -step, 50.1), CRS.from_epsg(4326), nodata=-9999)
    return west, east


def test_region_is_cut_on_the_source_grid_and_registered(earth_tiles, isolated_store):
    west, east = earth_tiles
    record = prepare.prepare_region("copernicus-glo30", "test-site", 10.05, 50.02, 10.15, 50.08, sources=[west, east, "missing.tif"])
    assert record["id"] == "test-site-copernicus-glo30" and record["path"] == "earth/regions/test-site_copernicus-glo30.tif"
    with rasterio.open(isolated_store / record["path"]) as ds:
        z = ds.read(1)
        assert ds.res == pytest.approx((0.001, 0.001)) and z.shape == (60, 100)
        assert ds.bounds.left == pytest.approx(10.05) and ds.bounds.top == pytest.approx(50.08)
        assert (z[:, :50] == 100).all() and (z[:, 50:] == 200).all()  # values copied, not resampled
    stored = store.load_manifest()["datasets"]["test-site-copernicus-glo30"]
    assert stored["region"]["bbox_lonlat"] == [10.05, 50.02, 10.15, 50.08] and stored["body"] == "earth"
    prov = store.read_provenance(record["path"])
    assert prov["source_urls"] == [west, east] and prov["missing_tiles"] == ["missing.tif"] and "no resampling" in prov["processing"]


def test_single_tile_region(earth_tiles, isolated_store):
    west, _east = earth_tiles
    record = prepare.prepare_region("copernicus-glo30", "one-tile", 10.02, 50.03, 10.06, 50.07, sources=[west])
    with rasterio.open(isolated_store / record["path"]) as ds:
        assert ds.read(1).shape == (40, 40) and (ds.read(1) == 100).all()
        assert ds.bounds.left == pytest.approx(10.02) and ds.bounds.bottom == pytest.approx(50.03)


def test_region_input_guards(earth_tiles):
    with pytest.raises(ValueError, match="lowercase"):
        prepare.prepare_region("copernicus-glo30", "Bad Name", 10, 50, 10.1, 50.1, sources=list(earth_tiles))
    with pytest.raises(ValueError, match="larger than"):
        prepare.prepare_region("copernicus-glo30", "huge", 0, 0, 10, 10)
    with pytest.raises(ValueError, match="not tiled"):
        prepare.prepare_region("lola-5mpp-site01", "x-y", 0, 0, 1, 1)
    with pytest.raises(FileNotFoundError):
        prepare.prepare_region("copernicus-glo30", "ocean", 10, 50, 10.1, 50.1, sources=["nothing.tif"])


# ---------------------------------------------------------------- cli


def test_cli(fake_download, lunar_file, capsys):
    assert cli(["fetch", "lola-5mpp-site01"]) == 0
    assert "analysis-ready: True" in capsys.readouterr().out
    assert cli(["list"]) == 0
    out = capsys.readouterr().out
    assert "in store" in out and "not fetched" in out and "tiled, read on demand" in out
    assert cli(["show", "lola-5mpp-site01"]) == 0 and '"body": "moon"' in capsys.readouterr().out
    assert cli(["show", "lola-5mpp-site04"]) == 1
    assert cli(["validate", lunar_file, "--body", "moon"]) == 0
    assert cli(["validate", lunar_file, "--body", "earth"]) == 1
    capsys.readouterr()
    assert cli(["fetch", "nope"]) == 1 and "Unknown dataset id" in capsys.readouterr().err
