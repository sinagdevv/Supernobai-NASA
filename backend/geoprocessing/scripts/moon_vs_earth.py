"""End-to-end run: a real lunar south-polar reference against Earth candidates.

Layer 2 fetches and validates the data; Layer 3 profiles, compares and screens it.

    python scripts/moon_vs_earth.py [--site lola-5mpp-site01] [--out DIR]

Reference : NASA LOLA 5 m/pix model of a lunar south-polar site (default Site01, Connecting ridge).
Candidates: SP Crater lava field, Arizona (established analog) and Imperial Valley cropland,
            California (deliberately unsuitable control), each a 16 km box like the lunar site.
Screening : the San Francisco Volcanic Field, cut into 3 km patches and checked against slope
            and roughness ranges derived from the lunar reference.

All comparisons use 30 m or coarser, the finest scale the Earth data supports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from terrawindow_data import data_dir, fetch_dataset, load_manifest, prepare_region
from terrawindow_geo import build_profile, compare_profiles, screen_region
from terrawindow_geo.models import DatasetRef, PatchRequest, ScreenRequest

SCALES_M = [30.0, 60.0, 120.0]
REGIONS = {
    "sp-crater": (-111.72, 35.51, -111.54, 35.655),
    "imperial-valley": (-115.60, 32.86, -115.43, 33.005),
    "sf-volcanic-field": (-112.00, 35.25, -111.35, 35.75),
}


def ensure_data(site: str) -> None:
    stored = load_manifest()["datasets"]
    if site not in stored:
        print(f"fetching {site} ...")
        fetch_dataset(site)
    for name, bbox in REGIONS.items():
        if f"{name}-copernicus-glo30" not in stored:
            print(f"cutting region {name} from Copernicus GLO-30 ...")
            prepare_region("copernicus-glo30", name, *bbox)


def table(profiles: dict) -> None:
    print(f"\n{'site':<34}{'scale':>7}{'slope mean':>12}{'median':>9}{'p90':>9}{'>15 deg':>9}{'rms height':>12}")
    for name, p in profiles.items():
        for s in p.scales:
            if s.slope is None:
                print(f"{name:<34}{s.scale_m:>6.0f}m   insufficient coverage")
                continue
            print(
                f"{name:<34}{s.scale_m:>6.0f}m{s.slope.stats.mean:>11.2f}°{s.slope.stats.median:>8.2f}°{s.slope.stats.p90:>8.2f}°"
                f"{s.slope.fraction_steeper_than['15']:>9.1%}{s.roughness.rms_height_m.median:>11.2f}m"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", default="lola-5mpp-site01")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    # Default to the untracked local/ part of the store: the committed <store>/results are the team's recorded run, and a routine
    # re-run must not overwrite them. Pass --out <store>/results to update that record on purpose.
    out = Path(args.out) if args.out else data_dir() / "local" / "results"
    out.mkdir(parents=True, exist_ok=True)

    ensure_data(args.site)

    def profile(dataset_id: str):
        return build_profile(PatchRequest(dataset=DatasetRef(id=dataset_id), scales_m=SCALES_M))

    moon = profile(args.site)
    profiles = {
        f"MOON {args.site}": moon,
        "EARTH sp-crater (analog)": profile("sp-crater-copernicus-glo30"),
        "EARTH imperial-valley (control)": profile("imperial-valley-copernicus-glo30"),
    }
    print(f"\nlunar reference: {moon.provenance.dataset_name}")
    print(f"  centre {moon.patch.center_lat:.3f}°, {moon.patch.center_lon:.3f}°  |  {moon.patch.width_m / 1000:.0f} x {moon.patch.height_m / 1000:.0f} km"
          f"  |  native {moon.provenance.native_pixel_size_m:g} m, analysed at {SCALES_M[0]:g} m and coarser")
    table(profiles)

    names = list(profiles)
    for name in names[1:]:
        result = compare_profiles(moon, profiles[name])
        slug = name.split()[1]
        (out / f"compare_{args.site}_vs_{slug}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\n{name} against the lunar reference:")
        for c in result.criteria:
            if c.scale_m not in (30.0,) and not c.metric.startswith("relief"):
                continue  # print the 30 m rows; every scale is in the JSON
            values = f"distance={c.difference!s:>8}" if c.reference is None and c.candidate is None else f"moon={c.reference!s:>8}  earth={c.candidate!s:>8}"
            print(f"  {c.metric:<34}{values:<34}{c.status}")
        print(f"  tally over all scales (not a score): {result.counts}")
    for name, p in profiles.items():
        (out / f"profile_{name.split()[1]}.json").write_text(p.model_dump_json(indent=2), encoding="utf-8")

    print("\nscreening the San Francisco Volcanic Field against ranges derived from the lunar reference ...")
    collection = screen_region(
        ScreenRequest(
            dataset=DatasetRef(id="sf-volcanic-field-copernicus-glo30"),
            patch_size_m=3000,
            scale_m=30,
            reference_profile=moon,
        )
    )
    (out / f"screen_sf-volcanic-field_vs_{args.site}.geojson").write_text(json.dumps(collection), encoding="utf-8")
    print("  criteria: " + ", ".join(f"{k} {v['min']:.2f}-{v['max']:.2f}" for k, v in collection["criteria"].items() if isinstance(v, dict) and "min" in v))
    print(f"  {collection['summary']}")
    best = [f for f in collection["features"] if f["properties"]["status"] == "candidate"]
    for f in best[:8]:
        m = f["properties"]["metrics"]
        print(f"  candidate {f['id']:<8} {f['properties']['center_lat']:.3f}, {f['properties']['center_lon']:.3f}"
              f"   slope mean {m['slope_mean_deg']:.1f}°  p90 {m['slope_p90_deg']:.1f}°  rms height {m['roughness_rms_height_m']:.2f} m")
    print(f"\nresults written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
