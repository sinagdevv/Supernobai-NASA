# Layer 5 — Mission Suitability and Evidence Engine

## Purpose and boundary

Layer 5 evaluates a Layer 3 terrain profile against a caller-defined mission
profile and may accept a serialized Layer 4 temporal result. It returns
criterion-level assessments, evidence records, provenance, completeness
information, and suitability gaps.

The relevant processing path is:

1. Layer 2 retrieves or prepares source datasets in the shared data store.
2. Layer 3 reads the selected elevation/land-cover sources and computes
   terrain metrics on the requested analysis grid.
3. Layer 4 evaluates the selected body's solar geometry, terrain illumination,
   shadow classifications, and temporal rehearsal windows.
4. Layer 5 obtains the Layer 3 profile from the candidate's source request,
   applies the caller's mission criteria, and records the result and evidence.

Layer 5 is part of the Layer 3 FastAPI application. It does not independently
calculate illumination, shadows, solar geometry, or temporal windows. It
validates and interprets a serialized Layer 4 result when one is supplied; it
does not rerun Layer 4 science.

For Layer 3, the required input is a `PatchRequest` describing an accessible
dataset and the candidate patch. The API computes the profile itself; callers
cannot submit client-computed Layer 3 metric values. A prior
`POST /v1/patches/profile` call is useful for inspection but is not required.
Layer 4 output is optional at the request level. Supply it when you want
Layer 4 criteria to have an external value to assess; if it is omitted, those
criteria remain unavailable and follow their configured missing-data
behavior. Supplied Layer 4 values remain external claims even when their
metadata matches.

Mission thresholds and completeness categories are caller-defined assumptions,
not validated mission standards. Layer 5 does not establish rover safety,
mobility, mission approval, or operational readiness.

## Installation and setup

The package metadata in [`pyproject.toml`](../backend/geoprocessing/pyproject.toml)
declares Python `>=3.12`. The repository setup uses Python 3.13. Runtime
dependencies are NumPy, SciPy, Rasterio, pyproj, FastAPI, Uvicorn, Pydantic,
and Pillow. The `dev` extra adds pytest and httpx. Rasterio's wheel bundles
GDAL; no separate GDAL installation is specified by the project.

From the repository root, on Windows PowerShell:

```powershell
Set-Location backend\geoprocessing
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn terrawindow_geo.api.app:app --reload --port 8000
```

Use an installed Python 3.12 or later in place of `-3.13` if needed. The same
commands are documented in the [Layer 3 geoprocessing README](../backend/geoprocessing/README.md).
On macOS/Linux, create the environment with `python3 -m venv .venv`, then use
`.venv/bin/python -m pip install -e ".[dev]"` and
`.venv/bin/python -m uvicorn terrawindow_geo.api.app:app --reload --port 8000`.
No activation step is required when invoking the environment's Python
executable directly.

Verify the service from another terminal:

```powershell
curl.exe -i http://127.0.0.1:8000/health
curl.exe -i http://127.0.0.1:8000/v1/suitability/metrics
```

The health endpoint returns JSON with `status: "ok"`, service name, and
version. Interactive API documentation is at
<http://127.0.0.1:8000/docs>; the OpenAPI document is at
<http://127.0.0.1:8000/openapi.json>.

The API has no Layer 5-specific environment variables. It uses the Layer 3
settings below; set them before starting the process. Settings are read when
the application starts.

| Variable | Default | Effect |
|---|---|---|
| `TWGEO_DATA_DIR` | `TERRAWINDOW_DATA_DIR`, otherwise `backend/data/` | Shared Layer 2 dataset store. |
| `TERRAWINDOW_DATA_DIR` | `backend/data/` when `TWGEO_DATA_DIR` is unset | Fallback data-store location. |
| `TWGEO_CACHE_DIR` | `<data dir>/cache` | JSON response/profile cache directory. |
| `TWGEO_CACHE` | `1` | Set to `0`, `false`, `no`, or `off` to disable caching. |
| `TWGEO_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed browser origins. |
| `TWGEO_ALLOW_ANY_LOCAL_PATH` | `0` | Allows API requests to read local rasters outside the data store when enabled. |
| `TWGEO_MAX_PATCH_PIXELS` | `16000000` | Maximum raster grid size for a request. |
| `TWGEO_MAX_SCREEN_CELLS` | `2500` | Maximum patches for a Layer 3 screening request; not used by Layer 5 assessment. |

For API requests, HTTP(S) raster URLs are allowed. Local raster paths must
resolve inside the configured data directory unless
`TWGEO_ALLOW_ANY_LOCAL_PATH` is enabled. Prefer dataset IDs registered by
Layer 2 or the built-in `copernicus-glo30` ID. The built-in Copernicus COG
source requires network access; use data already stored by Layer 2 when
working offline.

## API

### `GET /v1/suitability/metrics`

Returns the supported metric catalog (ID, source layer, unit, required
selectors, and description), comparison operators, criterion and overall
statuses, missing-data behaviors, evidence trust statuses, and spatial
association statuses.

- **Method/path:** `GET /v1/suitability/metrics`
- **Parameters/body:** none
- **Headers:** `Accept: application/json` is recommended; no authentication
  header is required.

```powershell
curl.exe -H "Accept: application/json" http://127.0.0.1:8000/v1/suitability/metrics
```

Response shape (only one metric is shown; the endpoint returns the full
catalog):

```json
{
  "metrics": [
    {
      "id": "terrain.slope.mean_deg",
      "source_layer": "layer3",
      "unit": "degrees",
      "description": "Mean Horn slope in degrees at the selected grid scale.",
      "selectors": ["scale_m"]
    }
  ],
  "operators": ["gt", "gte", "lt", "lte", "eq", "within_range"],
  "criterion_statuses": ["PASS", "FAIL", "UNVERIFIED", "INDETERMINATE", "NOT_ASSESSED"],
  "overall_statuses": ["SUITABLE", "NOT_SUITABLE", "INDETERMINATE", "PARTIALLY_ASSESSED"],
  "missing_data_behaviors": ["INDETERMINATE", "NOT_ASSESSED"],
  "evidence_trust_statuses": ["SERVER_COMPUTED", "UNVERIFIED_EXTERNAL", "NOT_SUPPLIED"],
  "spatial_association_statuses": [
    "MATCHED_METADATA_UNVERIFIED",
    "MISMATCHED",
    "UNPAIRED"
  ],
  "mission_profile_completeness": "SUITABLE requires a non-empty required_categories declaration and at least one required criterion in every declared category."
}
```

### `POST /v1/suitability/assess`

- **Method/path:** `POST /v1/suitability/assess`
- **Required top-level fields:** `candidate_id`, `candidate`, and
  `mission_profile`.
- **Optional top-level fields:** `candidate_name` and `layer4_result`.
- **Headers:** `Content-Type: application/json` and
  `Accept: application/json`; no authentication header is required.

`candidate` is a Layer 3 `PatchRequest`. Its `dataset` is required and must
specify exactly one of `id`, `uri`, or `uris`. The dataset's `body` defaults
to `earth`; `vertical_scale` defaults to `1.0` and multiplies stored elevation
values to metres. The API permits HTTP(S) sources and local rasters inside the
configured data directory by default. Optional `name` is a caller-provided
display label. A bbox with `crs: "geographic"` uses longitude/latitude degrees;
`crs: "native"` uses the source raster's native coordinates.

| Candidate field | Required/default | Behavior |
|---|---|---|
| `dataset` | Required | One registry/Layer 2 `id`, one `uri`, or a list of `uris`. |
| `bbox` | Optional in the model | Required for a global registry dataset or multiple rasters; omit only for a single-file raster to use its full extent. |
| `scales_m` | Defaults to supported 30/60/120/240 m scales | Any requested scale finer than the source supports is rejected. |
| `relief_windows_m` | `[300, 1000]` | Layer 3 relief-window selectors. |
| `slope_thresholds_deg` | `[5, 10, 15, 20, 25]` | Layer 3 slope fraction thresholds. |
| `min_coverage` | `0.9` | Minimum valid-elevation fraction for terrain summaries. |
| `include_landcover` | `false` | Requests Earth WorldCover metrics when set to `true`. |

`mission_profile` requires an ID, name, description, and 1–100 criteria.
`required_categories` is optional and defaults to an empty list; it must be
non-empty, with at least one required criterion in each declared category, for
`SUITABLE` to be possible.

The following request uses only Layer 3 criteria, so `layer4_result` is
explicitly `null`. The Layer 4 handoff workflow below shows how to replace it
with actual serialized Layer 4 output.

```json
{
  "candidate_id": "sp-crater-demo",
  "candidate_name": "SP Crater demonstration patch",
  "candidate": {
    "dataset": {"id": "copernicus-glo30"},
    "bbox": {
      "west": -111.67,
      "south": 35.55,
      "east": -111.59,
      "north": 35.62,
      "crs": "geographic"
    },
    "scales_m": [30, 60],
    "min_coverage": 0.9,
    "include_landcover": false
  },
  "mission_profile": {
    "id": "surface-access-demo",
    "name": "Surface access demonstration",
    "description": "Illustrative terrain screening criteria; not a validated mission standard.",
    "required_categories": ["terrain", "data-coverage"],
    "criteria": [
      {
        "id": "mean-slope-30m",
        "name": "Mean slope",
        "category": "terrain",
        "description": "Keep the mean 30 m terrain slope at or below the selected limit.",
        "source_layer": "layer3",
        "source_metric": "terrain.slope.mean_deg",
        "operator": "lte",
        "target_value": 15.0,
        "unit": "degrees",
        "required": true,
        "missing_data_behavior": "INDETERMINATE",
        "rationale": "Illustrative threshold only; set from mission-specific requirements.",
        "scale_m": 30
      },
      {
        "id": "elevation-coverage",
        "name": "Elevation coverage",
        "category": "data-coverage",
        "description": "Require at least 90 percent valid elevation coverage.",
        "source_layer": "layer3",
        "source_metric": "terrain.coverage.valid_fraction",
        "operator": "gte",
        "target_value": 0.9,
        "unit": "fraction",
        "required": true,
        "missing_data_behavior": "INDETERMINATE",
        "rationale": "The coverage criterion makes the data-support requirement explicit."
      }
    ]
  },
  "layer4_result": null
}
```

Submit the example after saving it as `assessment-request.json`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/v1/suitability/assess `
  -H "Content-Type: application/json" `
  -H "Accept: application/json" `
  --data-binary "@assessment-request.json"
```

On success, the response is a `MissionAssessment` JSON object with:

- assessment and candidate identity, including the Layer 3 patch metadata ID;
- mission profile name/ID and `overall_status` plus its explanation;
- profile completeness and optional spatial-association checks;
- one `criterion_results` item and one linked `evidence` record per configured
  criterion;
- Layer 3 and optional Layer 4 provenance summaries;
- `suitability_gaps` and `uncertainty_and_limitations`.

The following is a shape-complete illustrative response for a successful
Layer 3-only assessment. Numeric values and provenance strings are examples,
not results from a live dataset:

```json
{
  "assessment_id": "7efcece2-693a-45b2-b8fa-638770871f3c",
  "candidate": {
    "id": "sp-crater-demo",
    "name": "SP Crater demonstration patch",
    "body": "earth",
    "dataset_id": "copernicus-glo30",
    "bbox": {
      "west": -111.67,
      "south": 35.55,
      "east": -111.59,
      "north": 35.62,
      "crs": "geographic"
    },
    "center_lon": -111.63,
    "center_lat": 35.585,
    "area_km2": 70.0,
    "patch_identity_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "mission_profile_id": "surface-access-demo",
  "mission_profile_name": "Surface access demonstration",
  "mission_profile_description": "Illustrative terrain screening criteria; not a validated mission standard.",
  "assessed_at_utc": "2026-11-15T00:00:00Z",
  "overall_status": "SUITABLE",
  "overall_explanation": "Every required and optional criterion passed using the configured evidence; this is not a safety or operational-readiness finding.",
  "profile_completeness": {
    "status": "COMPLETE",
    "required_categories": ["terrain", "data-coverage"],
    "category_statuses": {"terrain": "PASS", "data-coverage": "PASS"},
    "note": "Completeness categories are mission-profile declarations, not a universal rover-suitability standard."
  },
  "spatial_association": null,
  "criterion_results": [
    {
      "criterion_id": "mean-slope-30m",
      "name": "Mean slope",
      "category": "terrain",
      "description": "Keep the mean 30 m terrain slope at or below the selected limit.",
      "rationale": "Illustrative threshold only; set from mission-specific requirements.",
      "source_layer": "layer3",
      "source_metric": "terrain.slope.mean_deg",
      "scale_m": 30.0,
      "window_m": null,
      "threshold_deg": null,
      "required": true,
      "status": "PASS",
      "measured_value": 8.21,
      "claimed_value": null,
      "unit": "degrees",
      "operator": "lte",
      "target_value": 15.0,
      "target_range": null,
      "equality_tolerance": null,
      "evidence_id": "7efcece2-693a-45b2-b8fa-638770871f3c:evidence:mean-slope-30m",
      "explanation": "Measured 8.21 degrees; required <= 15.0 degrees. Criterion PASS."
    },
    {
      "criterion_id": "elevation-coverage",
      "name": "Elevation coverage",
      "category": "data-coverage",
      "description": "Require at least 90 percent valid elevation coverage.",
      "rationale": "The coverage criterion makes the data-support requirement explicit.",
      "source_layer": "layer3",
      "source_metric": "terrain.coverage.valid_fraction",
      "scale_m": null,
      "window_m": null,
      "threshold_deg": null,
      "required": true,
      "status": "PASS",
      "measured_value": 0.98,
      "claimed_value": null,
      "unit": "fraction",
      "operator": "gte",
      "target_value": 0.9,
      "target_range": null,
      "equality_tolerance": null,
      "evidence_id": "7efcece2-693a-45b2-b8fa-638770871f3c:evidence:elevation-coverage",
      "explanation": "Measured 0.98 fraction; required >= 0.9 fraction. Criterion PASS."
    }
  ],
  "evidence": [
    {
      "evidence_id": "7efcece2-693a-45b2-b8fa-638770871f3c:evidence:mean-slope-30m",
      "source_layer": "layer3",
      "source_identity": "layer3-patch-metadata-fingerprint",
      "source_metric": "terrain.slope.mean_deg",
      "value": 8.21,
      "claimed_value": null,
      "unit": "degrees",
      "evidence_status": "AVAILABLE",
      "trust_status": "SERVER_COMPUTED",
      "spatial_association_status": "NOT_APPLICABLE",
      "execution_status": "PASS",
      "data_status": "AVAILABLE",
      "scientific_validation_status": "NOT_REPORTED",
      "timestamp_utc": "2026-11-15T00:00:00Z",
      "interval_start_utc": null,
      "interval_end_utc": null,
      "provenance": {"dataset_id": "copernicus-glo30"},
      "quality": {"sample_count": 12000, "sample_grid_cells": 15000},
      "uncertainty": null,
      "limitations": ["Illustrative sample; terrain metrics are not rover-scale hazard clearance."]
    },
    {
      "evidence_id": "7efcece2-693a-45b2-b8fa-638770871f3c:evidence:elevation-coverage",
      "source_layer": "layer3",
      "source_identity": "layer3-patch-metadata-fingerprint",
      "source_metric": "terrain.coverage.valid_fraction",
      "value": 0.98,
      "claimed_value": null,
      "unit": "fraction",
      "evidence_status": "AVAILABLE",
      "trust_status": "SERVER_COMPUTED",
      "spatial_association_status": "NOT_APPLICABLE",
      "execution_status": "PASS",
      "data_status": "AVAILABLE",
      "scientific_validation_status": "NOT_REPORTED",
      "timestamp_utc": "2026-11-15T00:00:00Z",
      "interval_start_utc": null,
      "interval_end_utc": null,
      "provenance": {"dataset_id": "copernicus-glo30"},
      "quality": {"valid_cell_count": 14700, "total_cell_count": 15000},
      "uncertainty": null,
      "limitations": ["Coverage does not establish source-raster authenticity."]
    }
  ],
  "suitability_gaps": [],
  "layer3_provenance": {"dataset_id": "copernicus-glo30"},
  "layer4_provenance": null,
  "uncertainty_and_limitations": [
    "Example response only; not a live assessment.",
    "Layer 3 source provenance is not an independent scientific validation."
  ]
}
```

Common error responses use the existing `{"error":{"code","message","details"}}`
envelope. Request/schema and Layer 4 body mismatches return HTTP 422 with
`code: "invalid_request"`; for example, body disagreement reports both body
identifiers. Processing-time `invalid_request` errors may return HTTP 400.
The source-access layer can return 403 `source_not_allowed` for disallowed
local paths and 404 `dataset_not_found`. `source_unavailable` can return 400
or 404 depending on the point at which the raster open fails. Raster profiling
may also return `scale_not_supported`, `patch_too_small`, or
`patch_too_large` (processing errors use HTTP 400). Unexpected server errors
return 500 `internal_error`. See the response body for structured details; do
not treat an error response as a partial assessment.

## End-to-end workflow

1. **Prepare the candidate source.** Use `GET /v1/datasets` to inspect built-in
   and Layer 2-registered IDs. For a registered single-file raster, `dataset`
   can be an ID and `bbox` can be omitted to profile the full raster. For a
   global dataset, provide a geographic longitude/latitude bounding box. You
   can preview the profile by sending the example's `candidate` object as the
   body to `POST /v1/patches/profile`; Layer 5 itself computes or loads this
   profile from the same `candidate` request.
2. **Run Layer 4 if its evidence is needed.** Use the selected-body workflow
   documented in the [Layer 4 guide](../solar_geometry_engine/LAYER4_DOCUMENTATION.md)
   to produce a `RehearsalEvaluation`; Layer 4 does not expose an HTTP endpoint
   in this repository. Do not copy its claims into hand-written values when
   the actual object/serialization is available.
3. **Build the request.** Start with the required `candidate_id`, `candidate`,
   and `mission_profile` fields. `candidate_name` and `layer4_result` are
   optional. In the process that has the Layer 4 result, serialize its actual
   output with the Layer 4 handoff type:

   ```python
   import json
   from pathlib import Path

   from rehearsal.windows import Layer5TemporalInput

   # Run this in the process/environment that produced evaluation.
   request_payload = json.loads(
       Path("assessment-request.json").read_text(encoding="utf-8")
   )
   layer4_handoff = Layer5TemporalInput(
       selected_body=evaluation.body,
       layer4_result=evaluation,
   ).to_dict()
   request_payload["layer4_result"] = layer4_handoff
   Path("assessment-request.json").write_text(
       json.dumps(request_payload),
       encoding="utf-8",
   )
   ```

   The wrapper serializes as `{"selected_body": ..., "layer4_result": ...}`.
   Layer 5 accepts this wrapper or the direct
   `evaluation.to_dict()` object. For the wrapper, `selected_body` must match
   the nested result's `body`; the API rejects a disagreement. If Layer 4
   output is already stored as JSON, load that exact JSON and assign it to
   `request_payload["layer4_result"]`. The Layer 4 record includes timestamps,
   observations, intervals, criteria, provenance, kernel identities,
   limitations, and evidence-state claims; use the producer's serializer
   rather than manually synthesizing these fields. The Layer 5 service itself
   requires only the resulting JSON, not the Layer 4 Python package.
4. **Submit the request.** Send the JSON to `POST /v1/suitability/assess` with
   `Content-Type: application/json`. The Layer 3 profile is computed by the
   API. Layer 4 data is caller-supplied and is only structurally checked.
5. **Interpret the result.** Read `overall_status` and
   `overall_explanation` first. Then inspect each `criterion_results` item,
   using its `evidence_id` to locate the corresponding `evidence` record.
   Check `profile_completeness`, `spatial_association`, provenance, quality
   counts, `suitability_gaps`, and `uncertainty_and_limitations`.
6. **Do not infer confidence.** Layer 5 emits no calibrated confidence score
   or probability. Evidence records currently report `uncertainty` as null;
   trust/status, sample/coverage quality, provenance, and limitations are the
   available interpretation aids.

## Spatial association contract

Layer 3 now reports its analysis-grid shape, the nine affine coefficients in
`Affine` iteration order, exact working-CRS WKT, source dataset/version fields
when registered, vertical scale, and coverage cell counts. Layer 5 computes a
SHA-256 **metadata fingerprint** from the Layer 3 body, source labels, grid,
vertical metadata, and coverage. This is a grid/provenance identifier, not a
raster-content hash or authenticity proof.

Layer 4 outputs do not carry a trusted Layer 3 patch identity. Where the
submitted result has the required metadata, Layer 5 compares:

- target pixel bounds against the Layer 3 grid dimensions;
- exact working-CRS WKT;
- affine coefficients;
- exact candidate and Layer 4 source identity-token sets;
- Earth `solar_geometry_pixel` against the supplied target pixel when present.

`source_grid_id` alone is not considered proof of alignment. Numeric target
longitude/latitude and `target_coordinate_frame` are preserved but are not
transformed or compared: the API has no verified body-specific transformation
contract for all supported source frames. Mars Layer 4 results do not currently
provide the same working CRS and affine metadata, so they remain unpaired by
this check.

These checks do not compare the Layer 4 grid dimensions or full terrain-analysis
footprint against Layer 3. A matching target pixel and affine transform can
therefore refer to the same target cell while the two engines used different
patch extents. `MATCHED_METADATA_UNVERIFIED` does not establish footprint
equality, source-content identity, or a trusted execution.

The association status is:

- `MATCHED_METADATA_UNVERIFIED`: all available grid/source checks match. This
  is a caller-metadata match, not authenticated spatial proof.
- `MISMATCHED`: supplied source, CRS, affine, or target-pixel metadata conflicts
  with the Layer 3 candidate.
- `UNPAIRED`: the required matching metadata is missing.

Mismatched or unpaired Layer 4 metrics are retained as `claimed_value` for
inspection but are `NOT_ASSESSED` and do not enter criterion comparisons.
Metadata-matched Layer 4 values are still external claims and receive
`UNVERIFIED` criterion status; they cannot support a definitive `PASS`, `FAIL`,
`SUITABLE`, or `NOT_SUITABLE` result.

## Evidence trust model

`EvidenceRecord.trust_status` distinguishes:

- `SERVER_COMPUTED`: the backend computed the Layer 3 metric from the selected
  raster request. It does not mean that the source raster itself was
  independently authenticated or scientifically validated.
- `UNVERIFIED_EXTERNAL`: a value or status came from the caller's Layer 4
  payload. Execution, real-terrain execution, synthetic verification,
  observational validation, kernel identities, and provenance are claims, not
  verified facts.
- `NOT_SUPPLIED`: no Layer 4 payload was provided.

Layer 5 hashes normalized Layer 4 JSON as a payload identity only. It does not
authenticate the sender, validate kernel hashes against files, prove
real-terrain execution, or establish observational accuracy. Claimed Layer 4
values and the claimed criterion comparison may be shown separately from
measured values. A claimed `PASS` status is never represented as verified
scientific validation.

Per-window `criteria_satisfied` and `criteria_failed` lists are caller claims.
The response marks their status `UNVERIFIED_EXTERNAL`; when both per-window
lists are supplied, Layer 5 checks their local consistency with each window's
candidate flag but does not recompute them against the top-level threshold
configuration.

There is no trusted execution registry, signature verification, or server-side
Layer 4 execution path. A metadata-matched Layer 4 result can be inspected and
its claimed values compared, but remains unverified. Missing evidence is never
replaced with zero.
The caller-reported Layer 4 execution state `PARTIAL` is also unverified; it is
not an overall Layer 5 assessment status.

## Temporal consistency validation

Layer 5 validates the serialized contract without recomputing solar geometry
or temporal classifications. It checks:

- timezone-aware start, end, observation, and window timestamps;
- ordered result bounds and observation coverage from start through end;
- observation count and interval lengths against the declared sampling step,
  including a shortened final interval;
- the current Layer 4 contract that boundary uncertainty equals the sampling
  step;
- allowed target classification names;
- window duration against window timestamp bounds;
- each continuous illumination interval against the contiguous
  `ILLUMINATED` observations, including its duration and optional sample count;
- candidate-window bounds and membership against intervals marked as
  candidates, including duplicate-interval detection;
- candidate flags against reported failed criteria when both criteria lists
  are supplied;
- total illumination and qualifying durations against observations/windows;
- target-classification durations against observations when supplied.

These are structural and arithmetic consistency checks. They do not prove
that a caller's classifications, criteria, provenance, or scientific status
claims are true.

## Mission criteria and completeness

Mission profiles contain 1–100 unique criteria. Each criterion declares a
source layer and metric, exact unit, operator and target, required/optional
status, missing-data behavior, and rationale. Layer 3 scale, relief-window,
and slope-threshold selectors must match the metric catalog. No unit
conversion or scientific threshold is inferred.

Operators are `gt`, `gte`, `lt`, `lte`, `eq`, and inclusive `within_range`.
The four inequalities compare against `target_value`; `within_range` requires
`target_range` with at least one of `min` or `max`, and both bounds are
inclusive. `eq` requires `target_value` and an explicit
`equality_tolerance` in the metric's unit; other operators reject that
tolerance. `required` and `missing_data_behavior` are explicit criterion
fields with no defaults. The allowed missing-data behaviors are
`INDETERMINATE` and `NOT_ASSESSED`. Comparisons use the value precision
available from the Layer 3 profile; see the precision note below.

The metric catalog endpoint is authoritative for supported metric IDs, units,
and selectors. The [Supported metrics](#supported-metrics) table below is a
human-readable copy of that catalog. No mission-specific thresholds or
criteria are supplied by default.

Each mission profile must declare its mission-specific `required_categories`
to be eligible for `SUITABLE`. Every declared category must contain at least
one required criterion. If the list is empty, the result cannot be
`SUITABLE`. The category list is a transparent completeness mechanism, not a
universal list of rover requirements; Layer 5 does not invent the mission's
essential dimensions or thresholds.

The response's `profile_completeness` reports whether completeness categories
were configured and the required-criterion status for each category.

## Supported metrics

| Metric ID | Source | Unit | Selector / availability |
|---|---|---|---|
| `terrain.coverage.valid_fraction` | Layer 3 | `fraction` | Finite elevation cells; assessed from cell counts |
| `terrain.elevation.min_m` | Layer 3 | `metres` | Requires adequate Layer 3 elevation coverage |
| `terrain.elevation.max_m` | Layer 3 | `metres` | Requires adequate Layer 3 elevation coverage |
| `terrain.elevation.mean_m` | Layer 3 | `metres` | Requires adequate Layer 3 elevation coverage |
| `terrain.elevation.range_m` | Layer 3 | `metres` | Requires adequate Layer 3 elevation coverage |
| `terrain.slope.mean_deg` | Layer 3 | `degrees` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.slope.median_deg` | Layer 3 | `degrees` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.slope.p90_deg` | Layer 3 | `degrees` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.slope.max_deg` | Layer 3 | `degrees` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.slope.rms_slope_deg` | Layer 3 | `degrees` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.slope.fraction_steeper_than` | Layer 3 | `fraction` | `scale_m`, `threshold_deg`; strict `>`; null when no valid slope samples exist |
| `terrain.roughness.rms_height_median_m` | Layer 3 | `metres` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.roughness.tri_median_m` | Layer 3 | `metres` | `scale_m`; adequate base and selected-scale coverage |
| `terrain.relief.median_m` | Layer 3 | `metres` | `window_m`; withheld when elevation coverage is inadequate |
| `terrain.landcover.valid_fraction` | Layer 3 | `fraction` | Valid WorldCover cells divided by patch cells |
| `terrain.landcover.excluded_fraction` | Layer 3 | `fraction` | Valid classifications only; withheld below the configured coverage minimum |
| `rehearsal.total_illumination_duration_seconds` | Layer 4 | `seconds` | Caller-supplied claim; spatial association and trust status apply |
| `rehearsal.total_qualifying_illumination_duration_seconds` | Layer 4 | `seconds` | Caller-supplied claim |
| `rehearsal.candidate_window_count` | Layer 4 | `count` | Caller-supplied candidate windows |
| `rehearsal.maximum_candidate_window_duration_seconds` | Layer 4 | `seconds` | Undefined when no candidate windows exist |
| `rehearsal.valid_terrain_coverage_mean_percent` | Layer 4 | `percent` | Nullable caller-supplied value |
| `rehearsal.measured_terrain_coverage_mean_percent` | Layer 4 | `percent` | Nullable; unavailable is not zero |
| `rehearsal.observation_coverage_availability_mean_percent` | Layer 4 | `percent` | Nullable caller-supplied value |
| `rehearsal.terrain_obstruction_max_percent` | Layer 4 | `percent` | Nullable caller-supplied value |
| `rehearsal.solar_elevation_min_deg` | Layer 4 | `degrees` | Minimum sampled value, if supplied |
| `rehearsal.solar_elevation_max_deg` | Layer 4 | `degrees` | Maximum sampled value, if supplied |
| `rehearsal.step_seconds` | Layer 4 | `seconds` | Declared temporal sampling step |

Layer 3 elevation values are in metres after `vertical_scale` is applied, but
remain source-datum specific. If a registered dataset manifest supplies
`vertical_reference` or `version`, those values are preserved; Layer 5 does
not infer missing datum metadata.

The Layer 3 excluded land-cover fraction is the number of excluded valid
classifications divided by all valid classifications—not by all candidate
cells. `terrain.landcover.valid_fraction` is a separate metric. The excluded
fraction is unavailable when valid classification coverage is below the
candidate's configured `min_coverage`; it is not treated as representative of
the whole candidate.

Layer 3 records valid/total cell counts for elevation coverage and, when
available, land-cover coverage. Evidence quality also carries terrain metric
sample counts where Layer 3 provides them. Slope, roughness, relief, and
elevation retain their Layer 3 definitions and scale limitations; they do not
establish soil strength, traction, or rover-scale hazard clearance.

For `terrain.slope.fraction_steeper_than`, zero valid slope samples produce a
null metric. Layer 5 records the criterion as unavailable and applies its
configured missing-data behavior; it does not treat the fraction as zero. A
measured zero fraction remains numeric when one or more valid slope samples
were evaluated and none exceeded the threshold. No defensible metric-specific
minimum for a nonzero slope sample count is currently configured: the existing
`min_coverage` threshold measures valid elevation cells, not valid slope
samples. Layer 5 exposes the valid slope sample count in evidence quality, but
nonzero sample representativeness remains an unresolved policy decision.

## Coverage and status aggregation

The Layer 3 `min_coverage` requirement is enforced before Layer 5 uses
elevation summaries, slope, roughness, or relief for criterion comparisons.
The valid-elevation-fraction metric itself remains assessable because it
measures the coverage requirement. Land-cover validity is measured separately;
an excluded fraction below adequate classification coverage is unavailable.
Unsupported summaries can therefore produce `INDETERMINATE` or
`NOT_ASSESSED`, not a definitive criterion failure.

Criterion statuses are:

- `PASS` / `FAIL`: a supported Layer 3 value satisfies / does not satisfy the
  configured comparison.
- `UNVERIFIED`: a metadata-matched Layer 4 value is only a caller claim. The
  response includes `claimed_value` and the claimed comparison separately.
- `INDETERMINATE` / `NOT_ASSESSED`: evidence is unavailable or unpaired. The
  configured missing-data behavior applies to ordinary missing evidence;
  spatially unpaired Layer 4 evidence is explicitly `NOT_ASSESSED`.

The overall status meanings are:

- `SUITABLE`: every configured criterion passed with adequate Layer 3
  evidence, required categories were declared, and no Layer 4 claim is used to
  establish the conclusion. This is not a safety or readiness certification.
- `NOT_SUITABLE`: at least one required criterion has an adequately supported
  `FAIL`. An unverified Layer 4 claim cannot create this result.
- `INDETERMINATE`: required evidence is missing, unpaired, or unverified, so
  suitability cannot be concluded. For example, a required Layer 4 criterion
  remains unverified even when its metadata matches.
- `PARTIALLY_ASSESSED`: no required criteria or completeness declaration were
  supplied, optional evidence failed/remains unresolved, or the Layer 3 patch
  has insufficient coverage. This is an incomplete evaluation, not a pass.

Overall aggregation is deterministic and is not a score:

1. A supported required `FAIL` yields `NOT_SUITABLE`.
2. Otherwise, a required `UNVERIFIED`, `INDETERMINATE`, or `NOT_ASSESSED`
   criterion yields `INDETERMINATE`.
3. No required criteria yields `PARTIALLY_ASSESSED`.
4. A failed or unresolved optional criterion yields `PARTIALLY_ASSESSED`.
5. An absent completeness declaration yields `PARTIALLY_ASSESSED`.
6. Insufficient Layer 3 coverage yields `PARTIALLY_ASSESSED`, unless an
   independently supported required coverage criterion itself fails.
7. Layer 4 criteria remain unverified or unpaired and cannot themselves produce
   a definitive `PASS` or `FAIL`; a separate supported Layer 3 required
   failure can still produce `NOT_SUITABLE`.
8. `SUITABLE` is possible only when the declared required categories and
   configured criteria pass with adequate Layer 3 evidence and no unresolved
   external Layer 4 claim is used.

Thus `NOT_SUITABLE` requires an adequately supported required failure.
Unverified external values cannot create a definitive failure or pass.

## Provenance and precision

The Layer 3 patch identity hashes the analysis-grid and coverage metadata; it
is explicitly not a source-raster content hash. Exact grid shape, affine
coefficients, and CRS WKT are returned for traceability. Dataset version and
vertical reference are reported only when supplied by the registered dataset
manifest. Arbitrary user rasters and remote sources may not have immutable
content identities.

The profile cache includes local raster size/modification time and, for
registered dataset IDs, manifest and resolved local-file metadata. This
detects ordinary local replacement but is not cryptographic content
verification. Remote source changes cannot be detected from the current
metadata contract.

Layer 3 rounds several statistics before returning the profile. Layer 5 uses
that returned precision for those metrics; it cannot recover precision already
discarded upstream. Coverage and land-cover fractions are computed from cell
counts for Layer 5 comparisons. Equality comparisons use the caller's explicit
`equality_tolerance`; no tolerance is silently added to other operators.

## Errors and compatibility

Invalid requests, units, metrics, criteria, temporal contracts, or body
disagreement use the existing structured request-validation errors. Layer 3
source-access and profiling errors retain the Layer 3 API error contract.
Layer 3 metric definitions and endpoints remain unchanged; the profile
response adds grid/provenance/count fields. Layer 4 engines and serialized
outputs are not modified.

Layer 4 measured-observation coverage remains unavailable when the source
does not provide sufficient count evidence; it is never converted to zero.
No independent observational shadow-accuracy validation is established by
successful execution, metadata matching, or synthetic checks.
