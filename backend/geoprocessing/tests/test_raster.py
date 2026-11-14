import math

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from conftest import UTM12N, box, utm_box, utm_grid, write_tif
from terrawindow_geo.errors import GeoError
from terrawindow_geo.io.raster import _block_mean, extract_patch, native_pixel_size
from terrawindow_geo.terrain.slope import slope_aspect

TEN_PERCENT = math.degrees(math.atan(0.1))
GEO_BOX = dict(west=-111.62, south=35.58, east=-111.58, north=35.62, crs="geographic")


def test_projected_source_is_copied_exactly(plane_tif):
    patch = extract_patch([plane_tif], utm_box(20, 30, 120, 90))
    with rasterio.open(plane_tif) as ds:
        expected = ds.read(1)[30:90, 20:120]
    assert patch.shape == (60, 100)
    assert patch.pixel_size_m == 10.0 and patch.native_pixel_size_m == 10.0
    assert np.array_equal(patch.z, expected.astype(np.float64))
    assert patch.crs == UTM12N and "exact copy" in patch.resampling


def test_geographic_source_becomes_metric_utm(geographic_tif):
    patch = extract_patch([geographic_tif], box(**GEO_BOX))
    assert patch.crs.to_epsg() == 32612
    # 1 arc-second of latitude is ~30.8 m; longitude is shorter at 35.6 N, so latitude sets the size.
    assert patch.native_pixel_size_m == pytest.approx(30.9, abs=0.2)
    assert patch.pixel_size_m == pytest.approx(patch.native_pixel_size_m)
    assert np.isfinite(patch.z).mean() > 0.99
    slope, _ = slope_aspect(patch.z, patch.pixel_size_m)
    assert np.nanmedian(slope) == pytest.approx(TEN_PERCENT, abs=0.1)
    lon, lat = patch.center_lonlat()
    assert lon == pytest.approx(-111.60, abs=0.002) and lat == pytest.approx(35.60, abs=0.002)


def test_finer_than_native_is_refused(geographic_tif, plane_tif):
    with pytest.raises(GeoError) as err:
        extract_patch([geographic_tif], box(**GEO_BOX), resolution_m=5)
    assert err.value.code == "scale_not_supported"
    with pytest.raises(GeoError):
        extract_patch([plane_tif], utm_box(0, 0, 100, 100), resolution_m=5)


def test_nominal_30m_request_is_accepted_for_30_9m_data(geographic_tif):
    patch = extract_patch([geographic_tif], box(**GEO_BOX), resolution_m=30)
    assert patch.pixel_size_m == 30.0


def test_aggregation_averages_and_keeps_slope(plane_tif):
    base = extract_patch([plane_tif], utm_box(0, 0, 200, 200))
    coarse = base.at_scale(40.0)
    assert coarse.shape == (50, 50) and coarse.pixel_size_m == 40.0
    assert coarse.z[0, 0] == pytest.approx(base.z[:4, :4].mean())
    slope, _ = slope_aspect(coarse.z, coarse.pixel_size_m)
    assert np.nanmedian(slope) == pytest.approx(TEN_PERCENT, abs=1e-4)
    with pytest.raises(GeoError):
        base.at_scale(5.0)


def test_non_integer_aggregation(plane_tif):
    coarse = extract_patch([plane_tif], utm_box(0, 0, 200, 200)).at_scale(25.0)
    assert coarse.shape == (80, 80)
    slope, _ = slope_aspect(coarse.z, 25.0)
    assert np.nanmedian(slope) == pytest.approx(TEN_PERCENT, abs=0.05)


def test_block_mean_does_not_fill_voids():
    z = np.arange(16, dtype=float).reshape(4, 4)
    z[:2, :2] = np.nan  # a fully empty block
    z[2, 2] = np.nan  # one missing cell in another block
    out = _block_mean(z, 2)
    assert np.isnan(out[0, 0])
    assert out[1, 1] == pytest.approx((11 + 14 + 15) / 3)


def test_nodata_becomes_nan(holes_tif):
    patch = extract_patch([holes_tif], utm_box(0, 0, 200, 200))
    assert np.isnan(patch.z[:, :80]).all() and np.isfinite(patch.z[:, 80:]).all()


def test_lunar_polar_grid_is_kept_and_aggregated(lunar_tif):
    patch = extract_patch([lunar_tif], box(-1000, -1000, 1000, 1000), body="moon", resolution_m=30)
    assert patch.native_pixel_size_m == 5.0 and patch.pixel_size_m == 30.0
    assert patch.resampling == "average"
    slope, _ = slope_aspect(patch.z, 30.0)
    assert np.nanmedian(slope) == pytest.approx(TEN_PERCENT, abs=0.05)
    _lon, lat = patch.center_lonlat()
    assert lat < -89.9  # footprint is reported in lunar lon/lat


def test_tiles_are_mosaicked_and_missing_ones_recorded(tmp_path):
    transform, east, _ = utm_grid(100, 100, 10.0)
    west = write_tif(tmp_path / "west.tif", np.full(east.shape, 1.0), transform, UTM12N)
    east_tif = write_tif(tmp_path / "east.tif", np.full(east.shape, 2.0), transform @ Affine.translation(100, 0), UTM12N)
    missing = str(tmp_path / "absent.tif")
    patch = extract_patch([west, missing, east_tif], utm_box(50, 0, 150, 100))
    assert patch.shape == (100, 100)
    assert (patch.z[:, :50] == 1).all() and (patch.z[:, 50:] == 2).all()
    assert len(patch.missing_sources) == 1 and "absent.tif" in patch.missing_sources[0]
    with pytest.raises(GeoError) as err:
        extract_patch([missing], utm_box(0, 0, 10, 10))
    assert err.value.code == "source_unavailable"


def test_patch_size_limit(plane_tif, monkeypatch):
    from terrawindow_geo.config import get_settings

    monkeypatch.setenv("TWGEO_MAX_PATCH_PIXELS", "1000")
    get_settings.cache_clear()
    with pytest.raises(GeoError) as err:
        extract_patch([plane_tif], utm_box(0, 0, 200, 200))
    assert err.value.code == "patch_too_large"


def test_native_pixel_size_from_metadata(plane_tif, geographic_tif):
    assert native_pixel_size([plane_tif], utm_box(0, 0, 10, 10)) == 10.0
    assert native_pixel_size([geographic_tif], box(**GEO_BOX)) == pytest.approx(30.9, abs=0.2)


# ---------------------------------------------------------------- planetary grids that are not true-scale in metres


def _mars_eqc():
    return CRS.from_proj4("+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs")


def _eqc_plane(tmp_path, lat0, slope=0.1, n=120, res=463.0935415503709):
    """Mars equirectangular grid (standard parallel 0, like the USGS MOLA mosaic) centred at lat0.
    Height rises `slope` metres per metre of TRUE ground distance eastward, so the right answer is atan(slope) at any latitude."""
    R = 3396190.0
    x0 = R * math.radians(77.5) - n * res / 2
    y0 = R * math.radians(lat0) + n * res / 2
    transform = Affine(res, 0, x0, 0, -res, y0)
    cc, rr = np.meshgrid(np.arange(n) + 0.5, np.arange(n) + 0.5)
    x, y = transform @ (cc, rr)
    lat = y / R  # radians
    # ground east distance from the western edge: R cos(lat) d(lon), with lon = x / R
    z = 1000 + slope * (x - x0) * np.cos(lat)
    return write_tif(tmp_path / f"eqc_{lat0}.tif", z, transform, _mars_eqc(), dtype="float64")


@pytest.mark.parametrize("lat0", [0.0, 18.4, 60.0])
def test_equirectangular_mars_slope_is_true_ground_slope_at_any_latitude(tmp_path, lat0):
    """Regression for the metre-unit trap: the 463 m pixel is only 463 m east-west on the equator."""
    from terrawindow_geo.models import BBox, DatasetRef, PatchRequest
    from terrawindow_geo.profile import build_profile

    tif = _eqc_plane(tmp_path, lat0)
    request = PatchRequest(dataset=DatasetRef(uri=tif, body="mars"), bbox=None, scales_m=[463.0935415503709 * 2])
    profile = build_profile(request)
    scale = profile.scales[0]
    assert scale.status == "assessed"
    assert scale.slope.stats.mean == pytest.approx(math.degrees(math.atan(0.1)), abs=0.25), (lat0, scale.slope.stats.mean)
    # the working grid is a local azimuthal one on the Mars sphere, not the source projection, once the source is not true-scale
    if lat0 > 0:
        assert "Azimuthal_Equidistant" in profile.provenance.working_crs


def test_native_pixel_size_reports_ground_spacing_not_projected_spacing(tmp_path):
    from terrawindow_geo.io.raster import native_pixel_size
    from terrawindow_geo.models import BBox

    tif = _eqc_plane(tmp_path, 60.0)
    native = native_pixel_size([tif], BBox(west=77.0, south=59.9, east=78.0, north=60.1))
    # east-west ground spacing is 463 * cos(60) = 232 m, north-south is 463 m; the coarser axis is reported
    assert native == pytest.approx(463.09, abs=1.0)


def test_true_scale_projections_are_still_used_unchanged(plane_tif):
    """The lunar polar stereographic tiles and UTM data keep their exact source grid (no resampling)."""
    from terrawindow_geo.io.raster import extract_patch
    from terrawindow_geo.models import BBox

    patch = extract_patch([plane_tif], BBox(west=440200, south=3940000 - 1800, east=441800, north=3940000 - 200, crs="native"))
    assert patch.resampling.startswith("exact copy")
