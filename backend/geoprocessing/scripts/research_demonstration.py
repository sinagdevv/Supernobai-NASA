"""Reproducible research demonstration: screen Earth terrain for a lunar south-polar reference, then characterise
the best screened candidate with Layers 3, 4 and 5.

    python scripts/research_demonstration.py [--out DIR]

Reference  : NASA LOLA 5 m/pix south-pole site model, Site01 (Connecting ridge), analysed at 30 m and coarser.
Search     : the San Francisco Volcanic Field, Arizona (Copernicus GLO-30, 30 m), cut into 3 km patches and screened
             against slope and roughness ranges derived from the lunar reference (Layer 3).
Candidate  : the best screened patch (smallest normalised distance from the lunar mean slope, 90th-percentile slope and
             roughness). It is characterised over a 5.5 km box centred on it, because Layer 4's horizon search needs
             room around the target.
Layer 4    : Earth solar geometry and terrain shadows at the candidate for one stated day (low-sun band 0.5-10 deg).
Layer 5    : an assessment against the interface's default lunar criteria, with the Layer 4 result attached.

Everything printed is computed by the repository's own code from stored data. None of it is observationally validated,
and the screening tolerances and mission thresholds are assumptions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from terrawindow_data import data_dir, load_manifest
from terrawindow_geo import build_profile, compare_profiles, screen_region
from terrawindow_geo.api.app import create_app
from terrawindow_geo.models import BBox, DatasetRef, PatchRequest, ScreenRequest

MOON, EARTH = "lola-5mpp-site01", "sf-volcanic-field-copernicus-glo30"
SCALES = [30.0, 60.0, 120.0]
HALF_DEG = 0.03  # 5.5 km box
START, END, STEP_MIN = "2026-12-15T00:00:00Z", "2026-12-16T00:00:00Z", 15  # one day at 15 min (96 samples, the service maximum); Earth orientation kernel ends 2027-02-08


def criteria(layer4_target_s: float = 3600.0) -> list[dict]:
    """The interface's default lunar screening criteria (frontend/src/lib/suitability.ts). Assumptions, not standards."""
    base = {"required": True, "missing_data_behavior": "INDETERMINATE", "rationale": "Assumption for screening a low-gravity, airless surface."}
    def c(i, name, cat, layer, metric, op, val, unit, **sel):
        return {"id": i, "name": name, "category": cat, "description": name, "source_layer": layer, "source_metric": metric, "operator": op, "target_value": val, "unit": unit, **base, **sel}
    return [
        c("slope-p90", "90th-percentile slope", "terrain", "layer3", "terrain.slope.p90_deg", "lte", 20, "degrees", scale_m=30.0),
        c("steep-share", "Share steeper than 20 degrees", "terrain", "layer3", "terrain.slope.fraction_steeper_than", "lte", 0.15, "fraction", scale_m=30.0, threshold_deg=20),
        c("roughness", "Median roughness (RMS height)", "terrain", "layer3", "terrain.roughness.rms_height_median_m", "lte", 1.5, "metres", scale_m=30.0),
        c("coverage", "Valid elevation coverage", "data-coverage", "layer3", "terrain.coverage.valid_fraction", "gte", 0.9, "fraction"),
        c("illumination", "Qualifying illumination", "illumination", "layer4", "rehearsal.total_qualifying_illumination_duration_seconds", "gte", layer4_target_s, "seconds"),
        c("obstruction", "Peak terrain shadow", "illumination", "layer4", "rehearsal.terrain_obstruction_max_percent", "lte", 50, "percent"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(data_dir() / "local" / "results"))
    out_dir = Path(ap.parse_args().out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stored = load_manifest()["datasets"]
    for ds in (MOON, EARTH):
        if ds not in stored or not (data_dir() / stored[ds]["path"]).is_file():
            print(f"{ds} is not on this machine; see 'Getting started' in the README.")
            return 1

    print("1. Lunar reference (Layer 3)")
    moon = build_profile(PatchRequest(dataset=DatasetRef(id=MOON), scales_m=SCALES))
    m30 = moon.scales[0]
    print(f"   Site01 at 30 m: mean slope {m30.slope.stats.mean:.2f} deg, 90th percentile {m30.slope.stats.p90:.2f} deg")

    print("2. Screen the San Francisco Volcanic Field in 3 km patches against ranges derived from the reference")
    fc = screen_region(ScreenRequest(dataset=DatasetRef(id=EARTH), patch_size_m=3000, scale_m=30, reference_profile=moon))
    cands = [f for f in fc["features"] if f["properties"]["status"] == "candidate"]
    print(f"   {fc['summary']}")
    if not cands:
        print("   no candidate: nothing to characterise")
        return 1
    ref = {"mean": m30.slope.stats.mean, "p90": m30.slope.stats.p90, "rms": m30.roughness.rms_height_m.median}

    def distance(f):
        m = f["properties"]["metrics"]
        return sum(abs(m[k] - ref[r]) / ref[r] for k, r in (("slope_mean_deg", "mean"), ("slope_p90_deg", "p90"), ("roughness_rms_height_m", "rms")))

    best = min(cands, key=distance)
    lat, lon = best["properties"]["center_lat"], best["properties"]["center_lon"]
    m = best["properties"]["metrics"]
    print(f"   {len(cands)} candidates; best {best['id']} at {lat:.4f}, {lon:.4f}: mean {m['slope_mean_deg']:.1f}, p90 {m['slope_p90_deg']:.1f}, rms {m['roughness_rms_height_m']:.2f} m (3 km patch)")

    box = BBox(west=lon - HALF_DEG, east=lon + HALF_DEG, south=lat - HALF_DEG * 0.82, north=lat + HALF_DEG * 0.82)
    cand = PatchRequest(dataset=DatasetRef(id=EARTH), bbox=box, scales_m=SCALES)
    print("3. Characterise the 5.5 km candidate box (Layer 3) and compare it with the lunar reference")
    prof = build_profile(cand)
    cmp = compare_profiles(moon, prof)
    for s in prof.scales:
        print(f"   {s.scale_m:>5.0f} m  slope mean {s.slope.stats.mean:5.2f}  p90 {s.slope.stats.p90:5.2f}  >20 deg {s.slope.fraction_steeper_than.get('20.0', s.slope.fraction_steeper_than.get('20')) or 0:.3f}  rms height {s.roughness.rms_height_m.median:.2f} m")
    print(f"   box {prof.patch.width_m:.0f} x {prof.patch.height_m:.0f} m, valid cells {prof.coverage.valid_fraction:.3f}; criteria tally (not a score): {cmp.counts}")

    print("4-5. Layer 4 (Earth solar geometry, terrain shadows) and Layer 5 (assessment), through the service code")
    client = TestClient(create_app(), raise_server_exceptions=False)
    body = {"candidate": json.loads(cand.model_dump_json()), "start_utc": START, "end_utc": END, "step_minutes": STEP_MIN,
            "criteria": {"minimum_continuous_illumination_minutes": 30, "solar_elevation_min_deg": 0.5, "solar_elevation_max_deg": 10}}
    r4 = client.post("/v1/rehearsal/evaluate", json=body)
    layer4 = r4.json() if r4.status_code == 200 else None
    if layer4:
        counts = layer4["classification_counts"]
        print(f"   {START[:10]} to {END[:10]}, every {STEP_MIN} min: sun elevation {layer4['solar_elevation_min_deg']:.1f} to {layer4['solar_elevation_max_deg']:.1f} deg, "
              f"{len(layer4['candidate_windows'])} candidate low-sun window(s) {[round(w['duration_seconds'] / 3600, 1) for w in layer4['candidate_windows']]} h, peak terrain shadow {layer4['terrain_obstruction_max_percent']:.1f} %")
        print(f"   target classes over the box (all samples): {counts}; evidence: {layer4['evidence']['observational_validation_status']}")
        # Layer 4 applies window criteria to a whole continuous illuminated interval, so a daytime interval spanning 2-31 deg
        # fails a 10 deg maximum as a unit. The low-sun samples themselves are counted here from its per-sample output.
        low = [o for o in layer4["observations"] if 0.5 <= o["solar_elevation_deg"] <= 10]
        lit = [o for o in low if o["target_classification"] == "ILLUMINATED"]
        print(f"   post-processing of the per-sample output: {len(low)} samples with sun 0.5-10 deg, {len(lit)} of them with the target illuminated "
              f"({len(lit) * STEP_MIN} min at {STEP_MIN} min sampling): {[o['time_utc'][11:16] for o in lit]} UTC; the others: "
              f"{sorted({o['target_classification'] for o in low if o not in lit})}")
        layer4["post_processing_low_sun"] = {"samples_in_band": len(low), "illuminated_samples": len(lit), "minutes": len(lit) * STEP_MIN, "times_utc": [o["time_utc"] for o in lit]}
    else:
        print(f"   Layer 4 unavailable here ({r4.status_code}): {r4.json().get('error', {}).get('message')}")
    payload = {"candidate_id": f"sf-volcanic-field-{best['id']}", "candidate_name": f"San Francisco Volcanic Field patch {best['id']}", "candidate": json.loads(cand.model_dump_json()),
               "mission_profile": {"id": "terrawindow-moon-rover-low-sun", "name": "Lunar south-polar rover mobility, low sun", "description": "Default lunar screening criteria. Thresholds are adjustable assumptions, not standards.",
                                   "required_categories": ["terrain", "data-coverage", "illumination"], "criteria": criteria()}}
    if layer4:
        payload["layer4_result"] = layer4
    r5 = client.post("/v1/suitability/assess", json=payload)
    assessment = r5.json()
    if r5.status_code == 200:
        print(f"   Layer 5 overall: {assessment['overall_status']} ({assessment['overall_explanation']})")
        for row in assessment["criterion_results"]:
            value = row["measured_value"] if row["measured_value"] is not None else f"claimed {row['claimed_value']}" if row["claimed_value"] is not None else "none"
            print(f"     {row['criterion_id']:<13}{row['status']:<14}{value!s:<18}{row['explanation']}")
        print(f"   spatial association: {assessment['spatial_association']['status'] if assessment.get('spatial_association') else 'no Layer 4 result'}")
        print(f"   gaps: {[g['id'] for g in assessment['suitability_gaps']]}")
    else:
        print(f"   Layer 5 failed: {r5.status_code} {assessment}")

    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "candidate": {"id": best["id"], "lat": lat, "lon": lon, "box": box.model_dump()},
              "reference_profile": json.loads(moon.model_dump_json()), "screen_summary": fc["summary"], "screen_criteria": fc["criteria"],
              "candidate_profile": json.loads(prof.model_dump_json()), "comparison": json.loads(cmp.model_dump_json()), "layer4": layer4, "layer5": assessment,
              "dataset_sha256": {d: stored[d]["products"]["surface"]["sha256"] for d in (MOON, EARTH)}}
    path = out_dir / "research_demonstration.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nfull record written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
