"""Synthetic rasters with known answers. No network, no real data."""

from __future__ import annotations

import numpy as np
import pyproj
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

UTM12N = CRS.from_epsg(32612)
MOON_SOUTH_POLAR = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs")
ORIGIN_E, ORIGIN_N = 440000.0, 3940000.0  # near Flagstaff, AZ


def write_tif(path, z, transform, crs, nodata=None, dtype="float32"):
    with rasterio.open(
        path, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1, dtype=dtype,
        crs=crs, transform=transform, nodata=nodata,
    ) as dst:
        dst.write(z.astype(dtype), 1)
    return str(path)


def utm_grid(rows, cols, res):
    """Pixel-centre easting/northing arrays for a north-up UTM grid."""
    transform = Affine(res, 0, ORIGIN_E, 0, -res, ORIGIN_N)
    cc, rr = np.meshgrid(np.arange(cols) + 0.5, np.arange(rows) + 0.5)
    east, north = transform @ (cc, rr)
    return transform, east, north


@pytest.fixture(autouse=True)
def settings_env(tmp_path, monkeypatch):
    from terrawindow_geo.config import get_settings

    monkeypatch.setenv("TWGEO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TWGEO_CACHE", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def plane_tif(tmp_path):
    """10 m UTM grid rising 0.1 m per metre eastward: slope atan(0.1) = 5.7106 deg, facing west."""
    transform, east, _north = utm_grid(200, 200, 10.0)
    return write_tif(tmp_path / "plane.tif", 1000 + 0.1 * (east - ORIGIN_E), transform, UTM12N)


@pytest.fixture
def flat_tif(tmp_path):
    transform, east, _ = utm_grid(200, 200, 10.0)
    return write_tif(tmp_path / "flat.tif", np.full(east.shape, 250.0), transform, UTM12N)


@pytest.fixture
def holes_tif(tmp_path):
    """Plane with the western 40 % missing."""
    transform, east, _ = utm_grid(200, 200, 10.0)
    z = 1000 + 0.1 * (east - ORIGIN_E)
    z[:, :80] = -9999
    return write_tif(tmp_path / "holes.tif", z, transform, UTM12N, nodata=-9999)


@pytest.fixture
def rough_tif(tmp_path):
    """30 m grid, west half flat, east half strongly undulating."""
    transform, east, north = utm_grid(200, 400, 30.0)
    x = east - (ORIGIN_E + 200 * 30.0)
    z = np.where(x > 0, 100 + 60 * np.sin(x / 150.0) * np.cos((north - ORIGIN_N) / 150.0), 100.0)
    return write_tif(tmp_path / "rough.tif", z, transform, UTM12N)


@pytest.fixture
def geographic_tif(tmp_path):
    """1 arc-second lon/lat grid whose elevation rises 0.1 m per metre of UTM northing."""
    step = 1 / 3600
    rows = cols = 360
    west, north = -111.65, 35.65
    transform = Affine(step, 0, west, 0, -step, north)
    cc, rr = np.meshgrid(np.arange(cols) + 0.5, np.arange(rows) + 0.5)
    lon, lat = transform @ (cc, rr)
    _e, n = pyproj.Transformer.from_crs(4326, 32612, always_xy=True).transform(lon, lat)
    return write_tif(tmp_path / "geographic.tif", 0.1 * (n - n.min()), transform, CRS.from_epsg(4326), dtype="float64")


@pytest.fixture
def lunar_tif(tmp_path):
    """5 m lunar south-polar stereographic grid in metres, 10 % slope."""
    res, n = 5.0, 600
    transform = Affine(res, 0, -1500.0, 0, -res, 1500.0)
    cc, _rr = np.meshgrid(np.arange(n) + 0.5, np.arange(n) + 0.5)
    return write_tif(tmp_path / "lunar.tif", 0.1 * cc * res, transform, MOON_SOUTH_POLAR)


def box(west, south, east, north, crs="native"):
    from terrawindow_geo.models import BBox

    return BBox(west=west, south=south, east=east, north=north, crs=crs)


def utm_box(x0_px, y0_px, x1_px, y1_px, res=10.0):
    """Native bbox covering a pixel window of the UTM fixtures (y counted down from the top)."""
    return box(ORIGIN_E + x0_px * res, ORIGIN_N - y1_px * res, ORIGIN_E + x1_px * res, ORIGIN_N - y0_px * res)
