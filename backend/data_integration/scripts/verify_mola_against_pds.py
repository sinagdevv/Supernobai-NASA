"""Check a Layer 2 MOLA region against the raw PDS bytes, independently of GDAL's PDS4 driver, and compare it with the USGS mosaic.

Layer 2 reads the PDS4 MEGDR tiles through GDAL. This script re-reads the same ground from the same tile as raw
big-endian int16, located from the tile's own label (5632 lines x 11520 samples, upper-left corner at 44 N, 0 E, 128 pixels/degree)
using plain NumPy and HTTP range requests, then compares every pixel. They must be identical.

With --usgs it also compares the region with the USGS Astropedia 463 m MOLA mosaic over the same ground. That product is not a copy
of the PDS grid: every USGS pixel equals the mean of a 2 x 2 block of PDS pixels (a half-pixel resampling), so it is smoother.

    python scripts/verify_mola_against_pds.py jezero-mola-megdr128 [--usgs]

Needs network access to pds-geosciences.wustl.edu (and planetarymaps.usgs.gov for --usgs). Exit code 0 only if the PDS check is exact.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request

import numpy as np
import rasterio

from terrawindow_data import store

PDS4 = "https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg128"
PPD = 128  # pixels per degree
TILE = "megt44n000hb"
TILE_LINES, TILE_SAMPLES = 5632, 11520  # PDS label: LINES, LINE_SAMPLES
TILE_NORTH, TILE_WEST = 44.0, 0.0  # PDS label: MAXIMUM_LATITUDE, WESTERNMOST_LONGITUDE
R_PDS = 3396000.0  # PDS4 label: a, b, c axis radius 3396.0 km
USGS = "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
R_USGS = 3396190.0


def fetch_rows(row0: int, row1: int) -> np.ndarray:
    """Rows row0..row1-1 of the tile as int16, by one HTTP range request."""
    rec = TILE_SAMPLES * 2
    req = urllib.request.Request(f"{PDS4}/{TILE}.img", headers={"Range": f"bytes={row0 * rec}-{row1 * rec - 1}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    if len(raw) != (row1 - row0) * rec:
        raise RuntimeError(f"expected {(row1 - row0) * rec} bytes, got {len(raw)}")
    return np.frombuffer(raw, dtype=">i2").reshape(row1 - row0, TILE_SAMPLES)


def agreement(a: np.ndarray, b: np.ndarray) -> dict:
    d = a.astype("float64") - b.astype("float64")
    return {
        "pearson_r": round(float(np.corrcoef(a.ravel(), b.ravel())[0, 1]), 5),
        "bias_m": round(float(d.mean()), 2),
        "rmse_m": round(float(np.sqrt((d**2).mean())), 2),
        "within_3m": round(float((np.abs(d) <= 3).mean()), 4),
        "max_abs_m": int(np.abs(d).max()),
    }


def main(region_id: str, usgs: bool) -> int:
    record = store.load_manifest()["datasets"][region_id]
    with rasterio.open(store.data_dir() / record["path"]) as ds:
        z = ds.read(1)
        t = ds.transform
        h, w = z.shape
    # upper-left corner of the region in degrees: the label's projection is centred on 180 E, so lon = 180 + x / R
    lon0 = 180 + math.degrees(t.c / R_PDS)
    lat0 = math.degrees(t.f / R_PDS)
    col0, row0 = round((lon0 - TILE_WEST) * PPD), round((TILE_NORTH - lat0) * PPD)
    if not (0 <= col0 and col0 + w <= TILE_SAMPLES and 0 <= row0 and row0 + h <= TILE_LINES):
        raise SystemExit(f"region is not inside {TILE} (0-90 E, 0-44 N); extend this script for other tiles")
    raw = fetch_rows(row0, row0 + h)[:, col0 : col0 + w].astype("int16")
    out = {
        "region": region_id,
        "pds4_product": f"urn:nasa:pds:mgs_mola_topography_derived:data_meg128:{TILE}",
        "pixels_compared": int(z.size),
        "identical_to_raw_pds_bytes": int((z == raw).sum()),
        "window_in_tile": {"first_line": row0, "first_sample": col0, "lines": h, "samples": w},
        "range_m": [int(z.min()), int(z.max())],
    }
    exact = bool((z == raw).all())
    if usgs:
        # The USGS grid is on a 3,396,190 m sphere with lon_0 = 0: lon = x / R. A USGS pixel is the mean of the 2 x 2 PDS pixels around its centre.
        with rasterio.open(USGS) as u:
            ucol, urow = round(lon0 * PPD + 23040) - 0, round((90 - lat0) * PPD)
            ucol = round((lon0 + 180) * PPD)
            win = rasterio.windows.Window(ucol, urow, w, h)
            uz = u.read(1, window=win).astype("float64")
        big = fetch_rows(row0 - 1, row0 + h)[:, col0 - 1 : col0 + w].astype("float64")  # one extra line and sample before the window
        block_mean = (big[:-1, :-1] + big[:-1, 1:] + big[1:, :-1] + big[1:, 1:]) / 4
        out["usgs_vs_pds_same_pixels"] = agreement(uz, z)
        out["usgs_vs_pds_2x2_mean"] = agreement(uz, block_mean)
    print(json.dumps(out, indent=2))
    return 0 if exact else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0] if args else "jezero-mola-megdr128", "--usgs" in sys.argv))
