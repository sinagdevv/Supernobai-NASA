# TERRAWINDOW Layer 3: Geospatial Processing Engine

Reads elevation rasters for Earth and planetary surfaces and turns a patch of terrain into
measurements: slope, roughness, local relief, land cover and data coverage, each at an explicit
spatial scale and with its provenance and limitations attached.

It is both a Python library (for Layers 4 and 5) and a FastAPI service (for the UI).
The request and response shapes for the UI are in [docs/layer3-api-contract.md](../../docs/layer3-api-contract.md).

## Setup

Python 3.12 or 3.13. The rasterio wheel bundles GDAL, so nothing else needs installing.

```bash
cd backend/geoprocessing
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python`.

## Run

```bash
.venv/Scripts/python -m uvicorn terrawindow_geo.api.app:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs. OpenAPI schema: http://localhost:8000/openapi.json.

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m pytest -m network
.venv/Scripts/python scripts/validation_demo.py --out data/validation
```

The default test run uses synthetic rasters with known answers and needs no internet. The
`network` tests and the validation demo read real Copernicus GLO-30 and ESA WorldCover tiles.

## Use as a library

```python
from terrawindow_geo import build_profile, compare_profiles, extract_dem, screen_region
from terrawindow_geo.models import BBox, DatasetRef, PatchRequest

site = BBox(west=-111.67, south=35.55, east=-111.59, north=35.62)
profile = build_profile(PatchRequest(dataset=DatasetRef(id="copernicus-glo30"), bbox=site, scales_m=[30, 60]))

# Layer 4: elevation on a north-up metric grid (NaN = no data), for horizon and shadow modelling
dem = extract_dem(DatasetRef(id="copernicus-glo30"), site, scale_m=30)
dem.z, dem.transform, dem.crs, dem.pixel_size_m
```

`terrawindow_geo.terrain.slope` also exposes `slope_aspect`, `gradients` and `hillshade`.

## Command line

Writes the same JSON the API returns, for precomputing demo data.

```bash
terrawindow-geo profile --dataset copernicus-glo30 --bbox -111.67 35.55 -111.59 35.62 -o sp_crater.json
terrawindow-geo screen --dataset copernicus-glo30 --bbox -111.75 35.50 -111.55 35.65 --slope-mean-max 8 -o candidates.geojson
terrawindow-geo compare reference.json candidate.json -o comparison.json
terrawindow-geo profile --dataset data/lunar/site.tif --body moon --native-bbox --bbox -2000 -2000 2000 2000 --scales 30 60
```

## Data sources

| Source | How to reference it |
|---|---|
| Copernicus DEM GLO-30 (public COGs on AWS) | `{"id": "copernicus-glo30"}` |
| ESA WorldCover 10 m 2021 | used automatically for land cover on Earth |
| Anything from Layer 2 (lunar, Mars, regional DEMs) | `{"uri": "<https URL or path inside the data folder>", "body": "moon"}` |

Any GeoTIFF/COG that GDAL can read works. Through the API, local files must be inside the data
folder (`TWGEO_DATA_DIR`, default `backend/geoprocessing/data/`, not versioned); the library has
no such restriction. Lunar polar products already in a metric projection are processed on their
own grid; use `"crs": "native"` in the bbox to address them in projected metres. If a raster
stores heights in kilometres, set `"vertical_scale": 1000`.

No lunar raster ships with this layer. Lunar reference profiles need a file from Layer 2
(for example the PGDA south-polar products listed in the proposal).

## Method

| Quantity | How it is computed |
|---|---|
| Working grid | Patch is reprojected to a square metric grid: the UTM zone of the patch on Earth, the source grid for metric planetary projections, otherwise an azimuthal grid centred on the patch. |
| Scale | Each metric is computed on a grid of a stated spacing. Coarser scales are area averages. A scale finer than the source's native pixel size is refused (5 % slack, so 30.9 m GLO-30 serves the nominal 30 m scale). |
| Slope | Horn (1981) 3x3 kernel, degrees. Reported baseline is twice the grid spacing. |
| Roughness | RMS of elevation after removing the 5x5-cell moving mean, so a uniform tilt contributes nothing. Also the Terrain Ruggedness Index (Riley et al. 1999). |
| Relief | Maximum minus minimum elevation in a square moving window. |
| Coverage | Fraction of cells with data. Below `min_coverage` (default 0.9) metrics are withheld, not computed on partial data. Voids are never filled. |
| Land cover | ESA WorldCover class fractions; a patch fails the screen when excluded classes (trees, cropland, built-up, snow/ice, water, wetland) exceed a set fraction. |
| Comparison | Per criterion: reference value, candidate value, difference, tolerance, status. Slope distributions are compared with the Wasserstein distance. |

Two rules from the proposal are enforced in code, not left to the caller:

1. **Compatible scales.** A 5 m lunar model and a 30 m Earth DEM are only compared at 30 m or
   coarser. Asking for 5 m on Earth data returns `scale_not_supported`.
2. **No universal score.** A comparison returns one result per criterion plus a tally of
   statuses. `not_assessed` (missing evidence) is kept separate from `outside_tolerance`
   (a negative finding).

## Validation demo

`scripts/validation_demo.py` profiles the SP Crater lava field in the San Francisco Volcanic
Field, Arizona (where NASA ran the JETT5 Artemis III simulations) and irrigated cropland in the
Imperial Valley, California, as a deliberately unsuitable control. Result on GLO-30 at 30 m:

| | slope mean | slope p90 | steeper than 15° | RMS height | land cover |
|---|---|---|---|---|---|
| SP Crater | 5.62° | 15.08° | 10.1 % | 0.76 m | grassland 90 %, bare 9 %: pass |
| Imperial Valley | 0.35° | 0.69° | 0.0 % | 0.13 m | cropland 66 %: fail |

24 of 35 criteria fall outside tolerance and the land-cover screen rejects the control.

## Limitations

- Terrain metrics from orbit cannot establish soil strength, wheel traction or field safety.
- At 30 m, rocks, small craters and ruts that matter to a rover are invisible.
- GLO-30 is a surface model: vegetation and buildings add height and apparent roughness.
- Near-native resampling is bilinear, which smooths slightly; the method used is in every response.
- Comparison tolerances and screening thresholds are adjustable assumptions, not validated
  mission requirements. Mission-specific criteria belong to Layer 5.
- Hillshade overlays have no cast shadows. Horizon and shadow modelling is Layer 4.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `TWGEO_DATA_DIR` | `./data` | Folder the API may read local rasters from |
| `TWGEO_CACHE_DIR` | `<data dir>/cache` | Where API results are cached as JSON |
| `TWGEO_CACHE` | `1` | Set `0` to disable the cache |
| `TWGEO_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins |
| `TWGEO_ALLOW_ANY_LOCAL_PATH` | `0` | Let the API read rasters outside the data folder |
| `TWGEO_MAX_PATCH_PIXELS` | `16000000` | Largest grid one request may read |
| `TWGEO_MAX_SCREEN_CELLS` | `2500` | Most patches one screening request may produce |
