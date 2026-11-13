"""Terrain-processing validation (proposal, Test 1): our slope against the published one.

The NASA LOLA 5 m/pix site models ship with their own slope raster. This recomputes slope from
the surface raster with the Layer 3 kernel at the native 5 m grid and compares pixel by pixel.

    terrawindow-data fetch lola-5mpp-site01 --products slope
    python scripts/validate_lunar_slope.py [--site lola-5mpp-site01]

The published product may use a different kernel or baseline, so a small systematic offset is
expected; a large one would point to a unit, grid-alignment or orientation error.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import rasterio

from terrawindow_data import data_dir, load_manifest
from terrawindow_geo.terrain.slope import slope_aspect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", default="lola-5mpp-site01")
    args = parser.parse_args()

    record = load_manifest()["datasets"].get(args.site)
    if not record or "slope" not in record.get("products", {}):
        print(f"The slope product of {args.site} is not in the store. Run:\n  terrawindow-data fetch {args.site} --products slope", file=sys.stderr)
        return 2

    with rasterio.open(data_dir() / record["products"]["surface"]["path"]) as ds:
        surface = ds.read(1).astype("float64")
        pixel = abs(ds.res[0])
        grid = (ds.transform, ds.shape)
    with rasterio.open(data_dir() / record["products"]["slope"]["path"]) as ds:
        published = ds.read(1).astype("float64")
        if (ds.transform, ds.shape) != grid:
            print("Surface and slope rasters are not on the same grid.", file=sys.stderr)
            return 1

    ours, _aspect = slope_aspect(surface, pixel)
    ok = np.isfinite(ours) & np.isfinite(published)
    a, b = ours[ok], published[ok]
    diff = a - b
    print(f"site {args.site}: {ok.sum():,} pixels compared at {pixel:g} m")
    print(f"  published slope   mean {b.mean():6.2f}°   median {np.median(b):6.2f}°   p90 {np.percentile(b, 90):6.2f}°")
    print(f"  Layer 3 slope     mean {a.mean():6.2f}°   median {np.median(a):6.2f}°   p90 {np.percentile(a, 90):6.2f}°")
    print(f"  difference        mean {diff.mean():+6.3f}°   median |d| {np.median(np.abs(diff)):.3f}°   p95 |d| {np.percentile(np.abs(diff), 95):.3f}°")
    print(f"  correlation       r = {np.corrcoef(a, b)[0, 1]:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
