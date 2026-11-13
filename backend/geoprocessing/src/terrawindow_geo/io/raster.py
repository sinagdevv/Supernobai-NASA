"""Read a terrain patch from one or more rasters onto a square metric grid.

Everything downstream (slope, roughness, relief, Layer 4 horizon modelling) assumes the grid
returned here: north-up, square pixels, spacing in metres, NaN where there is no data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
import pyproj
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.warp import reproject

from ..config import get_settings
from ..errors import GeoError
from ..models import BBox

# Public buckets need no credentials; these options keep remote COG reads to a few range requests.
GDAL_ENV = dict(
    AWS_NO_SIGN_REQUEST="YES",
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff,.TIF",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    GDAL_HTTP_TIMEOUT="30",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
)

# Finer than native is never allowed; 5 % slack lets a "30 m" request use a 30.9 m dataset.
SCALE_SLACK = 0.95


@dataclass
class Patch:
    z: np.ndarray
    transform: Affine
    crs: CRS
    pixel_size_m: float
    native_pixel_size_m: float
    native_crs: str
    body: str = "earth"
    sources: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    resampling: str = "none"

    @property
    def shape(self) -> tuple[int, int]:
        return self.z.shape

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(left, bottom, right, top) in the working CRS."""
        h, w = self.z.shape
        left, top = self.transform @ (0, 0)
        right, bottom = self.transform @ (w, h)
        return left, bottom, right, top

    def _to_lonlat(self) -> pyproj.Transformer:
        working = pyproj.CRS.from_wkt(self.crs.to_wkt())
        return pyproj.Transformer.from_crs(working, working.geodetic_crs, always_xy=True)

    def ring_lonlat(self, col0: int = 0, row0: int = 0, col1: int | None = None, row1: int | None = None) -> list[list[float]]:
        """Closed [lon, lat] ring around a pixel window (default: the whole patch)."""
        h, w = self.z.shape
        col1 = w if col1 is None else col1
        row1 = h if row1 is None else row1
        corners = [(col0, row0), (col1, row0), (col1, row1), (col0, row1), (col0, row0)]
        xs, ys = zip(*(self.transform @ c for c in corners))
        lon, lat = self._to_lonlat().transform(xs, ys)
        return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat)]

    def center_lonlat(self) -> tuple[float, float]:
        h, w = self.z.shape
        x, y = self.transform @ (w / 2, h / 2)
        lon, lat = self._to_lonlat().transform(x, y)
        return float(lon), float(lat)

    def at_scale(self, scale_m: float) -> "Patch":
        """Aggregate to a coarser grid spacing by area averaging. Never refines."""
        factor = scale_m / self.pixel_size_m
        if abs(factor - 1) < 0.01:
            return self
        if factor < 1:
            raise GeoError(
                "scale_not_supported",
                f"Requested {scale_m:g} m is finer than the working grid ({self.pixel_size_m:g} m).",
            )
        h, w = self.z.shape
        k = round(factor)
        if abs(factor - k) < 0.01:
            z = _block_mean(self.z, k)
        else:
            nh, nw = int(h / factor), int(w / factor)
            if nh < 1 or nw < 1:
                raise GeoError("patch_too_small", f"Patch is smaller than one {scale_m:g} m cell.")
            z = np.full((nh, nw), np.nan)
            reproject(
                source=self.z,
                destination=z,
                src_transform=self.transform,
                src_crs=self.crs,
                src_nodata=np.nan,
                dst_transform=self.transform @ Affine.scale(factor),
                dst_crs=self.crs,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
        return replace(self, z=z, transform=self.transform @ Affine.scale(factor), pixel_size_m=float(scale_m))


def _block_mean(z: np.ndarray, k: int, min_valid: float = 0.5) -> np.ndarray:
    h, w = (z.shape[0] // k) * k, (z.shape[1] // k) * k
    if h == 0 or w == 0:
        raise GeoError("patch_too_small", "Patch is smaller than one cell at the requested scale.")
    blocks = z[:h, :w].reshape(h // k, k, w // k, k).swapaxes(1, 2).reshape(h // k, w // k, k * k)
    valid = np.isfinite(blocks)
    n = valid.sum(axis=2)
    total = np.where(valid, blocks, 0.0).sum(axis=2)
    out = np.full(n.shape, np.nan)
    ok = n >= max(1, math.ceil(min_valid * k * k))
    out[ok] = total[ok] / n[ok]
    return out


def _pyproj(crs: CRS) -> pyproj.CRS:
    return pyproj.CRS.from_wkt(crs.to_wkt())


def _rio(crs: pyproj.CRS) -> CRS:
    return CRS.from_wkt(crs.to_wkt())


def _is_metric(crs: CRS) -> bool:
    if not crs.is_projected:
        return False
    try:
        return abs(crs.linear_units_factor[1] - 1.0) < 1e-9
    except Exception:
        return False


def _local_metric_crs(src: pyproj.CRS, lon: float, lat: float, body: str) -> pyproj.CRS:
    """UTM on Earth; elsewhere (or near Earth's poles) an azimuthal grid centred on the patch."""
    if body == "earth" and abs(lat) <= 84:
        zone = min(60, int((lon + 180) // 6) + 1)
        return pyproj.CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)
    ell = src.ellipsoid
    b = ell.semi_minor_metre or ell.semi_major_metre
    return pyproj.CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +a={ell.semi_major_metre} +b={b} +units=m +no_defs"
    )


def _native_pixel_size_m(ds, src: pyproj.CRS, lat: float) -> float:
    rx, ry = abs(ds.res[0]), abs(ds.res[1])
    if ds.crs.is_projected:
        f = ds.crs.linear_units_factor[1]
        return max(rx, ry) * f
    a = src.ellipsoid.semi_major_metre
    return max(math.radians(rx) * a * math.cos(math.radians(lat)), math.radians(ry) * a)


def _open_all(uris: list[str]):
    opened, missing = [], []
    for uri in uris:
        try:
            opened.append((uri, rasterio.open(uri)))
        except RasterioIOError as exc:
            missing.append(f"{uri} ({str(exc).splitlines()[0][:160]})")
    return opened, missing


def extract_patch(
    uris: list[str],
    bbox: BBox,
    *,
    body: str = "earth",
    resolution_m: float | None = None,
    categorical: bool = False,
    like: Patch | None = None,
    vertical_scale: float = 1.0,
) -> Patch:
    """Read `bbox` from the rasters in `uris` (mosaicked) onto a metric grid.

    resolution_m: grid spacing; defaults to the native pixel size. Finer than native is refused.
    categorical:  nearest-neighbour sampling for class rasters (land cover).
    like:         reuse another patch's grid exactly (used to stack land cover on a DEM).
    """
    settings = get_settings()
    with rasterio.Env(**GDAL_ENV):
        opened, missing = _open_all(uris)
        if not opened:
            raise GeoError(
                "source_unavailable",
                "None of the source rasters could be opened (no tile covers this area, or the source is unreachable).",
                status=404,
                details={"sources": missing},
            )
        try:
            first = opened[0][1]
            if first.crs is None:
                raise GeoError("invalid_request", f"Raster has no coordinate reference system: {opened[0][0]}")
            src_crs = first.crs
            src_pp = _pyproj(src_crs)
            geodetic = src_pp.geodetic_crs

            # Patch centre in lon/lat on the dataset's body.
            if bbox.crs == "geographic":
                lon_c, lat_c = (bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2
            else:
                to_geo = pyproj.Transformer.from_crs(src_pp, geodetic, always_xy=True)
                lon_c, lat_c = to_geo.transform((bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2)

            native = _native_pixel_size_m(first, src_pp, lat_c)

            if like is not None:
                work_crs, res = like.crs, like.pixel_size_m
                dst_transform, (height, width) = like.transform, like.shape
                same_grid = False
            else:
                keep_native = _is_metric(src_crs)
                work_pp = src_pp if keep_native else _local_metric_crs(src_pp, lon_c, lat_c, body)
                work_crs = src_crs if keep_native else _rio(work_pp)
                res = float(resolution_m) if resolution_m else native
                if not categorical and res < SCALE_SLACK * native:
                    raise GeoError(
                        "scale_not_supported",
                        f"Requested grid spacing {res:g} m is finer than the dataset's native {native:.2f} m. "
                        "Upsampling would invent detail that was never measured.",
                        details={"requested_m": res, "native_pixel_size_m": round(native, 3)},
                    )
                from_crs = geodetic if bbox.crs == "geographic" else src_pp
                if from_crs == work_pp:
                    left, bottom, right, top = bbox.west, bbox.south, bbox.east, bbox.north
                else:
                    tr = pyproj.Transformer.from_crs(from_crs, work_pp, always_xy=True)
                    left, bottom, right, top = tr.transform_bounds(bbox.west, bbox.south, bbox.east, bbox.north, densify_pts=21)

                # Keep the source grid when nothing needs resampling, so values are copied exactly.
                same_grid = keep_native and abs(res - native) < 1e-6 * native
                ox, oy = (first.transform.c, first.transform.f) if same_grid else (0.0, 0.0)
                left = ox + math.floor((left - ox) / res) * res
                top = oy + math.ceil((top - oy) / res) * res
                width = max(1, math.ceil((right - left) / res - 1e-9))
                height = max(1, math.ceil((top - bottom) / res - 1e-9))
                dst_transform = Affine(res, 0, left, 0, -res, top)

            if width * height > settings.max_patch_pixels:
                raise GeoError(
                    "patch_too_large",
                    f"Patch would be {width} x {height} pixels at {res:g} m; the limit is {settings.max_patch_pixels:,} pixels. "
                    "Use a smaller bbox or a coarser scale.",
                    details={"width": width, "height": height, "limit": settings.max_patch_pixels},
                )

            if categorical:
                method = Resampling.nearest
            elif same_grid:
                method = Resampling.nearest
            elif res / native >= 1.5:
                method = Resampling.average
            else:
                method = Resampling.bilinear

            z = np.full((height, width), np.nan)
            for _uri, ds in opened:
                tile = np.full((height, width), np.nan)
                reproject(
                    source=rasterio.band(ds, 1),
                    destination=tile,
                    src_nodata=ds.nodata,
                    dst_transform=dst_transform,
                    dst_crs=work_crs,
                    dst_nodata=np.nan,
                    resampling=method,
                )
                fill = np.isnan(z) & np.isfinite(tile)
                z[fill] = tile[fill]
            native_crs = src_crs.to_string()
        finally:
            for _uri, ds in opened:
                ds.close()

    if not categorical and vertical_scale != 1.0:
        z *= vertical_scale

    return Patch(
        z=z,
        transform=dst_transform,
        crs=work_crs,
        pixel_size_m=float(res),
        native_pixel_size_m=float(native),
        native_crs=native_crs,
        body=body,
        sources=[u for u, _ in opened],
        missing_sources=missing,
        resampling="exact copy (source grid kept)" if method == Resampling.nearest and not categorical else method.name,
    )


def native_pixel_size(uris: list[str], bbox: BBox) -> float:
    """Native pixel size in metres at the bbox, from metadata only (no pixel reads)."""
    with rasterio.Env(**GDAL_ENV):
        opened, missing = _open_all(uris)
        if not opened:
            raise GeoError("source_unavailable", "None of the source rasters could be opened.", status=404, details={"sources": missing})
        try:
            ds = opened[0][1]
            src_pp = _pyproj(ds.crs)
            if bbox.crs == "geographic":
                lat = (bbox.south + bbox.north) / 2
            else:
                tr = pyproj.Transformer.from_crs(src_pp, src_pp.geodetic_crs, always_xy=True)
                lat = tr.transform((bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2)[1]
            return _native_pixel_size_m(ds, src_pp, lat)
        finally:
            for _uri, d in opened:
                d.close()
