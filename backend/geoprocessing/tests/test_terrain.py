import math

import numpy as np
import pytest

from terrawindow_geo.terrain.relief import local_relief, window_pixels
from terrawindow_geo.terrain.roughness import rms_height, tri
from terrawindow_geo.terrain.slope import hillshade, slope_aspect, slope_metrics


def plane(rows, cols, res, d_east=0.0, d_north=0.0):
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    return d_east * cc * res + d_north * (-rr) * res  # row index grows southward


@pytest.mark.parametrize(
    "d_east,d_north,aspect",
    [(0.1, 0.0, 270.0), (-0.1, 0.0, 90.0), (0.0, 0.2, 180.0), (0.0, -0.2, 0.0), (0.1, 0.1, 225.0)],
)
def test_plane_slope_and_aspect(d_east, d_north, aspect):
    slope, asp = slope_aspect(plane(40, 50, 30.0, d_east, d_north), 30.0)
    assert np.allclose(slope[1:-1, 1:-1], math.degrees(math.atan(math.hypot(d_east, d_north))), atol=1e-9)
    inner = asp[1:-1, 1:-1]
    assert np.allclose(np.minimum(np.abs(inner - aspect), 360 - np.abs(inner - aspect)), 0, atol=1e-9)
    assert np.isnan(slope[0]).all() and np.isnan(slope[:, -1]).all()  # border has no full kernel


def test_slope_depends_on_pixel_size():
    z = plane(20, 20, 1.0, d_east=1.0)  # 1 m rise per cell
    assert np.nanmax(slope_aspect(z, 10.0)[0]) == pytest.approx(math.degrees(math.atan(0.1)))
    assert np.nanmax(slope_aspect(z, 100.0)[0]) == pytest.approx(math.degrees(math.atan(0.01)))


def test_flat_surface_is_zero_everywhere():
    z = np.full((40, 40), 123.0)
    slope, aspect = slope_aspect(z, 30.0)
    assert np.nanmax(slope) == 0 and np.isnan(aspect).all()
    assert np.nanmax(rms_height(z)) < 1e-9
    assert np.nanmax(tri(z)) == 0
    assert np.nanmax(local_relief(z, 5)) == 0


def test_nan_propagates_instead_of_being_filled():
    z = plane(30, 30, 10.0, d_east=0.1)
    z[15, 15] = np.nan
    slope, _ = slope_aspect(z, 10.0)
    assert np.isnan(slope[14:17, 14:17]).all()
    assert np.isfinite(slope[10, 10])


def test_tilted_plane_has_no_roughness():
    rough = rms_height(plane(60, 60, 30.0, d_east=0.3, d_north=-0.2), 5)
    assert np.isfinite(rough).any()
    assert np.nanmax(rough) < 1e-9


def test_sinusoid_rms_height_is_amplitude_over_root_two():
    amplitude, period = 4.0, 5  # period equals the window, so each window holds one full cycle
    cc, _ = np.meshgrid(np.arange(100), np.arange(100))
    rough = rms_height(amplitude * np.sin(2 * np.pi * cc / period), 5)
    assert np.nanmedian(rough) == pytest.approx(amplitude / math.sqrt(2), rel=1e-6)


def test_relief_of_plane_is_slope_times_window():
    z = plane(60, 60, 10.0, d_east=0.1)
    px = window_pixels(90.0, 10.0)
    assert px == 9
    relief = local_relief(z, px)
    assert np.nanmedian(relief) == pytest.approx(0.1 * 10.0 * (px - 1))
    assert np.isnan(relief[:4]).all()


def test_slope_metrics_fractions_and_histogram():
    slope = np.concatenate([np.full(75, 2.5), np.full(25, 22.5)]).reshape(10, 10)
    m = slope_metrics(slope, 30.0, [5, 15, 25])
    assert m.baseline_m == 60.0
    assert m.fraction_steeper_than == {"5": 0.25, "15": 0.25, "25": 0.0}
    assert sum(m.histogram.fractions) == pytest.approx(1.0)
    assert m.histogram.fractions[2] == 0.75 and m.histogram.fractions[22] == 0.25


def test_hillshade_faces_the_sun():
    east_facing = plane(20, 20, 10.0, d_east=-0.5)  # drops to the east
    lit = hillshade(east_facing, 10.0, sun_azimuth_deg=90, sun_elevation_deg=10)
    dark = hillshade(east_facing, 10.0, sun_azimuth_deg=270, sun_elevation_deg=10)
    assert np.nanmean(lit) > 0.5 and np.nanmax(dark) == 0
