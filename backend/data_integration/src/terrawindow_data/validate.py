"""Check that a raster is what the catalog says it is, before anything is computed from it.

Each check is pass / warn / fail with the observed value. A dataset is analysis-ready when no
check fails. Warnings are recorded and carried into provenance; they do not block use.
"""

from __future__ import annotations

import math

import numpy as np
import pyproj
import rasterio

from .catalog import BODY_RADIUS_M

# Plausible stored values per (body, kind). Lunar heights are relative to the 1737.4 km sphere.
PLAUSIBLE_RANGE = {
    ("earth", "elevation"): (-500.0, 9000.0),
    ("moon", "elevation"): (-10000.0, 11000.0),
    ("mars", "elevation"): (-9000.0, 22000.0),
}
SAMPLE_PX = 1024  # coverage and value range are estimated from an overview this size


def _check(name: str, status: str, observed, detail: str = "") -> dict:
    return {"check": name, "status": status, "observed": observed, "detail": detail}


def validate_raster(path: str, *, body: str, kind: str = "elevation", nominal_resolution_m: float | None = None) -> dict:
    """Validation report: {'ready': bool, 'checks': [...], 'summary': {...}}."""
    checks: list[dict] = []
    summary: dict = {}
    try:
        ds = rasterio.open(path)
    except Exception as exc:  # unreadable file: nothing else can be checked
        return {"ready": False, "checks": [_check("readable", "fail", None, str(exc).splitlines()[0])], "summary": {}}

    with ds:
        checks.append(_check("readable", "pass", f"{ds.driver}, {ds.width} x {ds.height}, {ds.count} band(s), {ds.dtypes[0]}"))

        if ds.crs is None:
            checks.append(_check("crs_present", "fail", None, "No coordinate reference system; the file cannot be georeferenced."))
            return {"ready": False, "checks": checks, "summary": summary}
        crs = pyproj.CRS.from_wkt(ds.crs.to_wkt())
        checks.append(_check("crs_present", "pass", crs.name))

        radius = crs.ellipsoid.semi_major_metre
        expected = BODY_RADIUS_M[body]
        ok = abs(radius - expected) / expected < 0.01
        checks.append(
            _check(
                "body_matches", "pass" if ok else "fail", round(radius, 1),
                "" if ok else f"CRS ellipsoid radius does not match {body} ({expected:.0f} m). Wrong body or wrong CRS.",
            )
        )

        if ds.crs.is_projected:
            unit, factor = ds.crs.linear_units_factor
            metric = abs(factor - 1.0) < 1e-9
            checks.append(_check("horizontal_unit", "pass" if metric else "warn", unit, "" if metric else "Not metres; Layer 3 will reproject."))
            px, py = abs(ds.res[0]) * factor, abs(ds.res[1]) * factor
        else:
            checks.append(_check("horizontal_unit", "pass", "degrees"))
            lat = (ds.bounds.bottom + ds.bounds.top) / 2
            px = math.radians(abs(ds.res[0])) * radius * math.cos(math.radians(lat))
            py = math.radians(abs(ds.res[1])) * radius
        pixel = max(px, py)
        summary["pixel_size_m"] = round(pixel, 3)

        if ds.crs.is_projected:
            square = abs(px - py) <= 1e-6 * pixel
            checks.append(_check("square_pixels", "pass" if square else "warn", [round(px, 4), round(py, 4)]))
        if nominal_resolution_m:
            close = abs(pixel - nominal_resolution_m) / nominal_resolution_m <= 0.1
            checks.append(
                _check(
                    "resolution_as_catalogued", "pass" if close else "warn", round(pixel, 3),
                    "" if close else f"Catalog says {nominal_resolution_m:g} m. Use the observed value.",
                )
            )

        checks.append(
            _check("nodata_declared", "pass" if ds.nodata is not None else "warn", ds.nodata,
                   "" if ds.nodata is not None else "No nodata value; voids cannot be told from data.")
        )

        scale = max(1, math.ceil(max(ds.width, ds.height) / SAMPLE_PX))
        sample = ds.read(1, out_shape=(max(1, ds.height // scale), max(1, ds.width // scale)), masked=True).astype("float64")
        values = sample.compressed()
        values = values[np.isfinite(values)]
        valid = values.size / sample.size if sample.size else 0.0
        summary["valid_fraction"] = round(valid, 4)
        checks.append(
            _check("has_data", "pass" if valid >= 0.5 else ("warn" if valid > 0 else "fail"), round(valid, 4),
                   "" if valid >= 0.5 else "Less than half of the raster holds data.")
        )

        if values.size:
            lo, hi = float(values.min()), float(values.max())
            summary["value_range"] = [round(lo, 2), round(hi, 2)]
            plausible = PLAUSIBLE_RANGE.get((body, kind))
            if plausible:
                ok = plausible[0] <= lo and hi <= plausible[1]
                checks.append(
                    _check(
                        "values_plausible_in_metres", "pass" if ok else "warn", [round(lo, 2), round(hi, 2)],
                        "" if ok else f"Outside {plausible} m for {body}. Heights may be in km or use another datum; set vertical_scale.",
                    )
                )

        summary.update(
            crs=ds.crs.to_string(),
            width=ds.width,
            height=ds.height,
            dtype=ds.dtypes[0],
            nodata=ds.nodata,
            bounds_native=[round(v, 3) for v in ds.bounds],
            extent_km=[round(ds.width * px / 1000, 2), round(ds.height * py / 1000, 2)],
        )
        to_geo = pyproj.Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        lon, lat = to_geo.transform((ds.bounds.left + ds.bounds.right) / 2, (ds.bounds.bottom + ds.bounds.top) / 2)
        summary["center_lonlat"] = [round(float(lon), 5), round(float(lat), 5)]

    return {"ready": not any(c["status"] == "fail" for c in checks), "checks": checks, "summary": summary}
