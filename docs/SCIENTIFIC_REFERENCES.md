# TERRAWINDOW scientific references and provenance

This document backs the claims in the [README](../README.md): which data TERRAWINDOW actually used, which calculations it
ran on them, what supports those calculations in the literature, how each result was checked, and what remains unverified.
Every external link and citation below was checked on 2026-11-15; items that could not be checked are marked **unverified**
rather than guessed. Nothing here is NASA-endorsed, and no result is observationally validated.

Contents: [1 Data actually used](#1-data-actually-used) · [2 Catalogued or suggested, not used](#2-catalogued-or-suggested-but-not-used) ·
[3 SPICE kernels](#3-spice-kernels-layer-4) · [4 Methods and their sources](#4-methods-and-their-sources) ·
[5 Verification levels](#5-what-has-been-verified-and-how) · [6 Research demonstration](#6-research-demonstration-a-characterised-earth-candidate) ·
[7 Licences and attribution](#7-licences-and-attribution) · [8 AI assistance](#8-ai-assistance-disclosure) ·
[9 References](#9-references-apa-7th-edition) · [10 Link audit](#10-link-audit)

## 1. Data actually used

"Used" means the file is retrieved by Layer 2 on the demonstration machine and read by a result reported in the README or
shown by the interface. Dataset identifiers, checksums and citations are recorded in `backend/data/manifest.json` and the
`*.provenance.json` files beside each raster (version-controlled); the rasters themselves are not committed.

### 1.1 Moon

| Item | Value |
|---|---|
| Dataset | LOLA 5 m/pixel south-pole site model, **Site01 (Connecting ridge)**, surface product `Site01_final_adj_5mpp_surf.tif` |
| Provider, mission | NASA Planetary Geodesy Data Archive (PGDA); Lunar Orbiter Laser Altimeter on the Lunar Reconnaissance Orbiter |
| Product page | <https://pgda.gsfc.nasa.gov/products/78> ("High-Resolution LOLA Topography for Lunar South Pole Sites") |
| File | <https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif> (server date 2020-06-05) |
| Required citation | Barker et al. (2021), per the product page: "Please cite ... Barker, M.K., et al. (2021)". See [references](#9-references-apa-7th-edition) |
| Coverage | 16 x 16 km, 3200 x 3200 cells, centre about 89.46 deg S, 137.46 deg W |
| Resolution | 5 m square cells; analysed by Layer 3 at 30 m and coarser for comparison, and 40 m for the interface's Layer 4 runs |
| Reference frame, units | Heights in metres above a 1737.4 km reference sphere; MOON_ME frame, DE421 realisation (product page); south polar stereographic projection |
| Retrieved | 2026-11-13 by `terrawindow-data` 0.1.0; 40,980,810 bytes |
| SHA-256 | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| Used in | Layer 3 profiles, comparison, screening reference; Layer 4 lunar illumination terrain; Layer 5 candidate |
| Known limitations | Heights are interpolated where no laser return exists (an observation-count product would show where; none is retrieved, so Layer 4 reports measured coverage as `UNAVAILABLE`); interpolation smooths slope and roughness there; 5 m cells do not resolve rover-scale rocks or small craters; one site only |

PGDA 78's abstract names Sites 1, 4, 7 and 11 (its site list also shows Site06). Layer 2's catalogue lists ten site directories;
**only Site01 is retrieved and used.**

### 1.2 Mars

| Item | Layer 2/3 regional terrain | Layer 4 solar-geometry terrain |
|---|---|---|
| Dataset | MGS MOLA MEGDR median topography, **128 pixels/degree**, product `megt44n000hb` (PDS4 `urn:nasa:pds:mgs_mola_topography_derived:data_meg128:megt44n000hb`, v1.1), region `jezero-mola-megdr128` | MGS MOLA MEGDR **32 pixels/degree**, products `megt90n000fb` (topography), `megc90n000fb` (observation counts), `megr90n000fb` (mean planetary radius); PDS3 version 2.0, PDS4 label 1.1 |
| Provider, mission | NASA Planetary Data System, Geosciences Node; Mars Orbiter Laser Altimeter on Mars Global Surveyor | same |
| Archive | <https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/> (collection `meg128`); overview <https://pds-geosciences.wustl.edu/missions/mgs/megdr.html> | same bundle, collection `meg032` |
| Dataset identifier | PDS3 `MGS-M-MOLA-5-MEGDR-L3-V1.0` (product label); PDS4 bundle `urn:nasa:pds:mgs_mola_topography_derived` v1.0. DataCite DOI for the bundle: 10.17189/1z1b-kv84 | same |
| Coverage | Jezero region, 76.4 to 78.6 E, 17.4 to 19.4 N (282 x 256 cells, about 125 x 119 km), cut from the 44 x 90 degree tile | global; Layer 4 reads a 61 x 61 cell window (about 113 km) around the target |
| Resolution | 463.06 m pixel (439 m east-west on the ground at Jezero); analysed at 463 m, 926 m and 1852 m | 1852.23 m pixel |
| Frame, units | Heights in metres above the MOLA areoid (label: "Goddard Mars potential model GMM3 (mgm1025) evaluated to degree and order 50"); planetocentric, east-positive, IAU 2000; equirectangular projection on a 3396.0 km sphere | same frame; radii in metres (physical radius = sample + 3,396,000 m) |
| Retrieved | 2026-11-14; 76,459 bytes (region only, by HTTP range request) | Acquired 2026-11-14 (Layer 4 provenance record); this demonstration machine re-fetched the files from the PDS `meg032` directory on 2026-11-15 and the engine verified the checksums; 132,710,400 bytes each |
| SHA-256 | region: `1d686bfbb4a5bdd87779f0a7809998a279564033d4b3096489d34f4e1f9e62f3` | `megt` `09ae1c09...ad8b`, `megc` `83aeb83d...45c0`, `megr` `42d8b660...eb8` (full values in `solar_geometry_engine/data/mars/mola_megdr/PROVENANCE.json`; Layer 4 re-hashes them on every read) |
| Used in | Layer 3 Mars terrain, Mars-Earth comparison, Layer 5 Mars candidate, the interface's Jezero preview | Layer 4 Mars solar geometry and illumination |
| Known limitations | Each pixel is the median of the shots in a 1/128 degree bin; empty bins are interpolated and cannot be told from measured ones (PDS: about 55 % of equatorial bins hold a shot; track gaps to about 12 km); at least 3 m vertical uncertainty; 463 m cells cannot represent rover-scale slope, rocks or traction; the areoid is named differently by USGS (GMM-2B) and the product label (GMM3), and heights are used as published | zero-count bins make Layer 4 rays `INSUFFICIENT_COVERAGE` (neither lit nor dark); in the 2.2 x 2.0 degree Jezero region about 81 % of the bins hold a count and about 48 % also have four counted neighbours; the MOLA coordinate origin and NAIF centre 499 are not tied |

The USGS Astropedia 463 m mosaic was examined and **not** used: against the PDS product it is the 2 x 2 mean of PDS pixels (Pearson r = 1.0000
after a half-pixel shift, RMSE 0.31 m; unshifted r = 0.9992, RMSE 19.7 m), so it is smoother.

### 1.3 Earth

| Item | Value |
|---|---|
| Dataset | Copernicus DEM **GLO-30** (a digital *surface* model: vegetation and buildings are included) |
| Provider | European Space Agency / Copernicus programme; credited to DLR and Airbus in the product's attribution wording; distributed as public cloud-optimised GeoTIFFs on AWS Open Data |
| Product page | <https://doi.org/10.5270/esa-c5d3d65> (resolves to the Copernicus Data Space page "Copernicus DEM - Global and European Digital Elevation Model"; acquisition 2011-2015) |
| Tile read | `Copernicus_DSM_COG_10_N35_00_W112_00_DEM` (and tiles for the other regions); URL in each provenance file |
| Regions retrieved by Layer 2 | `sp-crater` (111.72 to 111.54 W, 35.51 to 35.655 N), `imperial-valley` (115.6 to 115.43 W, 32.86 to 33.005 N), `sf-volcanic-field` (112.0 to 111.35 W, 35.25 to 35.75 N). Pixels are copied on the source grid, no resampling |
| Resolution | 30 m (1 arc second; 30.92 m east-west at these latitudes) |
| Reference frame, units | Orthometric height in metres above the EGM2008 geoid; WGS84 geographic grid (EPSG:4326) |
| SHA-256 | sp-crater `e5c7daf2...a7c2`, imperial-valley `6a4c1077...22e2`, sf-volcanic-field `b030f02c...f1bd` (full values in `backend/data/manifest.json`) |
| Used in | Layer 3 Earth profiles, comparison against the Moon and Mars, screening; Layer 4 Earth terrain (illumination); Layer 5 Earth candidate |
| Known limitations | Surface model, not bare ground; 30 m cells do not resolve rover-scale obstacles; GLO-30 is an elevation product, not soil strength or rock abundance |

## 2. Catalogued or suggested, but not used

| Resource | Status |
|---|---|
| ESA WorldCover 10 m 2021 v200 (<https://esa-worldcover.org/en/data-access>; <https://doi.org/10.5281/zenodo.7254221>) | **Optional code path** in Layer 3 (`include_landcover`) and catalogued in Layer 2. **No land-cover raster is retrieved and no reported result uses it** |
| Nine other LOLA site directories (Site04, 06, 07, 11, 20, 23, Haworth, Shoemaker, DM2) | Catalogued by Layer 2, not retrieved |
| Other MOLA tiles (15 of the 16 128 ppd tiles) | Catalogued, not retrieved |
| NASA Lunar Polar Illumination (PGDA 69, <https://pgda.gsfc.nasa.gov/products/69>; 240 m and 60 m polar maps) | **Not used.** A candidate independent reference for lunar illumination; it is the natural next validation dataset |
| Enhanced lunar south-pole topography with shape-from-shading (PGDA 104, <https://pgda.gsfc.nasa.gov/products/104>; 5 m SDEMs for the 13 original Artemis III candidate regions; Bertone et al., 2026) | **Not used.** Suggested future terrain input |
| NASA Earthdata (<https://www.earthdata.nasa.gov/>) | **Not used.** Listed in the project proposal as a resource; no Earthdata product is read |
| HiRISE or CTX digital terrain models for Mars | **Not integrated.** Needed for any rover-scale Mars claim |
| Lunar observation-count rasters (LOLA) | **Not retrieved.** Needed for measured lunar coverage in Layer 4 |

## 3. SPICE kernels (Layer 4)

Kernels are committed under `solar_geometry_engine/kernels/kernels/` and are identified by SHA-256 in every Layer 4 result.
Source: NAIF generic kernels, <https://naif.jpl.nasa.gov/pub/naif/generic_kernels/>. Coverage was read from the kernels with SpiceyPy on 2026-11-15.

| Kernel | Role | Coverage (UTC) | SHA-256 |
|---|---|---|---|
| `naif0012.tls` | Leap seconds; UTC to ET | n/a | `678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b` |
| `de440s.bsp` | Sun, Earth, Moon, planets (JPL DE440, short span) | 1849-12-26 to 2150-01-22 | `c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2` |
| `mar099s.bsp` | Mars centre (NAIF 499) and moons | 1994-12-31 to 2049-12-31 | `997dc93ba640e476da7a494d2237dcdeb145e528db37be8ccee588c615e4e1ff` |
| `pck00011.tpc` | Planetary constants, shapes, IAU rotation (current `IAU_MARS`) | n/a | `3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1` |
| `mars_iau2000_v1.tpc` | The IAU 2000 Mars orientation in which MOLA is expressed | n/a | `07ba38b939ae92c085882752a523addd749fde0abb7a3468423099ed02bb3949` |
| `moon_pa_de440_200625.bpc` | Lunar principal-axis orientation (DE440) | 1549-12-31 to 2650-01-25 | `60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f` |
| `moon_de440_250416.tf` | Lunar frames including `MOON_ME` (file dated 2025-04-16) | n/a | `a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768` |
| `earth_000101_270208_261113.bpc` | High-precision Earth orientation, `ITRF93` | 2000-01-01 to 2027-02-09 | `6e77690ba455a644e509b0b9cb308b0dec1a7154ceecf3355659b917b21ca45e` |

- **Time system:** UTC in and out; converted to ephemeris time with the leap-seconds kernel. Samples are left-closed, right-open intervals, so a window edge is known only to within one step.
- **Frames:** Earth `ITRF93` (WGS84 geodetic coordinates, geometric positions, no refraction or light-time correction); Moon `MOON_ME`; Mars `IAU_MARS` (`pck00011`), with an epoch-dependent rotation from the MOLA `IAU2000_MARS` realisation.
- **Earth dates are limited to 2027-02-09** by the Earth orientation kernel. This is the one coverage limit that a user can hit.
- **File name:** NAIF has since replaced the Earth orientation file; `earth_000101_270208_261113.bpc` is no longer at its original path, and the current release is `earth_000101_270210_261114.bpc`. The repository's file is identified by its hash above.

## 4. Methods and their sources

| Quantity | Implementation | Supported by |
|---|---|---|
| Slope, aspect | Horn 3 x 3 finite difference on a metric grid; degrees from horizontal (Layer 3 `terrain/slope.py`) | Horn (1981) |
| Terrain Ruggedness Index | Layer 3 `terrain/roughness.py` | Riley et al. (1999) |
| RMS height roughness, relief | Detrended RMS height in a moving window; max minus min in a square window (Layer 3) | Project definitions; stated beside every result |
| Grid handling | Aggregation only to coarser scales; equirectangular grids resampled to a local metric grid using the projection's own scale factors | Verified by test against synthetic planes (section 5) |
| Solar geometry | SPICE `spkpos`, `pxform`, UTC to ET (Layer 4) | Acton (1996); Acton et al. (2018); Park et al. (2021) for DE440 |
| Moon orientation | `MOON_ME` through DE440 principal axes | NAIF lunar frame kernel; Park et al. (2021) |
| Mars orientation | `IAU_MARS` and the MOLA IAU 2000 realisation | Archinal et al. (2018) for the IAU model; NAIF kernels |
| Terrain illumination | Ray marching along the solar azimuth over the DEM, point-Sun, direct illumination only (Layer 4 Numba kernels) | Method documented in `solar_geometry_engine/LAYER4_DOCUMENTATION.md` (the engine's authors); related lunar illumination work: Mazarico et al. (2011), Barker et al. (2021) |
| Mission assessment | Rule-based per-criterion comparison with explicit evidence status (Layer 5) | `docs/LAYER5_DOCUMENTATION.md`; thresholds are caller assumptions |

## 5. What has been verified, and how

Five levels are kept apart. **Independent computational agreement is not observational validation.**

### 5.1 Independently cross-checked calculations

| Check | How | Result |
|---|---|---|
| Moon/Earth/Mars terrain statistics against known answers | Synthetic planes of known slope (5.71 degrees) and ridges through the real code paths, including at 0, 18.4 and 60 degrees N for the equirectangular grid | Recovered; the grid test fails without the scale-factor fix |
| Mars source integrity | All 72,192 Jezero pixels compared with the raw big-endian PDS values read by NumPy from the product label, independently of GDAL (`verify_mola_against_pds.py`) | Identical |
| Mars slope | Layer 3 mean slope vs an independent Horn calculation on source pixels with true ground spacing | 3.11 vs 3.21 degrees (3 %); the difference is the bilinear resampling; test tolerance 5 % |
| Earth solar elevation | NOAA/Meeus low-precision algorithm, 12 samples, SP Crater | Max 0.016 degrees |
| Moon solar elevation | Same SPICE ephemeris, but `IAU_MOON` orientation (`pck00011`) instead of `MOON_ME` (DE440) | Max 0.001 degrees (only the orientation model is independent) |
| Mars solar elevation | Allison and McEwen (2000) "Mars24" analytic algorithm | Max 0.36 degrees (the fit is good to a few tenths of a degree) |
| Mars solar elevation, geometry path | SPICE `IAU_MARS` over the ellipsoid normal, without the MOLA frame transform | Max 0.003 degrees |
| Gateway fidelity | Same requests direct and through the gateway | Identical after local paths are hidden |

Reproduce with `backend/geoprocessing/scripts/layer4_reference_check.py`, `mars_vs_earth.py`, `moon_vs_earth.py` and `backend/data_integration/scripts/verify_mola_against_pds.py`. The first run needs the stored datasets and (for Layer 4) SPICE and Numba.

### 5.2 Computed scientific outputs (not independently cross-checked beyond 5.1)

Terrain profiles, comparisons, screening, rehearsal windows and terrain-shadow classifications, and Layer 5 assessments are computed by the repository's code
from the stored data. Their correctness rests on the unit tests and the checks above, not on observations.

### 5.3 Observationally validated findings

**None.** No illumination, shadow, sun-angle or terrain measurement from observations (for example NASA's lunar polar illumination maps, PGDA 69) has been compared with these outputs.
Every Layer 4 result carries `observational_validation_status = NOT_VALIDATED`, and the interface says "Not independently validated".

### 5.4 Unverified assumptions

- Screening tolerances (3 degrees mean and median slope, 5 degrees 90th percentile, 50 % roughness and relief, 0.10 in slope fractions) and every mission threshold are adjustable assumptions, not standards.
- The MOLA coordinate origin (Mars) and NAIF centre 499 are not tied; no translation is applied.
- Layer 4 treats the Sun as a point and counts only direct illumination; no thermal or atmospheric effects.
- Layer 5 has no minimum number of nonzero slope samples for a fraction metric.
- Layer 4 horizon search is finite (2.5 km Earth and Moon, 50 km Mars by default; 10 km is used for Jezero in the interface).
- DE421-to-DE440 lunar frame alignment is close, not identical (NAIF documents up to about 0.54 m at the surface).

### 5.5 Missing evidence

Observational validation of illumination and shadows; measured lunar observation coverage; rover-scale terrain for Mars; soil strength, traction and rock abundance for any body;
Layer 4 trusted server-side execution records (so Layer 5 can treat Layer 4 values as more than claims); a Layer 6 record of any result.

### 5.6 How Layer 5 treats evidence

| Status | Meaning |
|---|---|
| `PASS`, `FAIL` | A supported **Layer 3** value satisfies or does not satisfy the configured comparison |
| `UNVERIFIED` | A Layer 4 value that matches the candidate's grid is a caller claim: it is shown with its claimed comparison but cannot pass or fail |
| `NOT_ASSESSED` | Layer 4 evidence on a different grid (all of Mars: 1852 m vs 463 m) |
| `INDETERMINATE` | Evidence is missing or insufficient; the configured missing-data behaviour applies and **missing evidence never becomes a pass** |

Overall: `SUITABLE` only if every configured required criterion passed on adequate Layer 3 evidence, all required categories are declared, and no Layer 4 claim was needed.
`SUITABLE` is not a safety or readiness statement. Tests: `backend/geoprocessing/tests/test_layer5.py`, `test_rehearsal_service.py`.

## 6. Research demonstration: a characterised Earth candidate

Reproduce: `python scripts/research_demonstration.py` in `backend/geoprocessing` (needs the stored Site01 and `sf-volcanic-field` rasters, SPICE and Numba;
writes `backend/data/local/results/research_demonstration.json`).

**Objective.** Find Earth terrain whose slope and roughness statistics resemble the lunar south-polar reference (Site01), as a first, terrain-only step towards an analog for lunar south-polar rover mobility under low sun.

**Search.** The San Francisco Volcanic Field, Arizona (Copernicus GLO-30), was cut into 342 patches of 3 km and screened at 30 m against ranges derived from Site01:
mean slope 9.29 to 15.29 degrees, 90th-percentile slope 15.02 to 25.02 degrees, RMS height roughness 0.43 to 1.29 m (reference plus screening tolerances). **5 patches passed, 322 were rejected and 15 had insufficient data.**

**Candidate.** The passing patch closest to the reference (smallest summed relative difference in mean slope, 90th-percentile slope and roughness) is patch `r14c17`, centre **35.3614 N, 111.4239 W**
(elevation 1802 to 2434 m above the EGM2008 geoid over the 5.5 km box). It is characterised over a **5.5 x 5.5 km box** (111.4539 to 111.3939 W, 35.3368 to 35.3860 N, 30.5 km2), because Layer 4's horizon search needs room around the target.

**Terrain at 30 m (Layer 3; Site01 in brackets).**

| Statistic | Candidate box | Site01 |
|---|---|---|
| Mean slope | 9.82 deg | 12.29 deg |
| Median slope | 7.71 deg | 12.09 deg |
| 90th-percentile slope | 21.02 deg | 20.02 deg |
| Share steeper than 20 deg | 0.119 | 0.101 |
| Share steeper than 15 deg | 0.249 | 0.320 |
| Median RMS height roughness | 0.88 m | 0.86 m |
| Median relief, 330 m window | 54 m | 78 m |
| Median relief, 990 m window | 183 m | 224 m |

At 60 m and 120 m the candidate's mean slope is 9.52 and 8.97 degrees (Site01: 12.09 and 11.83). Across all scales the comparison puts **25 of 35 criteria within tolerance and 10 outside** (a tally, not a score; the whole SP Crater region scored 9 within and 26 outside, and the Imperial Valley control 5 and 30).
The candidate is gentler than the lunar site on median slope and the steeper share, close on the steep tail and roughness.

**Rehearsal geometry (Layer 4, 2026-12-15, every 15 minutes, 96 samples, Earth `ITRF93`).** Sun elevation ranged from -77.8 to 31.3 degrees. The target pixel was illuminated for one continuous 7.5 h interval (27,000 s) spanning 2.3 to 31.3 degrees,
which fails a 0.5 to 10 degree sun-elevation window as a unit, so Layer 4 reported **0 candidate low-sun windows** (its criteria apply to a whole continuous interval; it does not split an interval by elevation).
Counting the per-sample output directly shows **4 samples (60 minutes) with the target illuminated and the sun between 0.5 and 10 degrees**, all in the morning (14:45 to 15:30 UTC), and 4 more in that band with the target facing away or shadowed. Peak terrain shadow over the box was 39.0 % (mean 7.3 %); valid terrain coverage 100 %; time uncertainty +/-15 minutes.
This is the practical limit of an Earth analog at 35 degrees N: grazing sun lasts about an hour per day, against days at the lunar south pole (Site01: one 4.2-day window in a 7-day run).

**Layer 5 assessment (interface default lunar criteria; thresholds are assumptions).**

| Criterion | Status | Evidence |
|---|---|---|
| 90th-percentile slope <= 20 deg | **FAIL** | Measured 21.02 deg |
| Share steeper than 20 deg <= 0.15 | PASS | Measured 0.119 |
| Median roughness <= 1.5 m | PASS | Measured 0.88 m |
| Valid elevation coverage >= 0.9 | PASS | Measured 1.00 |
| Qualifying illumination >= 1 h (Layer 4) | UNVERIFIED | Layer 4 claims 0 s; comparison would FAIL but is only a claim |
| Peak terrain shadow <= 50 % (Layer 4) | UNVERIFIED | Layer 4 claims 39.0 %; comparison would PASS but is only a claim |

Overall **NOT_SUITABLE** (a supported required failure: slope). Spatial association with Layer 4 is `MATCHED_METADATA_UNVERIFIED`; gaps: unauthenticated Layer 4 evidence, no observational validation.

**Why NOT_SUITABLE when most measurements are within tolerance?** Two different tests are involved. The *screening and comparison tolerances* are deliberately wide (here a 90th-percentile slope anywhere from 15.0 to 25.0 degrees counts as lunar-like), so the candidate passes them. The Layer 5 *mission criterion* is a hard limit set by the user (90th-percentile slope at most 20 degrees), and the candidate measures 21.02 degrees. Layer 5 aggregates deterministically: one supported failure of a required criterion makes the whole assessment `NOT_SUITABLE`, however many other criteria pass; the passes are not averaged. The 20 degree limit is an assumption, not a standard, so the result says "does not meet this threshold on this evidence", not "is unsuitable as an analog". It is neither a confirmed analog nor a discovery.

*Reproduced on 2026-11-15 from a fresh run of the script; all of these were checked programmatically: 342 patches screened; 5 candidates, 322 rejected, 15 insufficient; best candidate `r14c17` at 35.3614 N, 111.4239 W; 5520 m box of 30.5 km2; mean slope 9.82 and 12.29 degrees; 90th percentile 21.02 and 20.02; roughness 0.88 and 0.86 m; 25 within and 10 outside tolerance of 35 comparisons; sun -77.8 to 31.3 degrees; no candidate window and one 27,000 s illuminated interval; 60 low-sun minutes; shadow peak 39.0 % and mean 7.3 %; Layer 5 statuses FAIL, PASS, PASS, PASS, UNVERIFIED, UNVERIFIED.*

**Interpretation and limits.** This is a **preliminary characterised candidate, not a discovery of a new analog.** It shows that screening with TERRAWINDOW's measured statistics narrows 342 patches to 5, that the best one resembles Site01 on most terrain criteria at 30 m and
above, and that it slightly exceeds the example 20 degree slope limit. It says nothing about regolith, rock abundance, wheel traction, thermal conditions or gravity; 30 m surface-model cells cannot show obstacles a rover must avoid;
the lunar cells include interpolated heights; the sun result is computed and not observed; and the thresholds are placeholders for a mission team's own.

## 7. Licences and attribution

The repository has **no licence file**. Nothing in it should be read as open-source licensed; third-party materials keep their own terms.

| Material | Terms (as verified) | How TERRAWINDOW credits it |
|---|---|---|
| LOLA 5 m products (NASA PGDA) | NASA data; the product page asks users to cite Barker et al. (2021) | Cited in the README, the manifest and each result |
| MOLA MEGDR (NASA PDS) | DataCite record: US Government work, CC0 1.0 | DOI 10.17189/1z1b-kv84 cited; PDS3 identifier and product names given |
| Copernicus DEM GLO-30 | "Available worldwide with a free license". Unmodified data: "(c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved". **Derived products such as slope or hillshade count as modified data** and take the wording "produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" | Credit line in the README; the interface's slope and elevation figures are derived products |
| ESA WorldCover | CC BY 4.0; credit "(c) ESA WorldCover project [year] / Contains modified Copernicus Sentinel data ([year]) processed by ESA WorldCover consortium" | **Not used in any result**; code path only |
| NAIF SPICE kernels and toolkit | Citation encouraged (not required); NAIF names Acton (1996) and Acton et al. (2018); credit kernel producers. SpiceyPy is MIT; the CSPICE toolkit it wraps has its own NAIF terms (not reviewed) | Cited; kernel names and hashes returned with every result |
| Esri World Imagery and Dark Gray Canvas (Analog Explorer basemaps) | Esri's [attribution page](https://developers.arcgis.com/documentation/mapping-apis-and-services/deployment/basemap-attribution/) (read 2026-11-15) requires the text "Powered by Esri", linked to https://www.esri.com, when its services are used through open-source libraries such as MapLibre, plus the data-source credit. Esri's developer documentation, as summarised by a search, says World Imagery needs no API key and is provided free; Dark Gray Canvas tiles also returned HTTP 200 without a key, but terms specific to that layer were not reviewed. Service credits read from the services' metadata: World Imagery "Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community"; Dark Gray Canvas "Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community". Static maps in reports and academic works are permitted with acknowledgement (not legal advice) | The map attribution control shows a linked "Powered by Esri" plus each credit, and the credit lists in the About dialog, README and exports carry the same wording |
| OpenTopoMap | CC-BY-SA 3.0; "Kartendaten: (c) OpenStreetMap-Mitwirkende, SRTM / Kartendarstellung: (c) OpenTopoMap (CC-BY-SA)" | Credited in the map and README. Tile-usage policy not checked |
| CARTO dark basemap | **Replaced on 2026-11-15.** CARTO's current basemap terms define the free service as one that "uses a CARTO-issued API key"; the app had used a keyless tile URL, which worked but is not the arrangement the terms describe. The dark base is now Esri's Dark Gray Canvas with its label layer | No CARTO request is made. OpenStreetMap data credit is retained through Esri's credit |
| Terrain Tiles (Mapzen, AWS Open Data) | Used for relief tiles | Credited in the map and README |
| MapLibre GL JS | BSD-3-Clause | Dependency |
| Fonts (Geist, Geist Mono, Newsreader via Fontsource) | OFL-1.1 | Dependency |
| Python and JavaScript dependencies | MIT, BSD-3-Clause, Apache-2.0, ISC, MIT-CMU; **psycopg and fpdf2 are LGPL-3.0**, used as unmodified libraries by the Layer 6 service | Listed in each `pyproject.toml` and `package.json` |
| README screenshots | Captured from the TERRAWINDOW interface; they contain Esri, OpenTopoMap and OpenStreetMap map imagery and NASA/Copernicus-derived figures under the terms above | Credits kept in the README |

Open item before submission: Esri's terms for the Dark Gray Canvas layer were not reviewed beyond its general attribution requirements. The Esri credit strings and "Powered by Esri" are in place, and the CARTO dependency is removed.

## 8. AI assistance disclosure

TERRAWINDOW was built with AI coding assistants. In this repository's development, AI assistance (Claude Code, Anthropic) was used for **coding, debugging, UI and UX implementation, writing and running tests, browser testing and documentation**,
and for **research assistance** in locating and checking sources and citation metadata against live records. Other contributors' tools are not recorded in the repository; the team should confirm and add any.

AI assistance is not a source of scientific data or evidence. The terrain, kernels and checksums come from NASA, ESA/Copernicus and NAIF products; numerical results come from the repository's own code, tested against synthetic cases and independent calculations (section 5.1);
no AI model validated a scientific conclusion, and no output was produced or verified by NASA. Commits by the project owner carry no AI co-author trailers; this section is the disclosure.
**Space Apps rules** (read from the live [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) on 2026-11-15). The form asks: "Did you utilize any Super Intelligence (SI) tools and software in preparing your solution? If yes, how did you use them?" SI tools, including large language models, are permitted "as a tool to accelerate innovation and creativity" but "should not be used to come up with your idea of how to solve the challenge". Teams must "clearly indicate where and how SI tools were utilized": images and videos need a visible watermark if SI-generated, audio needs acknowledgement in descriptive text and metadata, and code and data "must acknowledge SI generation in descriptive text and metadata". Generated content "may not use, contain, or modify any NASA branding or design elements". The SI answer is for data collection and is not shown to judges, but judges see SI indicators inside the project. The "NASA Data" field asks for specific details on the NASA data and resources used (at least one is needed for a Global Award). "Space Agency Partner Data and Other References" asks teams to list all data, resources and tools, including any code, text and images, even open-source ones. TERRAWINDOW uses NASA data (LOLA, MOLA, SPICE) and ESA/Copernicus data, and no generated images or NASA branding. Its concept came from the team's original proposal; the team should confirm that statement. This section, the README's disclosure and `docs/SPACE_APPS_SUBMISSION.md` are the acknowledgement; the screenshots are captures of the running interface.

## 9. References (APA 7th edition)

**Datasets**

Barker, M. K., Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Head, J. W. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions. *Planetary and Space Science, 203*, Article 105119. https://doi.org/10.1016/j.pss.2020.105119

Bertone, S., McKenna, T. E., Barker, M. K., Mazarico, E., Beyer, R. A., & Petro, N. (2026). Enhanced topography models for selected lunar south pole regions with shape-from-shading. *The Planetary Science Journal, 7*(5), Article 118. https://doi.org/10.3847/PSJ/ae5b70 *(cited as the PGDA 104 data reference; the dataset is not used)*

European Space Agency, & Airbus. (2022). *Copernicus DEM* [Data set]. European Space Agency. https://doi.org/10.5270/esa-c5d3d65

European Space Agency. (2024). *Copernicus Global Digital Elevation Model* [Data set]. OpenTopography. https://doi.org/10.5069/G9028PQB

Smith, D. E., Neumann, G., & Hughes, M. N. (2026). *MGS MOLA derived topography - MEGDR and SHADR dataset bundle* (Version 1.0) [Data set]. NASA Planetary Data System. https://doi.org/10.17189/1z1b-kv84

Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann, C., Kirches, G., Wevers, J., Cartus, O., Santoro, M., Fritz, S., Lesiv, M., Herold, M., Tsendbazar, N.-E., Xu, P., Ramoino, F., & Arino, O. (2022). *ESA WorldCover 10 m 2021 v200* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.7254221 *(optional resource; not used in any result)*

Instrument and mission papers

Smith, D. E., Zuber, M. T., Frey, H. V., Garvin, J. B., Head, J. W., Muhleman, D. O., Pettengill, G. H., Phillips, R. J., Solomon, S. C., Zwally, H. J., Banerdt, W. B., Duxbury, T. C., Golombek, M. P., Lemoine, F. G., Neumann, G. A., Rowlands, D. D., Aharonson, O., Ford, P. G., Ivanov, A. B., ... Sun, X. (2001). Mars Orbiter Laser Altimeter: Experiment summary after the first year of global mapping of Mars. *Journal of Geophysical Research: Planets, 106*(E10), 23689-23722. https://doi.org/10.1029/2000JE001364

Smith, D. E., Zuber, M. T., Neumann, G. A., Lemoine, F. G., Mazarico, E., Torrence, M. H., McGarry, J. F., Rowlands, D. D., Head, J. W., Duxbury, T. H., Aharonson, O., Lucey, P. G., Robinson, M. S., Barnouin, O. S., Cavanaugh, J. F., Sun, X., Liiva, P., Mao, D., Smith, J. C., & Bartels, A. E. (2010). Initial observations from the Lunar Orbiter Laser Altimeter (LOLA). *Geophysical Research Letters, 37*(18). https://doi.org/10.1029/2010GL043751

Smith, D. E., Zuber, M. T., Neumann, G. A., Mazarico, E., Lemoine, F. G., Head, J. W., III, Lucey, P. G., Aharonson, O., Robinson, M. S., Sun, X., Torrence, M. H., Barker, M. K., Oberst, J., Duxbury, T. C., Mao, D., Barnouin, O. S., Jha, K., Rowlands, D. D., Goossens, S., ... McClanahan, T. (2017). Summary of the results from the Lunar Orbiter Laser Altimeter after seven years in lunar orbit. *Icarus, 283*, 70-91. https://doi.org/10.1016/j.icarus.2016.06.006

*(Author lists follow the Crossref records checked on 2026-11-15; where a record has more than 20 authors, APA 7 lists the first 19, an ellipsis and the last. Names are as Crossref spells them.)*

**Methods**

Acton, C. H. (1996). Ancillary data services of NASA's Navigation and Ancillary Information Facility. *Planetary and Space Science, 44*(1), 65-70. https://doi.org/10.1016/0032-0633(95)00107-7

Acton, C., Bachman, N., Semenov, B., & Wright, E. (2018). A look towards the future in the handling of space science mission geometry. *Planetary and Space Science, 150*, 9-12. https://doi.org/10.1016/j.pss.2017.02.013

Allison, M., & McEwen, M. (2000). A post-Pathfinder evaluation of areocentric solar coordinates with improved timing recipes for Mars seasonal/diurnal climate studies. *Planetary and Space Science, 48*(2-3), 215-235. https://doi.org/10.1016/S0032-0633(99)00092-6

Archinal, B. A., Acton, C. H., A'Hearn, M. F., Conrad, A., Consolmagno, G. J., Duxbury, T., Hestroffer, D., Hilton, J. L., Kirk, R. L., Klioner, S. A., McCarthy, D., Meech, K., Oberst, J., Ping, J., Seidelmann, P. K., Tholen, D. J., Thomas, P. C., & Williams, I. P. (2018). Report of the IAU Working Group on Cartographic Coordinates and Rotational Elements: 2015. *Celestial Mechanics and Dynamical Astronomy, 130*(3), Article 22. https://doi.org/10.1007/s10569-017-9805-5

Horn, B. K. P. (1981). Hill shading and the reflectance map. *Proceedings of the IEEE, 69*(1), 14-47. https://doi.org/10.1109/PROC.1981.11918

Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. *Icarus, 211*(2), 1066-1081. https://doi.org/10.1016/j.icarus.2010.10.030

Park, R. S., Folkner, W. M., Williams, J. G., & Boggs, D. H. (2021). The JPL planetary and lunar ephemerides DE440 and DE441. *The Astronomical Journal, 161*(3), Article 105. https://doi.org/10.3847/1538-3881/abd414

Riley, S. J., DeGloria, S. D., & Elliot, R. (1999). A terrain ruggedness index that quantifies topographic heterogeneity. *Intermountain Journal of Sciences, 5*(1-4), 23-27. https://arc.lib.montana.edu/ojs/index.php/IJS/article/view/2914 *(no DOI; volume and pages not confirmed on the journal page)*

NOAA Global Monitoring Laboratory. (n.d.). *Solar calculation details*. https://gml.noaa.gov/grad/solcalc/calcdetails.html *(states its equations are based on Meeus's Astronomical Algorithms; Meeus's publisher and year were not verified, so the book is not listed)*

**Problem context**

Edgar, L. A., Rumpf, M. E., Skinner, J. A., Gullikson, A. L., Keszthelyi, L. P., Hunter, M. A., & Gaither, T. (2024). *Assessing community needs for terrestrial analog studies* (Open-File Report 2024-1042). U.S. Geological Survey. https://doi.org/10.3133/ofr20241042 *(authors from the Crossref record; the USGS page could not be opened, so a generational suffix on one name, if any, is unconfirmed)*

Litaker, H. L., Jr., Beaton, K. H., Bekdash, O. S., Crues, E. Z., Paddock, E. J., Rohde, B. A. J., Reagan, M. L., Van Velson, C. M., & Everett, S. F. (2024). *South pole lunar lighting studies for driving exploration on the lunar surface* [Conference paper]. 46th IEEE Aerospace Conference, Big Sky, MT, United States. NASA Technical Reports Server. https://ntrs.nasa.gov/citations/20240011393 *(year is the NTRS record date, 2024-10-03; the conference was held in March 2025)*

Null, C. (2025). *Lunar south pole light, human vision, and simulation* [Workshop presentation]. LAMP-Rover Workshop, Moffett Field, CA, United States. NASA Technical Reports Server. https://ntrs.nasa.gov/citations/20250003890

Chappell, M. (2024, December 24). *Characterizing the visual experience of astronauts at the lunar south pole*. NASA Engineering and Safety Center. https://www.nasa.gov/centers-and-facilities/nesc/characterizing-the-visual-experience-of-astronauts-at-the-lunar-south-pole/

NASA Space Apps Challenge. (2026). *Identify Earth locations that analog the permanent Moon base locations and Mars* [Challenge page]. https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/

NASA National Space Science Data Center. (n.d.). *Mars fact sheet*. https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html *(source of the orientation constants shown in the interface: gravity, obliquity, day length, pressure; used in no calculation)*

**What the literature supports.** The USGS report documents the community need for terrestrial analog studies and is the problem statement TERRAWINDOW addresses. The NASA lighting papers and NESC article support the claim that
low-angle south-polar illumination is a distinct challenge for driving and vision; they motivate Layer 4 and are **not** validation of its outputs. Mazarico et al. (2011) and Barker et al. (2021) are the closest published lunar illumination
and topography work. None of these supports a specific TERRAWINDOW numerical result.

**Not cited on purpose.** The earlier README, `backend/data/manifest.json`, the Jezero provenance record and the Layer 2 catalogue gave the MOLA dataset authors as "Smith, Zuber, Neumann, Guinness, & Slavney (2003)". No live source supports that author list. All four were corrected on 2026-11-15 to the PDS DataCite record (Smith, Neumann, & Hughes, 2026; DOI 10.17189/1z1b-kv84), which also says the data are a U.S. Government work released under CC0 1.0. Raster checksums and the product identifiers are unchanged.
Genova et al. (2016) was not cited as the source of the MOLA areoid: the 2003 label's "GMM3 (mgm1025)" predates it and the link is unconfirmed.

## 10. Link audit

Checked 2026-11-15 with HTTP requests and, for DOIs, the Crossref and DataCite APIs. "OK" means the page loaded and matches the description.

| Link | Result |
|---|---|
| <https://pgda.gsfc.nasa.gov/products/78>, `/69`, `/104` | OK. Product 78 covers Sites 1, 4, 7 and 11 (and lists Site06), not all south-pole sites |
| <https://pds-geosciences.wustl.edu/missions/mgs/mola.html>, `/megdr.html`, the PDS4 bundle and `meg032`/`meg128` directories | OK |
| <https://naif.jpl.nasa.gov/naif/>, `/tutorials.html`, `/data.html`, `/credit.html`, `generic_kernels/` and seven of the eight kernel files | OK |
| `pck/earth_000101_270208_261113.bpc` at NAIF | **404** (replaced by `earth_000101_270210_261114.bpc`); the repository's copy is identified by its hash |
| <https://doi.org/10.5270/esa-c5d3d65>, <https://doi.org/10.5069/G9028PQB> | OK |
| <https://esa-worldcover.org/en/data-access>, DOI 10.5281/zenodo.7254221 | OK (the DOI was confirmed through DataCite; doi.org blocks automated requests) |
| <https://www.earthdata.nasa.gov/> | OK |
| <https://doi.org/10.3133/ofr20241042> | DOI resolves; the USGS page itself returned 403 to the checker, so the metadata is from Crossref |
| NTRS 20240011393, NTRS 20250003890, the NESC article | OK; titles match |
| <https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/> and the [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) | **OK when opened in Chrome** on 2026-11-15 (command-line tools failed on this machine's certificate store). The challenge title is "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars". The submission form itself needs a login and was not opened; the guide describes its fields |
| DOIs in section 9 | Verified through Crossref, except where a note says otherwise |
