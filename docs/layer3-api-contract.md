# Layer 3 API contract (for the UI and Layers 4-6)

Base URL in development: `http://localhost:8000`. All bodies are JSON. The live schema is at
`/openapi.json`; a TypeScript client can be generated from it:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/layer3.d.ts
```

Calls that read remote tiles take 5-20 s the first time and are served from a disk cache after.

| Endpoint | Used by | Returns |
|---|---|---|
| `GET /health` | - | `{status, service, version}` |
| `GET /v1/datasets` | Mission Workspace | built-in datasets and default scales |
| `POST /v1/patches/profile` | Comparison Dashboard, Dossier | `TerrainProfile` |
| `POST /v1/patches/compare` | Comparison Dashboard | `ComparisonResult` |
| `POST /v1/discovery/screen` | Earth Analog Explorer | GeoJSON `FeatureCollection` |
| `POST /v1/patches/overlay` | map layers | PNG (base64) + corner coordinates |

## Shared request types

```ts
type BBox = {
  west: number; south: number; east: number; north: number;
  crs?: "geographic" | "native";   // geographic = lon/lat degrees (default); native = the raster's own CRS
};

type DatasetRef =                    // exactly one of id / uri / uris
  | { id: string }                   // "copernicus-glo30", or any id from GET /v1/datasets stored_datasets
  | { uri: string;  body?: "earth" | "moon" | "mars"; name?: string; vertical_scale?: number }
  | { uris: string[]; body?: "earth" | "moon" | "mars"; name?: string; vertical_scale?: number };
```

Prefer `id`. `GET /v1/datasets` returns `stored_datasets`: everything Layer 2 has fetched and
validated (for example `lola-5mpp-site01`, `sp-crater-copernicus-glo30`), each with `body`,
`ready`, `citation` and a `summary` (pixel size, extent, centre). For a stored id the body is
known and `bbox` may be omitted to use the whole raster; `copernicus-glo30` is global and always
needs a `bbox`.

`uri` is an `https://` GeoTIFF/COG, or a path relative to the data store.

## POST /v1/patches/profile

```json
{
  "dataset": { "id": "copernicus-glo30" },
  "bbox": { "west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62 },
  "scales_m": [30, 60, 120],
  "include_landcover": true
}
```

Optional: `relief_windows_m` (default `[300, 1000]`), `slope_thresholds_deg`
(default `[5, 10, 15, 20, 25]`), `min_coverage` (default `0.9`). Omit `scales_m` to get
30/60/120/240 m where the data supports them.

```ts
type Stats = {
  mean: number | null; median: number | null; std: number | null;
  p10: number | null; p25: number | null; p75: number | null;
  p90: number | null; p95: number | null; p99: number | null;
  min: number | null; max: number | null; n_valid: number;
};

type TerrainProfile = {
  patch: {
    body: "earth" | "moon" | "mars"; bbox: BBox;
    center_lon: number; center_lat: number;
    polygon_lonlat: [number, number][];        // closed ring of the analysed footprint
    width_m: number; height_m: number; area_km2: number;
  };
  provenance: Provenance;
  coverage: {
    valid_fraction: number; min_required: number; sufficient: boolean;
    largest_void_fraction: number; missing_sources: string[];
  };
  elevation: { unit: "metres"; min: number | null; max: number | null; mean: number | null; std: number | null; range: number | null };
  scales: {
    scale_m: number;
    status: "assessed" | "insufficient_coverage";
    coverage_fraction: number;
    grid_shape: [number, number];
    slope: null | {
      unit: "degrees"; baseline_m: number; stats: Stats; rms_slope_deg: number | null;
      fraction_steeper_than: Record<string, number>;          // key = threshold in degrees, e.g. "15"
      histogram: { bin_edges_deg: number[]; fractions: number[] };  // 1-degree bins, 0-90
    };
    roughness: null | { unit: "metres"; window_m: number; rms_height_m: Stats; tri_m: Stats };
  }[];
  relief: { window_m: number; grid_m: number; unit: "metres"; stats: Stats }[];
  landcover: null | {
    dataset: string; valid_fraction: number;
    classes: { code: number; label: string; fraction: number }[];   // sorted, largest first
    dominant_class: number | null; excluded_fraction: number | null;
    screen: "pass" | "fail" | "not_assessed"; reason: string | null;
  };
  skipped: { item: string; code: string; reason: string }[];   // requested but not computed, and why
  limitations: string[];                                        // show these next to the numbers
};

type Provenance = {
  dataset_id: string | null; dataset_name: string; sources: string[]; citation: string | null;
  native_crs: string; native_pixel_size_m: number;
  working_crs: string; working_pixel_size_m: number; resampling: string; vertical_unit: string;
  methods: Record<string, string>; engine_version: string; generated_at: string;
};
```

UI notes:
- When `scales[i].status` is `insufficient_coverage`, `slope` and `roughness` are `null`. Show
  "not enough data", not zero.
- `skipped` explains anything missing (a scale finer than the data, a patch too small for a scale).
- Plot the slope histogram from `bin_edges_deg` / `fractions`. Only overlay two sites' histograms
  when their `scale_m` matches.

## POST /v1/patches/compare

Each side is either a patch request to compute or a `TerrainProfile` you already hold.
`scales_m` at the top level applies to both sides so they share scales.

```json
{
  "reference": { "dataset": { "id": "lola-5mpp-site01" } },
  "candidate": { "dataset": { "id": "copernicus-glo30" },
                 "bbox": { "west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62 } },
  "scales_m": [30, 60],
  "tolerances": { "slope_mean_deg": 3, "roughness_rel": 0.5 }
}
```

Use `reference_profile` / `candidate_profile` instead of `reference` / `candidate` to pass profiles.

```ts
type ComparisonResult = {
  common_scales_m: number[];
  criteria: {
    metric: string;                  // slope_mean, slope_median, slope_p90, rms_slope,
                                     // fraction_steeper_than_15deg, slope_distribution_distance,
                                     // roughness_rms_height_median, relief_median_330m_window
    scale_m: number | null; unit: string;
    reference: number | null; candidate: number | null;
    difference: number | null;       // candidate - reference; a distance for slope_distribution_distance
    tolerance: number | null; tolerance_kind: "absolute" | "relative";
    normalized_difference: number | null;   // |difference| / allowed; <= 1 is within tolerance
    status: "within_tolerance" | "outside_tolerance" | "not_assessed";
    reason: string | null;
  }[];
  counts: { within_tolerance: number; outside_tolerance: number; not_assessed: number };
  notes: string[];
  tolerances: Record<string, number>;
  reference_profile: TerrainProfile;
  candidate_profile: TerrainProfile;
};
```

There is no overall similarity score, by design. `counts` is a tally for a summary chip, not a
percentage to rank sites by. Render `not_assessed` differently from `outside_tolerance`: one is
missing evidence, the other is a negative finding. Default tolerances are screening assumptions
the user should be able to change.

## POST /v1/discovery/screen

Cuts the bbox into square patches and checks each against the criteria.

```json
{
  "dataset": { "id": "copernicus-glo30" },
  "bbox": { "west": -111.75, "south": 35.50, "east": -111.55, "north": 35.65 },
  "patch_size_m": 3000,
  "criteria": {
    "slope_mean_deg": { "max": 8 },
    "slope_p90_deg": { "max": 20 },
    "fraction_steeper_than": { "threshold_deg": 15, "range": { "max": 0.2 } },
    "roughness_rms_height_m": { "min": 0.3 },
    "landcover": {}
  }
}
```

Every criterion is optional and takes `{min?, max?}`: `slope_mean_deg`, `slope_median_deg`,
`slope_p90_deg`, `roughness_rms_height_m`, `relief_m`. `"landcover": {}` turns on the WorldCover
screen with defaults (`excluded_classes`, `max_excluded_fraction: 0.2`); leave it out to skip land
cover. Pass `reference_profile` (a `TerrainProfile`) to derive any unset slope and roughness
ranges from it using `tolerances`. `include_rejected: false` returns candidates only.
Limits: `patch_size_m` at least 16 analysis cells (480 m at 30 m); at most 2500 patches per call.

Response is a GeoJSON `FeatureCollection` that MapLibre can take as a source directly:

```ts
type ScreenResponse = {
  type: "FeatureCollection";
  features: {
    type: "Feature"; id: string;                     // "r{row}c{col}"
    geometry: { type: "Polygon"; coordinates: [number, number][][] };   // lon/lat
    properties: {
      id: string;
      status: "candidate" | "rejected" | "insufficient_data";
      center_lon: number; center_lat: number; patch_size_m: number; scale_m: number;
      metrics: {
        coverage_fraction: number;
        slope_mean_deg: number | null; slope_median_deg: number | null;
        slope_p90_deg: number | null; slope_max_deg: number | null;
        roughness_rms_height_m: number | null; relief_m: number | null; elevation_mean_m: number | null;
        landcover_dominant?: string | null; landcover_excluded_fraction?: number | null;
      };
      criteria: { criterion: string; unit: string; value: number | null; min: number | null; max: number | null;
                  status: "pass" | "fail" | "not_assessed"; reason: string | null }[];
      not_assessed: string[];
    };
  }[];
  summary: { cells: number; candidate: number; rejected: number; insufficient_data: number; scale_m: number; patch_size_m: number };
  criteria: object;            // the criteria actually applied, including any derived from the reference
  provenance: Provenance;
  limitations: string[];
};
```

Colour the map by `properties.status`. A `candidate` passed every criterion that could be
assessed; it is a shortlist entry, not a suitability verdict. To drill in, send the feature's
ring bounds to `/v1/patches/profile`.

## POST /v1/patches/overlay

```json
{
  "dataset": { "id": "copernicus-glo30" },
  "bbox": { "west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62 },
  "layer": "hillshade",
  "sun_azimuth_deg": 120,
  "sun_elevation_deg": 7
}
```

`layer` is `slope` (default), `hillshade` or `elevation`. Optional `scale_m`, `slope_max_deg`
(top of the slope colour ramp, default 40).

```ts
type OverlayResponse = {
  layer: string; media_type: "image/png"; image_base64: string;
  coordinates: [number, number][];   // [lon, lat]: top-left, top-right, bottom-right, bottom-left
  width: number; height: number; scale_m: number;
  value_range: [number, number]; unit: string;
  legend: { value: number; color: string }[];
  provenance: Provenance;
};
```

```ts
map.addSource("terrain", {
  type: "image",
  url: `data:image/png;base64,${overlay.image_base64}`,
  coordinates: overlay.coordinates,
});
map.addLayer({ id: "terrain", type: "raster", source: "terrain", paint: { "raster-opacity": 0.7 } });
```

No-data pixels are transparent. Hillshade is simple shading for a given sun direction and has no
cast shadows; shadow modelling belongs to Layer 4.

## Errors

Every error has the same body, with an HTTP status of 400, 403, 404, 422 or 500:

```json
{ "error": { "code": "scale_not_supported", "message": "Requested grid spacing 5 m is finer than ...", "details": { "requested_m": 5, "native_pixel_size_m": 30.9 } } }
```

| Code | Status | Meaning |
|---|---|---|
| `invalid_request` | 400 / 422 | Body failed validation; `details.issues` lists the fields |
| `scale_not_supported` | 400 | Scale is finer than the dataset can support |
| `patch_too_small` | 400 | Patch has too few cells at the scale |
| `patch_too_large` | 400 | Bbox exceeds the pixel or patch-count limit |
| `source_not_allowed` | 403 | URI is not https and not inside the data folder |
| `dataset_not_found` | 404 | Unknown registry id |
| `source_unavailable` | 404 | No raster could be opened (no tile there, e.g. open ocean, or the source is down) |
| `internal_error` | 500 | Unexpected failure |

## For Layer 4 and Layer 5 (Python)

```python
from terrawindow_geo import build_profile, compare_profiles, extract_dem, screen_region
from terrawindow_geo.terrain.slope import gradients, hillshade, slope_aspect
```

`extract_dem(dataset, bbox, scale_m)` returns a `Patch`: `z` (float64, north-up, NaN = no data),
`transform` (affine), `crs`, `pixel_size_m`, plus `ring_lonlat()` and `center_lonlat()`.
`slope_aspect` returns slope in degrees and aspect as the downslope azimuth, clockwise from north.
