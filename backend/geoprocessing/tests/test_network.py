"""Real-data checks against the public COG buckets. Run with: pytest -m network"""

import pytest

from terrawindow_geo import build_profile, screen_region
from terrawindow_geo.models import BBox, DatasetRef, PatchRequest, Range, ScreeningCriteria, ScreenRequest

pytestmark = pytest.mark.network
SP_CRATER = BBox(west=-111.67, south=35.55, east=-111.59, north=35.62)


def test_glo30_profile_of_sp_crater():
    p = build_profile(PatchRequest(dataset=DatasetRef(id="copernicus-glo30"), bbox=SP_CRATER, scales_m=[30, 60], include_landcover=True))
    assert p.provenance.working_crs == "EPSG:32612"
    assert p.provenance.native_pixel_size_m == pytest.approx(30.9, abs=0.3)
    assert p.coverage.valid_fraction == 1.0
    assert 1500 < p.elevation.min < p.elevation.max < 2500  # the cinder cone stands near 2140 m
    assert 3 < p.scales[0].slope.stats.mean < 9
    assert p.landcover.classes and p.landcover.screen == "pass"


def test_glo30_screening_returns_candidates():
    fc = screen_region(
        ScreenRequest(
            dataset=DatasetRef(id="copernicus-glo30"),
            bbox=BBox(west=-111.75, south=35.50, east=-111.55, north=35.65),
            patch_size_m=3000,
            criteria=ScreeningCriteria(slope_mean_deg=Range(max=8)),
        )
    )
    assert fc["summary"]["cells"] >= 20 and fc["summary"]["candidate"] >= 1
    assert all(-112 < f["properties"]["center_lon"] < -111 for f in fc["features"])
