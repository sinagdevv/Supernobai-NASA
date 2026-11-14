"""Mars MOLA support in Layer 2: the PDS4 MEGDR catalogue entry, tile selection, lon/lat windowing of a projected source, ground-scale validation.

The sources here are synthetic rasters on the same grid as the PDS4 MEGDR tiles (equirectangular, lon_0 = 180, R = 3,396 km, 1/128 degree pixels, int16 metres),
shrunk so the tests need no network. Every pixel stores its own position, so a window's placement can be checked exactly.
"""

import math

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from terrawindow_data import catalog, prepare, store, validate
from terrawindow_data.cli import main as cli

# Fixtures shared with the main Layer 2 tests (pytest picks up imported fixtures).
from test_data_integration import isolated_store, write  # noqa: F401

R = 3396000.0
MARS = CRS.from_proj4(f"+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 +x_0=0 +y_0=0 +R={R} +units=m +no_defs")
PX = 2 * math.pi * R / (360 * 128)  # 463.0577 m, as in the PDS4 labels


def tile(tmp_path, name, west, north, rows=800, cols=800):
    """A synthetic tile whose upper-left corner is at `west` degrees east, `north` degrees north.

    Values are a function of the position on the PLANET (degrees from the corner of the first tile), so two abutting tiles form one continuous surface."""
    transform = Affine(PX, 0, R * math.radians(west - 180), 0, -PX, R * math.radians(north))
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    lon_px = np.round((west - 70.0) * 128).astype(int) + cc
    lat_px = np.round((25.0 - north) * 128).astype(int) + rr
    z = ((lon_px + 1000 * lat_px) % 30000).astype("int16")
    return write(tmp_path / f"{name}.tif", z, transform, MARS, dtype="int16")


@pytest.fixture
def mola_like(tmp_path):
    return tile(tmp_path, "mola_like", 70.0, 25.0)


def _names(urls):
    return sorted(u.rsplit("/", 1)[1].removesuffix(".xml") for u in urls)


def test_the_megdr_entry_is_documented_with_its_sources():
    e = catalog.get_entry("mola-megdr128")
    assert e.body == "mars" and e.access == "tiled" and e.kind == "elevation"
    assert e.nominal_resolution_m == pytest.approx(PX, abs=0.01)
    d = e.extra["details"]
    assert d["pds3_dataset_id"] == "MGS-M-MOLA-5-MEGDR-L3-V1.0" and d["pds4_bundle"] == "urn:nasa:pds:mgs_mola_topography_derived"
    assert "areoid" in e.vertical_datum and "planetocentric" in e.vertical_datum
    assert all(k in e.citation for k in ("Smith", "MGS-M-MOLA-5-MEGDR-L3-V1.0", "10.1029/2000JE001364", "mgs_mola_topography_derived"))
    assert any("463 m pixels cannot resolve rover-scale" in s for s in e.limitations)
    assert catalog.BODY_RADIUS_M["mars"] == 3396190.0


@pytest.mark.parametrize(
    "box, names",
    [
        ((76.4, 17.4, 78.6, 19.4), ["megt44n000hb"]),  # Jezero region
        ((137.0, -6.0, 139.0, -4.0), ["megt00n090hb"]),  # Gale region: 0 to -44, 90-180 E
        ((89.0, 43.0, 91.0, 45.0), ["megt44n000hb", "megt44n090hb", "megt88n000hb", "megt88n090hb"]),  # across a tile edge and a corner
        ((-100.0, -30.0, -99.0, -29.0), ["megt00n180hb"]),  # western longitudes are 260-261 E
    ],
)
def test_megdr_tiles_are_chosen_by_latitude_band_and_longitude(box, names):
    urls = catalog.megdr_tile_urls(*box)
    got = _names(urls)
    if box[0] < 0:  # -100 E is 260 E: the tile whose west edge is 180 covers 180-270
        assert got == ["megt00n180hb"]
    else:
        assert got == sorted(names)
    assert all(u.startswith(catalog.MEGDR_BASE) and u.endswith(".xml") for u in urls)


def test_the_polar_caps_are_refused():
    with pytest.raises(ValueError, match="polar caps"):
        catalog.megdr_tile_urls(0, 80, 10, 89)


def test_region_window_is_placed_by_longitude_and_latitude(mola_like, isolated_store):
    """The lon/lat box is converted into the tile's projected coordinates before windowing."""
    rec = prepare.prepare_region("mola-megdr128", "test-site", 71.0, 20.0, 72.0, 21.0, sources=[mola_like])
    with rasterio.open(isolated_store / rec["path"]) as out, rasterio.open(mola_like) as src:
        col0, row0 = round((71.0 - 70.0) * 128), round((25.0 - 21.0) * 128)
        assert np.array_equal(out.read(1), src.read(1)[row0 : row0 + out.height, col0 : col0 + out.width])  # exact copy, nothing resampled
        assert abs(out.width - 128) <= 1 and abs(out.height - 128) <= 1  # one degree is 128 pixels
        assert out.crs == src.crs
    assert rec["id"] == "test-site-mola-megdr128" and rec["body"] == "mars"
    assert rec["products"]["surface"]["unit"] == "metres" and rec["details"]["instrument"].startswith("Mars Orbiter Laser Altimeter")


def test_a_region_across_two_tiles_is_stitched_without_a_seam(tmp_path, isolated_store):
    west, east = tile(tmp_path, "w", 70.0, 25.0), tile(tmp_path, "e", 76.25, 25.0)  # 800 px = 6.25 degrees: the tiles abut at 76.25 E
    rec = prepare.prepare_region("mola-megdr128", "seam", 75.5, 20.0, 77.0, 21.0, sources=[west, east])
    with rasterio.open(isolated_store / rec["path"]) as out:
        z = out.read(1).astype("int64")
        # the surface is a plane in (column, row): column + 1000 * row. Across the seam its horizontal step must stay exactly +1
        steps = np.diff(z, axis=1) % 30000
        assert out.width >= 190 and (steps == 1).all(), "a seam or a shifted tile would show as a step other than +1"
        assert (np.diff(z, axis=0) % 30000 == 1000).all()


def test_region_is_validated_as_mars_and_flags_the_ground_scale(mola_like, isolated_store):
    rec = prepare.prepare_region("mola-megdr128", "test-site", 71.0, 20.0, 72.0, 21.0, sources=[mola_like])
    checks = {c["check"]: c for c in rec["validation"]["checks"]}
    assert rec["ready"] and checks["body_matches"]["status"] == "pass" and checks["resolution_as_catalogued"]["status"] == "pass"
    # at 20.5 N the east-west pixel is 463 * cos(20.5) on the ground: warn, with the numbers, and say what happens next
    assert checks["ground_scale"]["status"] == "warn" and "Layer 3 resamples" in checks["ground_scale"]["detail"]
    east_west, north_south = rec["validation"]["summary"]["ground_pixel_size_m"]
    assert east_west == pytest.approx(PX * math.cos(math.radians(20.5)), rel=0.01) and north_south == pytest.approx(PX, rel=0.01)


def test_a_utm_raster_still_passes_the_ground_scale_check(tmp_path):
    transform = Affine(30.0, 0, 440000, 0, -30.0, 3940000)
    path = write(tmp_path / "utm.tif", np.full((120, 120), 1500.0), transform, CRS.from_epsg(32612), nodata=-9999)
    report = validate.validate_raster(path, body="earth")
    assert next(c for c in report["checks"] if c["check"] == "ground_scale")["status"] == "pass"


def test_a_region_larger_than_the_limit_is_refused(mola_like):
    with pytest.raises(ValueError, match="larger than"):
        prepare.prepare_region("mola-megdr128", "too-big", 70.0, 10.0, 75.0, 20.0, sources=[mola_like])


def test_mars_region_setup_leaves_tracked_files_alone(mola_like, isolated_store):
    """The reference-versus-local separation holds for Mars too: a normal region setup writes only under local/."""
    prepare.prepare_region("mola-megdr128", "test-site", 71.0, 20.0, 72.0, 21.0, sources=[mola_like])
    assert not (isolated_store / "manifest.json").exists()
    assert "test-site-mola-megdr128" in store.load_manifest()["datasets"]
    assert "test-site-mola-megdr128" not in store.load_reference_manifest()["datasets"]


def test_cli_lists_the_mars_dataset(capsys):
    assert cli(["list"]) == 0
    assert "mola-megdr128" in capsys.readouterr().out
