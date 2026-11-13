# TERRAWINDOW Layer 2: Scientific Data Integration

Finds the open datasets the project uses, retrieves them into a local store, checks that each
file is what it claims to be, and records where it came from. Layer 3 reads the store's manifest,
so anything fetched here is usable there by id, with no file paths passed around.

| Responsibility in the proposal | Where it lives |
|---|---|
| Identify available datasets | `catalog.py`: every dataset, URL pattern, citation, licence, limitation |
| Retrieve relevant geographic regions | `fetch.py` (whole files), `prepare.py` (regions cut from tiled datasets) |
| Preserve data provenance | a `.provenance.json` beside every file: source URL, time, SHA-256, citation |
| Validate coordinate systems and units | `validate.py`: CRS, body, units, pixel size, value range |
| Record resolution and coverage limitations | validation summary and `limitations`, carried into the manifest |
| Prepare analysis-ready data | `manifest.json`: a dataset is listed with `ready: true` only if no check failed |

## Setup

Uses the same virtual environment as Layer 3.

```bash
cd backend
geoprocessing/.venv/Scripts/python -m pip install -e "data_integration[dev]"
```

## Use

```bash
terrawindow-data list
terrawindow-data fetch lola-5mpp-site01
terrawindow-data fetch lola-5mpp-site01 --products uncertainty slope counts
terrawindow-data region copernicus-glo30 sp-crater -111.72 35.51 -111.54 35.655
terrawindow-data validate path/to/any.tif --body moon
terrawindow-data show lola-5mpp-site01
```

```python
from terrawindow_data import CATALOG, fetch_dataset, prepare_region, load_manifest, validate_raster

fetch_dataset("lola-5mpp-site01", ["surface", "uncertainty"])
prepare_region("copernicus-glo30", "sp-crater", -111.72, 35.51, -111.54, 35.655)
```

Tests (no network; downloads are replaced by local files):

```bash
cd backend/data_integration
../geoprocessing/.venv/Scripts/python -m pytest
```

## Catalog

| Id | Body | Resolution | Access |
|---|---|---|---|
| `lola-5mpp-site01` Connecting ridge | Moon | 5 m | file, 41 MB per product |
| `lola-5mpp-site04` Shackleton rim | Moon | 5 m | file |
| `lola-5mpp-site06` Nobile rim 1 | Moon | 5 m | file |
| `lola-5mpp-site07` Peak near Shackleton | Moon | 5 m | file |
| `lola-5mpp-site11` de Gerlache rim | Moon | 5 m | file |
| `lola-5mpp-site20` Leibnitz beta plateau | Moon | 5 m | file |
| `lola-5mpp-site23` Malapert massif | Moon | 5 m | file |
| `lola-5mpp-haworth` Haworth | Moon | 5 m | file, 142 MB |
| `lola-5mpp-shoemaker` Shoemaker | Moon | 5 m | file |
| `lola-5mpp-dm2` Nobile rim 2 | Moon | 5 m | file |
| `copernicus-glo30` | Earth | 30 m | tiled; cut regions with `region` |
| `esa-worldcover` | Earth | 10 m | tiled; cut regions with `region` |

The lunar sites are NASA's LOLA 5 m/pix south-pole landing-site models (Barker et al. 2021,
[PGDA product 78](https://pgda.gsfc.nasa.gov/products/78)). Each has five products: `surface`
(height in metres above a 1737.4 km sphere), `uncertainty`, `slope`, `slope_uncertainty` and
`counts` (laser returns per pixel; 0 means the height was interpolated). The NASA server is slow:
expect several minutes per file.

Not catalogued yet: the enhanced shape-from-shading models of Bertone et al. (2026,
PGDA product 104), the PGDA illumination products (product 69), and Mars data.

## Store

Default location `backend/data/` (not versioned). Override with `TERRAWINDOW_DATA_DIR`.

```
backend/data/
  manifest.json
  lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif
  lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif.provenance.json
  earth/regions/sp-crater_copernicus-glo30.tif
  earth/regions/sp-crater_copernicus-glo30.tif.provenance.json
```

Teammates rebuild the same store by running the same `fetch` and `region` commands; the SHA-256
in each provenance file confirms they got identical data.

## Manifest: the contract with Layer 3

```json
{
  "version": 1,
  "datasets": {
    "lola-5mpp-site01": {
      "path": "lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif",
      "name": "LOLA 5 m/pix south-pole site model: Connecting ridge (Site01)",
      "body": "moon",
      "kind": "elevation",
      "vertical_scale": 1.0,
      "nominal_resolution_m": 5.0,
      "citation": "Barker, M. K., et al. (2021). ...",
      "products": { "surface": { "path": "...", "unit": "metres", "sha256": "..." } },
      "ready": true,
      "validation": { "ready": true, "checks": [], "summary": { "pixel_size_m": 5.0, "valid_fraction": 1.0 } },
      "limitations": ["Surface heights fill pixels with no laser return by interpolation; ..."]
    }
  }
}
```

Layer 3 needs `path`, `body` and `vertical_scale`; it shows `name`, `citation` and `limitations`
in its own provenance. Regions cut from tiled datasets are registered as `<name>-<dataset id>`,
for example `sp-crater-copernicus-glo30`.

## Validation checks

| Check | Fails when | Warns when |
|---|---|---|
| `readable` | GDAL cannot open the file | |
| `crs_present` | there is no coordinate system | |
| `body_matches` | the CRS radius is not the expected body's | |
| `horizontal_unit` | | a projected CRS is not in metres |
| `square_pixels` | | pixels are not square |
| `resolution_as_catalogued` | | pixel size is over 10 % from the catalogued value |
| `nodata_declared` | | no nodata value is set |
| `has_data` | the raster is empty | under half of it holds data |
| `values_plausible_in_metres` | | values fall outside the body's plausible height range (often km, not m) |

Coverage and value range are estimated from a reduced-resolution read, so they are approximate.

## Limitations

- Lunar surface heights include interpolated pixels. Fetch the `counts` product to see where.
- Region files copy source pixels unchanged, so they keep the source's geographic grid.
- Downloads are not resumable; an interrupted one leaves no partial file and is simply retried.
- Nothing here checks data against an independent source; validation is of form, not of truth.
