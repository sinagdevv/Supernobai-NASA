"""Candidate-screening validation (proposal, Test 2) on real Copernicus GLO-30 data.

Profiles an established analog site and a deliberately unsuitable site, compares them criterion
by criterion, and checks that the engine tells them apart. Needs internet access.

    python scripts/validation_demo.py [--out data/validation]

Sites
  reference : SP Crater lava field, San Francisco Volcanic Field, Arizona. NASA ran the JETT5
              Artemis III mission simulations in this volcanic field (USGS Astrogeology, 2024).
  control   : irrigated cropland in the Imperial Valley, California. Flat, vegetated, farmed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from terrawindow_geo import build_profile, compare_profiles
from terrawindow_geo.models import BBox, DatasetRef, PatchRequest

SITES = {
    "reference_sp_crater_az": BBox(west=-111.67, south=35.55, east=-111.59, north=35.62),
    "control_imperial_valley_ca": BBox(west=-115.56, south=32.90, east=-115.48, north=32.97),
}
SCALES_M = [30.0, 60.0, 120.0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None, help="folder to write the JSON results into")
    args = parser.parse_args()

    profiles = {}
    for name, bbox in SITES.items():
        request = PatchRequest(dataset=DatasetRef(id="copernicus-glo30"), bbox=bbox, scales_m=SCALES_M, include_landcover=True)
        profiles[name] = build_profile(request)

    print(f"{'site':<30}{'scale':>7}{'slope mean':>12}{'slope p90':>11}{'>15 deg':>9}{'rms height':>12}")
    for name, p in profiles.items():
        for s in p.scales:
            print(
                f"{name:<30}{s.scale_m:>6.0f}m{s.slope.stats.mean:>11.2f}°{s.slope.stats.p90:>10.2f}°"
                f"{s.slope.fraction_steeper_than['15']:>9.1%}{s.roughness.rms_height_m.median:>11.2f}m"
            )
        cover = p.landcover
        if cover and cover.classes:
            top = ", ".join(f"{c.label} {c.fraction:.0%}" for c in cover.classes[:3])
            print(f"{'':<30}land cover: {top} -> screen: {cover.screen}")

    reference, control = profiles.values()
    result = compare_profiles(reference, control)
    print("\nper-criterion comparison (control vs reference):")
    for c in result.criteria:
        scale = f"{c.scale_m:g} m" if c.scale_m else "-"
        values = f"distance={c.difference!s:>8}" if c.reference is None and c.candidate is None else f"ref={c.reference!s:>8}  cand={c.candidate!s:>8}"
        print(f"  {c.metric:<34}{scale:>7}  {values:<28}  {c.status}")
    print(f"\ntally (not a score): {result.counts}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, p in profiles.items():
            (out / f"{name}.json").write_text(p.model_dump_json(indent=2), encoding="utf-8")
        (out / "comparison.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"wrote results to {out}")

    distinguished = result.counts["outside_tolerance"] > 0
    cropland_flagged = control.landcover is not None and control.landcover.screen == "fail"
    print(f"\nterrain distinguishes the sites: {distinguished}")
    print(f"land-cover screen rejects the cropland control: {cropland_flagged}")
    return 0 if distinguished else 1


if __name__ == "__main__":
    sys.exit(main())
