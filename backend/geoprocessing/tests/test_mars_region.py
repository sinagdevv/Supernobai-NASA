"""Layer 3 on the real Martian terrain Layer 2 retrieved (MOLA MEGDR, Jezero region). Skipped when that region is not in the data store.

Fetch it with:  terrawindow-data region mola-megdr128 jezero 76.4 17.4 78.6 19.4
"""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from terrawindow_geo import build_profile
from terrawindow_geo.config import get_settings
from terrawindow_geo.models import DatasetRef, PatchRequest

STORE = Path(__file__).resolve().parents[2] / "data"
ID = "jezero-mola-megdr128"
NATIVE = 463.0576672
R = 3396000.0  # the sphere in the PDS4 label

pytestmark = pytest.mark.skipif(not (STORE / "mars" / "regions" / "jezero_mola-megdr128.tif").is_file(), reason="Jezero MOLA region not retrieved")


@pytest.fixture(autouse=True)
def real_store(monkeypatch):
    monkeypatch.setenv("TWGEO_DATA_DIR", str(STORE))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _independent_horn_mean_deg() -> float:
    """Horn slope computed straight from the source pixels with the true ground spacing of each row, sharing no code with Layer 3."""
    rec = json.loads((STORE / "manifest.json").read_text())["datasets"][ID]
    with rasterio.open(STORE / rec["path"]) as d:
        z = d.read(1).astype("float64")
        top = d.transform.f
    rows = z.shape[0]
    lat = np.radians((top - (np.arange(rows) + 0.5) * NATIVE) / R * 180 / np.pi)
    dx = (NATIVE * np.cos(lat))[1:-1, None]
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d_, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d_ + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * NATIVE)
    return float(np.degrees(np.arctan(np.hypot(dzdx, dzdy))).mean())


def test_the_stored_mars_region_is_profiled_as_mars_with_its_provenance():
    p = build_profile(PatchRequest(dataset=DatasetRef(id=ID), scales_m=[2 * NATIVE]))
    assert p.patch.body == "mars" and 77.0 < p.patch.center_lon < 78.0 and 18.0 < p.patch.center_lat < 19.0
    assert p.provenance.dataset_id == ID and "MOLA" in p.provenance.dataset_name and "10.1029/2000JE001364" in p.provenance.citation
    assert p.provenance.native_pixel_size_m == pytest.approx(NATIVE, abs=0.01)
    assert "Azimuthal_Equidistant" in p.provenance.working_crs  # not the source projection: it is not true-scale away from the equator
    assert any("463 m pixels cannot resolve rover-scale" in s for s in p.limitations)
    assert -3500 < p.elevation.min < p.elevation.max < -400  # metres above the areoid: Jezero and its surroundings are below the datum


def test_mars_slope_agrees_with_an_independent_calculation_from_the_source_pixels():
    """463 m scale: Layer 3 resamples onto a metric grid first, so it is slightly smoother than Horn on the source grid; 5 % is the allowance."""
    p = build_profile(PatchRequest(dataset=DatasetRef(id=ID), scales_m=[NATIVE]))
    layer3 = p.scales[0].slope.stats.mean
    independent = _independent_horn_mean_deg()
    assert layer3 == pytest.approx(independent, rel=0.05), (layer3, independent)


def test_scales_finer_than_the_463_m_pixel_are_refused_not_invented():
    p = build_profile(PatchRequest(dataset=DatasetRef(id=ID), scales_m=[30, 60, 120, 240, 2 * NATIVE]))
    assert [s.scale_m for s in p.scales] == [pytest.approx(2 * NATIVE)]
    assert {s.item for s in p.skipped if s.code == "scale_not_supported"} >= {"scale 30 m", "scale 240 m"}
