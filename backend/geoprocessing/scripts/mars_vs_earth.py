"""End-to-end run: real Martian terrain (MOLA, Jezero region) measured by Layer 3 and compared with Earth, at a stated common scale.

Layer 2 retrieves and validates the data; Layer 3 profiles and compares it. No suitability verdict is produced: that needs Layer 5.

    python scripts/mars_vs_earth.py [--out DIR]

Mars     : MGS MOLA MEGDR 128 pixels/degree (PDS4), 463 m pixels, a 2.2 x 2.0 degree region around Jezero crater (Layer 2 id jezero-mola-megdr128).
Earth    : the same Copernicus GLO-30 regions the Moon example uses.
Scale    : 926 m (two Martian pixels). 30 m Earth data is aggregated up to it; nothing is ever refined. Metrics at this scale describe
           regional terrain, not rover-scale obstacles, and are only comparable between sites measured at the same scale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from terrawindow_data import data_dir, load_manifest, prepare_region
from terrawindow_geo import build_profile, compare_profiles
from terrawindow_geo.models import DatasetRef, PatchRequest

MARS = "jezero-mola-megdr128"
MARS_BBOX = (76.4, 17.4, 78.6, 19.4)
NATIVE_M = 463.0576672
SCALE_M = 2 * NATIVE_M
EARTH = {
    "sp-crater": (-111.72, 35.51, -111.54, 35.655),
    "imperial-valley": (-115.60, 32.86, -115.43, 33.005),
    "sf-volcanic-field": (-112.00, 35.25, -111.35, 35.75),
}


def present(stored: dict, dataset_id: str) -> bool:
    """Listed in the manifest AND its raster is on disk: on a fresh checkout the reference manifest lists datasets whose rasters are not there yet."""
    return dataset_id in stored and (data_dir() / stored[dataset_id]["path"]).is_file()


def ensure_data() -> None:
    stored = load_manifest()["datasets"]
    if not present(stored, MARS):
        print("cutting the Jezero region from the PDS4 MEGDR tile ...")
        prepare_region("mola-megdr128", "jezero", *MARS_BBOX)
    for name, bbox in EARTH.items():
        if not present(stored, f"{name}-copernicus-glo30"):
            print(f"cutting region {name} from Copernicus GLO-30 ...")
            prepare_region("copernicus-glo30", name, *bbox)


def profile(dataset_id: str):
    return build_profile(PatchRequest(dataset=DatasetRef(id=dataset_id), scales_m=[SCALE_M], relief_windows_m=[5000]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    out = Path(args.out) if args.out else data_dir() / "local" / "results"
    out.mkdir(parents=True, exist_ok=True)
    ensure_data()

    mars = profile(MARS)
    s = mars.scales[0]
    print(f"\nMARS reference: {mars.provenance.dataset_name}")
    print(f"  patch {mars.patch.width_m / 1000:.0f} x {mars.patch.height_m / 1000:.0f} km at ({mars.patch.center_lon:.2f} E, {mars.patch.center_lat:.2f} N); "
          f"elevation {mars.elevation.min:.0f} to {mars.elevation.max:.0f} m above the areoid; coverage {mars.coverage.valid_fraction:.1%}")
    print(f"  at {SCALE_M:.0f} m: slope mean {s.slope.stats.mean:.2f} deg, p90 {s.slope.stats.p90:.2f} deg, roughness (RMS height, median) {s.roughness.rms_height_m.median:.1f} m")

    try:  # Layer 6 is optional here: only its pure shape checks are used, never its database
        from terrawindow_report.shapes import dataset_refs, detect_kind
    except ImportError:
        detect_kind = dataset_refs = None

    for name in EARTH:
        cid = f"{name}-copernicus-glo30"
        earth = profile(cid)
        result = compare_profiles(mars, earth)
        path = out / f"compare_{MARS}_vs_{cid}.json"
        path.write_text(result.model_dump_json(indent=1), encoding="utf-8")
        print(f"\nMARS vs EARTH {name}  ({result.counts['within_tolerance']} within, {result.counts['outside_tolerance']} outside, {result.counts['not_assessed']} not assessed; a tally, not a score)")
        for c in result.criteria:
            if c.metric in ("slope_mean", "slope_p90", "roughness_rms_height_median") or c.metric.startswith("relief"):
                print(f"  {c.metric:32} Mars {c.reference:>9} Earth {c.candidate:>9}  {c.unit:8} {c.status}")
        if detect_kind:
            doc = json.loads(path.read_text(encoding="utf-8"))
            print(f"  Layer 6 shape check: kind={detect_kind(doc)}, datasets={[d for _, d in dataset_refs('compare', doc)]}")
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
