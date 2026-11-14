# Layer 4 — Solar Geometry and Rehearsal Window Engine

## 1. Overview

Layer 4 provides body-specific solar geometry, terrain illumination and
obstruction classifications, and sampled temporal rehearsal-window
evaluations for Earth, the Moon, and Mars. It is a Python package in the
TERRAWINDOW repository, not a running service or a complete mission-suitability
application.

The package accepts explicit time, terrain, and SPICE-kernel inputs. Earth and
Moon terrain generally arrives as an in-memory Layer 3 patch; the Mars path can
also read the retained native MOLA MEGDR source grid. Single-epoch engines
produce body-specific geometry and per-cell illumination/ray products.
Temporal evaluators preserve those classifications at sampled epochs and
return a JSON-compatible result for a downstream Layer 5 consumer.

Responsibilities include:

- Earth ITRF93 solar geometry, strict Copernicus GLO-30 patch adaptation, and
  direct-illumination/terrain-obstruction classification.
- Lunar SPICE reference geometry, metadata-explicit LOLA patch adaptation,
  optional measured-observation-count coverage, and terrain illumination.
- Mars SPICE geometry, native MEGR/MEGC handling, epoch-dependent MOLA frame
  transformation, and terrain illumination.
- Strict single-body temporal dispatch, interval aggregation, candidate-window
  criteria, provenance, evidence states, and scientific limitations.

Layer 4 does not fetch Layer 2 data, expose a user interface, implement Layer 5
mission-suitability scoring, model temperature, establish rover safety, or
claim independent observational shadow accuracy. The three planetary
implementations deliberately remain separate.

## 2. Architecture

### Package and data flow

The distribution metadata remains `rehearsal` in `pyproject.toml`; Python
imports remain `rehearsal.*`. The repository directory is
`layer4_solar_geometry/`.

```text
one-body request
      |
      v
lazy temporal dispatcher
      |
      +--> Earth geometry + GLO-30 terrain + Earth illumination + Earth temporal
      +--> Moon geometry + LOLA terrain + lunar illumination + lunar temporal
      +--> Mars geometry + MOLA terrain + Mars illumination + Mars temporal
      |
      v
shared temporal aggregation and RehearsalEvaluation
      |
      v
Layer 5 consumer (suitability scoring is external)
```

`TemporalEvaluationRequest` has one `body`, one `terrain`, and one matching
`kernels` value; it has no fields for unselected bodies. The dispatcher
validates `body` as exactly `earth`, `moon`, or `mars`, then imports only that
body's evaluator. It does not import, load, or run the other planetary
pipelines. The body-specific evaluators call their own existing geometry and
single-epoch illumination paths. Shared code handles UTC intervals, aggregation,
criteria, serialization, and the Layer 5 result contract; it does not unify
planetary geometry, terrain, or illumination.

Useful package entry points include:

- `rehearsal.windows.TemporalEvaluationRequest`
- `rehearsal.windows.dispatch_temporal_evaluation()`
- `rehearsal.windows.evaluate_selected_body()`
- `rehearsal.windows.RehearsalCriteria`
- `rehearsal.windows.RehearsalEvaluation`
- `rehearsal.windows.Layer5TemporalInput`

Callers may instead use
`evaluate_earth_rehearsal_windows()`,
`evaluate_lunar_rehearsal_windows()`, or
`evaluate_mars_rehearsal_windows()` directly.

### Package contents and configuration

- `src/rehearsal/earth/`: Earth geometry, kernels, terrain, Numba kernels, and
  Earth temporal evaluation.
- `src/rehearsal/lunar/`: lunar reference geometry, kernels, terrain, Numba
  kernels, full-raster sampled-time products, and lunar temporal evaluation.
- `src/rehearsal/mars/`: Mars reference geometry, MOLA source reader and frame
  transform, terrain illumination, Numba kernels, and Mars temporal evaluation.
- `src/rehearsal/solar/`: shared time/angle conventions and SPICE mechanics.
- `src/rehearsal/windows/`: legacy solar-only window utility, body-selective
  dispatcher, shared temporal aggregation, and Layer 5 contract.
- `src/rehearsal/spice_provenance.py`: identities and SHA-256 hashes for
  furnished kernels.
- `configs/thresholds.yaml`: defaults consumed by the legacy solar-only
  threshold loader. It is runtime configuration, not test configuration.
- `data/mars/mola_megdr/`: retained MOLA products and provenance.
- `kernels/kernels/`: locally supplied SPICE kernels.
- `pyproject.toml`: package metadata, production dependencies, build backend,
  package discovery, and the optional Numba performance extra.

The package expects callers to supply compatible local kernel files. It does
not download or silently substitute kernels. SPICE kernel-pool operations are
serialized by the existing body-specific/shared helpers.

## 3. Earth engine

### SPICE geometry and coordinates

Earth solar states use geometric SPICE calculations with correction mode
`NONE`, transformed to NAIF `ITRF93` (frame ID 13000) using the supplied
high-precision binary Earth-orientation PCK. The generic PCK's `IAU_EARTH`
frame is not substituted: it lacks the selected binary PCK's Earth-orientation
corrections. The observer coordinate conversion uses WGS84:

- semi-major axis: 6,378,137 m;
- inverse flattening: 298.257223563;
- latitude: north-positive WGS84 geodetic degrees;
- longitude: east-positive degrees;
- site elevation: WGS84 ellipsoidal metres;
- solar elevation: geometric degrees above the horizon;
- solar azimuth: clockwise from local geodetic north in `[0, 360)`;
- returned solar direction: unit vector in ITRF93 rectangular axes.

No atmospheric refraction, light-time, stellar-aberration, or station-specific
WGS84-realization/epoch motion correction is applied. Azimuth is undefined at
exact zenith or nadir. SPICE UTC-to-ET conversion uses the furnished LSK.
Geometry calls validate required kernel files and epoch coverage; the binary
Earth PCK coverage is a limiting input.

### Copernicus GLO-30 terrain and illumination

`EarthTerrainPatch.from_layer3_patch()` adapts a Layer 3 patch with explicit
`EarthTerrainMetadata`. The v1 adapter accepts Copernicus GLO-30, requires
metre elevations and an explicitly identified EGM2008 vertical reference, and
rejects unknown vertical references or non-WGS84 working ellipsoids. It
preserves the elevation array, NoData/mask semantics, affine transform,
working and native CRS metadata, resampling, source URIs, pixel spacing, and
per-pixel longitude/latitude. Geographic degrees are not used as metric
distances.

GLO-30 elevations are orthometric (EGM2008) heights. The local terrain
calculation uses elevation differences over WGS84 geometry; it does not apply
geoid-undulation grids or model local geoid slope. Absolute EGM2008 heights
are not treated as ellipsoidal heights.

Terrain normals use finite differences over a configurable pixel radius.
Ellipsoid-aware horizon rays traverse the affine raster grid and retain local
curvature. Numba-compiled `compute_normals()`, `horizon_rays()`, and
`classify_grid()` provide normal generation, horizon analysis, and raster
classification. Rays stop at the configured finite `max_distance_m`.
`ILLUMINATED` means no obstruction was found within that search distance; it
does not establish an unobstructed global horizon. A DEM boundary or NoData
encounter before the limit yields an insufficient-coverage state rather than
an illuminated fallback.

The result distinguishes source validity, normal support, classification
coverage, and per-pixel `EarthRayStatus`. The classification values are
`NO_DATA`, `UNKNOWN`, `ILLUMINATED`, `TERRAIN_OBSTRUCTED`,
`SURFACE_FACING_AWAY`, and `INSUFFICIENT_COVERAGE`. The coverage mask means a
valid terrain normal supports a definitive classification; it does not mean
every ray reached the search limit.

`run_earth_illumination_series()` reuses prepared normals across ordered,
timezone-aware observations. The rehearsal-window evaluator computes solar
geometry at the selected target pixel and uses that same geometry for the
target classification; patch-wide cells are classified using that target
direction, not individual topocentric SPICE solutions per cell.

### Earth limitations and retained geometry checks

Earth's limitations include the finite search range, local patch boundaries,
NoData, DEM resampling and projection distortion, GLO-30 DSM surface/vegetation
content, point-Sun approximation, and omitted atmospheric/refraction and
solar-disc effects. The local vertical-datum calculation does not model geoid
slopes.

Historical Earth geometry comparisons are engineering checks, not observed
shadow validation. At 2024-06-21 19:30 UTC, the DE440S Earth-to-Sun geometric
vector differed from the stated JPL Horizons DE441 result by about 0.535 m in
vector norm (single-epoch comparison; 1 km threshold). Selected SPICE-versus-
legacy-Astropy site-angle samples met the documented engineering comparison
bounds of 0.01 degrees elevation and 0.1 degrees azimuth. Those pipelines use
different ephemeris, apparent/geometric, Earth-orientation, and time
conventions and are not independent observational truth.

The recorded JPL Horizons vector in J2000/ICRF axes was
`(-1498990.588799035, 139481133.9742695, 60462747.63667176) km`; the local
DE440S-minus-Horizons residual was `(0.000535220, 0.000002801, 0.000001788)`
km, norm `0.000535231 km`. For the selected site checks below, differences are
SPICE minus the former Astropy path, in degrees:

| Sample (site, UTC) | Astropy elevation / azimuth | SPICE elevation / azimuth | Difference elevation / azimuth |
|---|---:|---:|---:|
| Phoenix summer noon (2024-06-21 19:30) | 79.986025 / 179.623130 | 79.985953 / 179.591363 | -0.000072 / -0.031767 |
| Phoenix winter morning (2024-12-21 14:30) | -0.591441 / 118.030885 | -0.596078 / 118.027462 | -0.004637 / -0.003423 |
| Seattle equinox (2024-03-20 19:00) | 39.814274 / 154.734521 | 39.814959 / 154.727203 | +0.000685 / -0.007318 |
| Equator sunrise (2024-03-20 06:00) | -1.848272 / 89.952156 | -1.853519 / 89.949882 | -0.005246 / -0.002274 |
| Equator near-zenith noon (2024-03-20 12:00) | 88.166713 / 85.415108 | 88.161392 / 85.357275 | -0.005321 / -0.057834 |
| Equator sunset (2024-03-20 18:00) | 1.806193 / 270.245301 | 1.811432 / 270.247576 | +0.005240 / +0.002276 |
| Arctic summer midnight (70°N, 2024-06-21 00:00) | 3.436353 / 359.583180 | 3.436361 / 359.577540 | +0.000009 / -0.005640 |

These are comparisons between geometry pipelines, not observational
measurements; azimuth is particularly ill-conditioned close to zenith.

The retained Earth SPICE configuration and pinned hashes are:

| Kernel | Role | SHA-256 |
|---|---|---|
| `naif0012.tls` | UTC/ET conversion | `678E32BDB5A744117A467CD9601CD6B373F0E9BC9BBDE1371D5EEE39600A039B` |
| `de440s.bsp` | Sun and Earth states | `C1C7FEEAB882263FC493A9D5A5B2DDD71B54826CDF65D8D17A76126B260A49F2` |
| `earth_000101_270208_261113.bpc` | ITRF93 Earth orientation | `6E77690BA455A644E509B0B9CB308B0DEC1A7154CEECF3355659B917B21CA45E` |
| `pck00011.tpc` | Static radii/constants | `3DFF7B1DBECEAA01F25467767D3FA25816051C85D162D1EDF04ACB310EE28BB1` |

The Earth binary PCK coverage recorded for this kernel ends in 2027; use outside
its coverage requires an appropriately verified kernel, not extrapolation.
Kernel source: [NAIF generic kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/).

## 4. Lunar engine

### SPICE geometry and reference frames

The lunar geometry uses a DE-matched binary orientation PCK and frames FK,
plus a planetary SPK, LSK, and generic PCK. The supplied set is explicit,
validated, and not downloaded or silently replaced. The supported surface
frames are:

- `MOON_ME` (Mean Earth / rotation-axis; default);
- `MOON_PA` (Principal Axes).

Input latitude/longitude must use the selected frame. Latitude is
planetocentric by default; longitude is east-positive. Terrain map-projection
x/y coordinates must be transformed to planetocentric latitude/longitude in
the declared body-fixed frame before use as geographic coordinates. NAIF
recommends `MOON_ME` or `MOON_PA` for higher-accuracy lunar orientation rather
than generic `IAU_MOON`.

Solar geometry uses `spice.str2et()`, `spice.spkpos()`, `spice.pxform()`, and
`spice.bodvrd()`. It reports geometric surface-topocentric solar elevation
and azimuth in degrees; azimuth is clockwise from lunar north in `[0, 360)`.
The fixed-frame Moon-to-Sun vector is available through
`lunar_sun_direction_fixed()` and its ordered-series counterpart. No
atmospheric correction, aberration correction, solar-disc fraction, or
continuous lunar-day model is applied.

The local source product uses a 1,737,400 m reference sphere and
`MOON_ME`/DE421 realization. The supplied DE440 frame maps the corresponding
frame through `MOON_ME_DE440_ME421`; NAIF documents a maximum difference of
about 0.54 m at the lunar surface over 2000–2040. This is close alignment, not
exact frame identity, and is recorded as `frame_alignment_note`.

### LOLA terrain, validity, and measured coverage

`LunarTerrainPatch.from_layer3_patch()` requires explicit
`LunarTerrainMetadata`; it preserves the in-memory elevation values, affine
transform, CRS/WKT, native CRS, source and working pixel size, resampling,
source URIs, elevation reference, body-fixed frame/realization, and
provenance. The adapter does not infer a body-fixed frame from an unnamed
projection WKT and does not resample or rotate the source patch.

The retained Site01 LOLA product is a 3200 × 3200, one-band float32 DEM with
5 m square cells over a 16 × 16 km south-polar patch. Its source WKT describes
an unnamed south-polar stereographic CRS on a 1,737,400 m sphere, not a named
lunar frame. The Layer 2 product metadata identifies `MOON_ME` associated with
DE421. The GeoTIFF uses area pixel registration; the affine transform locates
corners and sampling uses pixel centres. The recorded surface-file SHA-256 is
`3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e`.
The source projected bounds are x `[-19000, -3000] m`, y `[-20000, -4000] m`;
the embedded projection yields an approximate geographic perimeter of
longitude `[-171.47, -101.89]` degrees and latitude `[-89.84, -89.09]`
degrees, with centre `(-137.48955, -89.46316)` degrees. Historical inspection
found all 10,240,000 source pixels finite and an elevation range of
`-523.1834` to `1959.4962 m` (mean `1139.0588 m`, population standard
deviation `422.1791 m`). These facts do not establish observed laser-return
support.

Elevation validity and measured-observation coverage are separate. LOLA
surface pixels may be interpolated where no laser return exists. An optional
observation-count Layer 3 patch must match the elevation patch's shape, CRS,
and affine grid; nonnegative integer counts are required. Positive counts
denote measured support, zero counts denote unobserved/interpolated locations,
and invalid count cells leave coverage unknown.

**If an aligned LOLA observation-count product is unavailable, measured
observation counts and coverage are reported as `UNAVAILABLE`, not interpreted
as zero observations or complete coverage.** Finite elevations remain
elevation-valid independently; unavailable count evidence is not encoded as
zero. The current retained Site01 input has no count raster.

### Lunar illumination and temporal products

The lunar terrain API provides body-fixed surface normals, local terrain
windows, directional horizon profiles, direct-obstruction checks, and
single-time or sampled-time raster classifications. Its Numba implementation
uses `compute_normal_window()` and `classify_window()` with row-parallel
processing. Rays use fixed 5 m steps over the configured range. The product
includes classification-support masks and ray statuses; classification
coverage is not a substitute for measured LOLA coverage.

`run_terrain_illumination_series()` is a separate full-raster workflow. It
reuses terrain-normal preparation and writes memory-mapped arrays for
classification, coverage, and ray-status stacks, along with counts,
transitions, persistence, execution metadata, and a report. Persistence counts
only definitive evaluable classes; `UNKNOWN`, `NO_DATA`, and
`INSUFFICIENT_COVERAGE` are excluded, and pixels without evaluable samples are
NaN. Existing output files are not silently overwritten. Horizon sectors
reaching a local DEM edge or NoData are marked partial; their sampled maximum
is a lower-bound observation, not a complete horizon estimate.

The sampled rehearsal evaluator is distinct from this full-raster export. It
processes one epoch at a time and uses the selected target's classification and
ray status in the temporal result.

### Lunar limitations

The local DEM is regional and does not imply distant terrain beyond its edge.
Fixed 5 m ray stepping, configured finite search distance, point-Sun treatment,
and sampled rather than continuous temporal evaluation remain limitations.
The DE421-to-DE440 frame correspondence is near-aligned but not identical.
Full-resolution 3200 × 3200 performance has not been verified. Measured
observation coverage is `UNAVAILABLE` when the aligned count product is absent.
No independent lunar observed-shadow accuracy validation has been performed.

NAIF references:
[lunar Earth PCK/FK tutorial](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/Tutorials/pdf/individual_docs/23_lunar-earth_pck-fk.pdf)
and [generic kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/).
LOLA source: [NASA PGDA Site01](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif).

## 5. Mars engine

### SPICE geometry and MOLA products

The Mars pipeline uses `IAU_MARS` (frame ID 10014, center 499) and explicit
Mars kernel sets. It evaluates geometric Sun position with
`spice.spkpos("SUN", ET, "IAU_MARS", "NONE", "MARS")`; the SPK set is checked
for Sun (10) and Mars center (499) coverage at the requested epoch.
Solar elevation is geometric above the local ellipsoid tangent plane;
azimuth is clockwise from north in `[0, 360)`. Atmospheric refraction and
solar-disc effects are not modeled.

`MarsMolaMegdr32ppd` reads native NASA/PDS MGS MOLA MEGDR products and verifies
recorded source hashes. The 32-pixel-per-degree global products are
5760 × 11520 signed big-endian 16-bit rasters. Rows increase north-to-south;
columns increase west-to-east. Pixel-centre coordinates are
`longitude=(column+0.5)/32` east and
`latitude=90-(row+0.5)/32` planetocentric. Longitude inputs are normalized
modulo 360 degrees. A source-grid window crossing the longitude seam is read
as adjacent windows; the source arrays are not changed.

Product roles must remain distinct:

- **MEGR** is the mean planetary-radius radial surface used for geometric
  positions.
- **MEGC** is the observation-count product. Positive counts indicate
  observation support; zero-count bins remain unsupported even if the
  interpolated MEGR radius is finite.
- **MEGT** is topography relative to the GMM3 (`mgm1025`) areoid, in metres.
  It is not added to MEGR radii; no verified common vertical-datum
  transformation supports that operation.

Elevation/surface validity and MEGC observation coverage remain independent.
The source labels do not declare a NoData constant; zero and negative MEGT
values are valid, and zero-count bins may contain interpolated finite values.
The adapter preserves source arrays, counts, pixel registration, grid
identity, and provenance without rescaling, interpolation, reprojection, or
filling.

### Frame transformation and surface geometry

PDS labels identify `IAU2000_MARS` and planetocentric, east-positive
coordinates. The current geometry uses `IAU_MARS` from `pck00011.tpc`.
`MarsMolaFrameTransform` uses both orientation models at the requested ET:

```text
R_current<-MOLA(t) =
    pxform("J2000", "IAU_MARS", t)_pck00011
    * pxform("IAU_MARS", "J2000", t)_mars_iau2000_v1
```

The PCKs resolve through SPICE to the same frame ID/center but are distinct
epoch-dependent orientation models and are furnished separately. No arbitrary
longitude offset is applied. The transformation rotates Mars-centered radial
vectors; longitude is normalized to `[0, 360)` and planetocentric latitude is
recovered from the transformed vector. Global source row/column indices are
retained, with target columns wrapped modulo the 11,520-column grid at the
seam.

The current reference radii are `(3396.19, 3396.19, 3376.20) km`. Radial
surface positions use MEGR distance directly. The PCK ellipsoid radial
intersection defines a local reference vertical and radial altitude
`h_radial = r - rho`; this is not geodetic-normal height or MEGT elevation.
Terrain normals are built from neighboring three-dimensional MEGR positions.
The four immediate neighboring positions must be valid and each must have
nonzero MEGC count.

### Mars direct illumination and temporal evaluation

`mars_illumination_raster()` and the body-specific temporal evaluator use a
Numba-accelerated, Mars-specific classification path. A supercover DDA follows
the solar azimuth through the current-frame raster, checks radial 3D terrain
positions, and distinguishes obstruction, search limit, observation gap,
NoData, boundary, unknown geometry, and surface-facing-away conditions.
`ILLUMINATED` means only that no obstruction was found within the configured
search range. The default horizon search is 50 km. Leaving the patch,
encountering NoData, or crossing an unobserved MEGC bin yields
`INSUFFICIENT_COVERAGE`, never an illuminated fallback.

Mars results separate `surface_valid_mask`, `elevation_valid_mask`, and
`observation_coverage_mask`, as well as `classification` and `ray_status`.
Classification codes are `NO_DATA=-1`, `UNKNOWN=0`, `ILLUMINATED=1`,
`TERRAIN_OBSTRUCTED=2`, `SURFACE_FACING_AWAY=3`, and
`INSUFFICIENT_COVERAGE=4`. Temporal output records patch-relative target
pixel, global MEGR source row/column, grid identifier, pixel-centre
coordinates, and frame.

### Mars limitations and source record

MEGR/MEGC values preserve native source evidence; MEGT stays separate. PDS
identifies the MOLA coordinate origin as Mars, whereas SPICE identifies center
499. The origin-to-center tie and any translation remain **unverified**; no
translation is applied. The 50 km default terrain-horizon limit is finite.
Mars illumination has no independent observed-shadow accuracy validation.

The retained provenance records the source files, checksums, and PDS labels.
Historical ingestion checks reported MEGT range -8,206 to 21,181 m, MEGC
counts 0–125, and 12,434,182 zero-count bins; zero and negative values were
preserved. These are source-decoding and coordinate checks, not illumination
accuracy results. The historical MOLA-to-current-frame rotation at the MEGR
label epoch (1999-08-08T03:10:20Z) was about 0.001763750416 degrees; the
rotation is epoch-dependent and the analytic 2050 model evaluation was not
independently validated.

The historical frame-transform checks also recorded approximately
0.001639306270 degrees at 2000-01-01, 0.002816933087 degrees at
2026-06-21, 0.002639179741 degrees at 2026-11-15, and 0.003796296680 degrees
at 2050-01-01. The 2050 value is an analytic-model evaluation, not a validated
forecast. Exact source and kernel hashes, product labels, and detailed
transformation provenance remain in
`data/mars/mola_megdr/PROVENANCE.json`.

Authoritative source references:

- [PDS4 MEGT label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/megt90n000fb.xml)
- [PDS4 MEGC label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/megc90n000fb.xml)
- [PDS4 MEGR label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/megr90n000fb.xml)
- [PDS MEG032 collection inventory](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg032/collection_data_meg032_inventory.csv)
- [PDS MOLA ENVI guidance](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/document/mola_envi.htm)
- [NAIF IAU 2000 Mars PCK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/mars_iau2000_v1.tpc)
- [NAIF current generic PCK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc)

## 6. Temporal rehearsal-window engine

### Requests, timestamps, and sampling

Each request names exactly one body and supplies that body's terrain, kernels,
time range, step, criteria, and optional body-specific options. Times must be
timezone-aware; evaluation normalizes them to UTC. The interval is
start-inclusive and end-exclusive, `[start_utc, end_utc)`. Samples define
left-closed intervals up to the next sample or requested end time. If the
duration is not an exact multiple of the step, the last interval is shorter.
Observation timestamps and interval ends are retained.

A classification transition may happen between samples. Reported boundary
times therefore have up to one sampling-step uncertainty, with up to two
steps of uncertainty in a duration derived from two boundaries. This is
sampling uncertainty, not a probabilistic confidence interval.

The target pixel defaults to the terrain patch centre; `target_pixel=(row,
column)` selects another cell. Continuous illumination intervals describe
that target. Patch-wide valid coverage, classification distributions,
obstruction, and ray support are aggregated separately. Temporal processing
streams one raster result at a time rather than holding a full time-by-raster
stack.

### Classifications, aggregation, and criteria

The original body-specific classifications and ray statuses are retained per
epoch. `INSUFFICIENT_COVERAGE` is not illumination and is not confirmed
darkness. `NO_DATA` and `UNKNOWN` remain distinct. Any non-illuminated or
unsupported target sample breaks a continuous interval; intervals are not
bridged across unsupported or unknown gaps.

For each sample, the engine records the target class/ray state, class and ray
counts, surface/elevation validity, observation evidence, solar geometry,
valid terrain coverage, obstruction statistics, and source metadata. Valid
terrain coverage uses all patch cells as denominator; terrain obstruction
uses valid surface cells; ray-support percentage is reported independently.
Measured-observation coverage is nullable when no aligned count evidence
exists.

`RehearsalCriteria` supports:

- minimum continuous illumination duration;
- minimum valid terrain coverage percentage;
- optional minimum/maximum solar elevation;
- optional solar azimuth range, including ranges that cross north;
- maximum terrain-obstruction percentage; and
- an optional body-specific condition evaluated against selected-body
  observations.

Criteria are applied to each continuous target-illumination interval. Every
interval is returned with `criteria_satisfied`, `criteria_failed`, and
`is_candidate`; only intervals passing all configured criteria appear in
`candidate_windows`. Missing data does not silently pass a criterion. No
confidence score is generated.

The older `windows.find_windows(SunSeries)` utility groups solar-elevation
samples without terrain and does not perform body dispatch or mission
qualification.

## 7. Output and evidence contract

### `RehearsalEvaluation`

The frozen dataclass in `rehearsal.windows.temporal` contains:

| Field | Meaning |
|---|---|
| `body` | Selected body (`earth`, `moon`, or `mars`). |
| `start_utc`, `end_utc` | Requested evaluation bounds. |
| `step_seconds`, `boundary_uncertainty_seconds` | Sampling step and stated boundary uncertainty. |
| `target_pixel` | Selected patch pixel `(row, column)`. |
| `observations` | Ordered `TemporalObservation` records, one per sampled interval. |
| `continuous_illumination_intervals` | All continuous target-illumination intervals with summaries and criteria results. |
| `candidate_windows` | Intervals satisfying every configured criterion. |
| `interruptions` | Non-illuminated or unsupported gaps between illuminated intervals. |
| `total_illumination_duration_seconds` | Total target illumination duration. |
| `total_qualifying_illumination_duration_seconds` | Duration qualifying under the evaluation's criteria. |
| `target_classification_durations_seconds` | Duration by target classification. |
| `classification_counts`, `ray_status_counts` | Aggregated patch-wide class and ray-status counts. |
| `valid_terrain_coverage_min_percent`, `valid_terrain_coverage_mean_percent`, `valid_terrain_coverage_max_percent` | Valid surface coverage summaries. |
| `ray_support_mean_percent_of_valid_terrain` | Mean ray support relative to valid terrain. |
| `terrain_obstruction_mean_percent`, `terrain_obstruction_max_percent` | Terrain obstruction summaries. |
| `solar_elevation_min_deg`, `solar_elevation_max_deg` | Solar elevation range. |
| `solar_azimuth_start_deg`, `solar_azimuth_end_deg`, `solar_azimuth_span_deg` | Circular solar-azimuth summary. |
| `criteria` | Serialized criteria applied to the evaluation. |
| `provenance` | Source and evaluation provenance metadata. |
| `scientific_limitations` | Body-specific and evaluation limitations. |
| `source_grid_id`, `source_row`, `source_column` | Source-grid identity where available; global source indices are paired and require a grid ID. |
| `target_longitude_deg`, `target_latitude_deg`, `target_coordinate_frame` | Target coordinates and their declared frame where available. |
| `kernel_identities` | Identities of kernels furnished for the evaluation. |
| `evidence` | Structured `ScientificEvidence`. |
| `observation_coverage_availability_min_percent`, `observation_coverage_availability_mean_percent` | Availability of observation-count evidence. |
| `measured_terrain_coverage_min_percent`, `measured_terrain_coverage_mean_percent`, `measured_terrain_coverage_max_percent` | Measured terrain summaries where counts are available. |
| `elevation_valid_coverage_mean_percent` | Mean coverage by valid source elevation. |

Properties `interruption_count` and `interruption_duration_seconds` derive
interruption totals. `to_dict()` returns JSON-compatible nested data and does
not include raster-sized arrays.

### Nested observations, windows, interruptions, and provenance

Each `TemporalObservation` records `time_utc`, `interval_end_utc`,
`target_classification`, `classification_counts`, `ray_status_counts`,
`total_cells`, `valid_terrain_cells`, `ray_supported_cells`,
`valid_terrain_coverage_percent`, `ray_support_percent_of_valid_terrain`,
`illuminated_cells`, `terrain_obstructed_cells`,
`insufficient_coverage_cells`, `unknown_cells`, `no_data_cells`,
`terrain_obstruction_percent`, `solar_elevation_deg`, `solar_azimuth_deg`,
`solar_direction_fixed`, `solar_frame`, `sun_distance_km`,
`source_dataset_id`, `source_metadata`, `target_ray_status`,
`target_ray_status_available`, `target_surface_valid`,
`target_elevation_valid`, `target_observation_coverage_status`,
`target_observation_count`, `elevation_invalid_cells`,
`surface_invalid_cells`, `elevation_valid_cells`,
`measured_valid_elevation_cells`, `unobserved_valid_elevation_cells`,
`observation_coverage_unavailable_cells`,
`observation_coverage_availability_percent`, and
`measured_terrain_coverage_percent`. `duration_seconds` is the interval
duration.

Each `RehearsalWindow` records start/end times, duration, sample count,
minimum/mean valid terrain coverage, maximum obstruction, mean illuminated
terrain percentage, solar elevation min/max, circular solar azimuth start/end/
span, classification and ray-status counts, criteria satisfied/failed,
`is_candidate`, and nullable observation-coverage availability and measured
terrain coverage.

Each `TemporalInterruption` records its start/end, duration, and
`target_classification_durations_seconds`.

`SpiceKernelIdentity` records `roles`, `filename`, resolved `source_path`,
`sha256`, `status`, and optional `warning`. Hashes are computed for actual
furnished files; failures remain visible as `NOT_AVAILABLE` rather than a
success-shaped fallback.

`ScientificEvidence` has independent statuses for
`implementation_status`, `synthetic_verification_status`,
`real_terrain_execution_status`, and
`observational_validation_status`, plus details. Values include `PASS`,
`FAIL`, `NOT_RUN`, `NOT_AVAILABLE`, `NOT_VALIDATED`, and `PARTIAL`.
`implementation_status=PASS` means only that the requested evaluation
returned. Synthetic verification means focused synthetic checks ran;
real-terrain execution means a retained terrain input was processed;
independent observational validation requires suitable external observations
and is not established by either of the first two.

For measured coverage, `UNOBSERVED` means an available count product reported
zero observations; `UNAVAILABLE` means the evidence could not be established.
These statuses are not interchangeable. In particular, lunar unavailable
counts are not zero and Mars MEGC coverage remains distinct from MEGR surface
validity and MEGT elevation validity.

`Layer5TemporalInput` requires a selected body matching
`RehearsalEvaluation.body`, preventing cross-body result mixing.

## 8. Numba and performance

Numba is an optional dependency in the `performance` extra; the terrain
illumination raster paths require it and fail explicitly if unavailable.
Numba `prange` parallelizes independent raster work. Worker count is controlled
by Numba (for example `NUMBA_NUM_THREADS` set before process startup).

Actual accelerated paths include:

- Earth: normal generation, horizon rays, and grid classification in
  `earth/_illumination_numba.py`; Earth temporal evaluation reuses prepared
  normals.
- Moon: normal-window preparation and classification in
  `lunar/_illumination_numba.py`; the full-raster sampled-time workflow reuses
  normals and writes memory-mapped time stacks.
- Mars: native-frame surface-position and terrain-classification/ray
  processing in `mars/_illumination_numba.py`; Mars temporal evaluation
  invokes the Mars single-epoch path at each epoch.

Historical warm-run measurements were made on small demonstration patches,
not full-resolution rasters:

| Body | Patch size | Warm execution |
|---|---:|---:|
| Earth | 65 × 65 | 1.61 s |
| Moon | 65 × 65 | 1.38 s |
| Mars | 61 × 61 | 2.32 s |

These are local demonstration timings, not stable benchmarks. The historical
Earth and Moon first-call runs took 27.72 s and 16.61 s respectively, including
first-call setup/Numba compilation. Warm-run Python `tracemalloc` peaks were
20,570,137 bytes (Earth), 22,309,041 bytes (Moon), and 24,841,579 bytes
(Mars). Terrain patches were constructed before tracing; those measurements
exclude native NumPy buffer allocation and are not process peak RSS. Lunar
full-resolution 3200 × 3200 performance remains unverified.

## 9. Layer 5 integration contract

Layer 5 supplies a `Layer5TemporalInput(selected_body, layer4_result)` and
consumes the matching `RehearsalEvaluation`. It receives the selected body,
candidate and continuous illumination windows, qualifying and total
illumination duration, exact sampled timestamps, target and patch
classifications, target ray statuses, solar geometry summaries, terrain-shadow
statistics, valid/elevation/measured coverage, interruptions, source-grid
identity, kernel identities and hashes, structured evidence statuses,
provenance, criteria outcomes, and scientific limitations.

Layer 5 **must not recalculate**:

- solar geometry;
- terrain illumination;
- shadow classifications; or
- temporal rehearsal windows.

Layer 5 must preserve the evidence distinctions and uncertainty supplied by
Layer 4. It must not reinterpret `UNKNOWN`, `NO_DATA`, `INSUFFICIENT_COVERAGE`,
or unavailable observation counts as confirmed illumination, darkness, or
complete coverage. It must retain sampling uncertainty, source and kernel
provenance, body-native frame/grid identity, validation status, and scientific
limitations. It must not create confidence or observational-accuracy claims
unsupported by the evidence. Layer 4 provides this handoff contract; no
Layer 5 suitability scorer or running cross-layer service is implemented in
this package.

## 10. Scientific limitations

- Independent observational shadow-accuracy validation has not been
  established for Earth, Moon, or Mars.
- Lunar measured-observation coverage is `UNAVAILABLE` if an aligned LOLA
  count raster is absent; finite interpolated elevation is not measured
  support.
- Full-resolution lunar 3200 × 3200 performance remains unverified.
- The MOLA-origin to NAIF Mars center-499 tie is unverified; no translation is
  applied.
- Mars terrain-horizon search is finite and defaults to 50 km.
- All bodies use a point-Sun/direct-illumination treatment; illumination is
  not thermal modelling.
- Shadow classification does not establish rover safety, mission suitability,
  or operational readiness.
- Earth uses local GLO-30 terrain and does not model local geoid slope,
  atmospheric refraction, or vegetation separately.
- Lunar horizons are limited by the regional DEM, finite search range, and
  fixed 5 m ray steps.
- Mars MEGT areoid-relative topography is not combined with MEGR radial
  distance; MEGC observation support stays separate from surface validity.
- Temporal windows are sampled. Transitions between sample times are
  uncertain by the stated time-step bounds and unsupported gaps are not
  bridged.

## 11. Historical verification record

The following are historical records from the earlier Layer 4 work; the
automated test files have since been removed and are not included here as
executable tests:

- **Automated tests:** 18 tests passed in the historical focused suite,
  including body-selective dispatch, temporal aggregation/gap cases, Earth
  target geometry, lunar count alignment, Mars seam mapping, and synthetic
  Mars flat/ridge/coverage cases.
- **Earth retained-terrain execution:** a 65 × 65 SP Crater GLO-30 crop, target
  `(32, 32)`, sampled at 2024-06-21 18:00 and 19:00 UTC. The target was
  `ILLUMINATED` at both samples with `SEARCH_LIMIT_REACHED`; valid terrain
  coverage was 100%, with a 500 m horizon limit and one candidate interval.
- **Moon retained-terrain execution:** a 65 × 65 Site01 LOLA crop, target
  `(32, 32)`, sampled at 2026-11-14 00:00 and 01:00 UTC. The target was
  `ILLUMINATED` at both samples with `SEARCH_LIMIT_REACHED`; count evidence
  was `UNAVAILABLE`, measured-cell counts remained null, and one candidate
  interval was returned with a 100 m horizon limit.
- **Mars retained-terrain execution:** a 61 × 61 native MEGR/MEGC window,
  target `(30, 29)` at global MOLA `(2330, 7229)`, sampled at 2024-04-01
  00:00 and 01:00 UTC. The target was `SURFACE_FACING_AWAY` at both samples,
  the target count was 13, measured terrain coverage was 82.29%, and no
  candidate interval was returned; the configured horizon limit was 50 km.
- These executions verified that the respective retained inputs could be
  processed; they are not independent observational shadow validation.
  Observational validation remains **`NOT_VALIDATED`**.

## 12. Package installation

`pyproject.toml` is required package configuration and is preserved. It defines
the `rehearsal` distribution, Python `>=3.10`, production dependencies
`numpy`, `pyproj>=3.6`, `pyyaml`, `spiceypy>=7.0.0`, and `tzdata>=2024.1`,
the setuptools build backend, and package discovery from `src`. Numba is
declared in the optional `performance` extra (`numba>=0.59`); there are no
test-only dependencies or pytest configuration in this file.

Install the package and acceleration extra from this directory with:

```bash
python -m pip install -e ".[performance]"
```

Earth, lunar, and Mars geometry still require compatible local kernels. The
`configs/thresholds.yaml` file is retained for the solar-only threshold
utility. The scientific source data and provenance remain separate from
generated Python/Numba caches; caches are not runtime deliverables.
