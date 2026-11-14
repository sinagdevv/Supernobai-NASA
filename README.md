# TERRAWINDOW

Mission-specific Earth analog discovery and rehearsal planning, for the NASA Space Apps Challenge. The working scope is
lunar south-polar rover mobility and navigation under low-angle illumination; Mars is a locked roadmap item.

This is a research prototype. It does not certify any site, produces no single Moon–Earth similarity score, and implies no
NASA endorsement.

## Architecture and status

| Layer | Responsibility | State | Where |
|---|---|---|---|
| 1 | Frontend and interactive research workspace | **Implemented** (the V4 interface). Not every screen is scientifically operational: see below | `frontend/` |
| 2 | Scientific data integration: catalog, retrieval, validation, provenance | Implemented | `backend/data_integration` |
| 3 | Geospatial processing engine: slope, roughness, relief, profile, compare, screen, overlays; FastAPI service | Implemented | `backend/geoprocessing`, `docs/layer3-api-contract.md` |
| 4 | Solar geometry and rehearsal-window engine | Not verified complete; not built here | – |
| 5 | Mission suitability and evidence engine | Not verified complete; not built here | – |
| 6 | Data storage and research reporting | Not verified complete; not built here | – |

Layer 1 is a user interface, not a processing layer, so it has no branch of its own: it lives in `frontend/`.

**An implemented interface is not the same as an operational scientific feature.** Every Layer 1 screen exists and works. Only
the parts fed by Layers 2 and 3 show measured data; the rest run on illustrative fixtures until their layer exists.

| Screen | Data today | Waiting on |
|---|---|---|
| Analog Explorer: the 8 example sites and their statuses | Illustrative | Layers 3 and 5 for real candidate assessment |
| Analog Explorer: **Live terrain** (map control) | **Live**: terrain overlays (slope, shade, height) and candidate-patch screening computed by Layer 3 from stored DEMs | – |
| Comparison: demonstration sections | Illustrative | Layers 3 and 5 |
| Comparison: **Measured terrain evidence** | **Live**: Layer 3 compare of a stored lunar and a stored Earth DEM | – |
| Rehearsal Windows | Illustrative (flat-horizon solar model in the browser, no terrain shadows) | Layer 4 |
| Mission, Dossier | Illustrative; the dossier says which content is measured and which is not | Layers 5 and 6 |
| Landing page | Illustrative figures, labelled | – |

Live content is labelled *LIVE · LAYER 3* and carries its dataset, citation, grid size and limitations. If the service is offline,
a dataset is unavailable, or a request fails, the interface says so and shows nothing in its place. It never substitutes
demonstration values. The header chip reads *Illustrative data* when the service is offline and *Demo data · Layer 3 live* when it
is connected. There is no combined similarity score anywhere, and nothing here implies NASA endorsement or certifies a site.

## Run it

Requirements: Node 20+, Python 3.12+.

```bash
# backend: one virtual environment for Layers 2 and 3
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e "geoprocessing[dev]" -e "data_integration[dev]"   # Windows; use .venv/bin/python elsewhere

# fetch the data the live panel uses (rasters are not versioned; the NASA download takes several minutes)
.venv/Scripts/terrawindow-data fetch lola-5mpp-site01
.venv/Scripts/terrawindow-data region copernicus-glo30 sp-crater -111.72 35.51 -111.54 35.655

# start the service
cd geoprocessing
../.venv/Scripts/python -m uvicorn terrawindow_geo.api.app:app --port 8000

# frontend, in another terminal
cd frontend
npm ci
npm run dev
```

Setting up data never dirties your working tree. `backend/data/manifest.json` and the `*.provenance.json` files beside the rasters are
the **version-controlled reference** (what each dataset is, where it came from, its checksum). `terrawindow-data` writes what happens
on your machine (validation result, timestamps) to `backend/data/local/`, which is not committed, and the service reads the two
together. Each setup is compared with the reference and reports `matches` or `differs` (a different checksum is flagged, never
overwritten). To change the reference on purpose, add `--update-reference`. Rasters (`*.tif`) are never committed. Set
`TERRAWINDOW_DATA_DIR` to keep the whole store outside the repository.

Check that the data is really there before using it:

```bash
cd backend/geoprocessing
../.venv/Scripts/python -m terrawindow_geo.cli check     # lists each dataset as available / missing / unreadable / not_validated, with the fix; exit 1 if any are not usable
```

The manifest (`backend/data/manifest.json`) is versioned but the rasters are not, so a fresh checkout lists datasets whose files
are absent. The service therefore decides readiness from the file itself (`GET /v1/datasets` returns `ready` and `availability`),
and requests for an unusable dataset fail early with a structured error (`source_unavailable`, `source_unreadable` or
`dataset_not_validated`) carrying the command that fixes it. The Explorer lists such datasets under "need setup".

The dev and preview servers proxy `/api` to `http://localhost:8000`. Set `VITE_TERRAWINDOW_API` to point somewhere else.
Set `TERRAWINDOW_DATA_DIR` (for both the `terrawindow-data` commands and the service) to keep the store outside the repository.

### Scripts

| | |
|---|---|
| `npm run dev` / `build` / `preview` / `lint` | in `frontend/` (`build` runs `tsc -b` first) |
| `npm test` | in `frontend/`: the API boundary (errors, request shapes, explanations) |
| `python -m pytest` | in `backend/geoprocessing` and in `backend/data_integration` (no network) |

## Frontend structure

`frontend/src/lib/api/` is the only boundary to the backend: `types.ts` (contract types), `client.ts` (requests and a single
`ApiError`), `explain.ts` (plain-language failures), `backend.tsx` (connection state), `live.ts` / `liveContext.tsx` (Explorer
state). Consumers: `components/LiveEvidence.tsx` (Comparison) and `components/map/` (`LivePanel.tsx`, `liveLayers.ts`, which add
and remove sources on the one map instance). Everything else in
`frontend/src` is the V4 interface and its fixture data in `src/data` and `src/lib`.

## Limitations

- Rehearsal-window timing uses a simplified flat-horizon solar model in the UI; terrain shadowing is Layer 4.
- Mission criteria on the demonstration screens are screening assumptions, not mission requirements (Layer 5).
- Layer 3's lunar and Earth datasets differ in resolution and in what they measure (Copernicus GLO-30 is a surface model). The panel shows the limitations the service returns beside the numbers.
- The Explorer's live layers cover Earth datasets only: the map is Web Mercator and cannot show the lunar south pole. Lunar data appears in Comparison.
- Landing-to-workspace uses the View Transitions API where available.
