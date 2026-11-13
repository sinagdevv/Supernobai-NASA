"""Command line: produce the same JSON the API returns, for precomputed demo data.

    terrawindow-geo profile --dataset copernicus-glo30 --bbox -111.66 35.55 -111.60 35.61 -o sp_crater.json
    terrawindow-geo compare reference.json candidate.json -o comparison.json
    terrawindow-geo screen --dataset copernicus-glo30 --bbox -111.8 35.4 -111.5 35.7 --slope-mean-max 15 -o candidates.geojson
    terrawindow-geo serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import GeoError
from .models import BBox, DatasetRef, PatchRequest, Range, ScreeningCriteria, ScreenRequest, TerrainProfile


def _dataset(args) -> DatasetRef:
    body = args.body
    if args.dataset.startswith(("http://", "https://")) or Path(args.dataset).suffix.lower() in {".tif", ".tiff", ".vrt", ".img"}:
        return DatasetRef(uri=args.dataset, body=body, name=args.name)
    return DatasetRef(id=args.dataset, body=body)


def _bbox(args) -> BBox:
    w, s, e, n = args.bbox
    return BBox(west=w, south=s, east=e, north=n, crs="native" if args.native_bbox else "geographic")


def _write(result, out: str | None) -> None:
    text = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)


def _add_source(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dataset", required=True, help="registry id (copernicus-glo30) or a GeoTIFF path / URL")
    p.add_argument("--bbox", required=True, nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--native-bbox", action="store_true", help="bbox is in the raster's own CRS, not lon/lat")
    p.add_argument("--body", default="earth", choices=["earth", "moon", "mars"])
    p.add_argument("--name", default=None)
    p.add_argument("-o", "--out", default=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="terrawindow-geo", description="TERRAWINDOW Layer 3 geospatial engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("profile", help="terrain profile of one patch")
    _add_source(p)
    p.add_argument("--scales", nargs="+", type=float, default=None)
    p.add_argument("--landcover", action="store_true")

    c = sub.add_parser("compare", help="compare two saved profiles")
    c.add_argument("reference")
    c.add_argument("candidate")
    c.add_argument("-o", "--out", default=None)

    s = sub.add_parser("screen", help="screen an area for candidate patches (GeoJSON)")
    _add_source(s)
    s.add_argument("--patch-size", type=float, default=3000.0)
    s.add_argument("--scale", type=float, default=None)
    s.add_argument("--slope-mean-max", type=float, default=None)
    s.add_argument("--slope-p90-max", type=float, default=None)

    v = sub.add_parser("serve", help="run the HTTP API")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    try:
        if args.command == "profile":
            from .profile import build_profile

            request = PatchRequest(dataset=_dataset(args), bbox=_bbox(args), scales_m=args.scales, include_landcover=args.landcover)
            _write(build_profile(request).model_dump(mode="json"), args.out)
        elif args.command == "compare":
            from .compare import compare_profiles

            ref = TerrainProfile.model_validate_json(Path(args.reference).read_text(encoding="utf-8"))
            cand = TerrainProfile.model_validate_json(Path(args.candidate).read_text(encoding="utf-8"))
            _write(compare_profiles(ref, cand).model_dump(mode="json"), args.out)
        elif args.command == "screen":
            from .discovery import screen_region

            criteria = ScreeningCriteria(
                slope_mean_deg=Range(max=args.slope_mean_max) if args.slope_mean_max is not None else None,
                slope_p90_deg=Range(max=args.slope_p90_max) if args.slope_p90_max is not None else None,
            )
            request = ScreenRequest(dataset=_dataset(args), bbox=_bbox(args), patch_size_m=args.patch_size, scale_m=args.scale, criteria=criteria)
            _write(screen_region(request), args.out)
        else:
            import uvicorn

            uvicorn.run("terrawindow_geo.api.app:app", host=args.host, port=args.port)
    except GeoError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
