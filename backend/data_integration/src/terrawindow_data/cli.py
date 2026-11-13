"""Command line for the data store.

    terrawindow-data list                                  what can be fetched, and what is in the store
    terrawindow-data fetch lola-5mpp-site01 --products surface uncertainty slope
    terrawindow-data region copernicus-glo30 sp-crater -111.70 35.52 -111.56 35.65
    terrawindow-data validate path/to/file.tif --body moon
    terrawindow-data show lola-5mpp-site01
"""

from __future__ import annotations

import argparse
import json
import sys

from .catalog import CATALOG
from .store import data_dir, load_manifest


def _progress(done: int, total: int) -> None:
    if total:
        print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", file=sys.stderr, flush=True)
        if done >= total:
            print(file=sys.stderr)


def _print_validation(validation: dict) -> None:
    for c in validation["checks"]:
        detail = f"  ({c['detail']})" if c["detail"] else ""
        print(f"  [{c['status']:<4}] {c['check']:<28} {c['observed']}{detail}")
    print(f"  analysis-ready: {validation['ready']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="terrawindow-data", description="TERRAWINDOW Layer 2 data store")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="catalog and store contents")
    f = sub.add_parser("fetch", help="download a file dataset into the store")
    f.add_argument("dataset_id")
    f.add_argument("--products", nargs="+", default=None)
    f.add_argument("--force", action="store_true")
    r = sub.add_parser("region", help="cut a lon/lat region from a tiled dataset")
    r.add_argument("dataset_id")
    r.add_argument("name")
    r.add_argument("bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    v = sub.add_parser("validate", help="check any raster file")
    v.add_argument("path")
    v.add_argument("--body", default="earth", choices=["earth", "moon", "mars"])
    s = sub.add_parser("show", help="print the manifest record of a stored dataset")
    s.add_argument("dataset_id")
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            stored = load_manifest()["datasets"]
            print(f"store: {data_dir()}\n\ncatalog")
            for e in CATALOG.values():
                state = "in store" if e.id in stored else ("tiled, read on demand" if e.access == "tiled" else "not fetched")
                print(f"  {e.id:<22}{e.body:<7}{e.nominal_resolution_m:>5g} m  {state:<24}{e.name}")
            regions = {k: d for k, d in stored.items() if k not in CATALOG}
            if regions:
                print("\nregions and other stored datasets")
                for k, d in regions.items():
                    print(f"  {k:<40}{d['body']:<7}{d['path']}")
        elif args.command == "fetch":
            from .fetch import fetch_dataset

            record = fetch_dataset(args.dataset_id, args.products, force=args.force, progress=_progress)
            print(f"{args.dataset_id}: {', '.join(record['products'])} -> {record['path']}")
            _print_validation(record["validation"])
        elif args.command == "region":
            from .prepare import prepare_region

            record = prepare_region(args.dataset_id, args.name, *args.bbox)
            print(f"{record['id']} -> {record['path']}")
            _print_validation(record["validation"])
        elif args.command == "validate":
            from .validate import validate_raster

            report = validate_raster(args.path, body=args.body)
            _print_validation(report)
            print(json.dumps(report["summary"], indent=2))
            return 0 if report["ready"] else 1
        else:
            stored = load_manifest()["datasets"]
            if args.dataset_id not in stored:
                print(f"error: '{args.dataset_id}' is not in the store. Run: terrawindow-data fetch {args.dataset_id}", file=sys.stderr)
                return 1
            print(json.dumps(stored[args.dataset_id], indent=2))
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
