import math

import numpy as np
import pytest

from conftest import ORIGIN_E, ORIGIN_N, box, utm_box
from terrawindow_geo import build_profile, compare_profiles, screen_region
from terrawindow_geo import landcover as lc
from terrawindow_geo.errors import GeoError
from terrawindow_geo.models import (
    DatasetRef,
    LandCoverRule,
    PatchRequest,
    Range,
    ScreeningCriteria,
    ScreenRequest,
    Tolerances,
)

TEN_PERCENT = math.degrees(math.atan(0.1))
WHOLE = utm_box(0, 0, 200, 200)


def profile(uri, bbox=WHOLE, **kw):
    return build_profile(PatchRequest(dataset=DatasetRef(uri=uri, body=kw.pop("body", "earth")), bbox=bbox, **kw))


def rough_box(c0, c1):
    """Native bbox over columns c0..c1 of the 30 m rough fixture (all 200 rows)."""
    return box(ORIGIN_E + c0 * 30, ORIGIN_N - 200 * 30, ORIGIN_E + c1 * 30, ORIGIN_N)


# ------------------------------------------------------------------ profile


def test_plane_profile_reports_known_values(plane_tif):
    p = profile(plane_tif, scales_m=[10, 20, 40], relief_windows_m=[90])
    assert [s.scale_m for s in p.scales] == [10, 20, 40]
    for s in p.scales:
        assert s.status == "assessed" and s.coverage_fraction == 1.0
        assert s.slope.stats.mean == pytest.approx(TEN_PERCENT, abs=1e-3)
        assert s.slope.baseline_m == 2 * s.scale_m
        assert s.slope.fraction_steeper_than["5"] == 1.0 and s.slope.fraction_steeper_than["10"] == 0.0
        assert s.roughness.rms_height_m.max < 1e-3  # a tilted plane is smooth
        assert s.roughness.window_m == 5 * s.scale_m
    assert p.relief[0].window_m == 90 and p.relief[0].stats.median == pytest.approx(8.0, abs=0.01)
    assert p.elevation.range == pytest.approx(199 * 1.0, abs=0.01)
    assert p.patch.area_km2 == 4.0 and p.coverage.sufficient
    assert p.provenance.native_pixel_size_m == 10.0 and p.provenance.sources == [plane_tif]
    assert p.limitations and not p.skipped
    assert p.patch.polygon_lonlat[0] == p.patch.polygon_lonlat[-1]
    assert -112 < p.patch.center_lon < -111 and 35 < p.patch.center_lat < 36


def test_default_scales_skip_what_the_data_cannot_support(geographic_tif):
    bbox = box(-111.64, 35.56, -111.56, 35.64, crs="geographic")
    p = profile(geographic_tif, bbox=bbox)
    assert [s.scale_m for s in p.scales][:2] == [30, 60]  # 30.9 m data honours the nominal 30 m scale

    p = profile(geographic_tif, bbox=bbox, scales_m=[5, 10, 30])
    assert [s.scale_m for s in p.scales] == [30]
    assert [k.code for k in p.skipped] == ["scale_not_supported", "scale_not_supported"]

    with pytest.raises(GeoError) as err:
        profile(geographic_tif, bbox=bbox, scales_m=[5, 10])
    assert err.value.code == "scale_not_supported"


def test_insufficient_coverage_withholds_metrics(holes_tif):
    p = profile(holes_tif, scales_m=[10])
    assert p.coverage.valid_fraction == 0.6 and not p.coverage.sufficient
    assert p.coverage.largest_void_fraction == 0.4
    s = p.scales[0]
    assert s.status == "insufficient_coverage" and s.slope is None and s.roughness is None
    assert p.relief == [] and any(k.code == "insufficient_coverage" for k in p.skipped)
    assert any("withheld" in note for note in p.limitations)

    relaxed = profile(holes_tif, scales_m=[10], min_coverage=0.5)
    assert relaxed.scales[0].status == "assessed"
    assert relaxed.scales[0].slope.stats.mean == pytest.approx(TEN_PERCENT, abs=1e-3)


def test_scale_too_coarse_for_the_patch_is_skipped(plane_tif):
    p = profile(plane_tif, scales_m=[10, 200])
    assert [s.scale_m for s in p.scales] == [10]
    assert p.skipped[0].code == "patch_too_small"


def test_lunar_and_earth_profiles_share_a_scale(lunar_tif, plane_tif):
    moon = profile(lunar_tif, bbox=box(-1400, -1400, 1400, 1400), body="moon", scales_m=[30, 60])
    earth = profile(plane_tif, scales_m=[30, 60])
    assert moon.patch.body == "moon" and moon.provenance.native_pixel_size_m == 5.0
    result = compare_profiles(moon, earth)
    assert result.common_scales_m == [30, 60]
    slope = [c for c in result.criteria if c.metric == "slope_mean"]
    assert all(c.status == "within_tolerance" for c in slope)


# ------------------------------------------------------------------ compare


def test_identical_profiles_are_within_every_tolerance(rough_tif):
    p = profile(rough_tif, bbox=rough_box(200, 400), scales_m=[30, 60])
    result = compare_profiles(p, p)
    assert result.counts["outside_tolerance"] == 0 and result.counts["within_tolerance"] > 0
    assert all(c.normalized_difference in (0, 0.0) for c in result.criteria if c.status == "within_tolerance")


def test_flat_and_rough_terrain_are_distinguished(rough_tif):
    rough = profile(rough_tif, bbox=rough_box(200, 400), scales_m=[30])
    flat = profile(rough_tif, bbox=rough_box(0, 190), scales_m=[30])
    assert rough.scales[0].slope.stats.mean > 10 and flat.scales[0].slope.stats.mean == 0

    result = compare_profiles(rough, flat)
    by_metric = {c.metric: c for c in result.criteria}
    assert by_metric["slope_mean"].status == "outside_tolerance"
    assert by_metric["slope_distribution_distance"].status == "outside_tolerance"
    assert by_metric["roughness_rms_height_median"].status == "outside_tolerance"
    assert by_metric["slope_mean"].difference < 0

    loose = compare_profiles(rough, flat, Tolerances(slope_mean_deg=90))
    assert {c.metric: c for c in loose.criteria}["slope_mean"].status == "within_tolerance"


def test_comparison_never_produces_an_overall_score(rough_tif):
    p = profile(rough_tif, bbox=rough_box(200, 400), scales_m=[30])
    dumped = compare_profiles(p, p).model_dump()
    assert not {"score", "similarity", "overall"} & set(dumped)
    assert set(dumped["counts"]) == {"within_tolerance", "outside_tolerance", "not_assessed"}


def test_missing_evidence_is_not_a_negative_finding(plane_tif, holes_tif):
    good = profile(plane_tif, scales_m=[10])
    holes = profile(holes_tif, scales_m=[10])
    result = compare_profiles(good, holes)
    assert result.counts["outside_tolerance"] == 0 and result.counts["not_assessed"] >= 3
    assert all("coverage" in c.reason.lower() or "relief" in c.metric for c in result.criteria)

    other_scale = profile(plane_tif, scales_m=[20])
    result = compare_profiles(good, other_scale)
    assert result.common_scales_m == [] and any("share no analysis scale" in n for n in result.notes)


# ------------------------------------------------------------------ discovery


def screen(uri, **kw):
    kw.setdefault("bbox", box(ORIGIN_E, ORIGIN_N - 200 * 30, ORIGIN_E + 400 * 30, ORIGIN_N))
    return screen_region(ScreenRequest(dataset=DatasetRef(uri=uri), patch_size_m=1500, **kw))


def test_screening_separates_flat_from_rough_cells(rough_tif):
    fc = screen(rough_tif, criteria=ScreeningCriteria(slope_mean_deg=Range(max=5)))
    assert fc["type"] == "FeatureCollection"
    assert fc["summary"] == {"cells": 32, "candidate": 16, "rejected": 16, "insufficient_data": 0, "scale_m": 30.0, "patch_size_m": 1500.0}
    west_edge = ORIGIN_E + 200 * 30
    for f in fc["features"]:
        ring = f["geometry"]["coordinates"][0]
        assert len(ring) == 5 and ring[0] == ring[-1]
        col = int(f["id"].split("c")[1])
        assert f["properties"]["status"] == ("candidate" if col < 4 else "rejected")
        check = next(c for c in f["properties"]["criteria"] if c["criterion"] == "slope_mean_deg")
        assert check["status"] == ("pass" if col < 4 else "fail")
    assert west_edge and fc["provenance"]["working_pixel_size_m"] == 30.0


def test_screening_can_look_for_rough_terrain_and_hide_rejects(rough_tif):
    fc = screen(rough_tif, criteria=ScreeningCriteria(slope_mean_deg=Range(min=8), roughness_rms_height_m=Range(min=1)), include_rejected=False)
    assert len(fc["features"]) == fc["summary"]["candidate"] == 16
    assert all(int(f["id"].split("c")[1]) >= 4 for f in fc["features"])


def test_screening_criteria_can_come_from_a_reference_profile(rough_tif):
    reference = profile(rough_tif, bbox=rough_box(200, 400), scales_m=[30])
    fc = screen(rough_tif, reference_profile=reference, tolerances=Tolerances(slope_mean_deg=6, slope_p90_deg=10, roughness_rel=0.8))
    assert fc["criteria"]["slope_mean_deg"]["min"] > 5
    statuses = {f["id"]: f["properties"]["status"] for f in fc["features"]}
    assert all(s == "rejected" for i, s in statuses.items() if int(i.split("c")[1]) < 4)
    assert any(s == "candidate" for i, s in statuses.items() if int(i.split("c")[1]) >= 4)


def test_screening_marks_cells_without_data(holes_tif):
    fc = screen_region(ScreenRequest(dataset=DatasetRef(uri=holes_tif), bbox=WHOLE, patch_size_m=400, scale_m=10))
    by_col = {}
    for f in fc["features"]:
        by_col.setdefault(int(f["id"].split("c")[1]), set()).add(f["properties"]["status"])
    assert by_col[0] == {"insufficient_data"} and by_col[1] == {"insufficient_data"}
    assert by_col[2] == by_col[4] == {"candidate"}
    empty = next(f for f in fc["features"] if f["id"] == "r0c0")
    assert empty["properties"]["metrics"]["slope_mean_deg"] is None  # withheld, not zero


def test_screening_input_guards(rough_tif, plane_tif):
    with pytest.raises(GeoError) as err:
        screen_region(ScreenRequest(dataset=DatasetRef(uri=rough_tif), bbox=rough_box(0, 400), patch_size_m=100))
    assert err.value.code == "patch_too_small"
    with pytest.raises(GeoError) as err:
        screen_region(ScreenRequest(dataset=DatasetRef(uri=plane_tif), bbox=WHOLE, scale_m=2))
    assert err.value.code == "scale_not_supported"


# ------------------------------------------------------------------ land cover


def test_landcover_fractions_and_screen():
    classes = np.full((10, 10), 60.0)  # bare / sparse vegetation
    classes[:3] = 10  # tree cover
    classes[9, 9] = np.nan
    summary = lc.summarize(classes, LandCoverRule(max_excluded_fraction=0.2))
    assert summary.dominant_class == 60 and summary.valid_fraction == 0.99
    assert summary.classes[0].label.startswith("Bare")
    assert summary.excluded_fraction == pytest.approx(30 / 99, abs=1e-3)
    assert summary.screen == "fail" and "tree cover" in summary.reason

    assert lc.summarize(classes, LandCoverRule(max_excluded_fraction=0.5)).screen == "pass"
    assert lc.summarize(classes).screen == "not_assessed"
    assert lc.summarize(np.full((4, 4), np.nan)).dominant_class is None
